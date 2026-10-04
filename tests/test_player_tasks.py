from copy import deepcopy
import json
import unittest
import test_session as fixtures
from test_workflow import open_window, packet, plan
from test_orchestrator import ISOLATION
from harness.integration.service import DuelService
from harness.integration.mcp import rpc
from harness.runner.orchestrator import Orchestrator
from harness.runner.player_tasks import PlayerTaskError
from harness.players.isolated import ContextOnlyPlayer, model_request
from harness.runner.duel import DuelRunner
from harness.storage.checkpoint import restore


class PlayerTaskTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown

    def setup_task(self, mode='agent-vs-agent'):
        config = deepcopy(self.config)
        config['mode'] = mode
        if mode != 'blind':
            config['human_deck'] = 'decks/unassigned/branded-despia'
        service = DuelService(self.repo, self.private)
        self.addCleanup(service.close)
        self.assertTrue(service.request({'op': 'start', 'config': config, 'rules_text': 'Test rules'})['ok'])
        runner = service.runner
        open_window(runner, 'agent')
        prompt = packet(runner)
        prompt['recommendations'][0]['label'] = 'PRIVATE_PLAYER_MENU'
        runner.workflow.present(prompt)
        self.now = 1000
        orchestrator = Orchestrator(runner, lambda: self.now)
        task = orchestrator.next()
        return service, runner, orchestrator, task

    def test_fail_closed_isolation_and_duplicate_dispatch(self):
        _, runner, orchestrator, task = self.setup_task()
        before = deepcopy(runner.state)
        for key, value in [('tools', ['exec']), ('parent_history', True), ('filesystem', True), ('evidence', '')]:
            policy = {**ISOLATION, key: value}
            with self.assertRaises(PlayerTaskError):
                orchestrator.players.begin(task['task_id'], key, policy)
        with self.assertRaises(PlayerTaskError):
            orchestrator.players.begin(task['task_id'], 'missing', {})
        receipt = orchestrator.players.begin(task['task_id'], 'dispatch', ISOLATION)
        duplicate = orchestrator.players.begin(task['task_id'], 'dispatch', ISOLATION)
        self.assertEqual(receipt['attempt_id'], duplicate['attempt_id'])
        self.assertTrue(receipt['dispatch_authorized'])
        self.assertFalse(duplicate['dispatch_authorized'])
        with self.assertRaises(PlayerTaskError):
            orchestrator.players.begin(task['task_id'], 'dispatch', ISOLATION, 20)
        with self.assertRaises(PlayerTaskError):
            orchestrator.players.begin(task['task_id'], 'duplicate-child', ISOLATION)
        self.assertEqual(orchestrator.next()['kind'], 'subagent_wait')
        self.assertEqual(runner.state, before)

    def test_timeout_late_results_termination_and_retry(self):
        _, runner, orchestrator, task = self.setup_task()
        before = deepcopy(runner.state)
        first = orchestrator.players.begin(task['task_id'], 'first', ISOLATION, 10)
        self.now = 1010
        failure = orchestrator.next()
        self.assertEqual(failure['status'], 'timed_out')
        self.assertFalse(failure['termination_confirmed'])
        self.assertNotIn('PRIVATE_PLAYER_MENU', failure['text'])
        with self.assertRaises(PlayerTaskError):
            orchestrator.agent_result(task['task_id'], first['attempt_id'], '1')
        with self.assertRaises(PlayerTaskError):
            orchestrator.players.begin(task['task_id'], 'second', ISOLATION)
        orchestrator.players.fail(task['task_id'], first['attempt_id'], 'timeout', True)
        second = orchestrator.players.begin(task['task_id'], 'second', ISOLATION)
        self.assertNotEqual(first['attempt_id'], second['attempt_id'])
        with self.assertRaises(PlayerTaskError):
            orchestrator.agent_result(task['task_id'], first['attempt_id'], '1')
        accepted = orchestrator.agent_result(task['task_id'], second['attempt_id'], '1')
        self.assertEqual(accepted, orchestrator.agent_result(task['task_id'], second['attempt_id'], '1'))
        self.assertEqual(orchestrator.next()['stage'], 'review_intent')
        self.assertEqual(runner.state, before)
        self.assertEqual(len(runner.workflow.data['submissions']), 1)

    def test_cancel_and_exhaustion_never_auto_select_or_advance(self):
        _, runner, orchestrator, task = self.setup_task()
        before = deepcopy(runner.state)
        for number in range(3):
            receipt = orchestrator.players.begin(task['task_id'], str(number), ISOLATION)
            orchestrator.players.fail(task['task_id'], receipt['attempt_id'], 'cancelled')
            with self.assertRaises(PlayerTaskError):
                orchestrator.agent_result(task['task_id'], receipt['attempt_id'], 'Pass')
            orchestrator.players.fail(task['task_id'], receipt['attempt_id'], 'cancelled', True)
        with self.assertRaisesRegex(PlayerTaskError, 'retry_exhausted'):
            orchestrator.players.begin(task['task_id'], 'fourth', ISOLATION)
        self.assertEqual(orchestrator.next()['kind'], 'subagent_failure')
        self.assertEqual(runner.state, before)
        self.assertEqual(runner.workflow.data['submissions'], {})

    def test_malformed_results_are_saved_and_do_not_leak_error_content(self):
        for index, response in enumerate((True, None, {'tool_calls': 'SECRET'}, '', '9', 'x' * 8193)):
            with self.subTest(response_type=type(response).__name__):
                self.config['id'] = 'invalid-' + str(index)
                service, runner, _, task = self.setup_task('open')
                orchestrator = Orchestrator(runner)
                receipt = orchestrator.players.begin(task['task_id'], 'dispatch', ISOLATION)
                result = service.request({'op': 'agent_result', 'task_id': task['task_id'],
                    'attempt_id': receipt['attempt_id'], 'response': response})
                self.assertFalse(result['ok'])
                self.assertEqual(result['error']['code'], 'malformed_player_response')
                self.assertNotIn('SECRET', json.dumps(result))
                self.assertEqual(runner.workflow.data['submissions'], {})
                orchestrator.players.fail(task['task_id'], receipt['attempt_id'], 'malformed', True)
                service.close()

    def test_running_attempt_survives_restore_and_cannot_spawn_second_child(self):
        service, runner, orchestrator, task = self.setup_task()
        receipt = orchestrator.players.begin(task['task_id'], 'original', ISOLATION)
        game = runner.game_dir
        checkpoint = runner.state_path.with_name('checkpoint.json')
        destination = self.private.parent / 'restored' / 'state.json'
        service.close()
        restore(checkpoint, destination, game)
        with DuelRunner(destination, game) as restored:
            again = Orchestrator(restored, lambda: 1001)
            self.assertEqual(again.next()['attempt_id'], receipt['attempt_id'])
            with self.assertRaises(PlayerTaskError):
                again.players.begin(task['task_id'], 'duplicate-after-crash', ISOLATION)
            again.players.fail(task['task_id'], receipt['attempt_id'], 'host_shutdown', True)
            retry = again.players.begin(task['task_id'], 'retry', ISOLATION)
            self.assertNotEqual(receipt['attempt_id'], retry['attempt_id'])

    def test_durable_submission_repairs_interrupted_attempt_finalization(self):
        _, runner, orchestrator, task = self.setup_task()
        receipt = orchestrator.players.begin(task['task_id'], 'dispatch', ISOLATION)
        runner.workflow.submit(task['decision_id'], 'player-task-' + task['task_id'], '1', task['player'])
        self.assertEqual(orchestrator.next()['stage'], 'review_intent')
        self.assertEqual(orchestrator.players.summary(orchestrator.players.task(task['task_id']))['status'], 'succeeded')
        self.assertEqual(orchestrator.agent_result(task['task_id'], receipt['attempt_id'], '1')['status'], 'submitted')

    def test_model_request_has_no_parent_history_tools_or_opponent_cards(self):
        _, runner, _, task = self.setup_task()
        request = model_request(task['context'])
        self.assertEqual(request['tools'], [])
        self.assertEqual(request['tool_choice'], 'none')
        self.assertEqual([message['role'] for message in request['messages']], ['system', 'user'])
        human_ids = [card['instance_id'] for card in runner.state['players']['human']['hand']]
        for identity in human_ids:
            self.assertNotIn(identity, json.dumps(request))
        with self.assertRaises(ValueError):
            model_request(runner.context('moderator'))
        with self.assertRaises(ValueError):
            model_request({**task['context'], 'parent_messages': ['SECRET']})
        called = []
        adapter = ContextOnlyPlayer(lambda payload: called.append(payload) or {'response': '1'})
        self.assertEqual(adapter.choose(task['context']), {'response': '1'})
        self.assertEqual(called, [request])
        for result in ({'tool_calls': [{'name': 'exec'}]}, {'response': '1', 'tool_calls': []}, {'response': True}):
            with self.assertRaises(ValueError):
                ContextOnlyPlayer(lambda payload: result).choose(task['context'])

    def test_service_rejects_mutations_and_missing_attempt_during_running_child(self):
        service, runner, _, task = self.setup_task()
        receipt = service.request({'op': 'player_start', 'task_id': task['task_id'],
                                   'request_id': 'dispatch', 'isolation': ISOLATION})['result']
        result = service.request({'op': 'step', 'request_id': 'unsafe', 'request': plan(runner, [])})
        self.assertEqual(result['error']['code'], 'child_still_active')
        self.assertFalse(service.request({'op': 'agent_result', 'task_id': task['task_id'], 'response': '1'})['ok'])
        call = rpc(service, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'duel_agent_result', 'arguments': {'task_id': task['task_id'], 'response': '1'}}})
        self.assertEqual(call['error']['code'], -32602)
        self.assertTrue(service.request({'op': 'agent_result', 'task_id': task['task_id'],
                                        'attempt_id': receipt['attempt_id'], 'response': '1'})['ok'])

    def test_child_handle_binding_and_no_low_level_submit_bypass(self):
        service, runner, _, task = self.setup_task()
        receipt = service.request({'op': 'player_start', 'task_id': task['task_id'],
                                   'request_id': 'dispatch', 'isolation': ISOLATION})['result']
        bind = {'op': 'player_bind', 'task_id': task['task_id'],
                'attempt_id': receipt['attempt_id'], 'child_id': 'native-child-42'}
        first = service.request(bind)
        self.assertTrue(first['ok'])
        self.assertEqual(first, service.request(bind))
        self.assertFalse(service.request({**bind, 'child_id': 'other-child'})['ok'])
        self.assertEqual(service.request({'op': 'status'})['result']['player_tasks'][0]['child_id'], 'native-child-42')
        self.assertEqual(service.request({'op': 'submit', 'decision_id': task['decision_id'],
            'request_id': 'bypass', 'player': 'agent', 'response': '1'})['error']['code'], 'player_attempt_required')
        self.assertTrue(service.request({'op': 'player_fail', 'task_id': task['task_id'],
            'attempt_id': receipt['attempt_id'], 'reason': 'cancelled', 'terminated': True})['ok'])

    def test_adapter_rejects_injected_opponent_hidden_zones_and_guides(self):
        _, runner, _, task = self.setup_task()
        injected = deepcopy(task['context'])
        injected['state']['players']['human']['hand'] = runner.context('human')['state']['players']['human']['hand']
        with self.assertRaises(ValueError):
            model_request(injected)
        injected = deepcopy(task['context'])
        injected['guides']['decks/human/secret/guide.md'] = {'excerpt': 'PRIVATE'}
        with self.assertRaises(ValueError):
            model_request(injected)
        injected = deepcopy(task['context'])
        injected['state']['players']['agent']['remaining_deck_order'] = []
        with self.assertRaises(ValueError):
            model_request(injected)

    def test_new_menu_cannot_reset_failed_attempt_budget(self):
        _, runner, orchestrator, task = self.setup_task()
        for index in range(3):
            receipt = orchestrator.players.begin(task['task_id'], str(index), ISOLATION)
            orchestrator.players.fail(task['task_id'], receipt['attempt_id'], 'cancelled', True)
            runner.workflow.present(packet(runner))
            task = orchestrator.next()
        with self.assertRaisesRegex(PlayerTaskError, 'retry_exhausted'):
            orchestrator.players.begin(task['task_id'], 'fourth', ISOLATION)
