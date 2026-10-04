from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_session as fixtures
from test_workflow import open_window, packet, plan
from harness.integration.service import DuelService
from harness.integration.mcp import rpc
from harness.runner.orchestrator import Orchestrator
from harness.storage.checkpoint import restore
from harness.runner.duel import DuelRunner


class OrchestratorTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown

    def service(self, mode='open'):
        config = deepcopy(self.config)
        config['mode'] = mode
        if mode != 'blind':
            config['human_deck'] = 'decks/unassigned/branded-despia'
        service = DuelService(self.repo, self.private)
        self.addCleanup(service.close)
        response = service.request({'op': 'start', 'config': config, 'rules_text': 'Agreed test rules.'})
        self.assertTrue(response['ok'], response)
        return service

    def test_lobby_discovery_and_mcp_setup_without_session_paths(self):
        service = DuelService(self.repo, self.private)
        self.addCleanup(service.close)
        names = [tool['name'] for tool in rpc(service, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['result']['tools']]
        self.assertEqual(len(names), 13)
        self.assertIn('duel_start', names)
        self.assertEqual(len(service.decks()), 2)
        self.assertFalse(service.request({'op': 'next'})['ok'])
        config = deepcopy(self.config)
        config['id'] = None
        response = rpc(service, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
            'name': 'duel_start', 'arguments': {'config': config, 'rules_text': 'Test rules'}}})
        self.assertFalse(response['result']['isError'])
        self.assertIn('rules.md', service.runner.assets)
        self.assertEqual(service.games()[0]['game_id'], service.runner.state['game_id'])
        self.assertEqual(service.request({'op': 'next'})['result']['kind'], 'moderator')

    def test_open_human_reply_and_opponent_task_resume(self):
        service = self.service()
        runner = service.runner
        open_window(runner)
        runner.workflow.present(packet(runner))
        question = service.request({'op': 'next'})['result']
        self.assertEqual(question['kind'], 'human')
        self.assertIn('text', question)
        reply = {'op': 'human_reply', 'decision_id': question['decision_id'], 'request_id': 'human-1', 'response': '1'}
        self.assertTrue(service.request(reply)['ok'])
        self.assertEqual(service.request({'op': 'next'})['result']['stage'], 'review_intent')
        runner.workflow.execute('switch', plan(runner, [{'op': 'decision', 'value': {'actor': 'agent', 'window': 'response'}}]), 'human-1')
        runner.workflow.present(packet(runner))
        task = service.request({'op': 'next'})['result']
        self.assertEqual(task['kind'], 'subagent')
        self.assertEqual(task['player'], 'agent')
        service.close()
        service.resume('test-001')
        self.assertEqual(task, service.request({'op': 'next'})['result'])
        result = {'op': 'agent_result', 'task_id': task['task_id'], 'response': 'Pass'}
        first = service.request(result)
        self.assertTrue(first['ok'])
        self.assertEqual(first, service.request(result))
        self.assertEqual(service.request({'op': 'next'})['result']['stage'], 'review_intent')
        result['response'] = 'Changed'
        self.assertFalse(service.request(result)['ok'])

    def test_agent_slots_are_sequential_and_contexts_private(self):
        service = self.service('agent-vs-agent')
        runner = service.runner
        open_window(runner, 'human')
        runner.workflow.present(packet(runner))
        first = service.request({'op': 'next'})['result']
        self.assertEqual(first['player'], 'human')
        self.assertNotIn('hand', first['context']['state']['players']['agent'])
        self.assertTrue(service.request({'op': 'agent_result', 'task_id': first['task_id'], 'response': '1'})['ok'])
        self.assertEqual(service.request({'op': 'next'})['result']['kind'], 'moderator')
        runner.workflow.execute('switch', plan(runner, [{'op': 'decision', 'value': {'actor': 'agent', 'window': 'response'}}]), 'player-task-' + first['task_id'])
        runner.workflow.present(packet(runner))
        second = service.request({'op': 'next'})['result']
        self.assertEqual(second['player'], 'agent')
        self.assertNotEqual(first['task_id'], second['task_id'])
        self.assertNotIn('hand', second['context']['state']['players']['human'])
        self.assertFalse(service.request({'op': 'human_reply', 'decision_id': second['decision_id'], 'request_id': 'x', 'response': '1'})['ok'])
        # A completed retry is safe even after advancing; a forged task is rejected.
        self.assertTrue(service.request({'op': 'agent_result', 'task_id': first['task_id'], 'response': '1'})['ok'])
        self.assertFalse(service.request({'op': 'agent_result', 'task_id': 'forged', 'response': '1'})['ok'])
        destination = self.private.parent / 'restored' / 'state.json'
        checkpoint = runner.state_path.with_name('checkpoint.json')
        game = runner.game_dir
        service.close()
        restore(checkpoint, destination, game)
        with DuelRunner(destination, game) as restored:
            self.assertEqual(second['task_id'], Orchestrator(restored).next()['task_id'])

    def test_blind_no_hidden_human_import_and_invalid_setup(self):
        service = self.service('blind')
        open_window(service.runner, 'agent')
        service.runner.workflow.present(packet(service.runner))
        task = service.request({'op': 'next'})['result']
        self.assertNotIn('hand', task['context']['state']['players']['human'])
        self.assertFalse(service.request({'op': 'resume', 'game_id': '../outside'})['ok'])
        self.assertFalse(service.request({'op': 'start', 'config': self.config, 'rules_text': 'x'})['ok'])

    def test_stale_player_task_rejected_after_revised_question(self):
        service = self.service()
        runner = service.runner
        open_window(runner, 'agent')
        runner.workflow.present(packet(runner))
        old = service.request({'op': 'next'})['result']
        updated = packet(runner)
        updated['question'] = 'Clarified question'
        runner.workflow.present(updated)
        current = service.request({'op': 'next'})['result']
        self.assertNotEqual(old['task_id'], current['task_id'])
        self.assertFalse(service.request({'op': 'agent_result', 'task_id': old['task_id'], 'response': '1'})['ok'])
        self.assertTrue(service.request({'op': 'agent_result', 'task_id': current['task_id'], 'response': '1'})['ok'])

    def test_pause_returns_fixed_state_and_reviewed_events(self):
        service = self.service()
        service.runner.workflow.execute('pause', plan(service.runner, [{'op': 'status', 'value': 'paused'}]))
        result = service.request({'op': 'next'})['result']
        self.assertEqual(result['kind'], 'paused')
        self.assertIn('**Game:**', result['text'])
        self.assertIn('Reviewed temporary scenario action.', result['text'])
        self.assertNotIn("'summary':", result['text'])

    def test_real_stdio_lobby_start_and_resume(self):
        command = [sys.executable, '-m', 'harness.integration.mcp', '--repo', str(self.repo),
                   '--private-root', str(self.private)]
        def call(name, arguments=None, identity=1):
            return {'jsonrpc': '2.0', 'id': identity, 'method': 'tools/call',
                    'params': {'name': name, 'arguments': arguments or {}}}
        messages = [call('duel_decks'), call('duel_start', {'config': self.config, 'rules_text': 'Test rules'}, 2),
                    call('duel_next', identity=3)]
        completed = subprocess.run(command, input=''.join(json.dumps(message) + '\n' for message in messages),
                                   text=True, capture_output=True, cwd=Path(__file__).resolve().parents[1], timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(responses), 3)
        self.assertTrue(all(not item['result']['isError'] for item in responses))
        completed = subprocess.run(command, input=json.dumps(call('duel_resume', {'game_id': 'test-001'})) + '\n',
                                   text=True, capture_output=True, cwd=Path(__file__).resolve().parents[1], timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(json.loads(completed.stdout)['result']['isError'])
