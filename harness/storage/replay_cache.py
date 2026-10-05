"""Verified replay and private disposable revision caches, never a live draw queue."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from harness.engine.actions import apply, digest, validate_state
from harness.storage.atomic import save
from harness.storage.snapshots import get, valid_name


def _hydrate(game, archive):
    state = deepcopy(archive['initial_state'])
    for actor, ref in archive.get('catalog_refs', {}).items():
        value = json.loads(get(game, ref['sha256']))
        state['players'][actor]['cards'] = value[ref['field']] if 'field' in ref else value
    return state


def _advance(state, event, schema):
    if event['before_sha256'] != digest(state):
        raise ValueError('Inconsistent archive state hash')
    action = deepcopy(event['action'])
    if schema == '3.0':
        from harness.storage.compact import execute
        from harness.storage.archive import _changes
        after = execute(state, action.pop('operations'))
        action['changes'] = _changes(state, after)
    state = apply(state, action)
    if event['after_sha256'] != digest(state):
        raise ValueError('Archive event result hash mismatch')
    return state


def load(game_dir, revision=None, cache_dir=None):
    game = Path(game_dir).resolve()
    raw = (game / 'events.json').read_bytes()
    archive = json.loads(raw)
    schema = archive.get('schema_version')
    if schema not in ('2.0', '3.0'):
        raise ValueError('Legacy summaries cannot reconstruct hidden states; migrate a private journal')
    # Verify immutable resources and metadata even for a warm replay cache.
    for name, sha in archive.get('assets_sha256', {}).items():
        path = game / valid_name(name)
        if schema == '2.0' and path.exists():
            if not path.resolve().is_relative_to(game) or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ValueError('Archive asset hash mismatch')
        else:
            get(game, sha)
    config = json.loads((game / 'game.json').read_text())
    if archive.get('configuration_sha256') != digest(config):
        raise ValueError('Archive configuration hash mismatch')
    initial = _hydrate(game, archive)
    if digest(initial) != archive.get('initial_state_sha256'):
        raise ValueError('Archive initial-state hash mismatch')
    validate_state(initial)
    if config['id'] != initial['game_id'] or config['mode'] != initial['mode']:
        raise ValueError('Archive configuration mismatch')
    start = initial.get('revision', 0)
    end = start + len(archive['events'])
    revision = end if revision is None else revision
    if type(revision) is not int or not start <= revision <= end:
        raise ValueError('Revision outside archived history')
    ids = set()
    for event in archive['events']:
        if event.get('event_sha256') != digest({k: v for k, v in event.items() if k != 'event_sha256'}):
            raise ValueError('Archive event hash mismatch')
        if event['action']['id'] in ids:
            raise ValueError('Duplicate archive event')
        ids.add(event['action']['id'])
    cache_root = Path(cache_dir).resolve() if cache_dir else (game.parent.parent.parent.parent / (game.parent.parent.parent.name + '-replay-cache') if game.parent.parent.name == 'games' else game.parent / 'replay-cache')
    repo = game.parent.parent.parent if game.parent.parent.name == 'games' else game
    if cache_root.is_relative_to(repo):
        raise ValueError('Replay cache must stay outside the repository')
    key = hashlib.sha256(raw).hexdigest()
    cache = cache_root / key
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache_root.chmod(0o700)
    cache.chmod(0o700)
    def expected(number):
        return archive['initial_state_sha256'] if number == start else archive['events'][number-start-1]['after_sha256']
    def read(number):
        try:
            value = json.loads((cache / f'{number}.json').read_text())
            cached = value['state']
            if value['archive_sha256'] != key or value['verified_end'] != end or cached['revision'] != number or digest(cached) != expected(number):
                return None
            validate_state(cached)
            return cached
        except (OSError, ValueError, KeyError, TypeError):
            return None
    def write(number, state):
        path = cache / f'{number}.json'
        save(path, {'archive_sha256': key, 'verified_end': end, 'state': state})
        path.chmod(0o600)
    final = read(end)
    cached = read(revision) if final is not None else None
    if cached is not None:
        return cached
    state = initial
    answer = deepcopy(initial) if revision == start else None
    if final is not None:
        nearest = start + ((revision-start)//16)*16
        for number in dict.fromkeys([revision, *range(nearest, start-1, -16)]):
            candidate = read(number)
            if candidate is not None:
                state = candidate
                break
        remaining = archive['events'][state['revision']-start:revision-start]
        for event in remaining:
            state = _advance(state, event, schema)
        write(revision, state)
        return state
    # A cold cache validates the entire history, including when asking for an early revision.
    checkpoints = {start: deepcopy(initial)}
    for event in archive['events']:
        state = _advance(state, event, schema)
        if state['revision'] == revision:
            answer = deepcopy(state)
        if (state['revision']-start) % 16 == 0:
            checkpoints[state['revision']] = deepcopy(state)
    checkpoints[end] = state
    checkpoints[revision] = answer
    for number, checkpoint in checkpoints.items():
        write(number, checkpoint)
    return answer
