"""Build stateless, tool-free model requests from already permitted player context.

The trusted transport sends this request to a model API; it must not append parent
messages, filesystem content, or tools. Native agents need host sandboxing instead.
"""
from copy import deepcopy
from harness.modes import shared_human_information
import json
from harness.runner.orchestrator import PLAYER_POLICY


def model_request(context):
    allowed = {'perspective', 'state', 'capabilities', 'decision', 'prompt',
               'recent_events', 'cards', 'rules', 'guides'}
    if not isinstance(context, dict) or set(context) - allowed or context.get('perspective') not in ('human', 'agent'):
        raise ValueError('Only a permitted player context may enter the model request')
    actor = context['perspective']
    state = context['state']
    for owner, player in state['players'].items():
        if any(key in player for key in ('deck', 'cards', 'remaining_deck_order')):
            raise ValueError('Authoritative card catalogs/orders are forbidden')
        open_human = shared_human_information(state['mode']) and actor == 'agent' and owner == 'human'
        if owner != actor and not open_human and any(key in player for key in ('hand', 'extra_deck', 'side_deck')):
            raise ValueError('Opponent hidden zones are forbidden')
    if any(not name.startswith('decks/' + actor + '/') for name in context.get('guides', {})):
        raise ValueError('Opponent guides are forbidden')
    return {'messages': [{'role': 'system', 'content': PLAYER_POLICY},
                         {'role': 'user', 'content': json.dumps(deepcopy(context), ensure_ascii=False)}],
            'tools': [], 'tool_choice': 'none'}


class ContextOnlyPlayer:
    def __init__(self, transport):
        self.transport = transport

    def choose(self, context):
        # Treat output as data only: no tool calls or code are ever executed here.
        result = self.transport(model_request(context))
        if not isinstance(result, dict) or set(result) != {'response'}:
            raise ValueError('Expected one response field from the model transport')
        response = result['response']
        if (type(response) not in (str, int) or (isinstance(response, str) and
                (not response.strip() or len(response) > 8192))):
            raise ValueError('Invalid player response')
        return {'response': response}
