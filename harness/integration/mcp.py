"""Dependency-free MCP stdio server. Codex supplies the LLM; this process keeps state."""
import argparse
from copy import deepcopy
import json
import sys
from time import perf_counter
from pathlib import Path
from harness.runner.duel import DuelRunner
from harness.__main__ import respond

TOOLS={
 'duel_context':('Get permitted state, card text, rules, and guide excerpts.',{'player':{'type':'string','enum':['human','agent','moderator','public']},'card_ids':{'type':'array','items':{'type':['string','integer']}}},[],'view'),
 'duel_agent_context':('Get compact perspective-filtered state, relevant exact card text and bounded guidance. Use card_ids for focused Extra/Side text.',{'player':{'type':'string','enum':['human','agent','moderator','public']},'card_ids':{'type':'array','items':{'type':['string','integer']}}},[],'view'),
 'duel_present':('Persist a reviewed decision packet and its numbered choices.',{'packet':{'type':'object'}},['packet'],'present'),
 'duel_submit':('Persist human or agent input bound to a decision ID; does not execute it.',{'decision_id':{'type':'string'},'request_id':{'type':'string'},'response':{'type':['string','integer']},'player':{'type':'string','enum':['human','agent']}},['decision_id','request_id','response'],'submit'),
 'duel_step':('Apply moderator-reviewed bookkeeping operations with retry protection.',{'request_id':{'type':'string'},'request':{'type':'object'},'submission_id':{'type':'string'}},['request_id','request'],'step'),
 'duel_status':('Inspect current revision, decision ID, and receipt statuses.',{},[],'status'),
 'duel_recover':('Recover local projections from the journal after a storage failure.',{},[],'recover'),
}


