"""Installed-runtime smoke test from a clean resource copy, outside the source cwd.

Host dispatch is simulated; this does not certify Codex/Claude/Gemini facilities.
Run with the installed wheel's Python: python tests/smoke_install.py --repo <source>.
"""
import argparse
import json
import tomllib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HOST = {key: True for key in ('execution', 'native_subagents', 'fresh_history', 'context_only_instructions', 'stop_children')}
HOST['evidence'] = 'Automated smoke fixture: simulated host capabilities and player callbacks, not vendor integration evidence.'


class Transport:
    def __init__(self, repo, private, cwd):
        self.process = subprocess.Popen([sys.executable, '-I', '-m', 'harness.integration.mcp',
            '--repo', str(repo), '--private-root', str(private)], cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.identity = 0

    def call(self, name, arguments=None):
        self.identity += 1
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.identity,
            'method': 'tools/call', 'params': {'name': name, 'arguments': arguments or {}}}) + '\n')
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        payload = json.loads(response['result']['content'][0]['text'])
        assert payload['ok'], (name, payload.get('error'))
        return payload['result']

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
            assert self.process.returncode == 0, self.process.stderr.read()
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.process.stdout.close()
            self.process.stderr.close()


def simulated_choice(transport, task, response):
    reservation = transport.call('duel_player_start', {'task_id': task['task_id'],
        'request_id': 'smoke-' + task['task_id'], 'isolation': {'method': 'cooperative',
        'parent_history': False, 'tools': [], 'filesystem': False,
        'evidence': 'Test double: supplied context only; no real vendor child.'}})
    assert reservation['dispatch_authorized']
    transport.call('duel_player_bind', {'task_id': task['task_id'],
        'attempt_id': reservation['attempt_id'], 'child_id': 'simulated-' + task['task_id']})
    reply = transport.call('duel_agent_result', {'task_id': task['task_id'],
        'attempt_id': reservation['attempt_id'], 'response': response})
    return reply['request_id']


