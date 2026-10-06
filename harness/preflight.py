"""Local readiness checks and honest host capability declarations; no model calls."""
import json
import os
from pathlib import Path
import sys
import tempfile


def validate_host(host):
    required = ('execution', 'native_subagents', 'fresh_history', 'context_only_instructions', 'stop_children')
    return (isinstance(host, dict) and all(host.get(key) is True for key in required)
            and isinstance(host.get('evidence'), str) and bool(host['evidence'].strip()))


def _writable(path):
    parent = Path(path)
    while not parent.exists():
        parent = parent.parent
    with tempfile.TemporaryFile(dir=parent) as handle:
        handle.write(b'readiness probe')


def inspect(repo, private_root=None, host=None, decks=None, require_docs=True):
    repo = Path(repo).resolve()
    private = Path(private_root).resolve() if private_root else repo.parent / (repo.name + '-private')
    checks = []
    def check(name, operation):
        try:
            detail = operation()
            checks.append({'name': name, 'ok': True, 'detail': detail or 'ready'})
        except (OSError, ValueError, KeyError, TypeError, ImportError):
            checks.append({'name': name, 'ok': False, 'detail': 'Failed; check the path, permissions or resource validity.'})
    def runtime():
        if sys.version_info < (3, 11) or os.name not in ('posix', 'nt'):
            raise ValueError('Requires Python 3.11+ on Windows or POSIX')
        from harness.storage.locking import lock_handle
        with tempfile.TemporaryFile() as handle:
            lock_handle(handle)
        return 'Python 3.11+ and native writer locks available'
    check('runtime', runtime)
    def repository():
        if not repo.is_dir() or not (repo / 'decks').is_dir():
            raise ValueError('Repository resource checkout required')
        if require_docs:
            for name in ('AGENTS.md', 'agents/orchestrator/AGENT.md', 'skills/duel-orchestrator/SKILL.md'):
                if not (repo / name).is_file():
                    raise ValueError('Missing orchestrator resource')
        for path in (repo, repo / 'games', repo / 'snapshots'):
            _writable(path)
        return 'Resource checkout and archive locations writable'
    check('repository', repository)
    def storage():
        if private.is_relative_to(repo) or repo.is_relative_to(private):
            raise ValueError('Private storage must be a separate directory outside the repository')
        _writable(private)
        return 'Private storage is outside Git and writable'
    check('private_storage', storage)
    folders = decks if decks is not None else [str(p.parent.relative_to(repo)) for p in sorted((repo / 'decks').glob('*/*/deck.json'))]
    if not folders:
        checks.append({'name': 'deck_bundles', 'ok': False, 'detail': 'No selectable deck bundles'})
    def bundle(folder):
        from harness.engine.session import load_bundle
        load_bundle(repo, folder)
        return 'Inventory and guide hash valid'
    for folder in dict.fromkeys(folders):
        check('deck:' + folder, lambda folder=folder: bundle(folder))
    if host is not None:
        checks.append({'name': 'host_declaration', 'ok': bool(validate_host(host)),
                       'detail': 'Host-reported capabilities only; not sandbox attestation'})
    ready = all(entry['ok'] for entry in checks)
    return {'runtime_ready': all(entry['ok'] for entry in checks if entry['name'] != 'host_declaration'),
            'host_ready': bool(validate_host(host)) if host is not None else None,
            'ready': ready and host is not None, 'checks': checks,
            'host_boundary': 'cooperative; verify actual host capabilities before declaring them'}
