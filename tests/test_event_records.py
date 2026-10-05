"""Selective event discovery, append recovery, and legacy compact archive support."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from harness.storage.records import load, read_event, write
from harness.storage.archive import load_replay
from harness.storage.atomic import save
import test_archive


class EventRecordTests(unittest.TestCase):
    setUp = test_archive.ArchiveTests.setUp
    step = test_archive.ArchiveTests.step

    def test_index_selective_read_and_immutable_records(self):
        self.step('draw', [{'op': 'draw', 'player': 'agent', 'count': 1}])
        index = json.loads((self.game / 'events.json').read_text())
        self.assertNotIn('events', index)
        entry = index['event_index'][0]
        self.assertEqual(entry['revision'], 1)
        self.assertEqual(entry['turn'], self.current['turn'])
        self.assertEqual(entry['phase'], self.current['phase'])
        self.assertEqual(entry['file'], 'events/000001.json')
        record = read_event(self.game, entry)
        self.assertEqual(record, load(self.game)['events'][0])
        raw = (self.game / entry['file']).read_bytes()
        self.step('shuffle', [{'op': 'shuffle', 'player': 'agent'}])
        self.assertEqual((self.game / entry['file']).read_bytes(), raw)
        bad = deepcopy(entry); bad['file'] = '../escape.json'
        with self.assertRaises(ValueError):
            read_event(self.game, bad)
        archive = load(self.game)
        archive['events'][0]['action']['public_summary'] = 'Different record'
        with self.assertRaisesRegex(ValueError, 'replace'):
            write(self.game, archive)

    def test_interrupted_append_keeps_old_index_and_retries(self):
        original = (self.game / 'events.json').read_bytes()
        # Build the next record, but simulate failure before publishing its index.
        from harness.engine.actions import append
        from harness.runner.state_tools import build
        from harness.storage.archive import build_archive
        action = build(self.current, {'kind': 'shuffle', 'actor': 'agent',
            'expected_revision': 0, 'moderator_approved': True,
            'public_summary_reviewed': True, 'public_summary': 'Shuffle.',
            'operations': [{'op': 'shuffle', 'player': 'agent'}]})
        journal, current = append(self.journal, action)
        archive = build_archive(journal, current, load(self.game))
        def interrupt(path, value):
            if path.name == 'events.json':
                raise OSError('Simulated interruption')
            save(path, value)
        with patch('harness.storage.records.save', side_effect=interrupt):
            with self.assertRaises(OSError):
                write(self.game, archive)
        self.assertEqual((self.game / 'events.json').read_bytes(), original)
        self.assertEqual(load(self.game)['events'], [])
        write(self.game, archive)
        self.assertEqual(len(load(self.game)['events']), 1)

    def test_schema_three_array_still_replays(self):
        self.step('draw', [{'op': 'draw', 'player': 'agent', 'count': 1}])
        archive = load(self.game)
        archive['schema_version'] = '3.0'
        save(self.game / 'events.json', archive)
        from harness.storage.archive import archive_state
        self.assertEqual(load_replay(self.game), archive_state(self.current))

    def test_missing_changed_or_reordered_records_rejected(self):
        self.step('draw', [{'op': 'draw', 'player': 'agent', 'count': 1}])
        self.step('shuffle', [{'op': 'shuffle', 'player': 'agent'}])
        path = self.game / 'events.json'
        index = json.loads(path.read_text())
        index['event_index'].reverse()
        save(path, index)
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            load_replay(self.game)
        index['event_index'].reverse()
        save(path, index)
        event_path = self.game / 'events/000002.json'
        event_path.unlink()
        with self.assertRaises(FileNotFoundError):
            load_replay(self.game)
