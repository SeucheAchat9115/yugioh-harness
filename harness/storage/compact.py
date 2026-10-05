"""Small deterministic state operations. The LLM still adjudicates game rules."""
from copy import deepcopy
import json


def _registry(state):
    result = {}
    def visit(card):
        if card is None:
            return
        result[card['instance_id']] = card
        for material in card.get('materials', []):
            visit(material)
    for player in state['players'].values():
        for zone in ('hand', 'deck', 'extra_deck', 'side_deck', 'monster_zones', 'spell_trap_zones', 'graveyard', 'banished'):
            for card in player[zone] or []:
                visit(card)
        visit(player['field_spell'])
    for cards in state.get('shared_zones', {}).values():
        for card in cards:
            visit(card)
    return result


def _encode(value, cards):
    if isinstance(value, dict):
        identity = value.get('instance_id')
        if identity in cards:
            original = cards[identity]
            encoded = {'$instance': identity}
            updates = {key: _encode(child, cards) for key, child in value.items() if key not in original or original[key] != child}
            deleted = [key for key in original if key not in value]
            if updates:
                encoded['set'] = updates
            if deleted:
                encoded['remove'] = deleted
            if len(json.dumps(encoded)) < len(json.dumps(value)):
                return encoded
        return {key: _encode(child, cards) for key, child in value.items()}
    if isinstance(value, list):
        return [_encode(child, cards) for child in value]
    return deepcopy(value)


def _decode(value, cards):
    if isinstance(value, dict):
        if '$instance' in value:
            if set(value) - {'$instance', 'set', 'remove'} or value['$instance'] not in cards:
                raise ValueError('Unknown or malformed physical-card reference')
            card = deepcopy(cards[value['$instance']])
            for key in value.get('remove', []):
                del card[key]
            card.update({key: _decode(child, cards) for key, child in value.get('set', {}).items()})
            return card
        return {key: _decode(child, cards) for key, child in value.items()}
    if isinstance(value, list):
        return [_decode(child, cards) for child in value]
    return deepcopy(value)


def _locations(state):
    result = {}
    for actor, player in state['players'].items():
        for zone in ('hand', 'deck', 'extra_deck', 'side_deck', 'monster_zones', 'spell_trap_zones', 'graveyard', 'banished'):
            for index, card in enumerate(player[zone] or []):
                if card is not None:
                    result[card['instance_id']] = ['players', actor, zone, index]
        if player['field_spell']:
            result[player['field_spell']['instance_id']] = ['players', actor, 'field_spell']
    return result


def _parent(state, path):
    parent = state
    for key in path[:-1]:
        parent = parent[key]
    return parent, path[-1]


def _move(state, op, cards):
    from harness.runner.state_tools import locate
    source = locate(state, op['instance'])
    if source != op['from']:
        raise ValueError('Physical move source mismatch')
    parent, key = _parent(state, source)
    card = parent[key]
    fixed_source = source[-1] == 'field_spell' or source[-2] in ('monster_zones', 'spell_trap_zones')
    if fixed_source:
        parent[key] = None
    else:
        parent.pop(key)
    parent, key = _parent(state, op['to'])
    if isinstance(parent[key], list):
        index = op['index']
        if type(index) is not int or not 0 <= index <= len(parent[key]):
            raise ValueError('Move destination index outside list')
        parent[key].insert(index, card)
    elif parent[key] is None:
        parent[key] = card
    else:
        raise ValueError('Move destination occupied')
    for key in op.get('remove', []):
        del card[key]
    card.update({key: _decode(value, cards) for key, value in op.get('attributes', {}).items()})


