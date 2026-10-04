"""Local JSON-lines moderator transport. Keep stdin private; no HTTP listener."""
import argparse
import json
import sys
from pathlib import Path
from harness.runner.duel import DuelRunner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--game-dir', type=Path, required=True)
    args = parser.parse_args()
    with DuelRunner(args.state, args.game_dir) as duel:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                operation = request.get('op')
                if operation == 'view':
                    result = duel.context(request.get('player', 'human'))
                elif operation == 'command':
                    result = duel.command(request['request'])
                elif operation == 'record':
                    result = duel.record(request['action'])
                elif operation == 'effect':
                    result = duel.effect(request['name'], request['request'])
                elif operation == 'display':
                    result = {'text': duel.display(request['packet'])}
                elif operation == 'capabilities':
                    result = {'commands': ['draw', 'shuffle'], 'effects': duel.effects.capabilities(),
                              'card_legality': 'moderator-reviewed'}
                else:
                    raise ValueError('Unknown operation')
                response = {'ok': True, 'result': result}
            except (ValueError, KeyError, TypeError, IndexError):
                # Do not echo private request values or exception contents to clients.
                response = {'ok': False, 'error': 'Request rejected; inspect locally with moderator.'}
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
