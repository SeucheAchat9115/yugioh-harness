"""Build a read-only Sites snapshot from the existing interaction view."""


def _card(card, cards, reveal=False):
    if card is None:
        return None
    if card.get('hidden') and not reveal:
        return {'hidden': True, 'position': card.get('position')}
    details = cards.get(str(card.get('card_id')), {})
    return {
        'name': card.get('current_name') or card.get('name') or details.get('name') or 'Card',
        'type': card.get('type') or details.get('type'),
        'text': details.get('desc'),
        'atk': card.get('atk'),
        'def': card.get('def'),
        'level': card.get('level'),
        'position': card.get('position'),
        'hidden': bool(card.get('hidden')),
    }


def board_snapshot(interaction):
    context = interaction['context']
    state = context['state']
    cards = context['cards']
    show_hand = interaction['perspective'] == 'human' and state['mode'] == 'managed'
    players = {}
    for actor in ('human', 'agent'):
        player = state['players'][actor]
        reveal = actor == 'human' and show_hand
        players[actor] = {
            **{key: player[key] for key in ('lp', 'hand_count', 'deck_count', 'extra_count')},
            'graveyard_count': len(player['graveyard']),
            'banished_count': len(player['banished']),
            'monsters': [_card(card, cards, reveal) for card in player['monster_zones']],
            'backrow': [_card(card, cards, reveal) for card in player['spell_trap_zones']],
            'field': _card(player['field_spell'], cards, reveal),
        }
        if reveal:
            players[actor]['hand'] = [_card(card, cards, reveal) for card in player['hand']]
    shared = []
    for card in state.get('shared_zones', {}).get('extra_monster_zones', []):
        shared.append(None if card is None else {
            'owner': card['owner'],
            'card': _card(card, cards, card['owner'] == 'human' and show_hand),
        })
    events = context['recent_events']
    return {
        'schema': 'duel-board-v1',
        **{key: state[key] for key in ('game_id', 'mode', 'status', 'turn', 'active_player', 'phase', 'revision')},
        'players': players,
        'extra_monsters': shared,
        'chain': [{'actor': link.get('actor'), 'name': link.get('name')} for link in state['chain']],
        'last_action': events[-1]['summary'] if events else None,
    }
