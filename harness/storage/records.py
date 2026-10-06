"""Schema-4 archive index and individually discoverable, verified event records."""
from copy import deepcopy
import json
from pathlib import Path

from harness.engine.actions import digest
from harness.storage.atomic import save


def _entry(event):
    action = event['action']
    revision = action['expected_revision'] + 1
    if event.get('revision') != revision:
        raise ValueError('Archive event revision mismatch')
    return {'file': f'events/{revision:06d}.json', 'revision': revision,
            'turn': event.get('turn'), 'phase': event.get('phase'),
            'actor': action['actor'], 'kind': action['kind'],
            'public_summary': action['public_summary'],
            'event_sha256': event['event_sha256']}


def read_event(game_dir, entry):
    """Read one indexed event without loading other events or hidden-state catalogs."""
    game = Path(game_dir).resolve()
    revision = entry.get('revision')
    if type(revision) is not int or revision < 1 or entry.get('file') != f'events/{revision:06d}.json':
        raise ValueError('Invalid archive event path')
    path = game / entry['file']
    if not path.resolve().is_relative_to(game):
        raise ValueError('Archive event escapes game directory')
    event = json.loads(path.read_text(encoding="utf-8"))
    if event.get('event_sha256') != digest({k: v for k, v in event.items() if k != 'event_sha256'}):
        raise ValueError('Archive event hash mismatch')
    if _entry(event) != entry:
        raise ValueError('Archive event differs from index')
    return event


def load(game_dir):
    """Hydrate event records for existing replay callers; legacy arrays remain readable."""
    game = Path(game_dir)
    archive = json.loads((game / 'events.json').read_text(encoding="utf-8"))
    if archive.get('schema_version') == '4.0':
        if 'events' in archive:
            raise ValueError('Schema-4 archives must not duplicate event records')
        entries = archive.pop('event_index')
        start = archive['initial_state'].get('revision', 0)
        if [entry['revision'] for entry in entries] != list(range(start + 1, start + len(entries) + 1)):
            raise ValueError('Archive event index is not contiguous')
        archive['events'] = [read_event(game, entry) for entry in entries]
    return archive


def write(game_dir, archive):
    """Publish records first and atomically replace the index last under the writer lock.

    Existing records are immutable; an interrupted append leaves an unindexed record
    that an identical retry can reuse. Replay only reads index-listed files.
    """
    game = Path(game_dir)
    if archive.get('schema_version') != '4.0':
        save(game / 'events.json', archive)
        return
    manifest = deepcopy(archive)
    events = manifest.pop('events')
    entries = [_entry(event) for event in events]
    (game / 'events').mkdir(exist_ok=True)
    for entry, event in zip(entries, events):
        path = game / entry['file']
        if not path.resolve().is_relative_to(game.resolve()):
            raise ValueError('Archive event escapes game directory')
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != event:
                raise ValueError('Refusing to replace a different archived event')
        else:
            save(path, event)
    manifest['event_index'] = entries
    save(game / 'events.json', manifest)
