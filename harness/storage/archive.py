"""Omniscient replay archives. Remaining decks are unordered inventories, not queues."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from harness.engine.actions import apply, digest, replay, validate_state
from harness.modes import self_managed
from harness.storage.atomic import save

SCHEMA = '2.0'
DUPLICATE_LOGS = ('state.json', 'actions.md', 'log.md', 'resume.md')


def archive_state(state):
    result = deepcopy(state)
    for player in result['players'].values():
        if player.get('deck') is not None:
            player['deck'].sort(key=lambda card: card['instance_id'])
    return result


def _changes(before, after):
    changes = []
    for key, value in after.items():
        if key == 'revision' or value == before[key]:
            continue
        if key == 'players':
            for actor, player in value.items():
                if player.keys() != before[key][actor].keys():
                    changes.append({'path': [key, actor], 'before': before[key][actor], 'after': player})
                    continue
                for field, contents in player.items():
                    old = before[key][actor][field]
                    if old != contents:
                        changes.append({'path': [key, actor, field], 'before': old, 'after': contents})
        else:
            changes.append({'path': [key], 'before': before[key], 'after': value})
    return changes


def _outcomes(before, after):
    outcomes = []
    for actor in before['players']:
        old = before['players'][actor].get('deck')
        new = after['players'][actor].get('deck')
        if old is None or new is None:
            continue
        old_ids = {card['instance_id'] for card in old}
        new_ids = {card['instance_id'] for card in new}
        removed = [deepcopy(card) for card in old if card['instance_id'] not in new_ids]
        placements = [{'card': deepcopy(card), 'position': 'top' if index == 0 else 'bottom' if index == len(new)-1 else index}
                      for index, card in enumerate(new) if card['instance_id'] not in old_ids]
        if removed or placements:
            outcomes.append({'player': actor, 'cards_leaving_deck_in_order': removed,
                             'cards_returned_to_deck': placements})
    return outcomes


def _event(source, before, after):
    first, last = archive_state(before), archive_state(after)
    action = deepcopy(source['action'])
    action['changes'] = _changes(first, last)
    event = {'recorded_at': source['recorded_at'], 'before_sha256': digest(first),
             'after_sha256': digest(last), 'action': action,
             'deck_outcomes': _outcomes(before, after)}
    event['event_sha256'] = digest(event)
    return event


def build_archive(journal, state=None, existing=None):
    """Append one verified transition cheaply; rebuild from the journal for migration."""
    sources = journal['events']
    tail = sources[-1]['after_sha256'] if sources else digest(journal['initial_state'])
    if existing and existing.get('schema_version') == SCHEMA and 'initial_state_sha256' in existing:
        if len(existing['events']) == len(sources) and existing.get('source_tail_sha256') == tail:
            return existing
        if state is not None and len(existing['events']) + 1 == len(sources):
            source = sources[-1]
            before = deepcopy(state)
            for change in reversed(source['action']['changes']):
                parent = before
                for key in change['path'][:-1]:
                    parent = parent[key]
                parent[change['path'][-1]] = deepcopy(change['before'])
            before['revision'] = source['action']['expected_revision']
            previous_hash = sources[-2]['after_sha256'] if len(sources) > 1 else digest(journal['initial_state'])
            archive_hash = existing['events'][-1]['after_sha256'] if existing['events'] else digest(existing['initial_state'])
            if (existing.get('source_tail_sha256') == previous_hash
                    and archive_hash == digest(archive_state(before))):
                result = deepcopy(existing)
                result['events'].append(_event(source, before, state))
                result['source_tail_sha256'] = tail
                return result
    current = deepcopy(journal['initial_state'])
    result = {'schema_version': SCHEMA, 'visibility': 'omniscient-archive',
              'deck_order': 'unordered-instance-inventory', 'purpose': 'replay-and-review-not-live-resume',
              'hidden_state_coverage': 'human-unknown' if self_managed(current['mode']) else 'complete',
              'initial_state': archive_state(current), 'initial_state_sha256': digest(archive_state(current)),
              'events': [], 'source_tail_sha256': tail}
    validate_state(current)
    for source in sources:
        if source['before_sha256'] != digest(current):
            raise ValueError('Source journal hash mismatch')
        after = apply(current, source['action'])
        if source['after_sha256'] != digest(after):
            raise ValueError('Source journal result mismatch')
        result['events'].append(_event(source, current, after))
        current = after
    if state is not None and current != state:
        raise ValueError('Source journal differs from supplied state')
    return result


def write_archive(journal, state, game_dir, assets=None):
    game_dir = Path(game_dir)
    path = game_dir / 'events.json'
    existing = json.loads(path.read_text()) if path.exists() else None
    archive = build_archive(journal, state, existing)
    if assets is None:
        files = list((game_dir / 'decks').rglob('*')) if (game_dir / 'decks').exists() else []
        files += [game_dir / 'rules.md']
        manifest = {str(file.relative_to(game_dir)): hashlib.sha256(file.read_bytes()).hexdigest()
                    for file in files if file.is_file() and file.name != '.writer.lock'}
    else:
        manifest = {name: asset['sha256'] for name, asset in assets.items()}
    archive['assets_sha256'] = manifest
    archive['configuration_sha256'] = digest(json.loads((game_dir / 'game.json').read_text()))
    save(path, archive)
    for name in DUPLICATE_LOGS:
        (game_dir / name).unlink(missing_ok=True)
    return archive


def load_replay(game_dir, revision=None, perspective='moderator'):
    """Verify archive/assets and reconstruct a chosen revision or filtered view."""
    game_dir = Path(game_dir)
    archive = json.loads((game_dir / 'events.json').read_text())
    if archive.get('schema_version') != SCHEMA:
        raise ValueError('Legacy summaries cannot reconstruct hidden states; migrate a private journal')
    for name, expected in archive.get('assets_sha256', {}).items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in ('decks', 'rules.md'):
            raise ValueError('Unsafe archive asset path')
        file = (game_dir / relative).resolve()
        if not file.is_relative_to(game_dir.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError('Archive asset hash mismatch')
    events = archive['events']
    start = archive['initial_state'].get('revision', 0)
    end = start + len(events)
    if revision is None:
        revision = end
    if type(revision) is not int or not start <= revision <= end:
        raise ValueError('Revision outside archived history')
    if perspective not in ('moderator', 'human', 'agent', 'public'):
        raise ValueError('Invalid replay perspective')
    if archive.get('initial_state_sha256') != digest(archive['initial_state']):
        raise ValueError('Archive initial-state hash mismatch')
    validate_state(archive['initial_state'])
    # Verify all events even when asking for an earlier revision.
    for event in events:
        if event.get('event_sha256') != digest({key: value for key, value in event.items() if key != 'event_sha256'}):
            raise ValueError('Archive event hash mismatch')
    final = replay(archive)
    state = final if revision == end else replay({**archive, 'events': events[:revision-start]})
    config = json.loads((game_dir / 'game.json').read_text())
    if archive.get('configuration_sha256') != digest(config):
        raise ValueError('Archive configuration hash mismatch')
    if config['id'] != state['game_id'] or config['mode'] != state['mode']:
        raise ValueError('Archive configuration mismatch')
    if perspective == 'moderator':
        return state
    from harness.views.perspective import view
    permitted = view(state, perspective)
    for player in permitted['players'].values():
        player.pop('remaining_deck_order', None)
    return permitted


def render_log(game_dir):
    """Generate readable summaries on demand, without a second persisted log."""
    load_replay(game_dir)
    archive = json.loads((Path(game_dir) / 'events.json').read_text())
    return '\n'.join(f"{event['action']['expected_revision']+1}. {event['action']['actor']}: {event['action']['public_summary']}"
                     for event in archive['events'])


def write_decisions(game_dir, workflow):
    """Archive submitted intentions, not duplicated guarded patches or host receipts."""
    path = Path(game_dir) / 'events.json'
    if not path.exists():
        return
    archive = json.loads(path.read_text())
    if archive.get('schema_version') != SCHEMA:
        return
    decisions = [{'request_id': key, **{field: deepcopy(value[field]) for field in
                 ('decision_id', 'player', 'revision', 'intention') if field in value}}
                 for key, value in workflow.get('submissions', {}).items()]
    packets = list(workflow.get('decision_packets', {}).values())
    if archive.get('decisions', []) != decisions or archive.get('decision_packets', []) != packets:
        archive['decisions'] = decisions
        archive['decision_packets'] = deepcopy(packets)
        save(path, archive)


def game_result(state, journal, previous=None):
    if state['status'] != 'finished':
        return previous
    explicit = next((event['action']['result'] for event in reversed(journal['events'])
                     if 'result' in event['action']), None)
    if explicit:
        return deepcopy(explicit)
    lost = [actor for actor, player in state['players'].items() if player['lp'] == 0]
    if lost:
        return {'winner': 'draw' if len(lost) == 2 else next(actor for actor in state['players'] if actor not in lost),
                'reason': 'LP reached zero', 'turn': state['turn'], 'revision': state['revision']}
    return previous  # Never invent a concession, deck-out or alternate win condition.


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('replay', 'log', 'migrate'))
    parser.add_argument('--game-dir', type=Path, required=True)
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--workflow', type=Path)
    parser.add_argument('--revision', type=int)
    parser.add_argument('--perspective', choices=('moderator', 'human', 'agent', 'public'), default='public')
    args = parser.parse_args()
    if args.command == 'migrate':
        if args.journal is None:
            parser.error('Migration requires the authoritative private journal')
        from harness.storage.locking import writer_lock
        with writer_lock(args.journal.with_name('state.json'), args.game_dir):
            journal = json.loads(args.journal.read_text())
            state = replay(journal)
            config = json.loads((args.game_dir / 'game.json').read_text())
            if config['id'] != state['game_id'] or config['mode'] != state['mode']:
                raise ValueError('Migration journal belongs to a different game')
            old = args.game_dir / 'events.json'
            if old.exists():
                data = json.loads(old.read_text())
                old_revision = data.get('initial_state', {}).get('revision', 0) + len(data.get('events', []))
                if old_revision > state['revision']:
                    raise ValueError('Migration would discard newer history')
            config['status'] = state['status']
            config['result'] = game_result(state, journal, config.get('result'))
            config['resume'] = {'revision': state['revision'], 'turn': state['turn'], 'phase': state['phase'],
                                'pending_actor': (state.get('pending_decision') or {}).get('actor'),
                                'pending_window': (state.get('pending_decision') or {}).get('window'),
                                'private_checkpoint_saved': args.journal.with_name('checkpoint.json').exists()}
            save(args.game_dir / 'game.json', config)
            write_archive(journal, state, args.game_dir)
            workflow = args.workflow or args.journal.with_name('workflow.json')
            if workflow.exists():
                write_decisions(args.game_dir, json.loads(workflow.read_text()))
            checkpoint = args.journal.with_name('checkpoint.json')
            if checkpoint.exists():
                packet = json.loads(checkpoint.read_text()).get('decision_packet')
                if packet:
                    archive = json.loads((args.game_dir / 'events.json').read_text())
                    if not archive.get('decision_packets'):
                        archive['decision_packets'] = [packet]
                        save(args.game_dir / 'events.json', archive)
            if load_replay(args.game_dir) != archive_state(state):
                raise ValueError('Migrated archive does not reproduce the source state')
            print(json.dumps({'game_id': state['game_id'], 'revision': state['revision'], 'verified': True}))
    elif args.command == 'log':
        print(render_log(args.game_dir))
    else:
        print(json.dumps(load_replay(args.game_dir, args.revision, args.perspective), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
