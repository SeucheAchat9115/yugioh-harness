"""Isolation policy selection, dispatch honesty, and durable resumption."""
from copy import deepcopy
import json
import unittest
import test_session as fixtures
from test_workflow import open_window, packet
from test_orchestrator import ISOLATION
from harness.engine.actions import apply
from harness.integration.service import DuelService
from harness.runner.duel import DuelRunner
from harness.runner.orchestrator import Orchestrator
from harness.runner.player_tasks import PlayerTaskError, validate_isolation
from harness.storage.checkpoint import verify_checkpoint

COOPERATIVE = {'method': 'cooperative', 'parent_history': False,
               'tools': ['functions', 'collaboration'], 'filesystem': True,
               'evidence': 'Fresh native child; shared tools/files exist; player instructed not to use them.'}


class IsolationPolicyTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown

    def service(self, policy=None, mode='managed'):
        config = deepcopy(self.config)
        config['mode'] = mode
        if mode not in ('self', 'blind'):
            config['human_deck'] = 'decks/unassigned/branded-despia'
        if policy is not None:
            config['player_isolation'] = policy
        service = DuelService(self.repo, self.private)
        self.addCleanup(service.close)
        response = service.request({'op': 'start', 'config': config, 'rules_text': 'Test rules'})
        self.assertTrue(response['ok'], response)
        return service

    def task(self, service):
        open_window(service.runner, 'agent')
        service.runner.workflow.present(packet(service.runner))
        return Orchestrator(service.runner).next()

    def test_cooperative_native_dispatch_records_actual_capabilities_and_preserves_lifecycle(self):
        service = self.service()
        task = self.task(service)
        self.assertEqual(task['isolation_policy'], 'cooperative')
        self.assertNotIn('hand', task['context']['state']['players']['human'])
        self.assertIn('Do not use network', task['instructions'])
        players = Orchestrator(service.runner).players
        receipt = players.begin(task['task_id'], 'dispatch', COOPERATIVE)
        self.assertEqual(receipt['isolation_boundary'], 'cooperative')
        attempt = players.task(task['task_id'])['attempts'][receipt['attempt_id']]
        self.assertEqual(attempt['isolation'], COOPERATIVE)
        self.assertFalse(players.begin(task['task_id'], 'dispatch', COOPERATIVE)['dispatch_authorized'])
        players.bind(task['task_id'], receipt['attempt_id'], 'native-handle')
        with self.assertRaisesRegex(PlayerTaskError, 'child_still_active'):
            players.begin(task['task_id'], 'second', COOPERATIVE)
        players.result(task['task_id'], receipt['attempt_id'], '1')
        self.assertEqual(Orchestrator(service.runner).next()['stage'], 'review_intent')
        status = service.request({'op': 'status'})['result']
        self.assertEqual(status['isolation_policy'], 'cooperative')
        self.assertEqual(status['player_tasks'][0]['isolation_boundary'], 'cooperative')

    def test_enforced_rejects_cooperative_and_accepts_enforced_boundary(self):
        service = self.service('enforced')
        task = self.task(service)
        players = Orchestrator(service.runner).players
        with self.assertRaises(PlayerTaskError):
            players.begin(task['task_id'], 'native', COOPERATIVE)
        receipt = players.begin(task['task_id'], 'api', ISOLATION)
        self.assertEqual(receipt['isolation_policy'], 'enforced')
        self.assertEqual(receipt['isolation_boundary'], 'enforced')

    def test_cooperative_can_use_stronger_boundary_but_cannot_mislabel_shared_tools(self):
        validate_isolation(ISOLATION, 'cooperative')
        for declaration in ({**ISOLATION, 'tools': ['exec']},
                            {**ISOLATION, 'filesystem': True},
                            {**COOPERATIVE, 'parent_history': True},
                            {**COOPERATIVE, 'tools': 'exec'},
                            {**COOPERATIVE, 'filesystem': 'false'},
                            {**COOPERATIVE, 'evidence': ''},
                            {**COOPERATIVE, 'method': 'unknown'}):
            with self.subTest(declaration=declaration):
                with self.assertRaises(PlayerTaskError):
                    validate_isolation(declaration, 'cooperative')

    def test_resume_keeps_policy_capabilities_and_live_child(self):
        service = self.service()
        task = self.task(service)
        players = Orchestrator(service.runner).players
        receipt = players.begin(task['task_id'], 'dispatch', COOPERATIVE, 120)
        players.bind(task['task_id'], receipt['attempt_id'], 'native-42')
        identity = service.runner.state['game_id']
        checkpoint = json.loads(service.runner.state_path.with_name('checkpoint.json').read_text(encoding="utf-8"))
        self.assertEqual(verify_checkpoint(checkpoint)['player_isolation'], 'cooperative')
        self.assertEqual(checkpoint['configuration']['player_isolation'], 'cooperative')
        service.close()
        service.resume(identity)
        pending = Orchestrator(service.runner).next()
        self.assertEqual(pending['kind'], 'subagent_wait')
        self.assertEqual(pending['child_id'], 'native-42')
        self.assertEqual(pending['isolation_policy'], 'cooperative')
        self.assertEqual(pending['isolation_boundary'], 'cooperative')
        self.assertEqual(Orchestrator(service.runner).players.task(task['task_id'])['attempts'][receipt['attempt_id']]['isolation'], COOPERATIVE)

    def test_policy_is_immutable_and_config_mismatch_cannot_downgrade_on_resume(self):
        service = self.service('enforced')
        runner = service.runner
        action = {'id': 'downgrade', 'kind': 'correction', 'actor': 'moderator',
                  'expected_revision': 0, 'moderator_approved': True, 'public_summary_reviewed': True,
                  'public_summary': 'Change policy', 'changes': [
                      {'path': ['player_isolation'], 'before': 'enforced', 'after': 'cooperative'}]}
        with self.assertRaisesRegex(ValueError, 'protected'):
            apply(runner.state, action)
        checkpoint = json.loads(runner.state_path.with_name('checkpoint.json').read_text(encoding="utf-8"))
        checkpoint['configuration']['player_isolation'] = 'cooperative'
        with self.assertRaisesRegex(ValueError, 'configuration differs'):
            verify_checkpoint(checkpoint)
        path, game = runner.state_path, runner.game_dir
        service.close()
        config = json.loads((game / 'game.json').read_text(encoding="utf-8"))
        config['player_isolation'] = 'cooperative'
        (game / 'game.json').write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, 'does not match'):
            DuelRunner(path, game)

    def test_legacy_missing_policy_remains_enforced(self):
        service = self.service(mode='open')
        self.assertEqual(service.runner.state['player_isolation'], 'enforced')
        path, game = service.runner.state_path, service.runner.game_dir
        service.close()
        # Simulate an original pre-policy save without altering its journal history.
        state = json.loads(path.read_text(encoding="utf-8")); state.pop('player_isolation')
        journal = json.loads(path.with_name('journal.json').read_text(encoding="utf-8"))
        journal['initial_state'].pop('player_isolation')
        config = json.loads((game / 'game.json').read_text(encoding="utf-8")); config.pop('player_isolation')
        checkpoint = json.loads(path.with_name('checkpoint.json').read_text(encoding="utf-8"))
        checkpoint.update(state=state, journal=journal, configuration=config)
        for target, data in ((path,state),(path.with_name('journal.json'),journal),
                             (path.with_name('checkpoint.json'),checkpoint),(game/'game.json',config)):
            target.write_text(json.dumps(data), encoding="utf-8")
        service.resume(state['game_id'])
        self.assertNotIn('player_isolation', service.runner.state)
        self.assertEqual(service.request({'op': 'status'})['result']['isolation_policy'], 'enforced')
        task = self.task(service)
        with self.assertRaises(PlayerTaskError):
            Orchestrator(service.runner).players.begin(task['task_id'], 'native', COOPERATIVE)

    def test_invalid_policy_rejected_before_loading_or_creating_game(self):
        service = DuelService(self.repo, self.private)
        self.addCleanup(service.close)
        config = deepcopy(self.config)
        config['player_isolation'] = 'maybe'
        self.assertFalse(service.request({'op': 'start', 'config': config, 'rules_text': 'Test rules'})['ok'])
        self.assertFalse((self.repo / 'games').exists())
