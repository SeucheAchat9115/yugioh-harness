import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yugioh_benchmark.card_metadata import build_metadata, fetch_response, request_url
from yugioh_benchmark.replay import load_bundle, canonical

ROOT = Path(__file__).resolve().parents[1]


class CardMetadataTests(unittest.TestCase):
    def setUp(self):
        self.replay = load_bundle(ROOT/'replays/db-json-40753-85958923')
        self.selected = json.loads((ROOT/'benchmarks/card-metadata/db-json-40753-85958923.json').read_text(encoding='utf-8'))
        self.response = json.dumps({'data': [c['api_card'] for c in self.selected['cards']]}).encode()

    def test_selected_snapshot_matches_replay_without_mutation(self):
        before = canonical(self.replay)
        rebuilt = build_metadata(self.replay, self.response, self.selected['retrieved_at'])
        for key in self.selected:
            if key != 'response_bytes_sha256':
                self.assertEqual(rebuilt[key], self.selected[key], key)
        self.assertEqual(canonical(self.replay), before)
        self.assertEqual(rebuilt['matched_distinct_passcodes'], 42)
        self.assertEqual(sum(not c['text_matches_all_observations'] for c in rebuilt['cards']), 10)
        self.assertTrue(all(c['name_matches_all_observations'] for c in rebuilt['cards']))
        self.assertFalse(rebuilt['historical_rules_verified'])
        self.assertFalse(rebuilt['complete_named_decklists'])
        self.assertIn('07572887', [c['passcode'] for c in rebuilt['cards']])
        self.assertIn('00213326', [c['passcode'] for c in rebuilt['cards']])

    def test_unresolved_and_missing_are_explicit_not_guessed(self):
        play = self.replay['source_metadata']['data']['plays'][0]
        play['cards'] = [{'name': 'Unknown', 'id': 71413901},
                         {'name': 'Bad', 'serial_number': '0'},
                         {'name': 'Malformed', 'serial_number': '123456789'}]
        result = build_metadata(self.replay, b'{"data": []}', '2026-10-08T00:00:00Z')
        self.assertEqual(result['matched_distinct_passcodes'], 0)
        self.assertEqual(len(result['missing_passcodes']), 42)
        self.assertEqual(len(result['unresolved_definitions']), 3)

    def test_reject_ambiguous_response_and_text_bundle(self):
        card = self.selected['cards'][0]['api_card']
        for body in ({'data': [card, card]}, {'data': [{'id': card['id'], 'name': card['name']}]},
                     {'error': 'not found'}):
            with self.assertRaises(ValueError):
                build_metadata(self.replay, json.dumps(body).encode(), '2026-10-08')
        with self.assertRaises(ValueError):
            build_metadata(self.replay, self.response, '')
        from copy import deepcopy
        text = deepcopy(self.replay)
        text['source']['adapter'] = 'duelingbook-text-v1'
        with self.assertRaises(ValueError):
            request_url(text)

    def test_fetch_is_one_batched_request_and_preserves_exact_bytes(self):
        from io import BytesIO
        with patch('yugioh_benchmark.card_metadata.urlopen', return_value=BytesIO(self.response)) as lookup:
            response = fetch_response(self.replay)
        self.assertEqual(response, self.response)
        request = lookup.call_args.args[0]
        self.assertEqual(request.full_url, request_url(self.replay))
        self.assertIn('Accept', request.headers)
        self.assertEqual(build_metadata(self.replay, response, '2026-10-08')['response_bytes_sha256'],
                         hashlib.sha256(self.response).hexdigest())

    def test_cli_offline_and_refuse_overwrite(self):
        from yugioh_benchmark.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            response, output = Path(tmp)/'response.json', Path(tmp)/'output.json'
            response.write_bytes(self.response)
            argv = ['benchmark', 'card-metadata', str(ROOT/'replays/db-json-40753-85958923'),
                    '--response', str(response), '--retrieved-at', '2026-10-08', '--output', str(output)]
            with patch('sys.argv', argv), patch('builtins.print'):
                main()
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['matched_distinct_passcodes'], 42)
            with patch('sys.argv', argv), patch('sys.stderr'), self.assertRaises(SystemExit):
                main()
