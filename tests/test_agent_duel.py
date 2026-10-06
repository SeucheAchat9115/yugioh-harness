from copy import deepcopy
import json
import subprocess
import sys
import unittest
import test_session as fixtures
from harness.engine.session import start, validate_config
from harness.runner.duel import DuelRunner
from harness.integration.arena import Arena, ArenaClient
from harness.integration.mcp import rpc
from harness.storage.checkpoint import restore
from test_workflow import plan, packet, open_window


class AgentDuelTests(unittest.TestCase):
    setUp=fixtures.SessionTests.setUp
    tearDown=fixtures.SessionTests.tearDown

    def start(self):
        config=deepcopy(self.config)
        config['mode']='agent-vs-agent'
        config['human_deck']='decks/unassigned/branded-despia'
        return start(self.repo,config,self.private)

    def test_two_managed_decks_private_hands_guides_and_set_cards(self):
        initial,game,path=self.start()
        from harness.storage.snapshots import collect
        assets = collect(game)
        self.assertIn('decks/human/branded-despia/deck.json', assets)
        self.assertIn('decks/agent/dracotail/deck.json', assets)
        with DuelRunner(path,game) as runner:
            first=initial['players']['human']['hand'][0]
            second=initial['players']['agent']['hand'][0]
            for actor,card in [('human',first),('agent',second)]:
                runner.workflow.execute(f'set-{actor}',plan(runner,[{'op':'move','card':card['instance_id'],
                    'to':['players',actor,'spell_trap_zones',0],'attributes':{'hidden':True}}],kind='set'))
            for actor,other in [('human','agent'),('agent','human')]:
                context=runner.context(actor)
                self.assertIn('hand',context['state']['players'][actor])
                self.assertNotIn('hand',context['state']['players'][other])
                self.assertNotIn('extra_deck',context['state']['players'][other])
                self.assertNotIn('card_id',context['state']['players'][other]['spell_trap_zones'][0])
                self.assertIn('card_id',context['state']['players'][actor]['spell_trap_zones'][0])
                self.assertTrue(all(name.startswith(f'decks/{actor}/') for name in context['guides']))
                self.assertNotIn('deck_inventory',context)
                self.assertNotIn('remaining_deck_order',json.dumps(context))
            moderator=runner.context('moderator')
            self.assertTrue(all('hand' in player for player in moderator['state']['players'].values()))
            self.assertEqual(set(moderator['deck_inventory']),{'human','agent'})
            self.assertEqual(len(moderator['guides']),2)
            spectator=runner.context('public')
            self.assertTrue(all('hand' not in player for player in spectator['state']['players'].values()))
            self.assertEqual(spectator['guides'],{})

    def test_player_one_packet_and_execution_do_not_expose_hand_to_spectator(self):
        initial,game,path=self.start()
        with DuelRunner(path,game) as runner:
            opened=open_window(runner)
            for card in initial['players']['human']['hand']:
                self.assertNotIn(card['instance_id'],json.dumps(opened))
            prompt=packet(runner);prompt['recommendations'][0]['label']='PRIVATE_AGENT_ONE_OPTION'
            shown=runner.workflow.present(prompt)
            self.assertNotIn('PRIVATE_AGENT_ONE_OPTION',json.dumps(shown))
            from harness.rendering.decision import render
            self.assertNotIn('PRIVATE_AGENT_ONE_OPTION',render(runner.state,prompt))
            self.assertNotIn('PRIVATE_AGENT_ONE_OPTION',json.dumps(runner.context('agent')))
            self.assertIn('PRIVATE_AGENT_ONE_OPTION',json.dumps(runner.context('human')))


    def test_role_bound_gateway_rejects_other_player_and_moderation(self):
        _,game,path=self.start()
        with DuelRunner(path,game) as runner:
            arena=Arena(runner,{'human':'first-token','agent':'second-token','moderator':'mod-token'})
            for request in [{'op':'view','player':'moderator'},{'op':'view','player':'agent'},
                            {'op':'step','request_id':'forged','request':{}},{'op':'recover'},
                            {'op':'submit','player':'agent','decision_id':'x','request_id':'y','response':'1'}]:
                result=arena.request('first-token',request)
                self.assertEqual(result['error']['code'],'role_forbidden')
            self.assertEqual(arena.request('bad',{'op':'view'})['error']['code'],'unauthorized')
            self.assertTrue(arena.request('first-token',{'op':'view'})['ok'])
            self.assertTrue(arena.request('second-token',{'op':'view'})['ok'])
            self.assertTrue(arena.request('mod-token',{'op':'view','player':'moderator'})['ok'])

    def test_private_hand_override_rejected_and_checkpoint_preserved(self):
        config=deepcopy(self.config);config['mode']='agent-vs-agent';config['presentation']['show_agent_hand']=True
        with self.assertRaises(ValueError):validate_config(config)
        _,game,path=self.start()
        with DuelRunner(path,game) as runner:
            open_window(runner,'agent')
            shown=runner.workflow.present(packet(runner))
            runner.workflow.submit(shown['decision_id'],'queued','1','agent')
            before=deepcopy(runner.state)
        restored=path.parent.parent/'restored'/'state.json'
        restore(path.with_name('checkpoint.json'),restored,game)
        with DuelRunner(restored,game) as runner:
            self.assertEqual(runner.state,before)
            self.assertEqual(runner.workflow.data['submissions']['queued']['status'],'submitted')

    def test_independent_mcp_clients_share_one_arena(self):
        _,game,path=self.start()
        credentials=path.parent.parent/'arena'
        process=subprocess.Popen([sys.executable,'-m','harness.integration.arena','--state',str(path),
                                  '--game-dir',str(game),'--private-dir',str(credentials)],
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True, encoding="utf-8")
        try:
            ready=json.loads(process.stdout.readline())
            self.assertTrue(ready['ready'])
            first=ArenaClient(ready['credentials']['player_1'])
            second=ArenaClient(ready['credentials']['player_2'])
            moderator=ArenaClient(ready['credentials']['moderator'])
            self.assertEqual(len(rpc(first,{'jsonrpc':'2.0','id':1,'method':'tools/list'})['result']['tools']),4)
            self.assertEqual(len(rpc(moderator,{'jsonrpc':'2.0','id':1,'method':'tools/list'})['result']['tools']),7)
            self.assertEqual(rpc(first,{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{
                'name':'duel_step','arguments':{'request_id':'x','request':{}}}})['error']['code'],-32602)
            request={'kind':'choice','actor':'moderator','expected_revision':0,'moderator_approved':True,
                     'public_summary_reviewed':True,'public_summary':'Agent 1 decision opened.',
                     'operations':[{'op':'decision','value':{'actor':'human','window':'main-phase'}}]}
            self.assertTrue(moderator.request({'op':'step','request_id':'open','request':request})['ok'])
            prompt={'expected_revision':1,'awaiting_user':True,'recommendations':[{'label':'Pass','reason':'Keep resources.'}],
                    'question':'Choose an intention.','option_review':{'complete':False,'meaningful_choices':None}}
            shown=moderator.request({'op':'present','packet':prompt})['result']
            self.assertNotIn('prompt',second.request({'op':'view'})['result'])
            self.assertTrue(first.request({'op':'submit','decision_id':shown['decision_id'],'request_id':'choice','response':'1'})['ok'])
            context=moderator.request({'op':'view','player':'moderator'})['result']
            self.assertEqual(context['submitted_intentions'][0]['request_id'],'choice')
            self.assertNotIn('executions',first.request({'op':'status'})['result'])
            gateway=subprocess.run([sys.executable,'-m','harness.integration.mcp','--credential',ready['credentials']['player_1']],
                input=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'duel_context','arguments':{}}})+'\n',
                text=True, encoding="utf-8",capture_output=True,check=True)
            self.assertFalse(json.loads(gateway.stdout)['result']['isError'])
            next_request={**request,'expected_revision':1,'operations':[{'op':'decision','value':{'actor':'agent','window':'response'}}]}
            self.assertTrue(moderator.request({'op':'step','request_id':'review-first','submission_id':'choice','request':next_request})['ok'])
            next_prompt={**prompt,'expected_revision':2}
            next_shown=moderator.request({'op':'present','packet':next_prompt})['result']
            self.assertNotIn('prompt',first.request({'op':'view'})['result'])
            self.assertTrue(second.request({'op':'submit','decision_id':next_shown['decision_id'],'request_id':'second-choice','response':'1'})['ok'])
            finish={**request,'kind':'finish','expected_revision':2,'operations':[{'op':'decision','value':None},
                {'op':'lp','player':'human','delta':-8000},{'op':'status','value':'finished'}]}
            result=moderator.request({'op':'step','request_id':'finish','submission_id':'second-choice','request':finish})
            self.assertTrue(result['ok'])
            self.assertTrue(all('hand' not in player for player in result['result']['state']['players'].values()))
            self.assertEqual(first.request({'op':'status'})['result']['status'],'finished')
            for name in ('player_1','player_2','moderator'):
                if sys.platform != 'win32':
                    self.assertEqual((credentials/f'{name}.json').stat().st_mode & 0o777,0o600)
                else:
                    self.assertTrue((credentials/f'{name}.json').is_file())
        finally:
            process.terminate()
            process.communicate(timeout=5)
