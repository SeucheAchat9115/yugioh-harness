from copy import deepcopy
from importlib.util import find_spec
import unittest

from yugioh_benchmark.kpis import digest, gameplay_state, score_kpis

HASH = '0' * 64  # Explicitly synthetic unit-test provenance.


def state():
    def player():
        return {'lp': 10000, 'hand': [], 'deck': [], 'extra_deck': [], 'side_deck': [],
                'monster_zones': [None]*5, 'spell_trap_zones': [None]*5,
                'field_spell': None, 'graveyard': [], 'banished': [], 'cards': {},
                'normal_summon_used': False, 'effect_usage': {}, 'restrictions': []}
    return {'game_id': 'synthetic-test', 'mode': 'agent-vs-agent',
            'player_isolation': 'cooperative', 'status': 'active', 'revision': 0,
            'turn': 1, 'phase': 'main1', 'active_player': 'agent',
            'players': {'human': player(), 'agent': player()}, 'shared_zones': {},
            'presentation': {'show_agent_hand': False}, 'pending_effects': [],
            'pending_decision': None, 'chain': []}


def suite():
    common = {'review': {'status': 'approved', 'reviewer': 'synthetic-unit-test'},
              'initial_state_sha256': digest(state()),
              'rules': {'format': 'synthetic', 'rules_version': 'synthetic-test',
                        'rules_sha256': HASH, 'banlist_sha256': HASH, 'card_text_sha256': HASH}}
    expected = state()
    expected['players']['agent']['lp'] = 9500
    return {'schema_version': '1.0', 'id': 'synthetic-test', 'cases': [
        {**deepcopy(common), 'id': 'update', 'task': 'state_recreation',
         'declared_play': 'Pay 500 LP', 'expected_state': expected},
        {**deepcopy(common), 'id': 'choice', 'task': 'human_move_reproduction',
         'human_move': {'kind': 'pass'},
         'source': {'replay': 'synthetic', 'before_sequence': 1, 'payload_sha256': HASH}}]}


def run(cases, rows):
    return {'suite_sha256': digest(cases), 'model': 'synthetic-test-model',
            'agent_instructions_sha256': HASH, 'harness_fingerprint_sha256': HASH,
            'results': rows}


def legality(row, case, verdict='valid'):
    row.pop('legality_review', None)
    row['legality_review'] = {'status': 'approved', 'reviewer': 'independent-unit-test',
                             'verdict': verdict, 'reason': 'Synthetic grading fixture',
                             'rules_sha256': digest(case['rules']),
                             'attempt_sha256': digest(row)}
    return row


def choice(case, move=None, verdict='valid'):
    row = {'case_id': case['id'], 'status': 'completed', 'response': 'synthetic response',
           'normalized_move': case['human_move'] if move is None else move}
    row['move_normalization_review'] = {
        'status': 'approved', 'reviewer': 'synthetic-normalizer',
        'response_sha256': digest(row['response']), 'move_sha256': digest(row['normalized_move'])}
    return legality(row, case, verdict)


