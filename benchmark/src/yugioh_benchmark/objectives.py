"""Objective success with independent legality and actual shared-runtime execution.

This metric deliberately does not compare a candidate to the human's recorded
move. Acceptable alternatives are explicit, private reviewer-authored signatures.
"""
import json
from .kpis import approved, digest, valid_hash, validate_suite


def score_objectives(suite, run):
    from harness.engine.actions import replay
    from harness.runner.intents import parse_intent, translate_intent
    from harness.runner.state_tools import build
    from harness.engine.actions import apply
    cases = validate_suite(suite)
    if run.get('protocol') != 'harness-objectives-v1' or run.get('suite_sha256') != digest(suite):
        raise ValueError('Objective run must pin its protocol and reviewed suite')
    if (not isinstance(run.get('model'), str) or not run['model'] or
            any(not valid_hash(run.get(k)) for k in ('agent_instructions_sha256', 'harness_fingerprint_sha256'))):
        raise ValueError('Record model, instructions and harness provenance')
    if not isinstance(run.get('results'), list):
        raise ValueError('Results must be a list')
    known = {case['id'] for case in cases}
    results = {}
    for row in run['results']:
        if row.get('case_id') not in known or row['case_id'] in results:
            raise ValueError('Unknown or duplicate result')
        results[row['case_id']] = row
    outcomes = []
    for case in cases:
        row = results.get(case['id'])
        status = 'missing' if row is None else row.get('status')
        if status not in {'missing', 'timeout', 'completed'}:
            raise ValueError('Unknown result status')
        success = legality_score = 0
        pending = []
        if status == 'completed':
            review = row.get('legality_review')
            normalization = row.get('move_normalization_review')
            if (not approved(normalization) or normalization.get('response_sha256') != digest(row.get('response'))
                    or normalization.get('move_sha256') != digest(row.get('normalized_move'))):
                raise ValueError('Objective normalization must bind response and semantic move')
            if not approved(review):
                success = legality_score = None
                pending.append('independent legality review missing or uncertain')
            else:
                if (review.get('rules_sha256') != digest(case['rules']) or
                        review.get('attempt_sha256') != digest({k:v for k,v in row.items() if k != 'legality_review'})
                        or review.get('verdict') not in {'valid', 'invalid'} or not review.get('reason')):
                    raise ValueError('Legality review must bind attempt, rules and verdict')
                legality_score = int(review['verdict'] == 'valid')
                # A correct-looking name with invalid costs, no execution, or a
                # failed translation is never a successful gameplay decision.
                if legality_score and row.get('execution_plan') is not None:
                    journal = row.get('journal', {})
                    initial = journal.get('initial_state')
                    if digest(initial) != case['initial_state_sha256']:
                        raise ValueError('Execution starts from a different reviewed position')
                    actual = replay(journal)
                    from .evaluation import normalized_move
                    if parse_intent(row['response']) != row['intent']:
                        raise ValueError('Intention does not match the submitted response')
                    if normalized_move(row['intent'], initial) != row['normalized_move']:
                        raise ValueError('Semantic move does not match the submitted intention')
                    # Independently reproduce the bookkeeping, so a bound but
                    # unrelated journal cannot stand in for candidate execution.
                    referee = json.loads(row['referee_response'])
                    candidate = translate_intent(initial, row['intent'], reviewed_activation=referee.get('activation'))
                    candidate.update(moderator_approved=True, public_summary_reviewed=True)
                    plan = row['execution_plan']
                    if (plan != candidate or plan.get('actor') != 'agent' or plan.get('expected_revision') != 0
                            or not journal.get('events') or len(journal['events']) != 1):
                        raise ValueError('Expected exactly one evaluated initiation')
                    expected = apply(initial, build(initial, plan))
                    if actual != expected:
                        raise ValueError('Journal differs from the executed candidate plan')
                    success = int(row['normalized_move'] in case['acceptable_moves'])
        outcomes.append({'case_id': case['id'], 'status': status,
                         'scores': {'objective_success': success, 'rule_correctness': legality_score},
                         'pending': pending})
    kpis = {}
    for name in ('objective_success', 'rule_correctness'):
        values = [row['scores'][name] for row in outcomes]
        graded = [value for value in values if value is not None]
        kpis[name] = {'total': len(values), 'graded': len(graded), 'pending': len(values)-len(graded),
                      'passed': sum(graded), 'score': sum(graded)/len(values) if len(graded)==len(values) else None}
    score = kpis['objective_success']['score']
    return {'schema_version': '1.0', 'metric': 'reviewed_objective_success',
            'protocol': 'harness-objectives-v1', 'suite': suite['id'], 'suite_sha256': digest(suite),
            'model': run['model'], 'kpis': kpis, 'final_score_percent': None if score is None else 100*score,
            'outcomes': outcomes, 'scope': 'Single-decision goal success gated by legality and execution; not win rate. '
                        'Rule correctness is a separate referee-dependent diagnostic, not a second score weight.'}
