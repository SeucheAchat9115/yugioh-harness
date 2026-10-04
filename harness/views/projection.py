"""Allowlisted public fields. Free text in these fields needs moderator review."""
from copy import deepcopy

CARD_FIELDS = ('instance_id', 'owner', 'card_id', 'name', 'position', 'hidden',
               'current_name', 'atk', 'def', 'level', 'attribute', 'type', 'race',
               'scale', 'linkval', 'linkmarkers', 'token', 'properly_summoned',
               'summon_type', 'summoned_turn', 'controller')
CHAIN_FIELDS = ('id', 'actor', 'name', 'effect', 'costs', 'targets',
                'effect_negated', 'activation_negated', 'resolution_started', 'resolution_step')
EFFECT_FIELDS = ('id', 'kind', 'actor', 'owner', 'source', 'source_instance_id',
                'name', 'effect', 'condition', 'expires', 'turn', 'phase', 'window',
                'targets', 'costs', 'resolved', 'used', 'count', 'names', 'effect_negated',
                'summon_event_id', 'cooldown_until_turn')
REF_FIELDS = ('instance_id', 'card_id', 'actor', 'owner', 'zone', 'index', 'count', 'kind')


def references(value):
    if isinstance(value, list):
        return [references(item) for item in value]
    if isinstance(value, dict):
        return {key: deepcopy(value[key]) for key in REF_FIELDS if key in value}
    return deepcopy(value)


def project(value, fields):
    result = {key: deepcopy(value[key]) for key in fields if key in value and key not in ('targets', 'costs')}
    for key in ('targets', 'costs'):
        if key in value:
            result[key] = references(value[key])
    return result


def chain_view(chain):
    return [project(link, CHAIN_FIELDS) for link in chain]


def effect_view(effects, viewer, mode):
    result = []
    for effect in effects:
        if effect.get('visibility', 'public') == 'private':
            owner = effect.get('owner', effect.get('actor'))
            if not (viewer == owner or viewer == 'moderator' or
                    (mode == 'open' and owner == 'human' and viewer == 'agent')):
                continue
        result.append(project(effect, EFFECT_FIELDS))
    return result
