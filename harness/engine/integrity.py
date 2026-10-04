"""Structural card accounting, independent of LLM rule adjudication."""
ZONES = ('hand', 'deck', 'extra_deck', 'side_deck', 'monster_zones',
         'spell_trap_zones', 'graveyard', 'banished')
HIDDEN = ('hand', 'deck', 'extra_deck', 'side_deck')


def inventory(state):
    cards = {}
    def visit(card, holder):
        if card is None:
            return
        if not isinstance(card, dict) or not isinstance(card.get('instance_id'), str) or not card['instance_id']:
            raise ValueError('Every located card needs a physical instance ID')
        identity = card['instance_id']
        if identity in cards:
            raise ValueError('A physical card cannot occupy two locations')
        if 'token' in card and type(card['token']) is not bool:
            raise ValueError('Token flag must be boolean')
        if 'card_id' in card and (type(card['card_id']) is not int or card['card_id'] <= 0):
            raise ValueError('Invalid card ID')
        owner = card.get('owner', holder)
        if owner not in ('human', 'agent'):
            raise ValueError('Invalid card owner')
        cards[identity] = (card.get('card_id'), owner, card.get('token') is True)
        materials = card.get('materials', [])
        if not isinstance(materials, list):
            raise ValueError('Materials must be a list of located cards')
        for material in materials:
            visit(material, owner)
    for actor, player in state['players'].items():
        for zone in ZONES:
            entries = player[zone]
            if entries is None and state['mode'] == 'blind' and actor == 'human' and zone in HIDDEN:
                continue
            if not isinstance(entries, list):
                raise ValueError('Card zones must be lists')
            for card in entries:
                if card is None and zone not in ('monster_zones', 'spell_trap_zones'):
                    raise ValueError('Only field zones allow empty slots')
                visit(card, actor)
        visit(player['field_spell'], actor)
    for entries in state.get('shared_zones', {}).values():
        if not isinstance(entries, list):
            raise ValueError('Shared zones must be lists')
        for card in entries:
            if card is not None and 'owner' not in card:
                raise ValueError('Shared-zone cards need an owner')
            visit(card, card.get('owner') if card else None)
    return cards


def validate_transition(before, after):
    old, new = inventory(before), inventory(after)
    for actor in ('human', 'agent'):
        for zone in ('monster_zones', 'spell_trap_zones'):
            if len(before['players'][actor][zone]) != len(after['players'][actor][zone]):
                raise ValueError('Field zone layout cannot change during play')
    if before.get('shared_zones', {}).keys() != after.get('shared_zones', {}).keys():
        raise ValueError('Shared zone layout cannot change during play')
    for zone, entries in before.get('shared_zones', {}).items():
        if len(entries) != len(after['shared_zones'][zone]):
            raise ValueError('Shared zone layout cannot change during play')
    for identity in old.keys() & new.keys():
        # Blind revealed identities can gain a card ID; managed identities cannot change.
        if old[identity][0] != new[identity][0] and not (before['mode']=='blind' and old[identity][1]=='human' and old[identity][0] is None):
            raise ValueError('Physical card identity cannot change')
        if old[identity][1] != new[identity][1]:
            raise ValueError('Physical owner cannot change; record controller separately')
        if old[identity][2] != new[identity][2]:
            raise ValueError('Existing cards cannot become tokens')
    def managed(cards):
        return {key for key, (_, owner, token) in cards.items()
                if not token and not (before['mode']=='blind' and owner=='human')}
    if managed(old) != managed(new):
        raise ValueError('Managed physical cards must be conserved across zones')