def operations(before, after):
    cards = _registry(before)
    result = []
    working = deepcopy(before)
    old_locations, new_locations = _locations(before), _locations(after)
    after_cards = _registry(after)
    for identity in sorted(old_locations.keys() & new_locations.keys()):
        old, new = old_locations[identity], new_locations[identity]
        if old[:3] == new[:3]:
            continue  # Remaining list positions can shift without an actual move.
        destination = new if len(new) == 3 or new[2] in ('monster_zones', 'spell_trap_zones') else new[:-1]
        parent, key = _parent(working, destination)
        if parent[key] is not None and not isinstance(parent[key], list):
            continue
        if isinstance(parent[key], list) and new[-1] > len(parent[key]):
            continue
        source = _locations(working)[identity]
        current = _registry(working)[identity]
        final = after_cards[identity]
        op = {'op': 'move', 'instance': identity, 'from': source, 'to': destination}
        if isinstance(parent[key], list):
            op['index'] = new[-1]
        updates = {key: _encode(value, cards) for key, value in final.items() if current.get(key) != value or key not in current}
        deleted = [key for key in current if key not in final]
        if updates:
            op['attributes'] = updates
        if deleted:
            op['remove'] = deleted
        _move(working, op, cards)
        result.append(op)
    def walk(old, new, path):
        if old == new:
            return
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(old.keys() - new.keys()):
                result.append({'op': 'delete', 'path': path + [key]})
            for key, value in new.items():
                if key not in old:
                    result.append({'op': 'set', 'path': path + [key], 'value': _encode(value, cards)})
                else:
                    walk(old[key], value, path + [key])
        elif isinstance(old, list) and isinstance(new, list):
            start = 0
            while start < min(len(old), len(new)) and old[start] == new[start]:
                start += 1
            end = 0
            while end < min(len(old), len(new)) - start and old[len(old)-1-end] == new[len(new)-1-end]:
                end += 1
            deleted = len(old) - start - end
            inserted = new[start:len(new)-end if end else len(new)]
            # Fixed field slots / unchanged card identity: update only changed attributes.
            if len(old) == len(new) and (path[-1] in ('monster_zones', 'spell_trap_zones')
                    or all(isinstance(a, dict) and isinstance(b, dict) and a.get('instance_id') == b.get('instance_id')
                           for a, b in zip(old, new))):
                for index, (a, b) in enumerate(zip(old, new)):
                    walk(a, b, path + [index])
            else:
                result.append({'op': 'splice', 'path': path, 'index': start, 'delete': deleted,
                               'values': _encode(inserted, cards)})
        elif type(old) is int and type(new) is int:
            result.append({'op': 'lp' if path[-1] == 'lp' else 'delta', 'path': path, 'delta': new-old})
        else:
            result.append({'op': 'reveal' if path[-1] == 'hidden' and new is False else 'set',
                           'path': path, 'value': _encode(new, cards)})
    for key in after:
        if key != 'revision':
            walk(working[key], after[key], [key])
    return result


def execute(before, ops):
    state = deepcopy(before)
    cards = _registry(before)
    for op in ops:
        if op.get('op') == 'move':
            if not isinstance(op.get('to'), list) or len(op['to']) not in (3, 4) or op['to'][:1] != ['players'] or op['to'][1] not in ('human', 'agent') or op['to'][2] not in ('hand', 'deck', 'extra_deck', 'side_deck', 'monster_zones', 'spell_trap_zones', 'graveyard', 'banished', 'field_spell'):
                raise ValueError('Invalid physical move destination')
            _move(state, op, cards)
            continue
        path = op['path']
        if not isinstance(path, list) or not path or path[0] in ('revision', 'game_id', 'mode', 'presentation', 'player_isolation'):
            raise ValueError('Invalid compact operation path')
        parent = state
        for key in path[:-1]:
            parent = parent[key]
        key = path[-1]
        if isinstance(parent, list) and (type(key) is not int or key < 0 or key >= len(parent)):
            raise ValueError('Invalid compact list index')
        kind = op['op']
        if kind in ('set', 'reveal'):
            parent[key] = _decode(op['value'], cards)
        elif kind in ('delta', 'lp'):
            if type(parent[key]) is not int or type(op['delta']) is not int:
                raise ValueError('Invalid numeric operation')
            parent[key] += op['delta']
        elif kind == 'delete':
            if not isinstance(parent, dict):
                raise ValueError('Delete applies to dictionary fields')
            del parent[key]
        elif kind == 'splice':
            target = parent[key]
            index, count = op['index'], op['delete']
            if (not isinstance(target, list) or type(index) is not int or type(count) is not int
                    or index < 0 or count < 0 or index+count > len(target)):
                raise ValueError('Invalid splice range')
            target[index:index+count] = _decode(op['values'], cards)
        else:
            raise ValueError('Unknown compact operation')
    return state
