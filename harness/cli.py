"""Installable maintainer commands; the orchestrator runs them during play."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=version('yugioh-harness'))
    commands = parser.add_subparsers(dest='command', required=True)
    doctor = commands.add_parser('doctor', help='Check runtime, resources and host declaration')
    doctor.add_argument('--repo', type=Path, default=Path.cwd())
    doctor.add_argument('--private-root', type=Path)
    doctor.add_argument('--host-file', type=Path)
    doctor.add_argument('--require-host', action='store_true')
    config = commands.add_parser('host-config', help='Generate stdio MCP configuration')
    config.add_argument('--repo', type=Path, required=True)
    config.add_argument('--host', choices=('codex', 'claude', 'gemini'), required=True)
    commands.add_parser('mcp', help='Start moderator MCP lobby', add_help=False)
    # Forward MCP flags untouched; legacy python -m harness.integration.mcp remains.
    if len(sys.argv) > 1 and sys.argv[1] == 'mcp':
        from harness.integration.mcp import main as mcp_main
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        mcp_main()
        return
    args = parser.parse_args()
    if args.command == 'doctor':
        from harness.preflight import inspect
        try:
            host = json.loads(args.host_file.read_text(encoding="utf-8")) if args.host_file else None
            result = inspect(args.repo, args.private_root, host)
        except (OSError, ValueError):
            parser.error('Cannot read host declaration JSON')
        print(json.dumps(result, indent=2))
        if not result['runtime_ready'] or (args.host_file is not None and not result['host_ready']) or (args.require_host and not result['ready']):
            raise SystemExit(1)
    else:
        executable = str(Path(sys.executable).absolute())
        argv = ['-m', 'harness.integration.mcp', '--repo', str(args.repo.resolve())]
        if args.host == 'codex':
            print('[mcp_servers.yugioh]\ncommand = ' + json.dumps(executable) + '\nargs = ' + json.dumps(argv))
        else:
            entry = {'command': executable, 'args': argv}
            if args.host == 'claude':
                entry['type'] = 'stdio'
            print(json.dumps({'mcpServers': {'yugioh': entry}}, indent=2))


if __name__ == '__main__':
    main()
