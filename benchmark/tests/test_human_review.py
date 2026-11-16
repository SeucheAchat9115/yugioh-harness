"""Recorded duel -> filtered iPad board -> exported choice -> scored benchmark."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_harness_replay import OracleTransport, ROOT, ZIP
from yugioh_benchmark.evaluation import evaluate
from yugioh_benchmark.human_review import ANSWERS, export_review_boards, prepare_human_review

CATALOG_PATH = ROOT / 'benchmark/benchmarks/reviews/edison-ipad-review-v1.json'


class HumanReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
        cls.catalog = export_review_boards(ZIP, cls.spec)

    def export(self, choice_id='normal-bora'):
        return {
            'schema': ANSWERS, 'catalog_sha256': self.catalog['sha256'],
            'answers': [{'case_id': 'edison-3', 'choice_id': choice_id, 'saved_at': 1}],
        }

    def test_catalog_has_only_three_blind_options_per_recorded_position(self):
        self.assertEqual([x['board']['revision'] for x in self.catalog['cases']], [3, 32, 88, 99, 165])
        for case in self.catalog['cases']:
            board = case['board']
            self.assertIn('hand', board['players']['human'])
            self.assertNotIn('hand', board['players']['agent'])
            self.assertNotIn('extra_deck', board['players']['agent'])
            self.assertNotIn('options', board)
            self.assertIsNone(board['last_action'])
            self.assertEqual(len(case['choices']), 3)
            self.assertTrue(all(set(x) == {'id', 'label'} for x in case['choices']))
        final = self.catalog['cases'][-1]['board']
        hidden = final['players']['agent']['monsters'][0]
        self.assertTrue(hidden['hidden'])
        self.assertNotIn('name', hidden)
        self.assertNotIn('image_id', hidden)

    def test_different_legal_answer_scores_as_mismatch(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / 'dataset'
            self.assertEqual(prepare_human_review(ZIP, self.spec, self.export(), dataset)['cases'], 1)
            steps = {x['id']: x for x in self.spec['checkpoints'][0]['choices']}
            for expected, choice_id in ((100, 'normal-bora'), (0, 'normal-gale')):
                transport = OracleTransport([{'reference_intent': steps[choice_id]['intent']}])
                report = evaluate(dataset, root / choice_id, ['offline-test'], transport,
                                  referee_model='offline-referee')[0]
                self.assertEqual(report['score']['final_score_percent'], expected)
                self.assertEqual(report['score']['kpis']['rule_correctness']['score'], 1)
                request = json.dumps(transport.requests[0])
                for move in steps.values():
                    self.assertIn(move['label'], request)
                self.assertNotIn('human_choice_id', request)
                self.assertNotIn('acceptable_moves', request)

    def test_reject_stale_catalog_and_invalid_or_duplicate_answers(self):
        invalid = [self.export('unknown'), {**self.export(), 'catalog_sha256': '0' * 64}]
        duplicate = deepcopy(self.export())
        duplicate['answers'].append(duplicate['answers'][0])
        invalid.append(duplicate)
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'dataset'
            for export in invalid:
                with self.subTest(export=export), self.assertRaises(ValueError):
                    prepare_human_review(ZIP, self.spec, export, path)
                self.assertFalse(path.exists())
