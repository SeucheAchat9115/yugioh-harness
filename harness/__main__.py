"""Local JSON-lines moderator transport. Keep stdin private; no HTTP listener."""
import argparse
import json
import sys
from pathlib import Path
from harness.runner.duel import DuelRunner, RecoveryRequired


class InvalidRequest(ValueError):
    pass


def dispatch(duel, request):
    if not isinstance(request, dict) or not isinstance(request.get('op'), str):
        raise InvalidRequest('Request must be an object with an operation')
    operation = request['op']
    required = {'command': 'request', 'record': 'action', 'effect': 'request', 'display': 'packet', 'present': 'packet', 'step': 'request'}
    if operation in required and not isinstance(request.get(required[operation]), dict):
        raise InvalidRequest('Operation payload must be an object')
    if operation == 'view':
        if request.get('player', 'human') not in ('human', 'agent', 'moderator'):
            raise InvalidRequest('Invalid player')
        return duel.context(request.get('player', 'human'), request.get('card_ids'))
    if operation == 'command':
        return duel.command(request['request'])
    if operation == 'record':
        return duel.record(request['action'])
    if operation == 'effect':
        if not isinstance(request.get('name'), str):
            raise InvalidRequest('Effect name required')
        return duel.effect(request['name'], request['request'])
    if operation == 'display':
        return {'text': duel.display(request['packet'])}
    if operation == 'present':
        return duel.workflow.present(request['packet'])
    if operation == 'submit':
        return duel.workflow.submit(request['decision_id'],request['request_id'],request['response'],request.get('player','human'))
    if operation == 'step':
        return duel.workflow.execute(request['request_id'],request['request'],request.get('submission_id'))
    if operation == 'status':
        return duel.workflow.status()
    if operation == 'recover':
        return duel.recover()
    if operation == 'capabilities':
        return {'commands': ['draw', 'shuffle'], 'effects': duel.effects.capabilities(),
                'card_legality': 'moderator-reviewed'}
    raise InvalidRequest('Unknown operation')


def respond(duel, line):
    try:
        return {'ok': True, 'result': dispatch(duel, json.loads(line))}
    except (json.JSONDecodeError, InvalidRequest):
        return {'ok': False, 'error': {'code': 'invalid_request', 'message': 'Invalid request shape or operation.'}}
    except RecoveryRequired as error:
        return {'ok': False, 'error': {'code': 'recovery_required',
                'message': 'Use recover before continuing; do not resubmit a recorded action.',
                'action_status': error.action_status}}
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        # Never echo private payloads, rule text, or exception contents.
        return {'ok': False, 'error': {'code': 'action_rejected', 'message': 'Action rejected by harness validation.'}}
    except OSError:
        return {'ok': False, 'error': {'code': 'storage_error', 'message': 'Local storage unavailable.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--game-dir', type=Path, required=True)
    args = parser.parse_args()
    with DuelRunner(args.state, args.game_dir) as duel:
        for line in sys.stdin:
            print(json.dumps(respond(duel, line), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
