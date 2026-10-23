"""Real JSON-lines/one-shot processes and filtered GUI projection, no model scores."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from harness.environment import DuelEnvironment, PROTOCOL
from harness.environment.positions import create_position
from harness.integration.headless import respond
from harness.runner.duel import DuelRunner
import test_session as fixtures
from test_workflow import open_window, packet, plan
from smoke_install import HOST


class HeadlessTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown

    def prepare(self):
        for name in ('AGENTS.md', 'agents/orchestrator/AGENT.md', 'skills/duel-orchestrator/SKILL.md'):
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixtures.REPO / name, target)
        for deck in ('blackwing', 'lightsworn'):
            shutil.copytree(fixtures.REPO / 'decks/edison' / deck, self.repo / 'decks/edison' / deck)
        self.edison = json.loads((fixtures.REPO / 'templates/edison-managed.json').read_text())
        self.edison['id'] = 'edison-headless'
        self.rules = '\n\n'.join((fixtures.REPO / path).read_text(encoding='utf-8')
                                 for path in ('rules/common.md', 'rules/edison.md', 'rules/banlists/tcg-2010-03-01.json'))

    def envelope(self, operation, **arguments):
        return {'protocol': PROTOCOL, 'id': 'request', 'request': {'op': operation, **arguments}}

    def call(self, env, operation, **arguments):
        result = env.request(self.envelope(operation, **arguments))
        self.assertTrue(result['ok'], result)
        return result['result']

    def start(self, env):
        self.call(env, 'preflight', host_capabilities=HOST)
        return self.call(env, 'start', config=self.edison, rules_text=self.rules)

    def test_protocol_gate_and_no_hidden_data_in_error(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            description = self.call(env, 'describe')
            self.assertEqual(description['action_mode'], 'open-intention')
            self.assertIn('agent_result', description['operations'])
            self.assertFalse(env.request(self.envelope('start', config=self.edison, rules_text=self.rules))['ok'])
            for value in (None, [], {'protocol': 'wrong', 'id': 'x', 'request': {'op': 'games'}},
                          self.envelope('view', player='other'), self.envelope('start', config=[], rules_text='SECRET'),
                          self.envelope('player_start', task_id='x', request_id='x', isolation={}, timeout_seconds=True),
                          self.envelope('games', unrecognized='SECRET')):
                result = env.request(value)
                self.assertFalse(result['ok'])
                self.assertNotIn('SECRET', json.dumps(result))
            self.assertFalse(respond(env, '{"private":"SECRET"')['ok'])
            self.start(env)  # Bad requests did not poison the stream.

    def test_open_intention_retry_response_window_and_gui_filter(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            runner = env.service.runner
            self.assertEqual(len(runner.state['players']['human']['hand']), 5)
            self.assertEqual(runner.configuration['settings']['field_layout']['extra_monster_zones'], 0)
            # A transport fixture opens a choice; this is not a full-game legality claim.
            open_window(runner)
            prompt = packet(runner)
            prompt['recommendations'][0]['operations'] = 'PRIVATE_EXECUTION_DETAILS'
            runner.workflow.present(prompt)
            before = self.call(env, 'interaction')
            self.assertTrue(before['awaiting_input'])
            self.assertEqual(before['decision']['action_mode'], 'open-intention')
            self.assertNotIn('hand', before['context']['state']['players']['agent'])
            self.assertNotIn('remaining_deck_order', json.dumps(before))
            self.assertNotIn('PRIVATE_EXECUTION_DETAILS', json.dumps(before))
            decision_id = before['decision']['decision_id']
            intention = 'I set a monster face down; please check the selected card.'
            args = dict(decision_id=decision_id, request_id='human-free-text', response=intention)
            first = self.call(env, 'human_reply', **args)
            self.assertEqual(first, self.call(env, 'human_reply', **args))
            self.assertEqual(first['intention']['text'], intention)
            self.assertFalse(self.call(env, 'interaction')['awaiting_input'])
            self.assertEqual(self.call(env, 'next')['stage'], 'review_intent')
            request = plan(runner, [{'op': 'decision', 'value': {'actor': 'agent', 'window': 'response'}}])
            self.call(env, 'step', request_id='review', request=request, submission_id='human-free-text')
            duplicate = self.call(env, 'step', request_id='review', request=request, submission_id='human-free-text')
            self.assertTrue(duplicate['duplicate'])
            menu = packet(runner)
            menu['question'] = 'PRIVATE_OPPONENT_MENU'
            runner.workflow.present(menu)
            task = self.call(env, 'next')
            self.assertEqual(task['kind'], 'subagent')
            self.assertNotIn('hand', task['context']['state']['players']['human'])
            display = self.call(env, 'interaction')
            self.assertIsNone(display['decision'])
            self.assertFalse(display['awaiting_input'])
            self.assertNotIn('PRIVATE_OPPONENT_MENU', json.dumps(display))
            self.assertNotIn('task_id', display)

    def test_spectator_projection_and_recovery_failure(self):
        self.prepare()
        self.edison['mode'] = 'agent-vs-agent'
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            runner = env.service.runner
            open_window(runner, 'human')
            prompt = packet(runner)
            prompt['question'] = 'PRIVATE_PLAYER_ONE_CHOICE'
            runner.workflow.present(prompt)
            display = self.call(env, 'interaction')
            self.assertEqual(display['perspective'], 'public')
            self.assertIsNone(display['decision'])
            self.assertFalse(display['awaiting_input'])
            self.assertNotIn('PRIVATE_PLAYER_ONE_CHOICE', json.dumps(display))
            for player in display['context']['state']['players'].values():
                self.assertNotIn('hand', player)
            runner._recovery_required = True
            result = env.request(self.envelope('interaction'))
            self.assertFalse(result['ok'])
            self.assertEqual(result['error']['code'], 'recovery_required')

    def test_real_cli_stream_and_single_request_resume(self):
        self.prepare()
        command = [sys.executable, '-m', 'harness.cli', 'duel', '--repo', str(self.repo),
                   '--private-root', str(self.private)]
        messages = [self.envelope('preflight', host_capabilities=HOST),
                    self.envelope('start', config=self.edison, rules_text=self.rules), self.envelope('interaction')]
        completed = subprocess.run(command, input='not json\n' + '\n'.join(map(json.dumps, messages)) + '\n',
                                   text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(rows), 4)
        self.assertFalse(rows[0]['ok'])
        self.assertTrue(all(row['ok'] for row in rows[1:]), rows)
        initial = rows[-1]['result']['context']['state']
        request = self.private / 'request.json'
        request.write_text(json.dumps(self.envelope('interaction')), encoding='utf-8')
        completed = subprocess.run([*command, '--game-id', 'edison-headless', '--request-file', str(request)],
                                   text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['result']['context']['state'], initial)
        request.write_text(json.dumps(self.envelope('unknown')), encoding='utf-8')
        rejected = subprocess.run([*command, '--request-file', str(request)], capture_output=True, timeout=15)
        self.assertEqual(rejected.returncode, 1)

    def test_fixed_position_used_by_benchmark_is_resumable_through_same_api(self):
        self.prepare()
        with DuelEnvironment(self.repo, self.private) as env:
            self.start(env)
            state = deepcopy(env.service.runner.state)
            config = deepcopy(env.service.runner.configuration)
        output = self.private.parent / 'scenario'
        path, game = create_position(output, position_id='scenario-one', configuration=config,
                                     state=state, rules_text=self.rules)
        with DuelEnvironment(output / 'archive', output / 'private') as env:
            self.assertEqual(self.call(env, 'games')[0]['game_id'], 'scenario-one')
            self.call(env, 'resume', game_id='scenario-one')
            projection = self.call(env, 'interaction')
            self.assertEqual(len(projection['context']['state']['players']['human']['hand']), 5)
            self.assertEqual(env.service.runner.state, state)
        with self.assertRaises(ValueError):
            create_position(output, position_id='scenario-one', configuration=config, state=state, rules_text=self.rules)
        with self.assertRaises(ValueError):
            create_position(output, position_id='../escape', configuration=config, state=state, rules_text=self.rules)
        with DuelRunner(path, game) as runner:
            self.assertEqual(runner.state, state)
