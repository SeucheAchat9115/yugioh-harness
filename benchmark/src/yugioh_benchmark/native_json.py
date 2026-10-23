"""Offline import of user-supplied Duelingbook view-replay JSON.

Native entries are observations, not certified engine actions. Unconcealed
exports contain private hands and future outcomes; never send them to players.
"""
from copy import deepcopy
import hashlib
import json
import re

from .replay import SCHEMA_VERSION, canonical, replay_id

ADAPTER_VERSION = 'duelingbook-json-v1'
PLAYER_FIELDS = {'username', 'main', 'extra', 'side', 'main_total', 'extra_total',
                 'side_total', 'start', 'legality'}
PHASES = {'Enter DP': 'DP', 'Enter SP': 'SP', 'Enter M1': 'M1',
          'Enter BP': 'BP', 'Enter M2': 'M2', 'Enter EP': 'EP'}
GROUPS = {
    'setup': {'RPS', 'Pick first', 'Begin next duel'},
    'draw': {'Draw card'},
    'turn': {'Start turn', 'End turn'},
    'summon': {'Normal Summon', 'SS ATK', 'SS DEF', 'Flip Summon'},
    'set': {'Set monster', 'Set ST'},
    'activation_observation': {'Activate ST', 'Declare'},
    'attack': {'Attack', 'Attack directly'},
    'lp': {'Life points'},
    'move': {'Mill', 'To hand', 'To GY', 'To B Deck', 'To T Deck', 'Banish', 'Move'},
    'shuffle': {'Shuffle deck', 'Shuffle hand'},
    'field_observation': {'Summon Token', 'Remove Token', 'Add counter', 'Remove counter',
                          'Target card', 'Edit stats', 'To ATK', 'To DEF'},
    'information_observation': {'View GY', 'View GY 2', 'View deck', 'View Banished',
                              'View Banished 2', 'Stop viewing'},
    'sideboarding': {'Siding', 'Done siding'},
    'result_observation': {'Admit defeat', 'Left duel'},
    'communication': {'Duel message', 'Thinking', 'Good', 'Countdown', 'Rejoin duel',
                      'Resume game', 'Add watcher', 'Remove watcher'},
}


def parse_export(text):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate JSON key: '+key)
            value[key] = item
        return value
    return json.loads(text, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))


