"""Publish replay review positions and import human answers into the evaluator."""

from copy import deepcopy
import re

from harness.environment.board import board_snapshot
from harness.runner.intents import translate_intent
from harness.runner.state_tools import build
from harness.storage.archive import load_replay
from harness.views.perspective import view

from .evaluation import normalized_move
from .harness_replay import ADAPTER, open_archive, prepare_harness, remap_player
from .kpis import approved, digest

CATALOG = 'harness-human-review-v1'
ANSWERS = 'harness-human-answers-v1'
QUESTION = 'Which of these three moves would you make?'
SLUG = re.compile(r'[a-z0-9][a-z0-9-]{0,99}')


def _catalog_rows(archive, spec):
    if (not isinstance(spec, dict) or spec.get('schema') != CATALOG or spec.get('adapter') != ADAPTER
            or not SLUG.fullmatch(spec.get('id', '')) or not approved(spec.get('review'))):
        raise ValueError('Expected an approved replay review catalog')
    with open_archive(archive) as (game, index, cache):
        if digest(index) != spec.get('source_index_sha256'):
            raise ValueError('Catalog refers to a different replay')
        positions, ids = set(), set()
        for row in spec['checkpoints']:
            revision, actor = row['revision'], row['player']
            identity = row['id']
            if (not SLUG.fullmatch(identity) or identity in ids or not approved(row.get('review'))
                    or not row.get('evidence') or len(row['choices']) != 3
                    or type(revision) is not int or not 0 <= revision < len(index['event_index'])
                    or actor not in {'human', 'agent'} or (revision, actor) in positions):
                raise ValueError('Each case must identify a unique reviewed position and three moves')
            positions.add((revision, actor))
            ids.add(identity)
            source = load_replay(game, revision=revision, cache_dir=cache)
            if ((source.get('pending_decision') or {}).get('actor') != actor
                    or not any(p['expected_revision'] == revision and p['actor'] == actor
                               for p in index.get('decision_packets', []))):
                raise ValueError('The source has no recorded decision at this position')
            state = remap_player(source, actor)
            labels, signatures = set(), {}
            for choice in row['choices']:
                cid, label = choice['id'], choice['label']
                if (not SLUG.fullmatch(cid) or cid in signatures or not label.strip()
                        or label in labels or not choice.get('rationale')):
                    raise ValueError('Each move needs a unique ID, label and legality review')
                labels.add(label)
                plan = translate_intent(state, choice['intent'], reviewed_activation=choice.get('activation'))
                build(state, {**plan, 'moderator_approved': True, 'public_summary_reviewed': True})
                signatures[cid] = normalized_move(choice['intent'], state)
            if len({digest(value) for value in signatures.values()}) != 3:
                raise ValueError('Choose three distinct semantic moves')
            yield row, source, signatures


def export_review_boards(archive, spec):
    """Return the reviewer's pre-move view. No recorded answer or future appears."""
    cases = []
    for row, source, _ in _catalog_rows(archive, spec):
        identity = row['id']
        state = remap_player(source, 'human') if row['player'] == 'agent' else deepcopy(source)
        state['mode'] = 'managed'
        state['presentation'] = {'show_agent_hand': False}
        projection = view(state, 'human')
        for link in projection['chain']:
            link.pop('effect', None)
        cards = {key: card for player in state['players'].values() for key, card in player['cards'].items()}
        board = board_snapshot({'perspective': 'human', 'context': {
            'state': projection, 'cards': cards, 'recent_events': [],
        }}, state, {'events': []})
        cases.append({'id': identity, 'board': board, 'facts': row['public_facts'],
                      'choices': [{k: choice[k] for k in ('id', 'label')} for choice in row['choices']]})
    if not cases:
        raise ValueError('Catalog contains no cases')
    return {'schema': CATALOG, 'id': spec['id'], 'sha256': digest(spec),
            'title': spec['title'], 'format': spec['format_label'], 'cases': cases}


def prepare_human_review(archive, spec, answers, output):
    """Bind human selections to the exact authored options and source replay."""
    catalog_hash = digest(spec)
    if (not isinstance(answers, dict) or answers.get('schema') != ANSWERS
            or answers.get('catalog_sha256') != catalog_hash
            or not isinstance(answers.get('answers'), list)):
        raise ValueError('Human answers refer to a different review catalog')
    picked = {}
    for entry in answers['answers']:
        identity, cid = entry['case_id'], entry['choice_id']
        if identity in picked:
            raise ValueError('Duplicate human answer')
        picked[identity] = cid
    if not picked:
        raise ValueError('Save at least one human decision before exporting')
    review = {key: spec[key] for key in ('adapter', 'id', 'source_index_sha256',
                                        'banlist_snapshot_marker', 'banlist', 'review')}
    rows = []
    for row, _, signatures in _catalog_rows(archive, spec):
        if row['id'] not in picked:
            continue
        cid = picked.pop(row['id'])
        if cid not in signatures:
            raise ValueError('Human selected a move outside the authored options')
        chosen = next(choice for choice in row['choices'] if choice['id'] == cid)
        options = '\n'.join(f'{i}. {choice["label"]}' for i, choice in enumerate(row['choices'], 1))
        rows.append({
            **{key: row[key] for key in ('id', 'revision', 'player', 'review')},
            'objective': QUESTION + ' Return the structured intention for your chosen move.',
            'public_facts': row['public_facts'] + '\n\n' + options,
            'reference_intent': chosen['intent'],
            'reference_activation': chosen.get('activation'),
            'acceptable_moves': [signatures[cid]],
            'rationale': 'Human preference among the three authored moves. ' + chosen['rationale'],
            'evidence': {'source': row['evidence'], 'catalog_sha256': catalog_hash,
                         'human_choice_id': cid},
        })
    if picked:
        raise ValueError('Human answers include an unknown case')
    return prepare_harness(archive, {**review, 'checkpoints': rows}, output)
