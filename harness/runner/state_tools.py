"""Build guarded actions from small bookkeeping operations; LLM judges legality."""
from copy import deepcopy
from uuid import uuid4
from harness.engine.actions import apply
from harness.engine.session import draw
import secrets

PLAYER_ZONES = {'hand','deck','extra_deck','side_deck','monster_zones','spell_trap_zones','graveyard','banished','field_spell'}
SLOTS = {'monster_zones','spell_trap_zones','field_spell'}


def locate(state, identity):
    found=[]
    def walk(card,path):
        if not isinstance(card,dict):return
        if card.get('instance_id')==identity:found.append(path)
        for index, material in enumerate(card.get('materials',[])):walk(material,path+['materials',index])
    for player,details in state['players'].items():
        for zone in PLAYER_ZONES:
            value=details[zone]
            if isinstance(value,list):
                for i,card in enumerate(value):walk(card,['players',player,zone,i])
            elif isinstance(value,dict):walk(value,['players',player,zone])
    for zone,cards in state.get('shared_zones',{}).items():
        for i,card in enumerate(cards):walk(card,['shared_zones',zone,i])
    if len(found)!=1:raise ValueError('Card reference is missing or ambiguous')
    return found[0]


def parent(state,path):
    value=state
    for key in path[:-1]:value=value[key]
    return value,path[-1]


def build(state, request, hand_refs=None):
    if not isinstance(request,dict) or request.get('moderator_approved') is not True or request.get('public_summary_reviewed') is not True:
        raise ValueError('Moderator legality and public narration review required')
    if request.get('expected_revision')!=state['revision']:raise ValueError('Stale revision')
    working=deepcopy(state)
    operations=request.get('operations')
    if not isinstance(operations,list):raise ValueError('Operations must be a list')
    for operation in operations:
        kind=operation['op']
        if kind=='move':
            identity=operation['card']
            identity=(hand_refs or {}).get(identity,identity)
            path=locate(working,identity)
            container,key=parent(working,path)
            card=container[key]
            if path[-1]=='field_spell' or path[-2] in SLOTS or (path[0]=='shared_zones' and len(path)==3):container[key]=None
            else:container.pop(key)
            destination=operation['to']
            if not isinstance(destination,list) or not destination or destination[0] not in ('players','shared_zones'):
                raise ValueError('Destination must be a card zone')
            if destination[0]=='players' and (len(destination)<3 or destination[2] not in PLAYER_ZONES):
                raise ValueError('Unknown destination zone')
            target,slot=parent(working,destination)
            value=target[slot]
            if isinstance(value,list):
                index=operation.get('index',len(value))
                value.insert(index,card)
            elif value is None:target[slot]=card
            else:raise ValueError('Destination slot is occupied')
            card.update(operation.get('attributes',{}))
        elif kind=='place':
            card=deepcopy(operation['card'])
            card.setdefault('instance_id',uuid4().hex)
            destination=operation['to']
            if destination[0] not in ('players','shared_zones'):raise ValueError('Expected card destination')
            target,slot=parent(working,destination)
            if isinstance(target[slot],list):target[slot].append(card)
            elif target[slot] is None:target[slot]=card
            else:raise ValueError('Destination occupied')
        elif kind=='remove':
            path=locate(working,operation['card'])
            container,key=parent(working,path)
            if path[-1]=='field_spell' or path[-2] in SLOTS or (path[0]=='shared_zones' and len(path)==3):container[key]=None
            else:container.pop(key)
        elif kind=='counts':
            if working['mode']!='blind' or operation['player']!='human':raise ValueError('Counts apply only to blind human zones')
            for key,delta in operation['deltas'].items():
                if key not in ('hand_count','deck_count','extra_count','side_count') or type(delta) is not int:raise ValueError('Invalid count delta')
                working['players']['human'][key]+=delta
        elif kind=='set':
            path=operation['path']
            if not path or path[0] not in ('players','shared_zones','pending_effects','pending_decision','chain'):raise ValueError('Unsupported custom path')
            target,key=parent(working,path)
            if key not in target and not isinstance(target,list):raise ValueError('Custom paths must exist')
            target[key]=deepcopy(operation['value'])
        elif kind=='lp':
            player=working['players'][operation['player']]
            player['lp']+=operation['delta']
        elif kind=='card':
            path=locate(working,(hand_refs or {}).get(operation['card'],operation['card']))
            container,key=parent(working,path)
            container[key].update(operation['attributes'])
        elif kind=='usage':
            working['players'][operation['player']]['effect_usage'][operation['effect']]=deepcopy(operation['value'])
        elif kind=='restrictions':
            working['players'][operation['player']]['restrictions']=deepcopy(operation['value'])
        elif kind=='decision':working['pending_decision']=deepcopy(operation.get('value'))
        elif kind=='chain':working['chain']=deepcopy(operation['value'])
        elif kind=='phase':working['phase']=operation['value']
        elif kind=='status':working['status']=operation['value']
        elif kind=='turn':
            working['turn']=operation['number'];working['active_player']=operation['player']
        elif kind=='normal_summon':working['players'][operation['player']]['normal_summon_used']=operation['used']
        elif kind=='pending_effects':working['pending_effects']=deepcopy(operation['value'])
        elif kind=='draw':draw(working,operation['player'],operation.get('count',1))
        elif kind=='shuffle':
            deck=working['players'][operation['player']]['deck']
            if deck is None:raise ValueError('Blind human shuffle is privately managed')
            secrets.SystemRandom().shuffle(deck)
        else:raise ValueError('Unsupported state operation')
    changes=[]
    # Diff changed zone/property roots, not entire players and their immutable card catalogs.
    for actor,details in working['players'].items():
        previous=state['players'][actor]
        if details.keys()!=previous.keys():
            changes.append({'path':['players',actor],'before':previous,'after':details})
        else:
            for key,value in details.items():
                if value!=previous[key]:
                    changes.append({'path':['players',actor,key],'before':previous[key],'after':value})
    for key in ('shared_zones','phase','turn','active_player','chain','pending_decision','pending_effects','status'):
        if working.get(key)!=state.get(key):changes.append({'path':[key],'before':state[key],'after':working[key]})
    action={key:deepcopy(request[key]) for key in ('kind','actor','expected_revision','moderator_approved','public_summary_reviewed','public_summary','automatic','option_review') if key in request}
    action.update(id=request.get('id',uuid4().hex),changes=changes)
    apply(state,action)
    return action
