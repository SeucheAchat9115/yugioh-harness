from copy import deepcopy
import json
import subprocess
import sys
import unittest

import test_session as fixtures
from harness.engine.actions import replay
from harness.runner.duel import DuelRunner


class RunnerTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown
    start = fixtures.SessionTests.start
    def test_incremental_draw_save_and_resume(self):
        initial, game, path = self.start('open')
        expected = initial['players']['agent']['deck'][0]
        with DuelRunner(path, game) as runner:
            result = runner.command({'id': 'draw-1', 'command': 'draw', 'actor': 'agent',
                                     'expected_revision': 0, 'moderator_approved': True})
            self.assertEqual(result['revision'], 1)
            self.assertEqual(runner.state['players']['agent']['hand'][-1], expected)
            self.assertEqual(runner.state, replay(runner.journal))
            with self.assertRaises(ValueError):
                runner.command({'command': 'draw', 'actor': 'agent', 'expected_revision': 0,
                                'moderator_approved': True})
        with DuelRunner(path, game) as resumed:
            self.assertEqual(resumed.state['revision'], 1)
            self.assertEqual(resumed.state['players']['agent']['hand'][-1], expected)

    def test_player_adapter_cannot_read_future_or_change_state(self):
        _, game, path = self.start('open')
        with DuelRunner(path, game) as runner:
            before = deepcopy(runner.state)
            context = runner.context('agent')
            self.assertNotIn('remaining_deck_order', context['state']['players']['human'])
            self.assertNotIn('remaining_deck_order', context['state']['players']['agent'])
            context['state']['players']['agent']['lp'] = 0
            self.assertEqual(runner.state, before)

    def test_pending_window_rejects_unprompted_commands(self):
        _, game, path = self.start('open')
        with DuelRunner(path, game) as runner:
            runner.record({'id': 'window', 'kind': 'choice', 'actor': 'moderator',
                'expected_revision': 0, 'moderator_approved': True, 'public_summary_reviewed': True,
                'public_summary': 'Human decision window opened.', 'changes': [
                    {'path': ['pending_decision'], 'before': None,
                     'after': {'actor': 'human', 'window': 'main-phase'}}]})
            with self.assertRaisesRegex(ValueError, 'Pending'):
                runner.command({'command': 'draw', 'actor': 'human', 'expected_revision': 1,
                                'moderator_approved': True})

    def test_single_writer_and_external_legacy_writer_detection(self):
        _, game, path = self.start('open')
        with DuelRunner(path, game) as runner:
            with self.assertRaises(BlockingIOError):
                DuelRunner(path, game)
            journal_path = path.with_name('journal.json')
            journal_path.write_text(journal_path.read_text(encoding="utf-8") + '\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, 'External writer'):
                runner.command({'command': 'draw', 'actor': 'agent', 'expected_revision': 0,
                                'moderator_approved': True})

    def test_stdio_transport(self):
        _, game, path = self.start('open')
        result = subprocess.run([sys.executable, '-m', 'harness', '--state', str(path),
                                 '--game-dir', str(game)], input='{"op":"capabilities"}\n{"op":"view","player":"human"}\n',
                                text=True, encoding="utf-8", capture_output=True, check=True)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertTrue(all(response['ok'] for response in responses))
        self.assertNotIn('hand', responses[1]['result']['state']['players']['agent'])