def gameplay_export(data):
    """Remove account/display metadata, preserving literal gameplay structures."""
    def clean(value):
        if isinstance(value, list):
            return [clean(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in {'player1', 'player2', 'player3', 'player4'} and isinstance(item, dict):
                item = {field: content for field, content in item.items() if field in PLAYER_FIELDS}
            if key in {'pic', 'default_pic', 'sleeve', 'liked', 'watching', 'password'}:
                continue
            result[key] = clean(item)
        return result
    return clean(deepcopy(data))


def kind(play):
    if play in PHASES:
        return 'phase'
    return next((group for group, plays in GROUPS.items() if play in plays), 'unclassified')


def native_audit(data):
    """Literal coverage and LP arithmetic, never a legal-state reconstruction."""
    game = 1
    totals, baselines = {}, {}
    named_draws, unknown_draws = {}, {}
    conflicts = []
    for index, play in enumerate(data['plays']):
        if play['play'] == 'Begin next duel':
            game += 1
        logs = play.get('log', [])
        if isinstance(logs, dict):
            logs = [logs]
        for log in logs:
            if not isinstance(log, dict):
                continue
            private, public = log.get('private_log', ''), log.get('public_log', '')
            if public.startswith('Drew ') or private.startswith('Drew '):
                key = log.get('username', 'unknown')
                counts = named_draws if re.fullmatch(r'Drew "[^"]+"', private) else unknown_draws
                counts[key] = counts.get(key, 0)+1
        if play['play'] == 'Life points' and type(play.get('life')) is int and type(play.get('amount')) is int:
            key = (game, play.get('username'))
            totals[key] = totals.get(key, 0)+play['amount']
            baseline = play['life']-totals[key]
            if key in baselines and baselines[key] != baseline:
                conflicts.append(index)
            baselines.setdefault(key, baseline)
    return {'games': game, 'named_private_draws': named_draws,
            'draws_without_private_names': unknown_draws,
            'lp_baselines_from_absolute_updates': [
                {'game': game, 'username': username, 'lp': lp} for (game, username), lp in baselines.items()],
            'lp_inconsistent_source_indexes': conflicts,
            'named_complete_decklists': False,
            'rules_profile_verified': False}


def convert_json(data, source=None, retrieved_at=None):
    if not isinstance(data, dict) or not isinstance(data.get('plays'), list) or not data['plays']:
        raise ValueError('Expected a nonempty view-replay JSON object with plays')
    if data.get('tag_duel') is True:
        raise ValueError('Tag duels require a separate four-player adapter')
    if type(data.get('id')) is not int or data['id'] < 1:
        raise ValueError('Expected a numeric source duel ID')
    identity = replay_id(source) if source is not None else str(data['id'])
    if int(identity.split('-')[-1]) != data['id']:
        raise ValueError('Replay URL and native duel ID disagree')
    if any(not isinstance(data.get(slot), dict) for slot in ('player1', 'player2')):
        raise ValueError('Expected two source player objects')
    names = [data[slot].get('username') for slot in ('player1', 'player2')]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != 2:
        raise ValueError('Expected two distinct source player names')
    exported = gameplay_export(data)
    digest = hashlib.sha256(canonical(exported)).hexdigest()
    actors = {name: f'p{i+1}' for i, name in enumerate(names)}
    events, game, turn = [], 1, None
    for index, play in enumerate(exported['plays']):
        if not isinstance(play, dict) or not isinstance(play.get('play'), str) or not play['play']:
            raise ValueError('Native plays must contain a nonempty play label')
        if play.get('seconds') is not None and (type(play['seconds']) not in (int, float) or play['seconds'] < 0):
            raise ValueError('Native elapsed seconds must be nonnegative when supplied')
        if play['play'] == 'Begin next duel':
            game, turn = game+1, None
        elif play['play'] == 'Pick first':
            turn = 1
        elif play['play'] == 'Start turn':
            turn = turn+1 if turn is not None else None
        payload = {'play': play['play'], 'native': deepcopy(play),
                   'elapsed_seconds': play.get('seconds'), 'turn': turn}
        definitions = play.get('cards', [])
        if not isinstance(definitions, list):
            raise ValueError('Native cards must be an array')
        definitions = definitions+([play['card']] if isinstance(play.get('card'), dict) else [])
        payload['card_names'] = [card['name'] for card in definitions
                                 if isinstance(card, dict) and isinstance(card.get('name'), str)]
        if play['play'] in PHASES:
            payload['phase'] = PHASES[play['play']]
        if play['play'] == 'Life points':
            if type(play.get('amount')) is not int or type(play.get('life')) is not int:
                raise ValueError('LP observations require explicit signed amount and absolute life')
            payload.update(lp_delta=play['amount'], lp_after=play['life'])
        events.append({'sequence': index+1, 'source_index': index, 'game': game,
                       'actor': actors.get(play.get('username')), 'kind': kind(play['play']),
                       'payload': payload})
    return {'schema_version': SCHEMA_VERSION, 'id': 'db-json-'+identity,
            'source': {'provider': 'duelingbook', 'replay_id': identity,
                       'url': 'https://www.duelingbook.com/replay?id='+identity,
                       'payload_sha256': digest, 'retrieved_at': retrieved_at, 'adapter': ADAPTER_VERSION},
            'format': {'source_code': exported.get('format'), 'source_rules': exported.get('rules'),
                       'profile': None, 'banlist': None, 'rules_version': None, 'reviewed': False},
            'players': {f'p{i+1}': {'name': name, 'source_key': f'player{i+1}'} for i, name in enumerate(names)},
            'coverage': {'source_events': 'provided_native_plays',
                         'hidden_state': 'private_observations_present' if exported.get('conceal') is False else 'concealed_or_unknown',
                         'state_reconstruction': 'not_performed', 'decision_windows': 'not_reviewed',
                         'legality': 'not_reviewed', 'strategic_labels': 'none',
                         'physical_copy_ids': 'runtime_and_card_object_references_preserved_not_resolved',
                         'decklists': 'runtime_reference_arrays_not_complete_named_lists'},
            'source_metadata': {'data': exported, 'audit': native_audit(exported)}, 'events': events}


def validate_json(replay):
    source = replay['source']
    expected = convert_json(replay['source_metadata']['data'], source['url'], source['retrieved_at'])
    if replay != expected:
        raise ValueError('Native JSON source digest or derived annotations mismatch')
    return replay
