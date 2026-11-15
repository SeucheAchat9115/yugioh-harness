"""Build a read-only Sites display from the interaction view."""


def _card(card, cards, reveal=False):
    if card is None:
        return None
    if card.get('hidden') and not reveal:
        return {'hidden': True, 'position': card.get('position')}
    details = cards.get(str(card.get('card_id')), {})
    result = {
        'name': card.get('current_name') or card.get('name') or details.get('name') or 'Card',
        'type': card.get('type') or details.get('type'),
        'text': details.get('desc'),
        'atk': card.get('atk'),
        'def': card.get('def'),
        'level': card.get('level'),
        'position': card.get('position'),
        'hidden': bool(card.get('hidden')),
    }
    card_id = card.get('card_id')
    if type(card_id) is int and 0 < card_id <= 999999999:
        result['image_id'] = card_id
    return result


# A cost label describes a recorded operation without exposing card identities.
PUBLIC_COSTS = {'discard', 'banish', 'tribute', 'detach', 'pay-lp', 'send-to-graveyard',
                'return-to-hand', 'return-to-deck', 'destroy', 'reveal', 'shuffle'}


def _chain_cards(state, active_state):
    players = state['players']
    public_zones = ('monster_zones', 'spell_trap_zones', 'graveyard', 'banished')
    public_cards = [card for player in players.values() for zone in public_zones for card in player[zone]]
    public_cards.extend(player['field_spell'] for player in players.values())
    public_cards.extend(card for cards in state.get('shared_zones', {}).values() for card in cards)
    by_instance = {card['instance_id']: card for card in public_cards
                   if card and 'instance_id' in card and not card.get('hidden')}

    links = []
    for link, active in zip(state['chain'], active_state['chain']):
        actor = link.get('actor')
        name = link.get('name')
        catalog = active_state['players'].get(actor, {}).get('cards', {})
        source = by_instance.get(active['card']) if isinstance(active.get('card'), str) else None
        if source is None and isinstance(name, str) and name:
            # Legacy moderator records carry the public activation name rather than a card reference.
            source = next(({'card_id': int(key), 'name': name}
                           for key, card in catalog.items() if card['name'].casefold() == name.casefold()), None)
        display = _card(source or {'name': name or 'Card effect'}, catalog)
        costs = link.get('costs') or []
        kinds = [(cost['kind'].strip().lower().replace('_', '-').replace(' ', '-'))
                 for cost in costs if isinstance(cost, dict) and isinstance(cost.get('kind'), str)]
        links.append({
            'actor': actor, 'name': display['name'], 'card': display, 'effect': link.get('effect'),
            'action': 'resolve' if active.get('resolution_started') is True else 'activate',
            'costs': list(dict.fromkeys(kind for kind in kinds if kind in PUBLIC_COSTS)),
        })
    return links


def board_snapshot(interaction, active_state):
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
            'graveyard': [_card(card, cards, reveal) for card in player['graveyard']],
            'banished': [_card(card, cards, reveal) for card in player['banished']],
        }
        if reveal:
            players[actor]['hand'] = [_card(card, cards, reveal) for card in player['hand']]
            players[actor]['extra_deck'] = [_card(card, cards, reveal) for card in player['extra_deck']]
    shared = []
    for card in state.get('shared_zones', {}).get('extra_monster_zones', []):
        shared.append(None if card is None else {
            'owner': card['owner'],
            'card': _card(card, cards, card['owner'] == 'human' and show_hand),
        })
    events = context['recent_events']
    options = {}
    decision = interaction.get('decision')
    if interaction['perspective'] == 'human' and interaction.get('awaiting_input') and decision:
        options['options'] = {
            'question': decision['question'],
            'recommendations': [
                {key: move[key] for key in ('label', 'reason')}
                for move in decision['recommendations']
            ],
        }
    return {
        'schema': 'duel-board-v1',
        **{key: state[key] for key in ('game_id', 'mode', 'status', 'turn', 'active_player', 'phase', 'revision')},
        'players': players,
        'extra_monsters': shared,
        'chain': _chain_cards(state, active_state),
        **options,
        'last_action': events[-1]['summary'] if events else None,
    }
