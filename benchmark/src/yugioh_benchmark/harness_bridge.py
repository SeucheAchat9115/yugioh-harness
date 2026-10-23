"""Optional bridge to the harness's existing filtered player interface.

A reviewer reconstructs a position first. No automatic conversion of simulator
operations into moderator-approved harness actions is performed.
"""
from copy import deepcopy
from time import perf_counter


def prepare_case(runner, *, case_id, source, sequence, actor, review, grading):
    if actor not in {'human', 'agent'}:
        raise ValueError('Select a harness player, not the moderator')
    if review.get('status') != 'approved' or not review.get('reviewer'):
        raise ValueError('A reviewed decision position is required')
    if type(sequence) is not int or sequence < 1:
        raise ValueError('Sequence must identify a source decision boundary')
    from harness.players.isolated import model_request
    context = runner.context(actor, compact=True)
    if (context.get('perspective') != actor or
            not isinstance(context.get('decision'), dict) or
            context['decision'].get('actor') != actor):
        raise ValueError('The position must be awaiting this player decision')
    model_request(context)  # Reject omniscient/invalid contexts before storing.
    return {'schema_version':'1.0', 'id':case_id,
            'source':{'replay':source, 'before_sequence':sequence},
            'review':deepcopy(review), 'player_context':deepcopy(context),
            'grading':deepcopy(grading)}


def run_case(case, transport):
    """Run one decision; the transport must enforce its own request deadline."""
    if case['review'].get('status') != 'approved':
        raise ValueError('Unreviewed cases cannot be scored')
    from harness.players.isolated import ContextOnlyPlayer
    started = perf_counter()
    result = ContextOnlyPlayer(transport).choose(deepcopy(case['player_context']))
    return {'case_id':case['id'], 'response':result['response'],
            'latency_seconds':perf_counter()-started,
            'assessment':None}  # Reviewer/rubric scoring is a separate step.
