from harness.storage.records import load as read_archive
"""Compact replay portability, cache invalidation, and context privacy boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness.engine.actions import append, digest, initialize, replay
from harness.storage.archive import archive_state, load_replay, write_archive
from harness.storage.compact import execute, operations
from harness.storage.snapshots import collect, object_path, root
from harness.runner.duel import DuelRunner
from harness.integration.mcp import rpc
from harness.integration.service import DuelService
from harness.players.isolated import model_request
from test_actions import state, action, change
import test_session as fixtures


class CompactStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.game = self.repo / 'games' / 'test' / 'test'
        self.game.mkdir(parents=True)
        (self.game / 'game.json').write_text(json.dumps({'id': 'test', 'mode': 'open'}), encoding="utf-8")
        self.journal = initialize(state())
        self.current = replay(self.journal)
        self.cache = Path(self.tmp.name) / 'cache'

    def step(self, request):
        self.journal, self.current = append(self.journal, request)
        write_archive(self.journal, self.current, self.game)

    def test_crlf_snapshot_preserves_exact_bytes_and_removes_verified_copy(self):
        raw = b'Historical rules.\r\nSecond line.\r\n'
        (self.game / 'rules.md').write_bytes(raw)
        write_archive(self.journal, self.current, self.game)
        self.assertFalse((self.game / 'rules.md').exists())
        asset = collect(self.game)['rules.md']
        self.assertEqual(asset['content'].encode('utf-8'), raw)
        self.assertEqual(object_path(self.game, asset['sha256']).read_bytes(), raw)
        self.assertEqual(load_replay(self.game), archive_state(self.current))

    def test_shared_objects_and_catalog_hydration_in_fresh_checkout(self):
        (self.game / 'rules.md').write_text('Historical rules', encoding="utf-8")
        write_archive(self.journal, self.current, self.game)
        shared = root(self.game)
        first_files = sorted(str(p.relative_to(shared)) for p in shared.rglob('*') if p.is_file())
        other = self.repo / 'games' / 'test' / 'another'
        other.mkdir()
        (other / 'game.json').write_text(json.dumps({'id': 'test', 'mode': 'open'}), encoding="utf-8")
        (other / 'rules.md').write_text('Historical rules', encoding="utf-8")
        write_archive(self.journal, self.current, other)
        self.assertEqual(first_files, sorted(str(p.relative_to(shared)) for p in shared.rglob('*') if p.is_file()))
        archive = read_archive(self.game)
        self.assertNotIn('cards', archive['initial_state']['players']['agent'])
        self.assertFalse((self.game / 'rules.md').exists())
        self.assertEqual(load_replay(self.game, cache_dir=self.cache), archive_state(self.current))
        import shutil
        clone = Path(self.tmp.name) / 'clone'
        shutil.copytree(self.repo, clone)
        self.assertEqual(load_replay(clone / 'games/test/test', cache_dir=self.cache / 'clone'), archive_state(self.current))

    def test_warm_cache_skips_transition_replay_and_corruption_rebuilds(self):
        write_archive(self.journal, self.current, self.game)
        original = self.current['players']['agent']['hand']
        self.step(action(self.current, 'move', [change(['players','agent','hand'], original, []),
                                               change(['players','agent','graveyard'], [], original)]))
        expected = load_replay(self.game, cache_dir=self.cache)
        with patch('harness.storage.replay_cache._advance', side_effect=AssertionError('Replay ran')):
            self.assertEqual(load_replay(self.game, cache_dir=self.cache), expected)
        entry = next(self.cache.glob('*/1.json'))
        entry.write_text('{broken', encoding="utf-8")
        self.assertEqual(load_replay(self.game, cache_dir=self.cache), expected)
        self.step(action(self.current, 'choice', [change(['phase'], 'main1', 'end')], 'phase'))
        self.assertEqual(load_replay(self.game, cache_dir=self.cache)['phase'], 'end')
        with self.assertRaises(ValueError):
            load_replay(self.game, cache_dir=self.repo / 'cache')

    def test_schema_two_remains_readable_and_reports_partial_evidence(self):
        from harness.storage.archive import _changes, evidence_coverage
        first = archive_state(self.current)
        original = self.current['players']['agent']['hand']
        self.journal, self.current = append(self.journal, action(self.current, 'move', [
            change(['players','agent','hand'], original, []), change(['players','agent','graveyard'], [], original)]))
        final = archive_state(self.current)
        source = self.journal['events'][0]
        a = deepcopy(source['action']); a['changes'] = _changes(first, final)
        e = {'recorded_at': source['recorded_at'], 'before_sha256': digest(first),
             'after_sha256': digest(final), 'action': a, 'deck_outcomes': []}
        e['event_sha256'] = digest(e)
        legacy = {'schema_version':'2.0','initial_state':first,'initial_state_sha256':digest(first),
                  'events':[e],'assets_sha256':{},'configuration_sha256':digest(json.loads((self.game/'game.json').read_text(encoding="utf-8")))}
        (self.game / 'events.json').write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(load_replay(self.game, cache_dir=self.cache), final)
        legacy['events'][0]['action']['kind'] = 'summon'
        self.assertEqual(evidence_coverage(legacy)['status'], 'partial')

    def test_structural_operations_handle_materials_tokens_and_nested_metadata(self):
        before = replay(initialize(state()))
        after = deepcopy(before)
        card = after['players']['agent']['hand'].pop()
        card['hidden'] = False
        after['players']['agent']['monster_zones'][0] = card
        after['players']['agent']['monster_zones'][0]['materials'] = after['players']['agent']['deck'][:]
        after['players']['agent']['deck'] = []
        after['players']['agent']['lp'] = 7000
        after['players']['agent']['effect_usage']['once'] = {'turn':1,'used':True}
        ops = operations(before, after)
        self.assertEqual(execute(before, ops), after)
        self.assertTrue(any(op['op']=='lp' for op in ops))
        self.assertLess(len(json.dumps(ops)), len(json.dumps(after)))
        with self.assertRaises(ValueError):
            execute(before, [{'op':'set','path':['mode'],'value':'blind'}])


class AgentContextTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    tearDown = fixtures.SessionTests.tearDown
    start = fixtures.SessionTests.start

    def test_context_shrinks_and_focus_cannot_reveal_opponent_hidden_cards(self):
        self.config['human_deck']='decks/unassigned/branded-despia'
        _, game, path = self.start('managed')
        with DuelRunner(path, game) as runner:
            full = runner.context('agent')
            small = runner.context('agent', compact=True)
            self.assertLess(len(json.dumps(small)), len(json.dumps(full)))
            self.assertEqual(small['context_version'], 'compact-v1')
            self.assertNotIn('hand', small['state']['players']['human'])
            self.assertNotIn('remaining_deck_order', json.dumps(small))
            self.assertEqual(model_request(small)['tools'], [])
            allowed = set(full['cards'])
            secret = next(str(card['card_id']) for card in runner.state['players']['human']['hand']
                          if str(card['card_id']) not in allowed)
            self.assertNotIn(secret, runner.context('agent', [secret], compact=True)['cards'])
            extra = str(runner.state['players']['agent']['extra_deck'][0]['card_id'])
            focused = runner.context('agent', [extra], compact=True)
            self.assertIn(extra, focused['cards'])
            self.assertIn('desc', focused['cards'][extra])

    def test_mcp_compact_endpoint_and_legacy_full_endpoint(self):
        config = deepcopy(self.config);config['mode']='managed';config['human_deck']='decks/unassigned/branded-despia'
        service = DuelService(self.repo, self.private)
        self.addCleanup(service.close)
        self.assertTrue(service.request({'op':'start','config':config,'rules_text':'Agreed rules'})['ok'])
        def call(name):
            r=rpc(service, {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':{'player':'agent'}}})
            return json.loads(r['result']['content'][0]['text'])['result']
        self.assertEqual(call('duel_agent_context')['context_version'], 'compact-v1')
        self.assertNotIn('context_version', call('duel_context'))
