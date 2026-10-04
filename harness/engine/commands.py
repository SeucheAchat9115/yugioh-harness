"""Deterministic primitives. Legality is reviewed by the moderator."""
from copy import deepcopy
import secrets
from uuid import uuid4
from harness.engine.session import draw


def prepare(state, request):
    if request.get('moderator_approved') is not True:
        raise ValueError('Commands require moderator legality approval')
    if type(request.get('expected_revision')) is not int or request['expected_revision'] != state['revision']:
        raise ValueError('Stale command')
    if state['status'] != 'active':
        raise ValueError('Game is not active')
    if state.get('pending_decision') is not None or state['chain']:
        raise ValueError('Pending decisions/chains require a moderated action or effect handler')
    actor = request.get('actor')
    if actor not in ('human', 'agent'):
        raise ValueError('Unknown player')
    name = request.get('command')
    updated = deepcopy(state)
    if name == 'draw':
        count = request.get('count', 1)
        draw(updated, actor, count)
        summary = f'{actor} drew {count} card(s); identities private.'
    elif name == 'shuffle':
        deck = updated['players'][actor]['deck']
        if deck is None:
            raise ValueError('Blind human shuffles are human-managed')
        secrets.SystemRandom().shuffle(deck)
        summary = f'{actor} shuffled their Deck.'
    else:
        raise ValueError('Unsupported command; moderator/effect handler required')
    changes = [{'path': ['players', actor, key], 'before': value,
                'after': updated['players'][actor][key]}
               for key, value in state['players'][actor].items()
               if value != updated['players'][actor][key]]
    return {'id': request.get('id', uuid4().hex), 'kind': name, 'actor': actor,
            'expected_revision': state['revision'], 'moderator_approved': True,
            'public_summary_reviewed': True, 'public_summary': summary, 'changes': changes}
