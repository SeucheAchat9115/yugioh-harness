"""Verified schema-4 archive -> explicitly reviewed, single-decision checkpoints.

The archive and review specification are TRUSTED evaluator inputs. They never
enter a player request. Import alone grants no approval and reconstructs no gaps.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

from .kpis import digest, approved

ADAPTER = 'harness-archive-v1'
PROTOCOL = 'harness-objectives-v1'
MAX_BYTES = 64 * 1024 * 1024


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


@contextmanager
def open_archive(source):
    """Extract bounded, path-safe ZIPs; always cold-verify all events and assets."""
    from harness.storage.archive import load_replay
    source = Path(source).resolve()
    with tempfile.TemporaryDirectory(prefix='harness-import-') as temporary:
        temp = Path(temporary)
        if source.is_dir():
            game = source
        else:
            if source.stat().st_size > MAX_BYTES:
                raise ValueError('Archive exceeds 64 MiB')
            try:
                with zipfile.ZipFile(source) as archive:
                    entries = archive.infolist()
                    if len(entries) > 10000 or sum(e.file_size for e in entries) > MAX_BYTES:
                        raise ValueError('Archive expands beyond import limits')
                    seen = set()
                    for entry in entries:
                        path = PurePosixPath(entry.filename)
                        mode = entry.external_attr >> 16
                        if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                                or ':' in entry.filename or not path.parts or path in seen
                                or (mode & 0o170000) == 0o120000):
                            raise ValueError('Unsafe or duplicate ZIP path')
                        seen.add(path)
                    archive.extractall(temp/'source')
            except zipfile.BadZipFile as exc:
                raise ValueError('Expected a schema-4 directory or replay ZIP') from exc
            games = list((temp/'source').rglob('game.json'))
            if len(games) != 1:
                raise ValueError('ZIP must contain exactly one game')
            game = games[0].parent
        index = _json(game/'events.json')
        if index.get('schema_version') != '4.0':
            raise ValueError('Only verified schema-4 harness archives are supported')
        cache = temp/'cache'
        load_replay(game, cache_dir=cache)  # Verify the complete source, including future events.
        yield game, index, cache


def audit_harness(source):
    with open_archive(source) as (game, index, _):
        config = _json(game/'game.json')
        return {'adapter': ADAPTER, 'replay': config['id'], 'status': 'unreviewed',
                'index_sha256': digest(index), 'event_count': len(index['event_index']),
                'decision_evidence': deepcopy(index.get('decision_evidence')),
                'candidates': [{'revision': p['expected_revision'], 'actor': p['actor'],
                                'decision_id': p['decision_id']}
                               for p in index.get('decision_packets', [])]}


def remap_player(state, player):
    """Change slot labels, never physical IDs, card metadata or source narration."""
    if player not in {'human', 'agent'}:
        raise ValueError('Choose a recorded player slot')
    def visit(value):
        if isinstance(value, dict):
            return {swap(k): visit(v) for k, v in value.items()}
        if isinstance(value, list):
            return [visit(v) for v in value]
        return swap(value) if isinstance(value, str) else value
    def swap(value):
        return {'human': 'agent', 'agent': 'human'}.get(value, value) if player == 'human' else value
    return visit(state)


def player_context(state, rules, public_facts):
    """Use the live runtime's visibility projection, with no archive narration/menu."""
    from harness.environment.positions import create_position
    from harness.runner.duel import DuelRunner
    with tempfile.TemporaryDirectory(prefix='reviewed-context-') as root:
        config = {'id': state['game_id'], 'mode': state['mode'], 'player_isolation': 'enforced',
                  'format': rules['format'], 'rules_version': rules['rules_version'],
                  'banlist': 'Pinned reviewed archive banlist', 'settings': {}}
        private, game = create_position(root, position_id=state['game_id'], configuration=config,
                                        state=state, rules_text=rules['text'])
        with DuelRunner(private, game) as runner:
            context = runner.context('agent')
    # Archived chain prose can include old slot labels or accidental hidden hints.
    # Retain public structured links/targets/costs; explicit reviewed facts supply
    # the decision situation, never the source's coaching or proposed response.
    for link in context['state']['chain']:
        link.pop('effect', None)
    context['rules'] = deepcopy(rules)  # Full pinned text, never the runtime's 8k excerpt.
    context['guides'] = {}
    context['recent_events'] = []
    context['prompt'] = {'public_facts': public_facts}
    return context