def run(repo):
    with tempfile.TemporaryDirectory() as temporary:
        # Windows TEMP may use an 8.3 alias; generated configs use resolved paths.
        root = Path(temporary).resolve()
        clone = root / 'checkout with spaces'
        clone.mkdir()
        for name in ('decks', 'agents', 'skills', 'rules', 'templates'):
            shutil.copytree(repo / name, clone / name, ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('AGENTS.md', 'CLAUDE.md', 'GEMINI.md'):
            shutil.copyfile(repo / name, clone / name)
        private = root / 'private'
        for host in ('codex', 'claude', 'gemini'):
            result = subprocess.run([sys.executable, '-I', '-m', 'harness.cli', 'host-config',
                '--host', host, '--repo', str(clone)], cwd=root, capture_output=True, text=True, encoding="utf-8", check=True)
            config = tomllib.loads(result.stdout)['mcp_servers']['yugioh'] if host == 'codex' else json.loads(result.stdout)['mcpServers']['yugioh']
            assert config['command'] == str(Path(sys.executable).absolute())
            assert config['args'][-1] == str(clone.resolve())
        result = subprocess.run([sys.executable, '-I', '-m', 'harness.cli', 'doctor',
            '--repo', str(clone), '--require-host'], cwd=root, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 1 and json.loads(result.stdout)['host_ready'] is None
        for mode in ('managed', 'self', 'agent-vs-agent'):
            c = json.loads((clone / 'templates/duel-config.json').read_text(encoding="utf-8"))
            c.update(id='smoke-' + mode, mode=mode, format='edison', banlist='2010-03-01',
                rules_profile='rules/edison.md', rules_version='smoke',
                agent_deck='decks/edison/blackwing',
                human_deck=None if mode == 'self' else 'decks/edison/lightsworn',
                human_deck_counts={'main': 40, 'extra': 15, 'side': 15}, starting_player='agent')
            c['settings'] = {'starting_lp': 8000, 'opening_hand_size': 5,
                'starting_player_draws': True, 'starting_player_battle_phase': False,
                'field_layout': {'main_monster_zones': 5, 'spell_trap_zones': 5, 'extra_monster_zones': 0}}
            t = Transport(clone, private, root)
            try:
                assert t.call('duel_preflight', {'host_capabilities': HOST})['ready']
                t.call('duel_start', {'config': c, 'rules_text': (clone / 'rules/edison.md').read_text(encoding="utf-8")})
                def step(identity, kind, actor, operations, submission=None):
                    revision = t.call('duel_status')['revision']
                    args = {'request_id': identity, 'request': {'kind': kind, 'actor': actor,
                        'expected_revision': revision, 'moderator_approved': True,
                        'public_summary_reviewed': True, 'public_summary': 'Reviewed smoke fixture action.',
                        'operations': operations}}
                    if submission:
                        args['submission_id'] = submission
                    return t.call('duel_step', args)
                def present():
                    revision = t.call('duel_status')['revision']
                    return t.call('duel_present', {'packet': {'expected_revision': revision,
                        'role': 'Moderator', 'events': [], 'recommendations': [],
                        'question': 'Choose a legal intention.', 'awaiting_user': True,
                        'option_review': {'complete': False, 'meaningful_choices': None}}})
                step('open-agent', 'choice', 'moderator', [{'op': 'decision', 'value': {'actor': 'agent', 'window': 'smoke'}}])
                present()
                task = t.call('duel_next')
                assert task['kind'] == 'subagent'
                if mode in ('managed', 'agent-vs-agent'):
                    assert 'hand' not in task['context']['state']['players']['human']
                else:
                    assert task['context']['state']['players']['human']['hand_count'] == 5
                submission = simulated_choice(t, task, 'Pass')
                step('agent-pass', 'pass', 'agent', [{'op': 'decision', 'value': {'actor': 'human', 'window': 'smoke-pause'}}], submission)
                decision = present()
                next_task = t.call('duel_next')
                if mode == 'agent-vs-agent':
                    assert next_task['kind'] == 'subagent'
                    assert 'hand' not in next_task['context']['state']['players']['agent']
                    submission = simulated_choice(t, next_task, 'Pause the game')
                else:
                    assert next_task['kind'] == 'human'
                    submission = 'smoke-human-pause'
                    t.call('duel_human_reply', {'decision_id': decision['decision_id'],
                        'request_id': submission, 'response': 'Pause the game'})
                step('pause', 'choice', 'human', [{'op': 'status', 'value': 'paused'}], submission)
                before = json.loads((private / c['id'] / 'checkpoint.json').read_text(encoding="utf-8"))
                assert before['state']['status'] == 'paused'
            finally:
                t.close()
            t = Transport(clone, private, root)
            try:
                t.call('duel_resume', {'game_id': c['id']})
                assert t.call('duel_next')['kind'] == 'paused'
                after = json.loads((private / c['id'] / 'checkpoint.json').read_text(encoding="utf-8"))
                assert after['state'] == before['state']  # Includes exact hidden deck queues.
                assert after['decision_packet'] == before['decision_packet']
                # Finish a cancelled fixture without claiming a competitive winner.
                revision = t.call('duel_status')['revision']
                t.call('duel_step', {'request_id': 'cancel', 'request': {'kind': 'finish',
                    'actor': 'moderator', 'expected_revision': revision, 'moderator_approved': True,
                    'public_summary_reviewed': True, 'public_summary': 'Smoke fixture cancelled without result.',
                    'automatic': True, 'option_review': {'complete': True, 'meaningful_choices': 0,
                        'basis': 'human-confirmed-none', 'reason': 'Test controller cancels the paused fixture.'},
                    'operations': [{'op': 'status', 'value': 'finished'}]}})
                assert t.call('duel_next')['kind'] == 'finished'
            finally:
                t.close()
            archive = json.loads((clone / 'games/edison' / c['id'] / 'events.json').read_text(encoding="utf-8"))
            assert archive['schema_version'] == '4.0' and 'events' not in archive
            assert len(archive['event_index']) == 4
            print(mode + ': setup, simulated player dispatch, pause/resume and cancellation passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    run(parser.parse_args().repo.resolve())