CONVERSATIONAL_TOOLS = {
 'duel_decks': ('List complete selectable deck bundles.', {}, [], 'decks'),
 'duel_games': ('List saved local duels without exposing private cards.', {}, [], 'games'),
 'duel_start': ('Initialize an agreed duel internally; no user terminal steps.', {'config': {'type': 'object'}, 'rules_text': {'type': 'string'}}, ['config', 'rules_text'], 'start'),
 'duel_resume': ('Resume an existing local duel without reshuffling.', {'game_id': {'type': 'string'}}, ['game_id'], 'resume'),
 'duel_next': ('Get the next human display, private subagent task, or moderator review. Never show subagent or moderator payloads to the user.', {}, [], 'next'),
 'duel_player_start': ('Reserve a bounded player attempt after declaring host capabilities under the saved cooperative/enforced policy; call before spawning.', {'task_id': {'type': 'string'}, 'request_id': {'type': 'string'}, 'isolation': {'type': 'object'}, 'timeout_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 120}}, ['task_id', 'request_id', 'isolation'], 'player_start'),
 'duel_player_bind': ('Save the native host child handle for cancellation and resume. Never pass this moderator tool to a player.', {'task_id': {'type': 'string'}, 'attempt_id': {'type': 'string'}, 'child_id': {'type': 'string'}}, ['task_id', 'attempt_id', 'child_id'], 'player_bind'),
 'duel_player_fail': ('Record child timeout, cancellation, or failure. Confirm termination only after the host has stopped the child.', {'task_id': {'type': 'string'}, 'attempt_id': {'type': 'string'}, 'reason': {'type': 'string', 'enum': ['timeout', 'cancelled', 'malformed', 'transport_error', 'host_shutdown', 'isolation_failed']}, 'terminated': {'type': 'boolean'}}, ['task_id', 'attempt_id', 'reason'], 'player_fail'),
 'duel_agent_result': ('Store the response from the assigned player child; does not execute it.', {'task_id': {'type': 'string'}, 'attempt_id': {'type': 'string'}, 'response': {'type': ['string', 'integer']}}, ['task_id', 'attempt_id', 'response'], 'agent_result'),
 'duel_human_reply': ('Bind natural-language or numbered human input to the displayed question.', {'decision_id': {'type': 'string'}, 'request_id': {'type': 'string'}, 'response': {'type': ['string', 'integer']}}, ['decision_id', 'request_id', 'response'], 'human_reply'),
}


def rpc(duel,message):
    if not isinstance(message,dict) or message.get('jsonrpc')!='2.0':
        return {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request'}}
    identity=message.get('id')
    method=message.get('method')
    if identity is None:return None
    role=getattr(duel,'role','moderator')
    catalog = {**TOOLS, **CONVERSATIONAL_TOOLS} if getattr(duel, 'conversational', False) else TOOLS
    available=catalog if role=='moderator' else {name:TOOLS[name] for name in ('duel_context','duel_agent_context','duel_submit','duel_status')}
    if method=='initialize':
        result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},
                'serverInfo':{'name':'yugioh-harness','version':'1.0.0'},
                'instructions':('You are the single conversational orchestrator. Read agents/orchestrator/AGENT.md and skills/duel-orchestrator/SKILL.md. Handle all runtime calls internally; delegate player choices sequentially with permitted contexts. Adjudicate rules, preserve privacy, and save locally only.' if role=='moderator' else f'You are the player in slot {role}, not the referee. Use only your own context, choose a legal intention, and submit it with the decision ID. The moderator executes actions. Never request opponent or moderator context.')}
    elif method=='ping':result={}
    elif method=='tools/list':
        definitions=[]
        for name,(description,properties,required,_) in available.items():
            properties=deepcopy(properties)
            if role!='moderator' and 'player' in properties:properties['player']['enum']=[role]
            definitions.append({'name':name,'description':description,
                'inputSchema':{'type':'object','properties':properties,'required':required,'additionalProperties':False}})
        result={'tools':definitions}
    elif method=='tools/call':
        params=message.get('params',{})
        name=params.get('name') if isinstance(params,dict) else None
        arguments=params.get('arguments',{}) if isinstance(params,dict) else None
        if name not in available or not isinstance(arguments,dict):
            return {'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':'Invalid tool call'}}
        _,properties,required,operation=available[name]
        if any(key not in arguments for key in required) or any(key not in properties for key in arguments):
            return {'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':'Invalid tool arguments'}}
        started=perf_counter()
        request={'op':operation,**arguments}
        if name == 'duel_agent_context':request['compact']=True
        if role!='moderator' and operation in ('view','submit'):request.setdefault('player',role)
        response=duel.request(request) if hasattr(duel,'request') else respond(duel,json.dumps(request))
        response['harness_elapsed_ms']=round((perf_counter()-started)*1000,2)
        result={'content':[{'type':'text','text':json.dumps(response,ensure_ascii=False)}],'isError':not response['ok']}
    else:return {'jsonrpc':'2.0','id':identity,'error':{'code':-32601,'message':'Method not found'}}
    return {'jsonrpc':'2.0','id':identity,'result':result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path)
    parser.add_argument('--private-root',type=Path)
    parser.add_argument('--state',type=Path)
    parser.add_argument('--game-dir',type=Path)
    parser.add_argument('--credential',type=Path)
    args=parser.parse_args()
    if args.repo:
        if args.credential or args.state or args.game_dir:parser.error('Choose repository lobby or a direct session')
        from harness.integration.service import DuelService
        service = DuelService(args.repo, args.private_root)
        try:run_stdio(service)
        finally:service.close()
        return
    if args.private_root:parser.error('private-root requires repo')
    if args.credential:
        if args.state or args.game_dir:parser.error('Choose credential or direct session paths')
        from harness.integration.arena import ArenaClient
        transport=ArenaClient(args.credential)
        run_stdio(transport)
    else:
        if not args.state or not args.game_dir:parser.error('Set state/game-dir or credential')
        with DuelRunner(args.state,args.game_dir) as duel:run_stdio(duel)


def run_stdio(duel):
    for line in sys.stdin:
        try:response=rpc(duel,json.loads(line))
        except (ValueError,TypeError,KeyError,AttributeError,OSError):
            response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Malformed request or unavailable transport'}}
        if response is not None:print(json.dumps(response,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