class KpiTests(unittest.TestCase):
    def test_rules_only_cases_do_not_invent_human_agreement(self):
        cases = suite()
        case = deepcopy(cases['cases'][1])
        case.update(id='rules-only', task='rule_correctness')
        case.pop('human_move')
        case.pop('source')
        cases['cases'] = [cases['cases'][0], case]
        row = legality({'case_id': 'rules-only', 'status': 'completed',
                        'response': 'Pass'}, case)
        result = score_kpis(cases, run(cases, [row]))
        self.assertEqual(result['kpis']['human_move_agreement']['total'], 0)
        self.assertIsNone(result['final_score_percent'])
        self.assertEqual(result['kpis']['rule_correctness']['score'], 0.5)

    def test_missing_attempts_count_in_all_denominators(self):
        cases = suite()
        result = score_kpis(cases, run(cases, []))
        self.assertEqual(result['final_score_percent'], 0)
        self.assertEqual([result['kpis'][key]['total'] for key in result['kpis']], [1, 1, 2])

    def test_agreement_and_legality_are_independent(self):
        cases = suite()
        result = score_kpis(cases, run(cases, [choice(cases['cases'][1], verdict='invalid')]))
        self.assertEqual(result['kpis']['human_move_agreement']['score'], 1)
        self.assertEqual(result['kpis']['rule_correctness']['score'], 0)

    def test_ungraded_attempt_blocks_final_score(self):
        cases = suite()
        row = {'case_id': 'choice', 'status': 'completed', 'response': 'ungraded'}
        result = score_kpis(cases, run(cases, [row]))
        self.assertIsNone(result['final_score_percent'])
        self.assertEqual(result['kpis']['rule_correctness']['pending'], 1)
        self.assertEqual(result['kpis']['human_move_agreement']['pending'], 1)

    def test_changed_rules_response_or_suite_rejected(self):
        cases = suite()
        for key in ('rules', 'response', 'suite'):
            with self.subTest(key=key):
                row = choice(cases['cases'][1])
                artifact = run(cases, [row])
                changed = deepcopy(cases)
                if key == 'rules':
                    row['legality_review']['rules_sha256'] = HASH
                elif key == 'response':
                    row['response'] = 'changed after review'
                else:
                    changed['cases'][0]['declared_play'] = 'Different play'
                with self.assertRaises(ValueError):
                    score_kpis(changed, artifact)

    def test_bad_weights_duplicate_results_and_unreviewed_cases_rejected(self):
        cases = suite()
        for value in (0.5, float('nan')):
            with self.assertRaises(ValueError):
                score_kpis(cases, run(cases, []), {key: value for key in
                           ('state_recreation', 'human_move_agreement', 'rule_correctness')})
        row = choice(cases['cases'][1])
        with self.assertRaises(ValueError):
            score_kpis(cases, run(cases, [row, row]))
        cases['cases'][0]['review']['status'] = 'pending'
        with self.assertRaises(ValueError):
            score_kpis(cases, run(cases, []))

    def test_public_kpi_command_scores_trusted_artifacts(self):
        import json
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from yugioh_benchmark.cli import main
        cases = suite()
        with TemporaryDirectory() as temporary:
            case_path, run_path = Path(temporary)/'suite.json', Path(temporary)/'run.json'
            case_path.write_text(json.dumps(cases))
            run_path.write_text(json.dumps(run(cases, [])))
            output = StringIO()
            with patch('sys.argv', ['benchmark', 'score-kpis', str(case_path), str(run_path)]), patch('sys.stdout', output):
                main()
            result = json.loads(output.getvalue())
            self.assertEqual(result['metric'], 'agentic_workflow_kpis')
            self.assertEqual(result['final_score_percent'], 0)
            self.assertTrue(all(kpi['passed'] == 0 for kpi in result['kpis'].values()))

    def test_gameplay_comparison_preserves_order_and_ignores_admin(self):
        initial = state()
        other = deepcopy(initial)
        other.update(game_id='other', revision=99)
        self.assertEqual(gameplay_state(initial), gameplay_state(other))
        initial['players']['agent']['deck'] = ['a', 'b']
        other['players']['agent']['deck'] = ['b', 'a']
        self.assertNotEqual(gameplay_state(initial), gameplay_state(other))

    @unittest.skipUnless(find_spec('harness'), 'requires pinned harness')
    def test_equal_weight_harness_journal_score_and_tampering(self):
        from harness.engine.actions import initialize, append
        from harness.runner.state_tools import build
        initial = state()
        request = {'kind': 'damage', 'actor': 'agent', 'expected_revision': 0,
                   'moderator_approved': True, 'public_summary_reviewed': True,
                   'public_summary': 'Synthetic 500 LP payment',
                   'operations': [{'op': 'lp', 'player': 'agent', 'delta': -500}]}
        journal, _ = append(initialize(initial), build(initial, request))
        cases = suite()
        row = legality({'case_id': 'update', 'status': 'completed', 'journal': journal}, cases['cases'][0])
        alternative = choice(cases['cases'][1], {'kind': 'summon', 'card': 'synthetic'})
        result = score_kpis(cases, run(cases, [row, alternative]))
        self.assertAlmostEqual(result['final_score_percent'], 200/3)
        cases['cases'][0]['expected_state']['players']['agent']['lp'] = 9400
        result = score_kpis(cases, run(cases, [row, alternative]))
        self.assertEqual(result['kpis']['state_recreation']['score'], 0)
        row['journal']['events'][0]['after_sha256'] = HASH
        legality(row, cases['cases'][0])
        with self.assertRaises(ValueError):
            score_kpis(cases, run(cases, [row, alternative]))
