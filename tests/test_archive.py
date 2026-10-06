from harness.storage.records import load as read_archive
"""Verify hidden-state replay, randomness, integrity and live-view boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from harness.engine.actions import append, initialize, replay
from harness.runner.state_tools import build
from harness.storage.archive import archive_state, load_replay, write_archive
from test_actions import state


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.game = Path(self.tmp.name)
        initial = state()
        initial['mode'] = 'managed'
        initial['players']['agent']['deck'] += [
            {'instance_id': 'copy-3', 'card_id': 456},
            {'instance_id': 'copy-0', 'card_id': 789}]
        self.journal = initialize(initial)
        self.current = replay(self.journal)
        (self.game / 'game.json').write_text(json.dumps({'id': 'test', 'mode': 'managed'}), encoding="utf-8")
        write_archive(self.journal, self.current, self.game)

    def step(self, kind, operations):
        request = {'kind': kind, 'actor': 'agent', 'expected_revision': self.current['revision'],
                   'moderator_approved': True, 'public_summary_reviewed': True,
                   'public_summary': 'A reviewed step.', 'operations': operations}
        action = build(self.current, request)
        self.journal, self.current = append(self.journal, action)
        write_archive(self.journal, self.current, self.game)
        return self.current

    def test_random_outcomes_reproduce_every_revision_without_shuffled_queue(self):
        history = [deepcopy(self.current)]
        history.append(deepcopy(self.step('shuffle', [{'op': 'shuffle', 'player': 'agent'}])))
        drawn = deepcopy(self.current['players']['agent']['deck'][:2])
        history.append(deepcopy(self.step('draw', [{'op': 'draw', 'player': 'agent', 'count': 2}])))
        for revision, original in enumerate(history):
            self.assertEqual(load_replay(self.game, revision), archive_state(original))
        archive = read_archive(self.game)
        self.assertEqual(archive['events'][0]['action']['operations'], [])
        self.assertEqual(archive['events'][1]['deck_outcomes'][0]['cards_leaving_deck_in_order'], drawn)
        self.assertEqual(archive['initial_state']['players']['agent']['deck'],
                         sorted(history[0]['players']['agent']['deck'], key=lambda c: c['instance_id']))
        rebuilt = self.game / 'events.json'
        rebuilt.unlink()
        write_archive(self.journal, self.current, self.game)
        self.assertEqual(read_archive(self.game), archive)

    def test_set_identity_and_counters_preserved_but_player_view_filtered(self):
        self.step('set', [{'op': 'move', 'card': 'copy-1',
                          'to': ['players', 'agent', 'spell_trap_zones', 0],
                          'attributes': {'hidden': True, 'position': 'face-down', 'set_turn': 1}},
                         {'op': 'usage', 'player': 'agent', 'effect': 'used-ability',
                          'value': {'turn': 1, 'used': True, 'owner': 'agent'}}])
        full = load_replay(self.game)
        self.assertEqual(full['players']['agent']['spell_trap_zones'][0]['card_id'], 123)
        human = load_replay(self.game, perspective='human')
        self.assertNotIn('card_id', human['players']['agent']['spell_trap_zones'][0])
        self.assertNotIn('hand', human['players']['agent'])
        self.assertNotIn('remaining_deck_order', json.dumps(human))

    def test_tampered_outcome_and_asset_rejected(self):
        self.step('draw', [{'op': 'draw', 'player': 'agent', 'count': 1}])
        path = self.game / 'events/000001.json'
        event = json.loads(path.read_text(encoding="utf-8"))
        event['deck_outcomes'] = []
        path.write_text(json.dumps(event), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, 'event hash'):
            load_replay(self.game)
        path.unlink()
        (self.game / 'events.json').unlink()
        (self.game / 'rules.md').write_text('Exact agreed rules', encoding="utf-8")
        write_archive(self.journal, self.current, self.game)
        from harness.storage.snapshots import object_path
        archived = read_archive(self.game)
        object_path(self.game, archived['assets_sha256']['rules.md']).write_text('Changed rules', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, 'asset hash'):
            load_replay(self.game)

    def test_top_return_is_recorded_without_storing_rest_of_queue(self):
        self.step('move', [{'op': 'move', 'card': 'copy-1', 'to': ['players', 'agent', 'deck'], 'index': 0}])
        archive = read_archive(self.game)
        returned = archive['events'][0]['deck_outcomes'][0]['cards_returned_to_deck']
        self.assertEqual(returned[0]['position'], 'top')
        self.assertEqual(returned[0]['card']['instance_id'], 'copy-1')
        self.assertEqual(load_replay(self.game), archive_state(self.current))

    def test_self_archive_does_not_invent_human_hidden_identities(self):
        from test_experience import fixture
        current = fixture('blind')
        journal = initialize(current)
        (self.game / 'events.json').unlink()
        (self.game / 'game.json').write_text(json.dumps({'id': 'test', 'mode': 'blind'}), encoding="utf-8")
        write_archive(journal, current, self.game)
        archived = read_archive(self.game)
        self.assertEqual(archived['hidden_state_coverage'], 'human-unknown')
        self.assertIsNone(load_replay(self.game)['players']['human']['hand'])

    def test_result_and_revision_zero_integrity(self):
        self.step('finish', [{'op': 'lp', 'player': 'agent', 'delta': -8000},
                             {'op': 'status', 'value': 'finished'}])
        from harness.storage.archive import game_result
        self.assertEqual(game_result(self.current, self.journal)['winner'], 'human')
        explicit = {'winner': 'agent', 'reason': 'Human conceded'}
        initial = replay(initialize(state()))
        a = build(initial, {'kind': 'finish', 'actor': 'human', 'expected_revision': 0,
                            'moderator_approved': True, 'public_summary_reviewed': True,
                            'public_summary': 'Human conceded.', 'result': explicit,
                            'operations': [{'op': 'status', 'value': 'finished'}]})
        j, s = append(initialize(initial), a)
        self.assertEqual(game_result(s, j), explicit)
        with self.assertRaises(ValueError):
            build(initial, {**a, 'operations': []})
        (self.game / 'events.json').unlink()
        write_archive(initialize(initial), initial, self.game)
        archive = json.loads((self.game / 'events.json').read_text(encoding="utf-8"))
        archive['initial_state']['turn'] = 99
        (self.game / 'events.json').write_text(json.dumps(archive), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, 'initial-state hash'):
            load_replay(self.game)
