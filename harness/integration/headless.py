"""JSON-lines host transport; the same workflow as MCP, with no GUI dependency."""
import argparse
import json
from pathlib import Path
import sys

from harness.environment import DuelEnvironment, PROTOCOL
from harness.integration.stdio import configure_utf8


def respond(environment, line):
    try:
        return environment.request(json.loads(line))
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        return {'protocol': PROTOCOL, 'id': None, 'ok': False,
                'error': {'code': 'invalid_request', 'message': 'Invalid JSON request or unavailable storage.'}}


def main():
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--game-id', help='Resume this saved session before processing requests')
    parser.add_argument('--host-file', type=Path, help='Observed host capabilities; never assumed by the CLI')
    parser.add_argument('--request-file', type=Path, help='Process one envelope and exit; omit for JSON lines on stdin')
    args = parser.parse_args()
    try:
        with DuelEnvironment(args.repo, args.private_root) as environment:
            def bootstrap(request):
                result = environment.request({'protocol': PROTOCOL, 'id': 'bootstrap', 'request': request})
                if not result['ok'] or (request['op'] == 'preflight' and not result['result']['ready']):
                    parser.exit(1, 'Cannot initialize headless session; check host readiness and session locator.\n')
            if args.host_file:
                bootstrap({'op': 'preflight', 'host_capabilities': json.loads(args.host_file.read_text(encoding='utf-8'))})
            if args.game_id:
                bootstrap({'op': 'resume', 'game_id': args.game_id})
            if args.request_file:
                result = respond(environment, args.request_file.read_text(encoding='utf-8'))
                print(json.dumps(result, ensure_ascii=False), flush=True)
                return 0 if result['ok'] else 1
            for line in sys.stdin:
                print(json.dumps(respond(environment, line), ensure_ascii=False), flush=True)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'Cannot open headless session resources.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
