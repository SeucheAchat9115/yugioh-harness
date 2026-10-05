"""Compact contexts constructed from permitted views, never from omniscient archives."""
from copy import deepcopy
from harness.runner.context import excerpts


def compact(runner, context, card_ids=None, recent_limit=4, guide_budget=1200):
    result = deepcopy(context)
    state = result['state']
    relevant = set()
    def collect(value):
        if isinstance(value, dict):
            if 'card_id' in value:
                relevant.add(str(value['card_id']))
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    for player in state['players'].values():
        for zone in ('hand', 'monster_zones', 'spell_trap_zones', 'graveyard', 'banished', 'field_spell'):
            collect(player.get(zone))
        if state['phase'] != 'sideboard':
            player.pop('side_deck', None)
        # Preserve selectable Extra/Side identities, but avoid their unused effect text.
        for zone in ('extra_deck', 'side_deck'):
            if zone in player:
                player[zone] = [{key: deepcopy(card[key]) for key in
                                 ('instance_id', 'card_id', 'name', 'type', 'level', 'atk', 'def') if key in card}
                                for card in player[zone]]
        player['effect_usage'] = {key: usage for key, usage in player['effect_usage'].items()
                                  if usage.get('turn', state['turn']) == state['turn'] or usage.get('kind') != 'attack'}
    collect(state.get('chain'))
    collect(state.get('pending_effects'))
    if card_ids is not None:
        relevant = {str(identity) for identity in card_ids}
    result['cards'] = {key: card for key, card in result.get('cards', {}).items() if key in relevant}
    result['recent_events'] = result.get('recent_events', [])[-recent_limit:]
    terms = [card['name'].lower() for card in result['cards'].values() if card.get('name')]
    terms.extend([state['phase'], (state.get('pending_decision') or {}).get('window', '')])
    for name, guide in result.get('guides', {}).items():
        content = runner.assets[name]['content']
        excerpt = excerpts(content, terms, guide_budget)
        guide.update(excerpt=excerpt, truncated=len(excerpt) < len(content), sha256=runner.assets[name]['sha256'])
    result.pop('deck_inventory', None)
    result['context_version'] = 'compact-v1'
    result['context_limits'] = {'recent_events': recent_limit, 'guide_chars_per_deck': guide_budget,
                                'card_text': 'visible hands, board, GYs, banished and pending effects; Extra/Side text on explicit focus',
                                'details': 'orchestrator can request full duel_context or focused duel_agent_context before dispatch'}
    return result
