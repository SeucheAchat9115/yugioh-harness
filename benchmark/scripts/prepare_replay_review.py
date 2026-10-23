"""Reproduce selected reviewer fixtures; requires the pinned harness on PYTHONPATH.

This authors checkpoints, not a runtime action/effect engine or an approval bot.
Only explicit source-bound evaluator approvals are used; no blanket approval.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from yugioh_benchmark.extraction import extract_observations
from yugioh_benchmark.kpis import digest, validate_suite
from yugioh_benchmark.replay import load_bundle
from harness.engine.actions import validate_state
from harness.players.isolated import model_request
from harness.runner.duel import DuelRunner

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'benchmarks/review/db-json-40753-85958923'
HARNESS = 'd3f5a4193cdc81dea033742f9c639b63f21427eb'
REVIEWER = 'Codex evaluator preparation review, 2026-10-08; not an external human certification'
APPROVED = {333: ('D.D. Warrior Lady', 'monster_zones', 2),
            334: ('Mirror Force', 'spell_trap_zones', 2),
            335: ('Dark Bribe', 'spell_trap_zones', 3),
            336: ('Soul Exchange', 'spell_trap_zones', 1)}
SUPPLEMENTAL = {13,48,21,125,133,199,245,248,264,355,364,
                137,202,203,205,215,216,253,267,344}
PHASES = {'DP':'draw','SP':'standby','M1':'main1','BP':'battle','M2':'main2','EP':'end'}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')


def apply_followup_review(values, packets, records, state_for, context_for, catalog, pinned_rules):
    """Apply explicit, source-bound evaluator dispositions; never auto-approve."""
    review_path=FOLDER/'review-decisions.json'
    audit=json.loads(review_path.read_text(encoding='utf-8'))
    assert audit['source_payload_sha256']==values['manifest']['source_payload_sha256']
    rows={row['source']['source_index']:row for row in values['review-index']}
    assert set(map(int,audit['items']))=={i for i,row in rows.items() if row['status']=='pending_review'}
    for key, finding in audit['items'].items():
        i=int(key); record=records[i]; row=rows[i]; identity=row['id']
        assert finding['before_observation_sha256']==digest(record['before'])
        assert finding['recorded_action_sha256']==digest(record['observed_action'])
        assert finding['source_payload_sha256']==row['source']['payload_sha256']
        row['status']=finding['status'];row['review_finding']='review-decisions.json#items/'+key
        row['blockers']=[] if finding['status']=='approved_scoped' else [finding['finding'],*finding['required_next_steps']]
        evaluator=values['evaluator'][identity]
        evaluator.update(review_status=row['status'],blockers=deepcopy(row['blockers']),disposition=deepcopy(finding))
        if row['status']=='excluded':
            row['packet']=None;packets.pop(identity,None)
            evaluator['grading_status']='Excluded from independent action-initiation score; retained as source evidence'
            continue
        if row['status']!='approved_scoped':
            packets[identity]['runnable']=False
            evaluator['grading_status']='Reviewed and blocked; not eligible for scoring'
            continue
        contract=finding['contract'];kind=contract['kind'];chosen=contract['card'];zone=contract['zone'];slot=contract['slot']
        state,mapping=state_for(record)
        state['pending_decision']={'actor':'agent','window':'end_phase_action' if state['phase']=='end' else 'main_phase_action'}
        assert state['active_player']=='agent' and not record['gaps'] and not record['unresolved_prior_source_indexes']
        context=context_for(record,state,full_history=True)
        context['context_limits']['checkpoint_scope']='Reviewed fixed checkpoint: one action initiation, before opponent response; unknown deck/Fusion/Side identities and historical-dependent alternatives remain unavailable.'
        model_request(context)
        expected=deepcopy(state)
        if kind in {'set','normal_summon'}:
            player=state['players']['agent'];matches=[c for c in player['hand'] if c.get('card_id')==catalog[chosen]['id']]
            assert len(matches)==1 and player[zone][slot] is None and state['phase'] in {'main1','main2'}
            card=deepcopy(matches[0]);expected['players']['agent']['hand'].remove(card)
            expected['players']['agent'][zone][slot]=card
            if kind=='set':
                card['hidden']=True
                move={'kind':'set','card':chosen,'zone_type':'spell_trap'}
                expected['pending_decision']={'actor':'human','window':'after_set'}
                declared=f'Set {chosen} from my hand face-down in Spell/Trap Zone {slot+1}. Stop with an opponent response decision (actor human, window after_set); do not activate or resolve an effect.'
            else:
                assert catalog[chosen]['level']<=4 and not player['normal_summon_used']
                card.update(hidden=False,position='ATK')
                expected['players']['agent']['normal_summon_used']=True
                expected['pending_decision']={'actor':'human','window':'summon_negation'}
                move={'kind':'normal_summon','card':chosen,'position':'ATK'}
                declared=f'Attempt to Normal Summon {chosen} from my hand face-up in Attack Position in Monster Zone {slot+1}. Consume the Normal Summon allowance. Stop with an opponent summon-negation decision (actor human, window summon_negation). Do not confirm the summon, create or apply summon-trigger effects, activate an ignition effect, or decide an opponent response.'
        elif kind=='end_turn':
            assert state['phase'] in {'main1','main2','end'}
            expected['phase']='end';expected['pending_decision']={'actor':'human','window':'end_phase_response'}
            move={'kind':'end_turn'}
            declared='Request ending my turn. Enter End Phase and stop with an opponent response decision (actor human, window end_phase_response). Do not advance the turn, draw, resolve an effect or decide an opponent response.'
        else:raise ValueError('Unexpected explicitly reviewed action contract')
        validate_state(state);validate_state(expected)
        review={'status':'approved','reviewer':REVIEWER,'date':'2026-10-08','scope':'Observed fixed checkpoint, one basic action initiation only; not prior effect correctness, full deck or continuing match approval','evidence':[finding['finding'],'Own hand, public field, LP and pile inventory checked against pre-boundary observations','No unresolved extractor gap at this boundary; prior resolution outcomes accepted only as observed checkpoint facts','Conditional summon triggers and opponent responses are outside the endpoint'], 'historical_text_dependent_legality':'deferred for alternative effects','full_deck_reviewed':False}
        packets[identity]={'schema_version':'1.0','id':identity,'runnable':True,'player_context':context}
        evaluator.update(initial_state=state,expected_state=expected,human_move=move,rules=deepcopy(pinned_rules),review=review,grading_status='Reviewed scoped action initiation',normalization={'ignore':['wording','hand order','nonconsequential empty field slot'],'retain':['action kind','card name','position when relevant']},legality_rubric={'reference':'Basic action initiation under Perfect Circle profile; preserve continuous face-up effects and await actual opponent input','other_moves':'Independent legality review required; leave historically dependent or unknown-card alternatives pending','scope':'Observed checkpoint facts do not certify preceding manual effect execution'})
        if kind=='set':evaluator['expected_set_state']=deepcopy(expected)
        base={'source':deepcopy(row['source']),'review':review,'initial_state_sha256':digest(state),'rules':deepcopy(pinned_rules),'checkpoint':'evaluator.json#'+identity,'player_packet':row['packet'],'player_context_sha256':digest(context)}
        values['suite']['cases'] += [{**deepcopy(base),'id':identity+'-state','task':'state_recreation','declared_play':declared,'expected_state':expected},{**deepcopy(base),'id':identity+'-choice','task':'human_move_reproduction','human_move':move}]
    values['suite']['id']='db-json-40753-85958923-reviewed-actions-v2'
    values['suite']['cases'].sort(key=lambda c:(c['source']['source_index'],c['task']))
    validate_suite(values['suite'])
    counts=dict(Counter(row['status'] for row in values['review-index']))
    count=counts['approved_scoped']; manifest=values['manifest']
    manifest.update(id='db-json-40753-85958923-whole-match-review-v2',status_counts=counts,player_packets=len(packets),approved_checkpoints=count,suite_cases=2*count,kpi_denominators={'state_recreation':count,'human_move_agreement':count,'rule_correctness':2*count},scope='All 185 previous pending work items received a disposition; scoped fixed-checkpoint actions only, not full match execution',reviewed_previous_pending=185,review_decisions='review-decisions.json',review_decisions_sha256=digest(audit),disposition_pass_completed=True)
    return values,packets


def prepared():
    replay=load_bundle(ROOT/'replays/db-json-40753-85958923')
    extraction=extract_observations(replay); records=extraction['records']
    metadata=json.loads((ROOT/'benchmarks/card-metadata/db-json-40753-85958923.json').read_text(encoding='utf-8'))
    fields={'id','name','type','frameType','desc','race','archetype','atk','def','level','attribute','scale','linkval','linkmarkers','pend_desc','monster_desc'}
    catalog={c['api_card']['name']:{k:v for k,v in c['api_card'].items() if k in fields} for c in metadata['cards']}
    assets=FOLDER/'assets'
    common=(assets/'common.md').read_text(encoding='utf-8'); profile=(assets/'perfect-circle.md').read_text(encoding='utf-8')
    banlist=(assets/'perfect-circle-2007-09-01.json').read_bytes()
    rules_snapshot={'format':'perfect-circle','rules_version':'perfect-circle-2026-10-08',
                    'text_scope':'Historical profile with current card texts; no complete historical text overrides',
                    'precedence':'Perfect Circle profile overrides shared basics',
                    'common':common,'profile':profile}
    pinned_rules={'format':'perfect-circle','rules_version':'perfect-circle-2026-10-08',
                  'rules_sha256':digest(rules_snapshot),
                  'banlist_sha256':hashlib.sha256(banlist).hexdigest(),
                  'card_text_sha256':digest(catalog),
                  'historical_card_text_complete':False,
                  'legality_scope':'case-local action initiation; historical-text-dependent alternatives provisional'}
    public_rules='''Perfect Circle 2007 pilot (September 2007 banlist). 8000 LP,
5 opening cards, first player draws; first-turn Battle Phase is forbidden.
Five Monster and five Spell/Trap Zones. One Normal Summon OR Normal Set per
turn; a Level 4 monster can be Normal Summoned/Set without a Tribute. A Normal
Set is face-down Defense Position. Spell/Trap cards may be Set in empty S/T
slots during your Main Phase; setting does not activate their effects. A Trap
or Quick-Play Spell cannot be activated in the turn it was Set. Leave valid
opponent response opportunities to the moderator. Current supplied card texts
are provisional for historical-text-dependent effects. This is a single-decision
checkpoint, not a complete deck or a continuing duel: unseen deck and Extra/Side
identities are unavailable. Do not invent cards; stop before resolving a choice
that needs unavailable information. Choose your own next action from the
available information; do not try to retrieve the source replay or benchmark.
'''
    def state_for(record):
        observed=record['before']; actor=record['actor']
        names=list(observed['players']); mapping={actor:'agent',next(n for n in names if n!=actor):'human'}
        state={'game_id':'reference-checkpoint','mode':'agent-vs-agent','player_isolation':'enforced',
               'status':'active','revision':0,'turn':observed['turn'] or 1,
               'phase':PHASES.get(observed['phase'],'draw'),
               'active_player':mapping.get(observed['active_player'],'agent'),
               'players':{},'shared_zones':{'extra_monster_zones':[]},
               'presentation':{'show_agent_hand':False},'chain':[],'pending_effects':[],
               'pending_decision':{'actor':'agent','window':'main_phase_action' if record['source_index'] in APPROVED
                                   else 'unreviewed_observation'}}
        for name,observations in observed['players'].items():
            role=mapping[name]; cards={}
            def entry(card_name, identity, **attrs):
                result={'instance_id':identity,'owner':role,**attrs}
                if card_name in catalog:
                    info=catalog[card_name]; result['card_id']=info['id']; cards[str(info['id'])]=deepcopy(info)
                else: result['name']=card_name or 'Unobserved identity'
                return result
            hand=[entry(n,f'{role}-hand-{i+1}') for i,n in enumerate(observations['hand'])]
            def anonymous(zone, count):
                return [{'instance_id':f'{role}-{zone}-unknown-{i+1}','owner':role}
                        for i in range(count or 0)]
            detail={'lp':observations['lp'],'hand':hand,
                    'deck':anonymous('deck',observations['deck_count']),
                    'extra_deck':anonymous('extra',15),'side_deck':anonymous('side',15),
                    'monster_zones':[None]*5,'spell_trap_zones':[None]*5,'field_spell':None,
                    'graveyard':[],'banished':[],'cards':cards,
                    'normal_summon_used':False,'effect_usage':{},'restrictions':[]}
            # Reviewers use this as a usage hint, not a blanket rules certificate.
            for prior in records[:record['source_index']]:
                if prior['game']!=record['game']: continue
                if prior['kind'] in {'Pick first','Start turn'}: detail['normal_summon_used']=False
                if prior['actor']==name and prior['kind'] in {'Normal Summon','Set monster'}:
                    detail['normal_summon_used']=True
            for zone,c in observations['field'].items():
                obj=entry(c['name'],f"field-ref-{c['runtime_ref']}",hidden=c['face_down'])
                obj['owner']=mapping.get(c['owner'],role)
                if c['position'] is not None: obj['position']=c['position']
                for source,target in [('atk','atk'),('defense','def'),('counter_total','counters')]:
                    if source in c: obj[target]=deepcopy(c[source])
                dest='monster_zones' if zone.startswith('M-') else 'spell_trap_zones' if zone.startswith('S-') else None
                if dest: detail[dest][int(zone.split('-')[1])-1]=obj
                else: detail['field_spell']=obj
            for zone in ('graveyard','banished'):
                for i,c in enumerate(observations[zone]):
                    obj=entry(c['name'],f"pile-ref-{c['runtime_ref']}",hidden=False)
                    obj['owner']=mapping.get(c['owner'],role);detail[zone].append(obj)
            state['players'][role]=detail
        validate_state(state)
        return state,mapping
    def context_for(record,state,full_history=False):
        prior=[]
        for event in replay['events'][:record['source_index']]:
            if event['game']!=record['game']: continue
            logs=event['payload']['native'].get('log',[])
            if isinstance(logs,dict): logs=[logs]
            for log in logs:
                if log.get('public_log'): prior.append({'action':{'id':f"prior-{event['sequence']}",
                    'kind':event['kind'],'actor':log.get('username'),'public_summary':log['public_log']}})
        configuration={'format':'perfect-circle','banlist':'TCG pool 2007-09-01',
                       'rules_version':'perfect-circle-2026-10-08','settings':{
                           'starting_lp':8000,'opening_hand_size':5,'starting_player_draws':True,
                           'starting_player_battle_phase':False}}
        runner=SimpleNamespace(state=deepcopy(state),_fresh=lambda:None,packet=None,
                               journal={'events':prior},assets={'rules.md':{'content':public_rules}},
                               configuration=configuration)
        context=DuelRunner.context(runner,'agent',compact=True)
        if full_history:
            context['recent_events']=[{'id':event['action']['id'],'kind':event['action']['kind'],'actor':event['action']['actor'],'summary':event['action']['public_summary']} for event in prior]
            context['context_limits']['recent_events']=len(prior)
        context['context_limits']['checkpoint_scope']='single next action; unseen identities and chain/effect bookkeeping need review outside approved set cases'
        model_request(context)
        return context
    index=[]; packets={}; evaluator={}; suite={'schema_version':'1.0','id':'db-json-40753-85958923-reviewed-sets-v1','cases':[]}
    coverage=[]
    for record in records:
        i=record['source_index']; play=record['kind']
        supplemental=(i in SUPPLEMENTAL or play in {'Target card','To ATK','To DEF','Pick first','Admit defeat'})
        candidate=record['candidate'] or supplemental
        coverage.append({'source_index':i,'before_sequence':i+1,'game':record['game'],'play':play,
                         'classification':'decision_work_item' if candidate else 'supporting_observation'})
        if not candidate: continue
        identity=f'db-json-40753-85958923-before-{i+1:06d}'
        exclusion=record['after_concession'] or play in {'Start turn','Admit defeat'}
        status='excluded' if exclusion else 'approved_scoped' if i in APPROVED else 'pending_review'
        blockers=[]
        if record['after_concession']: blockers.append('After recorded concession; not a live decision')
        if play=='Start turn': blockers.append('Automatic turn progression, not an independent human choice')
        if play=='Admit defeat': blockers.append('Surrender is outside this action-initiation pilot')
        if i not in APPROVED and not exclusion:
            blockers+=['Review decision/response boundary and any chain/pending-effect bookkeeping',
                       'Review usage, attachment, token and physical-copy facts relevant to this boundary',
                       'Unseen deck/Extra/Side identities are unavailable; restrict scope or obtain them',
                       'Current card text is not complete historical text; affected rulings unresolved']
        if record['gaps'] or record['unresolved_prior_source_indexes']:
            blockers.append('Resolve recorded transition gaps and their downstream effects')
        source={'replay':replay['id'],'payload_sha256':replay['source']['payload_sha256'],
                'before_sequence':i+1,'source_index':i,'game':record['game'],'seconds':record['seconds']}
        index.append({'id':identity,'source':source,'actor':record['actor'],'play':play,
                      'status':status,'blockers':blockers,'packet':f'player-packets/{identity}.json' if not exclusion else None,
                      'grading':'evaluator.json#'+identity,'origin':'native_candidate' if record['candidate'] else 'supplemental_choice_or_setup_work_item'})
        evaluator[identity]={'source':source,'review_status':status,
                             'recorded_action':deepcopy(record['observed_action']),
                             'grading_status':'reviewed scoped set' if i in APPROVED else 'not eligible for scoring',
                             'blockers':blockers}
        if exclusion: continue
        state,mapping=state_for(record); context=context_for(record,state)
        packets[identity]={'schema_version':'1.0','id':identity,'runnable':i in APPROVED,
                           'player_context':context}
        if i not in APPROVED: continue
        chosen,zone,slot=APPROVED[i]
        player=state['players']['agent'];matches=[c for c in player['hand'] if c.get('card_id')==catalog[chosen]['id']]
        assert len(matches)==1 and player[zone][slot] is None and state['phase']=='main1'
        if zone=='monster_zones': assert not player['normal_summon_used'] and catalog[chosen]['level']==4
        expected=deepcopy(state); card=deepcopy(matches[0]); expected['players']['agent']['hand'].remove(card)
        card['hidden']=True
        if zone=='monster_zones':
            card['position']='DEF';expected['players']['agent']['normal_summon_used']=True
        expected['players']['agent'][zone][slot]=card
        expected['pending_decision']={'actor':'human','window':'after_set'}
        # This endpoint is a harness response-window convention supplied in the
        # declared-play contract; the native log does not record response passes.
        validate_state(expected)
        move={'kind':'set','card':chosen,'zone_type':'monster' if zone=='monster_zones' else 'spell_trap'}
        if zone=='monster_zones': move['position']='DEF'
        declared=f"Set {chosen} from my hand face-down in {'Monster' if zone=='monster_zones' else 'Spell/Trap'} Zone {slot+1}. Stop with an opponent response decision (actor human, window after_set); do not activate or resolve an effect."
        review={'status':'approved','reviewer':REVIEWER,'date':'2026-10-08',
                'scope':'Basic setting action only, independently reset fixed checkpoint; not full-game approval',
                'evidence':['Private source log identifies the card and destination',
                            'Batched opening names plus preceding named draw reproduce the hand',
                            'No previous activation, battle, chain or triggered effect in game 2 at these boundaries',
                            'Normal Set consumes the unused normal summon allowance; subsequent S/T sets do not',
                            'Known chosen card is eligible to be Set in the empty source slot'],
                'historical_text_dependent_legality':'deferred for alternative effects',
                'full_deck_reviewed':False}
        evaluator[identity].update(initial_state=state,expected_set_state=expected,human_move=move,
                                  rules=deepcopy(pinned_rules),review=review,
                                  normalization={'ignore':['wording','hand order','nonconsequential field slot for human agreement'],
                                                 'retain':['card name','action kind','zone type','monster DEF position']},
                                  legality_rubric={'valid_reference':'During own Main Phase with empty destination; level 4 Normal Set without Tribute if normal allowance unused; S/T set does not activate effect',
                                                   'invalid_examples':['Activate a newly set Trap in the same turn','Use a second Normal Summon/Set after the normal allowance is consumed','Skip or resolve an opponent response without input'],
                                                   'other_moves':'Judge independently of human agreement. If missing identities or historical text determine legality, leave grading pending; do not guess.'})
        base={'source':source,'review':review,'initial_state_sha256':digest(state),'rules':deepcopy(pinned_rules),
              'checkpoint':'evaluator.json#'+identity,'player_packet':f'player-packets/{identity}.json',
              'player_context_sha256':digest(context)}
        suite['cases'] += [{**deepcopy(base),'id':identity+'-state','task':'state_recreation',
                            'declared_play':declared,'expected_state':expected},
                           {**deepcopy(base),'id':identity+'-choice','task':'human_move_reproduction','human_move':move}]
    validate_suite(suite)
    manifest={'schema_version':'1.0','id':'db-json-40753-85958923-whole-match-review-v1',
              'source_replay':replay['id'],'source_payload_sha256':replay['source']['payload_sha256'],
              'source_events':len(records),'games':2,'decision_work_items':len(index),
              'status_counts':dict(Counter(row['status'] for row in index)),
              'player_packets':len(packets),'approved_checkpoints':len(APPROVED),'suite_cases':len(suite['cases']),
              'kpi_denominators':{'state_recreation':4,'human_move_agreement':4,'rule_correctness':8},
              'whole_game_fully_reviewed':False,'whole_game_model_run_completed':False,
              'suite':'suite.json','harness_commit':HARNESS,'reviewer':REVIEWER,
              'scope':'Full observed-match preparation index plus four scoped opening checkpoints; not a full autonomous match or win rate',
              'unknowns':['Unobserved deck/Extra/Side names/order','Runtime lineage through shuffles',
                          'Unlogged response windows, chains and pending effects','Historical texts deferred',
                          'Game 1 ownership conflict at source index 313'],
              'rules':pinned_rules,'asset_provenance':{'harness_commit':HARNESS,
                  'common_sha256':hashlib.sha256(common.encode()).hexdigest(),
                  'profile_sha256':hashlib.sha256(profile.encode()).hexdigest(),
                  'banlist_sha256':hashlib.sha256(banlist).hexdigest(),
                  'card_metadata':'../../card-metadata/db-json-40753-85958923.json'}}
    values={'manifest':manifest,'review-index':index,'timeline':coverage,'evaluator':evaluator,
            'suite':suite,'rules-snapshot':rules_snapshot,'card-texts':catalog}
    return apply_followup_review(values,packets,records,state_for,context_for,catalog,pinned_rules)


def main():
    values,packets=prepared()
    for path in (FOLDER/'player-packets').glob('*.json'):
        if path.stem not in packets:path.unlink()
    for name,value in values.items(): save(FOLDER/(('assets/' if name in {'rules-snapshot','card-texts'} else '')+name+'.json'),value)
    for identity,packet in packets.items(): save(FOLDER/'player-packets'/f'{identity}.json',packet)
    print(json.dumps(values['manifest'],indent=2))

if __name__=='__main__': main()
