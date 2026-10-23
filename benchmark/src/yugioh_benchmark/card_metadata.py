"""Passcode-bound current card references; never historical rules or deck inference."""
import hashlib
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .replay import canonical

ENDPOINT = 'https://db.ygoprodeck.com/api/v7/cardinfo.php'
FIELDS = ('id', 'name', 'desc', 'type', 'frameType', 'race', 'atk', 'def',
          'level', 'attribute', 'scale', 'linkval', 'linkmarkers', 'ygoprodeck_url')


def replay_definitions(replay):
    if replay['source']['adapter'] != 'duelingbook-json-v1':
        raise ValueError('Card lookup requires a native JSON replay with explicit passcodes')
    definitions, unresolved = {}, []
    for index, play in enumerate(replay['source_metadata']['data']['plays']):
        cards = play.get('cards', []) + ([play['card']] if isinstance(play.get('card'), dict) else [])
        for card in cards:
            if not isinstance(card, dict):
                continue
            serial = card.get('serial_number')
            value = str(serial) if type(serial) is int else serial
            if not isinstance(value, str) or not value.isascii() or not value.isdigit() or not 1 <= len(value) <= 8 or int(value) == 0:
                unresolved.append({'source_index': index, 'name': card.get('name'),
                                   'reason': 'missing_or_invalid_passcode'})
                continue
            definitions.setdefault(int(value), []).append(card)
    return definitions, unresolved


def request_url(replay):
    definitions, _ = replay_definitions(replay)
    if not definitions:
        raise ValueError('No explicit card passcodes to query')
    return ENDPOINT + '?' + urlencode({'id': ','.join(map(str, sorted(definitions)))})


def fetch_response(replay):
    request = Request(request_url(replay), headers={
        'User-Agent': 'yugioh-benchmark/0.1 card-metadata lookup', 'Accept': 'application/json'})
    with urlopen(request, timeout=30) as response:
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024:
        raise ValueError('Card API response exceeds 64 MiB')
    return data


def build_metadata(replay, response_bytes, retrieved_at):
    if not isinstance(retrieved_at, str) or not retrieved_at.strip():
        raise ValueError('An explicit retrieval timestamp is required')
    from .native_json import parse_export
    response = parse_export(response_bytes.decode('utf-8-sig'))
    if not isinstance(response, dict) or not isinstance(response.get('data'), list):
        raise ValueError('Expected YGOPRODeck response with a data array')
    records = {}
    for card in response['data']:
        if not isinstance(card, dict) or type(card.get('id')) is not int or card['id'] <= 0:
            raise ValueError('API card IDs must be positive integer passcodes')
        if card['id'] in records:
            raise ValueError('Duplicate API card passcode')
        if any(not isinstance(card.get(field), str) or not card[field] for field in ('name', 'desc')):
            raise ValueError('API cards require a name and description')
        records[card['id']] = card
    definitions, unresolved = replay_definitions(replay)
    cards, missing = [], []
    for passcode, observations in sorted(definitions.items()):
        if passcode not in records:
            missing.append(f'{passcode:08d}')
            continue
        api_card = records[passcode]
        names = sorted({c['name'] for c in observations if isinstance(c.get('name'), str)})
        texts = sorted({c['effect'] for c in observations if isinstance(c.get('effect'), str)})
        cards.append({'passcode': f'{passcode:08d}',
                      'match_basis': 'exact_serial_number_to_api_id',
                      'replay_names': names, 'replay_texts': texts,
                      'name_matches_all_observations': bool(names) and names == [api_card['name']],
                      'text_matches_all_observations': bool(texts) and texts == [api_card['desc']],
                      'api_card': {key: api_card[key] for key in FIELDS if key in api_card}})
    return {'schema_version': '1.0', 'adapter': 'ygoprodeck-card-reference-v1',
            'source_replay': replay['id'], 'source_payload_sha256': replay['source']['payload_sha256'],
            'provider': 'ygoprodeck', 'endpoint': ENDPOINT, 'request_url': request_url(replay),
            'retrieved_at': retrieved_at,
            'response_bytes_sha256': hashlib.sha256(response_bytes).hexdigest(),
            'selected_api_cards_sha256': hashlib.sha256(canonical([c['api_card'] for c in cards])).hexdigest(),
            'text_scope': 'current_api_snapshot_not_historical_rules',
            'historical_rules_verified': False, 'complete_named_decklists': False,
            'requested_distinct_passcodes': len(definitions), 'matched_distinct_passcodes': len(cards),
            'missing_passcodes': missing, 'unresolved_definitions': unresolved,
            'cards': cards}
