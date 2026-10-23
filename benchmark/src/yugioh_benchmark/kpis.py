"""Three reviewed agentic-workflow KPIs; structural coverage never contributes.

This consumes trusted evaluation artifacts from the existing harness workflow.
It is not a second game loop, a legality engine, or a model-output self-grader.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from .inputs import read_text
from .replay import canonical

KPI_NAMES = ('state_recreation', 'human_move_agreement', 'rule_correctness')
STATE_FIELDS = ('players', 'shared_zones', 'phase', 'turn', 'active_player',
                'chain', 'pending_decision', 'pending_effects', 'status')
RULE_FIELDS = ('format', 'rules_version', 'rules_sha256', 'banlist_sha256', 'card_text_sha256')
DEFAULT_WEIGHTS = {name: 1/3 for name in KPI_NAMES}


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def approved(review):
    return (isinstance(review, dict) and review.get('status') == 'approved'
            and isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip()))


def valid_hash(value):
    return (isinstance(value, str) and len(value) == 64
            and all(char in '0123456789abcdef' for char in value))


def gameplay_state(state):
    """All gameplay roots; omit only administrative IDs, revision and rendering."""
    if not isinstance(state, dict) or any(field not in state for field in STATE_FIELDS):
        raise ValueError('A complete gameplay state is required')
    if not isinstance(state['players'], dict) or set(state['players']) != {'human', 'agent'}:
        raise ValueError('Both harness player slots are required')
    return {field: state[field] for field in STATE_FIELDS}


def validate_suite(suite):
    if suite.get('schema_version') != '1.0' or not suite.get('id'):
        raise ValueError('Expected a versioned KPI suite with an ID')
    cases = suite.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('A nonempty reviewed case list is required')
    ids = set()
    for case in cases:
        identity = case.get('id')
        if not isinstance(identity, str) or not identity or identity in ids:
            raise ValueError('Case IDs must be unique nonempty strings')
        ids.add(identity)
        if not approved(case.get('review')):
            raise ValueError('KPI cases require reviewer approval')
        if case.get('task') not in {'state_recreation', 'human_move_reproduction', 'rule_correctness'}:
            raise ValueError('Unknown KPI task')
        rules = case.get('rules', {})
        if (any(field not in rules for field in RULE_FIELDS)
                or not isinstance(rules['format'], str) or not rules['format']
                or not isinstance(rules['rules_version'], str) or not rules['rules_version']
                or any(not valid_hash(rules[field]) for field in RULE_FIELDS[2:])):
            raise ValueError('Pin the format, rules version, rules, banlist and card-text hashes')
        if not valid_hash(case.get('initial_state_sha256')):
            raise ValueError('Pin the reviewed initial harness state')
        if case['task'] == 'state_recreation':
            gameplay_state(case.get('expected_state'))
            if not isinstance(case.get('declared_play'), str) or not case['declared_play'].strip():
                raise ValueError('State recreation requires the player-declared play')
        elif case['task'] == 'human_move_reproduction':
            move = case.get('human_move')
            if not isinstance(move, dict) or not isinstance(move.get('kind'), str) or not move['kind']:
                raise ValueError('Human reproduction requires a reviewed semantic move signature')
            source = case.get('source', {})
            if (not isinstance(source.get('replay'), str) or not source['replay']
                    or type(source.get('before_sequence')) is not int or source['before_sequence'] < 1
                    or not valid_hash(source.get('payload_sha256'))):
                raise ValueError('Human moves must link to a pinned replay decision boundary')
    return cases


def validate_weights(weights):
    if (not isinstance(weights, dict) or set(weights) != set(KPI_NAMES)
            or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                   for value in weights.values())
            or not math.isclose(sum(weights.values()), 1, abs_tol=1e-9)):
        raise ValueError('Three positive finite KPI weights must sum to one')
    return dict(weights)


def score_kpis(suite, run, weights=None):
    """A: exact final-state match; B: semantic human agreement; C: reviewed legality.

    Missing model attempts receive zero. Ungraded present attempts remain pending
    and prevent a final score. Independent grading evidence is mandatory.
    """
    cases = validate_suite(suite)
    weights = validate_weights(DEFAULT_WEIGHTS if weights is None else weights)
    if run.get('suite_sha256') != digest(suite):
        raise ValueError('Run must pin the full reviewed suite digest')
    for key in ('model', 'agent_instructions_sha256', 'harness_fingerprint_sha256'):
        if not run.get(key):
            raise ValueError('Record the model, instructions and harness implementation')
    if (not isinstance(run['model'], str)
            or not valid_hash(run['agent_instructions_sha256'])
            or not valid_hash(run['harness_fingerprint_sha256'])):
        raise ValueError('Invalid run provenance')
    rows = run.get('results')
    if not isinstance(rows, list):
        raise ValueError('Results must be a list')
    known = {case['id'] for case in cases}
    results = {}
    for row in rows:
        identity = row.get('case_id')
        if identity not in known or identity in results:
            raise ValueError('Unknown or duplicate case result')
        results[identity] = row
    outcomes = []
    for case in cases:
        row = results.get(case['id'])
        primary = {'state_recreation': 'state_recreation',
                   'human_move_reproduction': 'human_move_agreement'}.get(case['task'])
        scores = {'rule_correctness': None}
        if primary is not None:
            scores[primary] = None
        pending = []
        status = 'missing' if row is None else row.get('status')
        if status not in {'missing', 'timeout', 'completed'}:
            raise ValueError('Result status must be completed, timeout or missing')
        if status != 'completed':
            scores = {name: 0 for name in scores}
        else:
            if case['task'] == 'state_recreation':
                journal = row.get('journal')
                if not isinstance(journal, dict):
                    pending.append('authoritative harness journal missing')
                else:
                    if digest(journal.get('initial_state')) != case['initial_state_sha256']:
                        raise ValueError('Journal starts from a different reviewed position')
                    from harness.engine.actions import replay
                    actual = replay(journal)  # Reject tampered before/after hashes and invalid transitions.
                    if not journal.get('events'):
                        raise ValueError('A declared-play attempt must record its execution')
                    scores[primary] = int(gameplay_state(actual) == gameplay_state(case['expected_state']))
            elif case['task'] == 'human_move_reproduction':
                review = row.get('move_normalization_review')
                move = row.get('normalized_move')
                if not approved(review) or not isinstance(move, dict):
                    pending.append('reviewed semantic move normalization missing')
                elif (review.get('response_sha256') != digest(row.get('response'))
                      or review.get('move_sha256') != digest(move)):
                    raise ValueError('Normalization review is not bound to response and move')
                else:
                    scores[primary] = int(move == case['human_move'])
            legality = row.get('legality_review')
            if not approved(legality):
                pending.append('independent legality review missing')
            elif (legality.get('rules_sha256') != digest(case['rules'])
                  or legality.get('attempt_sha256') != digest({key: value for key, value in row.items()
                                                             if key != 'legality_review'})):
                raise ValueError('Legality review is not bound to this attempt and rules profile')
            elif legality.get('verdict') not in {'valid', 'invalid'} or not legality.get('reason'):
                raise ValueError('Legality review needs a valid/invalid verdict and justification')
            else:
                scores['rule_correctness'] = int(legality['verdict'] == 'valid')
        outcomes.append({'case_id': case['id'], 'format': case['rules']['format'],
                         'status': status, 'scores': scores, 'pending': pending})
    kpis = {}
    for name in KPI_NAMES:
        values = [item['scores'][name] for item in outcomes if name in item['scores']]
        graded = [value for value in values if value is not None]
        kpis[name] = {'total': len(values), 'graded': len(graded),
                      'pending': len(values)-len(graded), 'passed': sum(graded),
                      'score': sum(graded)/len(values) if values and len(graded)==len(values) else None}
    ready = all(kpis[name]['score'] is not None for name in KPI_NAMES)
    final = 100*sum(weights[name]*kpis[name]['score'] for name in KPI_NAMES) if ready else None
    return {'schema_version': '1.0', 'metric': 'agentic_workflow_kpis',
            'suite': suite['id'], 'suite_sha256': digest(suite), 'model': run['model'],
            'weights': weights, 'kpis': kpis, 'final_score_percent': final,
            'formats': dict(Counter(item['format'] for item in outcomes)),
            'outcomes': outcomes,
            'scope': 'reviewed task performance; not win rate or competitive-strength certification'}


def main():
    parser = argparse.ArgumentParser(description='Score reviewed agentic workflow KPIs')
    parser.add_argument('suite', type=Path)
    parser.add_argument('run', type=Path)
    parser.add_argument('--weights', nargs=3, type=float, metavar=('STATE', 'HUMAN', 'RULES'))
    args = parser.parse_args()
    try:
        weights = dict(zip(KPI_NAMES, args.weights)) if args.weights is not None else None
        print(json.dumps(score_kpis(json.loads(read_text(args.suite)),
                                   json.loads(read_text(args.run)), weights), ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