def prepare_harness(source, review, output):
    """Author a dataset only from explicit approvals pinned to this exact archive."""
    from harness.storage.archive import load_replay
    from harness.storage.snapshots import collect
    from harness.engine.actions import validate_state
    from .evaluation import normalized_move
    from harness.runner.intents import translate_intent
    output = Path(output)
    if output.exists():
        raise ValueError('Use a new dataset directory')
    review = deepcopy(review)
    if review.get('adapter') != ADAPTER or not approved(review.get('review')):
        raise ValueError('Explicit scoped review approval is required')
    suite_id = review.get('id', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', suite_id):
        raise ValueError('Dataset ID must be a lowercase slug')
    with open_archive(source) as (game, index, cache):
        if review.get('source_index_sha256') != digest(index):
            raise ValueError('Review refers to a different archive index')
        config = _json(game/'game.json')
        assets = collect(game)
        text = assets['rules.md']['content']
        # Extract the dated banlist embedded in the original immutable rules;
        # never silently substitute today's repository banlist.
        banlist = review.get('banlist')
        if not isinstance(banlist, dict) or not review.get('banlist_snapshot_marker'):
            raise ValueError('Pin the original embedded banlist and its marker')
        marker = review['banlist_snapshot_marker']
        start = text.find(marker)
        if start < 0 or json.JSONDecoder().raw_decode(text[start:])[0] != banlist:
            raise ValueError('Banlist is absent from the original rules snapshot')
        rules = {'format': config['format'], 'rules_version': config['rules_version'],
                 'text': text, 'truncated': False,
                 'checkpoint_slot_notice': 'The evaluated player is agent; human is the opponent. '
                     'Original game-setup role labels in the historical snapshot do not describe '
                     'this remapped checkpoint. Use current state and reviewed public facts.'}
        final = load_replay(game, cache_dir=cache)
        cards = {}
        for owner in final['players'].values():
            for identity, card in owner['cards'].items():
                if identity in cards and cards[identity] != card:
                    raise ValueError('Conflicting source card catalogs')
                cards[identity] = deepcopy(card)
        banlist_bytes = (json.dumps(banlist, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
        pins = {'format': config['format'], 'rules_version': config['rules_version'],
                'rules_sha256': digest(rules), 'card_text_sha256': digest(cards),
                'banlist_sha256': hashlib.sha256(banlist_bytes).hexdigest(),
                'assets': {'rules': 'assets/rules-snapshot.json', 'cards': 'assets/card-texts.json',
                           'banlist': 'assets/banlist.json'}}
        cases, entries, evaluator, packets = [], [], {}, {}
        for row in review.get('checkpoints', []):
            identity = row['id']
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', identity):
                raise ValueError('Checkpoint ID must be a lowercase slug')
            if not approved(row.get('review')) or not row.get('rationale') or not row.get('evidence'):
                raise ValueError('Each objective requires scoped review, reasoning and evidence')
            rev, actor = row['revision'], row['player']
            if type(rev) is not int or rev < 0 or rev >= len(index['event_index']):
                raise ValueError('Checkpoint must precede a recorded action')
            source_state = load_replay(game, revision=rev, cache_dir=cache)
            matches = [p for p in index.get('decision_packets', [])
                       if p['expected_revision'] == rev and p['actor'] == actor]
            if (not matches or (source_state.get('pending_decision') or {}).get('actor') != actor):
                raise ValueError('No captured decision boundary for the selected player')
            state = remap_player(source_state, actor)
            # Descriptive evaluator case IDs often name the intended tactic.
            # Give the player an opaque position ID instead of that answer hint.
            position_id='checkpoint-'+digest({'index':digest(index),'revision':rev,'player':actor})[:16]
            state.update(game_id=position_id, revision=0, mode='managed', player_isolation='enforced')
            state['presentation'] = {'show_agent_hand': False}
            validate_state(state)
            for owner in state['players'].values():
                if any(cards[key] != card for key, card in owner['cards'].items()):
                    raise ValueError('Checkpoint card text differs from pinned assets')
            context = player_context(state, rules, row['public_facts'])
            gold = row['reference_intent']  # Explicit reviewer choice; never taken from archived recommendations.
            reference_plan=translate_intent(state, gold, reviewed_activation=row.get('reference_activation'))
            reference_plan.update(moderator_approved=True, public_summary_reviewed=True)
            from harness.runner.state_tools import build
            build(state, reference_plan)  # Ensure the scoped reference is executable bookkeeping too.
            accepted = row['acceptable_moves']
            if normalized_move(gold, state) not in accepted:
                raise ValueError('Reviewed reference does not meet its semantic objective')
            source_pin = {'replay': config['id'], 'revision': rev, 'before_sequence': rev+1,
                          'payload_sha256': digest(index), 'adapter': ADAPTER,
                          'source_state_sha256': digest(source_state),
                          'original_player': actor, 'decision_ids': [p['decision_id'] for p in matches],
                          'decision_evidence': deepcopy(index.get('decision_evidence'))}
            cases.append({'id': identity+'-choice', 'task': 'objective_choice', 'rules': pins,
                          'review': row['review'], 'source': source_pin,
                          'initial_state_sha256': digest(state), 'player_context_sha256': digest(context),
                          'player_packet': 'packets/'+identity+'.json',
                          'objective': row['objective'], 'public_facts': row['public_facts'],
                          'acceptable_moves': accepted})
            entries.append({'id': identity, 'status': 'approved_scoped', 'revision': rev,
                            'review': row['review'], 'rationale': row['rationale'], 'evidence': row['evidence']})
            evaluator[identity] = {'initial_state': state, 'reference_intent': gold,
                                   'reference_activation': row.get('reference_activation')}
            packets[identity] = {'id': identity, 'runnable': True, 'player_context': context}
        suite = {'schema_version': '1.0', 'id': suite_id, 'evaluation_protocol': PROTOCOL,
                 'review': review['review'], 'cases': cases,
                 'scope': 'Reviewed single-decision objectives; no resolution, future draws, win rate or hidden-order continuation.'}
        from .kpis import validate_suite
        validate_suite(suite)
        # Stage everything before publishing; failed validation leaves no runnable dataset.
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output.parent) as staging:
            stage = Path(staging)/'dataset'
            _write(stage/'suite.json', suite)
            _write(stage/'review-index.json', entries)
            _write(stage/'evaluator.json', evaluator)
            _write(stage/'assets/rules-snapshot.json', rules)
            _write(stage/'assets/card-texts.json', cards)
            _write(stage/'assets/banlist.json', banlist)
            for identity, packet in packets.items():
                _write(stage/'packets'/f'{identity}.json', packet)
            _write(stage/'provenance.json', {'adapter': ADAPTER, 'source_index_sha256': digest(index),
                    'source_assets': index['assets_sha256'], 'review_sha256': digest(review),
                    'transformations': ['evaluated slot -> agent', 'revision -> 0', 'fresh position ID',
                        'tool-free enforced player policy', 'archive deck inventories remain unordered',
                        'runtime visibility projection', 'omit archived narration, menus and guides'],
                    'decision_evidence': index.get('decision_evidence')})
            stage.rename(output)
    return {'dataset': str(output), 'cases': len(cases), 'protocol': PROTOCOL}
