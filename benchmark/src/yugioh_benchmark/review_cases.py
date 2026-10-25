"""Load approved fixed-checkpoint fixtures; never dispatch pending review packets."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .inputs import read_text
from .kpis import digest, validate_suite


def _read(folder, relative):
    path=(folder/relative).resolve()
    if not path.is_relative_to(folder):
        raise ValueError('Review asset must remain inside its dataset')
    return json.loads(read_text(path))


def load_reviewed_case(folder, case_id):
    """Return a bridge case and evaluator checkpoint to the trusted caller.

    Only bridge['player_context'] goes to the isolated player. The checkpoint
    and grading material are private evaluator inputs, not player context.
    """
    folder=Path(folder).resolve()
    suite=_read(folder,'suite.json')
    cases=validate_suite(suite)
    matches=[case for case in cases if case['id']==case_id]
    if len(matches)!=1: raise ValueError('Select an approved suite case ID')
    case=matches[0]
    index=_read(folder,'review-index.json')
    entries=[row for row in index if case_id in {row['id']+'-state',row['id']+'-choice'}]
    if len(entries)!=1 or entries[0]['status']!='approved_scoped':
        raise ValueError('The boundary is not approved for this scoped suite')
    entry=entries[0]
    packet=_read(folder,case['player_packet'])
    if packet.get('runnable') is not True or packet.get('id')!=entry['id']:
        raise ValueError('Unreviewed or mismatched player packet')
    evaluator=_read(folder,'evaluator.json')[entry['id']]
    if digest(evaluator['initial_state'])!=case['initial_state_sha256']:
        raise ValueError('Reviewed checkpoint differs from its suite digest')
    assets=case['rules'].get('assets', {})
    rules=_read(folder,assets.get('rules','assets/rules-snapshot.json'))
    cards=_read(folder,assets.get('cards','assets/card-texts.json'))
    banlist_path=(folder/assets.get('banlist','assets/perfect-circle-2007-09-01.json')).resolve()
    if not banlist_path.is_relative_to(folder):
        raise ValueError('Review asset must remain inside its dataset')
    banlist=banlist_path.read_bytes()
    if (digest(rules)!=case['rules']['rules_sha256'] or digest(cards)!=case['rules']['card_text_sha256']
            or hashlib.sha256(banlist).hexdigest()!=case['rules']['banlist_sha256']):
        raise ValueError('Pinned rules/card assets changed')
    from harness.engine.actions import validate_state
    from harness.players.isolated import model_request
    validate_state(evaluator['initial_state'])
    context=deepcopy(packet['player_context'])
    if digest(context)!=case['player_context_sha256']:
        raise ValueError('Player context differs from its reviewed digest')
    model_request(context)
    if context.get('decision',{}).get('actor')!='agent':
        raise ValueError('Checkpoint must await the evaluated player')
    if suite.get('evaluation_protocol') == 'harness-objectives-v1':
        from .harness_replay import player_context
        state=evaluator['initial_state']
        if state.get('player_isolation')!='enforced' or state['mode']!='managed':
            raise ValueError('Objective checkpoints require a private stateless player boundary')
        if any(cards.get(key)!=value for owner in state['players'].values()
               for key,value in owner['cards'].items()):
            raise ValueError('Checkpoint catalog differs from the pinned card assets')
        if context != player_context(state, rules, case['public_facts']):
            raise ValueError('Player packet differs from the live runtime privacy projection')
    bridge={'schema_version':'1.0','id':case_id,'source':deepcopy(case['source']),
            'review':deepcopy(case['review']),'player_context':context,
            'grading':deepcopy(evaluator)}
    return bridge,deepcopy(evaluator['initial_state'])
