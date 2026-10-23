"""Versioned host API over the existing sole-writer orchestrator workflow.

This is a trusted moderator API, not an unauthenticated player endpoint. Models
receive only filtered tasks. A GUI receives interaction(), never raw next tasks.
"""
from copy import deepcopy

from harness.integration.mcp import CONVERSATIONAL_TOOLS, TOOLS
from harness.integration.service import DuelService
from harness.runner.duel import RecoveryRequired

PROTOCOL = 'duel-v1'


def operations():
    """Reuse MCP's operation schemas so transports cannot acquire different rules."""
    result = {}
    for _, (description, properties, required, operation) in {**TOOLS, **CONVERSATIONAL_TOOLS}.items():
        result.setdefault(operation, {'description': description, 'properties': deepcopy(properties),
                                      'required': list(required)})
    result['view']['properties']['compact'] = {'type': 'boolean'}
    result['describe'] = {'description': 'Discover the versioned host contract.', 'properties': {}, 'required': []}
    result['interaction'] = {'description': 'Filtered human/spectator data for chat or a future GUI.',
                             'properties': {}, 'required': []}
    return result


def valid_type(value, expected):
    types = {'object': dict, 'array': list, 'string': str, 'integer': int,
             'boolean': bool, 'null': type(None)}
    return any(type(value) is types[item] for item in
               (expected if isinstance(expected, list) else [expected]))


class DuelEnvironment:
    """Own one session writer; the host supplies LLM adjudication and pilot calls."""

    def __init__(self, repo, private_root=None):
        self.service = DuelService(repo, private_root, require_host=True)

    def close(self):
        self.service.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def interaction(self):
        """Display data only: no moderator state, opponent menus or task envelopes."""
        runner = self.service.runner
        if runner is None:
            raise ValueError('Start or resume first')
        runner._fresh()
        spectator = runner.state['mode'] == 'agent-vs-agent'
        perspective = 'public' if spectator else 'human'
        context = runner.context(perspective, compact=True)
        pending = runner.state.get('pending_decision') or {}
        packet = runner.packet or {}
        own_decision = (not spectator and pending.get('actor') == 'human'
                        and packet.get('expected_revision') == runner.state['revision']
                        and packet.get('awaiting_user', True))
        decision = None
        context.pop('prompt', None)
        if own_decision:
            decision = {key: deepcopy(packet[key]) for key in
                        ('decision_id', 'question') if key in packet}
            decision['recommendations'] = [
                {key: deepcopy(move[key]) for key in ('label', 'reason') if key in move}
                for move in packet.get('recommendations', [])]
            decision.update(actor='human', window=pending.get('window'), action_mode='open-intention')
        answered = any(row['decision_id'] == packet.get('decision_id')
                       for row in runner.workflow.data['submissions'].values())
        return {'perspective': perspective, 'context': context, 'decision': decision,
                'awaiting_input': bool(own_decision and not answered and runner.state['status'] == 'active')}

    def request(self, envelope):
        identity = envelope.get('id') if isinstance(envelope, dict) else None
        if type(identity) not in (str, int):
            identity = None
        response = {'protocol': PROTOCOL, 'id': identity}
        error = {'ok': False, 'error': {'code': 'invalid_request',
                 'message': 'Use duel-v1, an id, and a supported request object.'}}
        if (not isinstance(envelope, dict) or set(envelope) != {'protocol', 'id', 'request'}
                or envelope['protocol'] != PROTOCOL or identity is None
                or not isinstance(envelope['request'], dict)):
            return {**response, **error}
        request = envelope['request']
        if request == {'op': 'describe'}:
            return {**response, 'ok': True, 'result': {
                'protocol': PROTOCOL, 'authority': 'trusted-moderator',
                'action_mode': 'open-intention', 'operations': operations(),
                'task_kinds': ['human', 'subagent', 'moderator', 'subagent_wait',
                               'subagent_failure', 'paused', 'finished'],
                'adjudication': 'host-agent', 'gui_projection': 'interaction',
                'randomness': 'recorded outcomes; seed alone cannot reproduce LLM decisions'}}
        definition = operations().get(request.get('op')) if isinstance(request.get('op'), str) else None
        if definition is None:
            return {**response, **error}
        properties = definition['properties']
        if (set(request) - {'op', *properties}
                or any(key not in request for key in definition['required'])):
            return {**response, **error}
        for key, value in request.items():
            if key == 'op':
                continue
            rule = properties[key]
            if not valid_type(value, rule['type']) or ('enum' in rule and value not in rule['enum']):
                return {**response, **error}
            if type(value) is int and not rule.get('minimum', value) <= value <= rule.get('maximum', value):
                return {**response, **error}
        if request['op'] == 'interaction':
            try:
                return {**response, 'ok': True, 'result': self.interaction()}
            except RecoveryRequired as exc:
                return {**response, 'ok': False, 'error': {'code': 'recovery_required',
                        'action_status': exc.action_status}}
            except (ValueError, KeyError, TypeError, AttributeError, OSError):
                return {**response, **error}
        return {**response, **self.service.request(deepcopy(request))}
