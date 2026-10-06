"""Immutable content-addressed assets shared by game archives; logical paths stay stable."""
import hashlib
import json
from pathlib import Path
import re
import tempfile


def root(game_dir):
    game = Path(game_dir).resolve()
    return game.parent.parent.parent / 'snapshots' if game.parent.parent.name == 'games' else game / 'snapshots'


def object_path(game_dir, sha):
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
        raise ValueError('Invalid snapshot hash')
    return root(game_dir) / sha[:2] / sha


def put(game_dir, content):
    raw = content.encode('utf-8') if isinstance(content, str) else content
    sha = hashlib.sha256(raw).hexdigest()
    path = object_path(game_dir, sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('Immutable snapshot has been modified')
    else:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            handle.write(raw)
            temporary = Path(handle.name)
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return sha


def get(game_dir, sha):
    path = object_path(game_dir, sha)
    if not path.resolve().is_relative_to(root(game_dir).resolve()):
        raise ValueError('Snapshot escapes its store')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('Snapshot asset hash mismatch')
    return raw.decode('utf-8')


def valid_name(name):
    path = Path(name)
    if path.is_absolute() or not path.parts or '..' in path.parts or path.parts[0] not in ('decks', 'rules.md'):
        raise ValueError('Unsafe logical asset path')
    return path


def collect(game_dir):
    """Read shared refs or legacy local files, also accepting a deliberate new asset."""
    game_dir = Path(game_dir)
    assets = {}
    archive_path = game_dir / 'events.json'
    if archive_path.exists():
        archive = json.loads(archive_path.read_text(encoding="utf-8"))
        for name, sha in archive.get('assets_sha256', {}).items():
            relative = valid_name(name)
            if archive.get('schema_version') in ('3.0', '4.0'):
                content = get(game_dir, sha)
            else:
                path = game_dir / relative
                if not path.resolve().is_relative_to(game_dir.resolve()):
                    raise ValueError('Snapshot escapes game directory')
                content = path.read_text(encoding='utf-8')
            assets[name] = {'sha256': sha, 'content': content}
    files = list((game_dir / 'decks').rglob('*')) if (game_dir / 'decks').exists() else []
    files += [game_dir / 'rules.md']
    for path in files:
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(game_dir.resolve()):
            raise ValueError('Snapshot escapes game directory')
        content = path.read_text(encoding='utf-8')
        assets[path.relative_to(game_dir).as_posix()] = {'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(), 'content': content}
    return assets


def intern(game_dir, assets):
    refs = {}
    for name, asset in assets.items():
        valid_name(name)
        sha = put(game_dir, asset['content'])
        if sha != asset['sha256']:
            raise ValueError('Snapshot content differs from expected hash')
        refs[name] = sha
    return refs


def remove_copies(game_dir, refs):
    """Remove only verified duplicate assets after writing their shared references."""
    game = Path(game_dir)
    for name, sha in refs.items():
        path = game / valid_name(name)
        if path.exists():
            if not path.resolve().is_relative_to(game.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ValueError('Refusing to remove a modified snapshot copy')
            path.unlink()
    decks = game / 'decks'
    if decks.exists():
        for path in sorted(decks.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        if not any(decks.iterdir()):
            decks.rmdir()
