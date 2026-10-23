"""Reviewer-only states from explicit native observations; no effect engine."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .native_json import kind as native_kind, validate_json

EXTRACTOR_VERSION = 'native-observations-v1'
KINDS = {'Normal Summon', 'SS ATK', 'SS DEF', 'Flip Summon', 'Set monster',
         'Set ST', 'Activate ST', 'Declare', 'Attack', 'Attack directly',
         'Start turn', 'End turn', 'Enter DP', 'Enter SP', 'Enter M1',
         'Enter BP', 'Enter M2', 'Enter EP'}
MOVES = {'Normal Summon', 'SS ATK', 'SS DEF', 'Set monster', 'Set ST',
         'Activate ST', 'To hand', 'To GY', 'To B Deck', 'To T Deck',
         'Banish', 'Move', 'Remove Token'}
PHASES = {'Enter DP':'DP', 'Enter SP':'SP', 'Enter M1':'M1',
          'Enter BP':'BP', 'Enter M2':'M2', 'Enter EP':'EP'}


def logs(play):
    value = play.get('log', [])
    return [value] if isinstance(value, dict) else value


def label(play):
    return next((l.get('private_log') or l.get('public_log') or ''
                 for l in logs(play)), '')


def _extract(data, source):
    names = [data[k]['username'] for k in ('player1','player2')]
    records = []; gaps = []
    def gap(index, reason):
        gaps.append({'source_index':index, 'reason':reason})
    def reset(game, metadata=None):
        metadata = metadata or data
        return {'game':game, 'turn':None, 'active_player':None, 'phase':None,
                'turn_ended':False, 'result':None,
                'players':{n:{'hand':[], 'field':{}, 'graveyard':[], 'banished':[],
                             'deck_count':metadata.get(f'player{i+1}', {}).get('main_total'),
                             'lp':None} for i,n in enumerate(names)}}
    state = reset(1)
    # Derive LP baselines for reviewer use from absolute source updates. Never
    # treat this hindsight derivation as an independent historical rules proof.
    baselines = {}; sums = {}; game = 1
    for i,p in enumerate(data['plays']):
        if p['play'] == 'Begin next duel': game += 1
        if p['play'] == 'Life points':
            key=(game,p['username']); sums[key]=sums.get(key,0)+p['amount']
            baseline=p['life']-sums[key]
            if key in baselines and baselines[key] != baseline: gap(i,'LP baseline conflict')
            baselines.setdefault(key,baseline)
    def init_lp():
        for n in names: state['players'][n]['lp']=baselines.get((state['game'],n))
    init_lp()
    def find_field(runtime):
        return [(n,z,c) for n in names for z,c in state['players'][n]['field'].items()
                if runtime is not None and c['runtime_ref']==runtime]
    def deck_delta(n, delta):
        value=state['players'][n]['deck_count']
        if value is not None: state['players'][n]['deck_count']=value+delta
    for index,p in enumerate(data['plays']):
        kind=p['play']; actor=p.get('username'); runtime=p.get('id')
        if kind=='Begin next duel': state=reset(state['game']+1, p); init_lp()
        before=deepcopy(state); text=label(p); name_match=re.search(r'"([^"]+)"',text)
        name=name_match.group(1) if name_match else p.get('card',{}).get('name')
        from_match=re.search(r' from (hand|GY|Deck|M-\d|S-\d|F-\d)',text)
        origin=from_match.group(1) if from_match else ('banished' if 'banished "' in text else None)
        to_match=re.search(r' (?:to|in) ((?:M2?|S2?|F2?)-\d)\b',text)
        target=to_match.group(1) if to_match else p.get('zone')
        hits=find_field(runtime)
        owner=p.get('owner') or (hits[0][2]['owner'] if len(hits)==1 else actor)
        item={'name':name, 'runtime_ref':runtime, 'owner':owner,
              'face_down':kind in {'Set monster','Set ST'} or 'Set "' in text,
              'position':'ATK' if kind in {'SS ATK','Normal Summon'} else
                         'DEF' if kind in {'SS DEF','Set monster'} else None}
        local_start=len(gaps)
        if kind=='Pick first':
            state['turn']=1; state['active_player']=actor; state['phase']='DP'
            for l in logs(p):
                if (l.get('private_log') or l.get('public_log','')).startswith('Drew '):
                    m=re.fullmatch(r'Drew "([^"]+)"',l.get('private_log',''))
                    n=l['username']; state['players'][n]['hand'].append(m.group(1) if m else None)
                    deck_delta(n,-1)
                    if m is None: gap(index,'Unnamed opening draw')
        elif kind=='Start turn':
            state['turn']=(state['turn'] or 0)+1; state['active_player']=actor
            state['phase']='DP'; state['turn_ended']=False
        elif kind=='End turn': state['turn_ended']=True
        elif kind in PHASES: state['phase']=PHASES[kind]
        elif kind=='Life points':
            old=state['players'][actor]['lp']
            if old is not None and old+p['amount'] != p['life']: gap(index,'LP delta mismatch')
            state['players'][actor]['lp']=p['life']
        elif kind=='Draw card':
            state['players'][actor]['hand'].append(name); deck_delta(actor,-1)
            if name is None: gap(index,'Unnamed draw')
        elif kind=='Flip Summon':
            if len(hits)==1: hits[0][2].update(face_down=False, position='ATK')
            else: gap(index,'Flip summon target not uniquely resolved')
        elif kind=='Mill':
            state['players'][actor]['graveyard'].append(item); deck_delta(actor,-1)
        elif kind in MOVES:
            # Check logged pre-operation hand counts without resolving shuffle IDs.
            count=re.search(r'from hand \(\d+/(\d+)\)',text)
            if count and len(state['players'][actor]['hand']) != int(count.group(1)):
                gap(index,'Logged pre-action hand count disagrees with observed inventory')
            if origin=='hand':
                hand=state['players'][actor]['hand']
                if name in hand: hand.remove(name)
                else: gap(index,'Source card absent from observed hand')
            elif origin=='Deck': deck_delta(actor,-1)
            elif origin in {'GY','banished'}:
                pool=state['players'][owner]['graveyard' if origin=='GY' else 'banished']
                found=[c for c in pool if c['runtime_ref']==runtime]
                if len(found)==1: pool.remove(found[0]); item=deepcopy(found[0])
                else: gap(index,'Source pile runtime reference not uniquely resolved')
            elif hits:
                if len(hits)!=1: gap(index,'Multiple field cards share runtime reference')
                else:
                    n,z,old=hits[0]; item=deepcopy(old); del state['players'][n]['field'][z]
                    if origin and origin!=z: gap(index,'Logged origin differs from observed slot')
            elif kind=='Activate ST': gap(index,'Set activation has no observed field card')
            elif kind!='Remove Token': gap(index,'Movement origin not resolved')
            if name is not None: item['name']=name
            if kind in {'Set monster','Set ST'}: item['face_down']=True
            if kind in {'SS ATK','SS DEF','Normal Summon','Activate ST'}: item['face_down']=False
            if kind in {'SS ATK','Normal Summon'}: item['position']='ATK'
            if kind=='SS DEF': item['position']='DEF'
            if kind=='To hand':
                # Preserve who receives the logged operation; do not silently
                # repair a control/ownership inconsistency using card rules.
                state['players'][actor]['hand'].append(item['name'])
                if item['owner']!=actor: gap(index,'Card returned to logged controller instead of recorded owner; needs adjudication')
            elif kind in {'To GY','Banish'}:
                item.update(face_down=False, position=None)
                state['players'][item['owner']]['graveyard' if kind=='To GY' else 'banished'].append(item)
            elif kind in {'To B Deck','To T Deck'}: deck_delta(item['owner'],1)
            elif kind!='Remove Token':
                if target:
                    controller=actor; zone=target
                    if re.match(r'[MSF]2-',target):
                        controller=next(n for n in names if n!=actor); zone=target.replace('2-','-')
                    if zone in state['players'][controller]['field']: gap(index,'Destination slot already occupied')
                    state['players'][controller]['field'][zone]=item
                else: gap(index,'Destination slot absent from source log')
        elif kind=='Summon Token':
            item.update(name='Token',face_down=False,position=None)
            if target: state['players'][actor]['field'][target]=item
            else: gap(index,'Token destination absent')
        elif kind in {'Add counter','Remove counter','Edit stats','To ATK','To DEF'}:
            if len(hits)==1:
                card=hits[0][2]
                if kind in {'Add counter','Remove counter'}: card['counter_total']=p['total']
                elif kind=='Edit stats': card.update(atk=p.get('atk'),defense=p.get('def'))
                else: card['position']='ATK' if kind=='To ATK' else 'DEF'
            else: gap(index,'Field attribute target not uniquely resolved')
        elif kind=='Admit defeat': state['result']={'loser':actor,'source_index':index}
        elif native_kind(kind)=='unclassified': gap(index,'Unsupported native operation; state change not reconstructed')
        if kind=='Shuffle hand' and len(p.get('hand',[]))!=len(state['players'][actor]['hand']):
            gap(index,'Shuffle hand size disagrees with observed inventory')
        # Card identities are a multiset in hand. prev/hand arrays are retained
        # in source; no position-to-copy lineage is assumed by this extractor.
        for n in names: state['players'][n]['hand'].sort(key=lambda x:x or '')
        records.append({'source_index':index,'seconds':p.get('seconds'),'game':state['game'],
                        'kind':kind,'actor':actor,'candidate':kind in KINDS and actor in names,
                        'after_concession':before.get('result') is not None,
                        'unresolved_prior_source_indexes':[g['source_index'] for g in gaps if
                            g['source_index'] < index and records[g['source_index']]['game']==state['game']],
                        'observed_action':{'private_log':text,'public_logs':[l.get('public_log') for l in logs(p)],
                                           'runtime_ref':runtime,'card_name':name,
                                           'source_zone':origin,'destination_zone':target,
                                           'attacking_ref':p.get('attacking_id') or (runtime if kind=='Attack directly' else None),
                                           'attacked_ref':p.get('attacked_id')},
                        'before':before,'after':deepcopy(state), 'gaps':deepcopy(gaps[local_start:])})
    return {'status':'unreviewed_observation_reconstruction','audience':'reviewer_only_contains_both_private_hands_and_outcomes',
            'source_url':source['url'],
            'source_payload_sha256':hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
            'extractor_version':EXTRACTOR_VERSION,
            'source_replay':source['replay_id'],
            'reviewed':False, 'legality_reviewed':False,
            'limitations':['No inferred chains, effect resolution, response windows or legal choices',
                           'Hands are name multisets; physical-copy lineage through shuffles remains unresolved',
                           'Unseen deck identities/order and sideboarding identities remain unknown',
                           'Default card stats, token position/type, attachments and summon negation require review',
                           'Snapshots include reviewer-only LP baseline derivation from later absolute updates',
                           'Observed next operation is not necessarily a complete strategic human decision'],
            'lp_baselines':[{'game':g,'player':n,'lp':lp} for (g,n),lp in baselines.items()],
            'records':records,'gaps':gaps}

def extract_observations(replay):
    """Extract validated source observations, never a scored case/player packet."""
    validate_json(replay)
    return _extract(replay['source_metadata']['data'], replay['source'])


def extraction_summary(report):
    records = report['records']
    candidates = [record for record in records if record['candidate']]
    return {key: report[key] for key in (
                'status', 'audience', 'source_url', 'source_payload_sha256',
                'extractor_version', 'source_replay', 'reviewed', 'legality_reviewed',
                'limitations', 'lp_baselines', 'gaps')} | {
        'source_events': len(records),
        'games': max(record['game'] for record in records),
        'candidate_decision_points': len(candidates),
        'candidates_before_concession': sum(not record['after_concession'] for record in candidates),
        'candidates_after_concession': sum(record['after_concession'] for record in candidates),
        'candidate_kinds': dict(Counter(record['kind'] for record in candidates)),
        'reviewed_scored_cases': 0, 'player_packets_generated': 0}


def write_extraction(report, directory):
    """Save reviewer-only artifacts to a fresh directory, refusing overwrite."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    summary = extraction_summary(report)
    artifacts = {'states-and-actions.json': report,
                 'decision-review.json': {key: value for key, value in report.items() if key != 'records'} | {
                     'records': [record for record in report['records'] if record['candidate']]},
                 'summary.json': summary}
    for name, value in artifacts.items():
        with (directory/name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    return summary
