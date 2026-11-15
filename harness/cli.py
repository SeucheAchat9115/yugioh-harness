"""Installable maintainer commands; the orchestrator runs them during play."""
import argparse
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import sys


def main():
    from harness.integration.stdio import configure_utf8
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    try:
        release = version('yugioh-harness')
    except PackageNotFoundError:
        release = 'source-checkout'
    parser.add_argument('--version', action='version', version=release)
    commands = parser.add_subparsers(dest='command', required=True)
    doctor = commands.add_parser('doctor', help='Check runtime, resources and host declaration')
    doctor.add_argument('--repo', type=Path, default=Path.cwd())
    doctor.add_argument('--private-root', type=Path)
    doctor.add_argument('--host-file', type=Path)
    doctor.add_argument('--require-host', action='store_true')
    config = commands.add_parser('host-config', help='Generate stdio MCP configuration')
    config.add_argument('--repo', type=Path, required=True)
    config.add_argument('--host', choices=('codex', 'claude', 'gemini'), required=True)
    guide = commands.add_parser('deck-guide-pdf', help='Export a compact A4 deck guide')
    guide.add_argument('deck', help='Folder containing deck.json, deck.ydk and guide.md')
    guide.add_argument('--repo', type=Path, default=Path.cwd())
    guide.add_argument('-o', '--output', type=Path, required=True)
    guide.add_argument('--language', choices=('en', 'de'), default='en', help='Language of the printable playbook')
    guide.add_argument('--art-cache', type=Path, help='Folder of cached YGOPRODeck <card-id>.jpg files')
    commands.add_parser('duel', help='Run the versioned headless duel API', add_help=False)
    commands.add_parser('mcp', help='Start moderator MCP lobby', add_help=False)
    # Forward MCP flags untouched; legacy python -m harness.integration.mcp remains.
    if len(sys.argv) > 1 and sys.argv[1] == 'duel':
        from harness.integration.headless import main as headless_main
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        raise SystemExit(headless_main())
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
    elif args.command == 'deck-guide-pdf':
        from harness.engine.session import load_bundle
        try:
            from harness.rendering.deck_guide_pdf import default_art_cache, export, read_guide
        except ModuleNotFoundError as error:
            if error.name not in {'reportlab', 'PIL'}:
                raise
            parser.error("Install the optional PDF support with pip install -e '.[pdf]'")
        try:
            folder, deck = load_bundle(args.repo.resolve(), args.deck)
            missing = export(deck, read_guide(folder, args.language), args.output,
                             args.art_cache or default_art_cache(), language=args.language)
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(f'Cannot export guide: {error}')
        for card_id in missing:
            print(f'YGOPRODeck image unavailable for {deck["cards"][str(card_id)]["name"]}', file=sys.stderr)
        print(args.output)
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
