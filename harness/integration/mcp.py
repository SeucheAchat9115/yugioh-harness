"""Dependency-free MCP stdio server. Codex supplies the LLM; this process keeps state."""
import argparse
import json
import sys
from time import perf_counter
from pathlib import Path
from harness.runner.duel import DuelRunner
from harness.__main__ import respond

TOOLS={
 'duel_context':('Get permitted state, card text, rules, and guide excerpts.',{'player':{'type':'string','enum':['human','agent','moderator']},'card_ids':{'type':'array','items':{'type':['string','integer']}}},[],'view'),
 'duel_present':('Persist a reviewed decision packet and its numbered choices.',{'packet':{'type':'object'}},['packet'],'present'),
 'duel_submit':('Persist human or agent input bound to a decision ID; does not execute it.',{'decision_id':{'type':'string'},'request_id':{'type':'string'},'response':{'type':['string','integer']},'player':{'type':'string','enum':['human','agent']}},['decision_id','request_id','response'],'submit'),
 'duel_step':('Apply moderator-reviewed bookkeeping operations with retry protection.',{'request_id':{'type':'string'},'request':{'type':'object'},'submission_id':{'type':'string'}},['request_id','request'],'step'),
 'duel_status':('Inspect current revision, decision ID, and receipt statuses.',{},[],'status'),
 'duel_recover':('Recover local projections from the journal after a storage failure.',{},[],'recover'),
}


def rpc(duel,message):
    if not isinstance(message,dict) or message.get('jsonrpc')!='2.0':
        return {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request'}}
    identity=message.get('id')
    method=message.get('method')
    if identity is None:return None
    if method=='initialize':
        result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},
                'serverInfo':{'name':'yugioh-harness','version':'1.0.0'},
                'instructions':'Trusted moderator tools. The LLM adjudicates rules; use player views for opponent choices. Never expose moderator context or agent-private choices to the human. Submit input before applying a reviewed step; saves are local only.'}
    elif method=='ping':result={}
    elif method=='tools/list':
        result={'tools':[{'name':name,'description':description,
                         'inputSchema':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}
                        for name,(description,properties,required,_) in TOOLS.items()]}
    elif method=='tools/call':
        params=message.get('params',{})
        name=params.get('name') if isinstance(params,dict) else None
        arguments=params.get('arguments',{}) if isinstance(params,dict) else None
        if name not in TOOLS or not isinstance(arguments,dict):
            return {'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':'Invalid tool call'}}
        _,properties,required,operation=TOOLS[name]
        if any(key not in arguments for key in required) or any(key not in properties for key in arguments):
            return {'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':'Invalid tool arguments'}}
        started=perf_counter()
        response=respond(duel,json.dumps({'op':operation,**arguments}))
        response['harness_elapsed_ms']=round((perf_counter()-started)*1000,2)
        result={'content':[{'type':'text','text':json.dumps(response,ensure_ascii=False)}],'isError':not response['ok']}
    else:return {'jsonrpc':'2.0','id':identity,'error':{'code':-32601,'message':'Method not found'}}
    return {'jsonrpc':'2.0','id':identity,'result':result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--game-dir',type=Path,required=True)
    args=parser.parse_args()
    with DuelRunner(args.state,args.game_dir) as duel:
        for line in sys.stdin:
            try:response=rpc(duel,json.loads(line))
            except (ValueError,TypeError,KeyError,AttributeError):
                response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Malformed request'}}
            if response is not None:print(json.dumps(response,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
