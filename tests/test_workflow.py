from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_session as fixtures
from harness.runner.duel import DuelRunner, RecoveryRequired
from harness.runner.loop import DuelLoop
from harness.players.adapters import CallbackPlayer
from harness.storage.checkpoint import restore


def plan(runner,operations,kind='choice',**extra):
    return {'kind':kind,'actor':'moderator','expected_revision':runner.state['revision'],
            'moderator_approved':True,'public_summary_reviewed':True,
            'public_summary':'Reviewed temporary scenario action.','operations':operations,**extra}


def packet(runner):
    return {'expected_revision':runner.state['revision'],'awaiting_user':True,'role':'Moderator / Coach',
            'events':[],'recommendations':[{'label':'Pass','reason':'Keep resources.'},
                                           {'label':'Choose another action','reason':'Consider a legal alternative.'}],
            'question':'Your move?','option_review':{'complete':False,'meaningful_choices':None}}


def open_window(runner,actor='human'):
    return runner.workflow.execute(f'window-{runner.state["revision"]}',plan(runner,[
        {'op':'decision','value':{'actor':actor,'window':'main-phase'}}]))


class WorkflowTests(unittest.TestCase):
    setUp=fixtures.SessionTests.setUp
    tearDown=fixtures.SessionTests.tearDown
    start=fixtures.SessionTests.start

    def test_bound_numbered_input_retry_and_restart(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            open_window(runner)
            display=runner.workflow.present(packet(runner))
            identity=display['decision_id']
            accepted=runner.workflow.submit(identity,'human-1','1')
            self.assertEqual(accepted['intention']['text'],'Pass')
            self.assertEqual(runner.workflow.submit(identity,'human-1','1'),accepted)
            with self.assertRaises(ValueError):runner.workflow.submit(identity,'human-1','2')
            with self.assertRaises(ValueError):runner.workflow.submit('old','different','1')
            with self.assertRaises(ValueError):runner.workflow.submit(identity,'different','2')
        with DuelRunner(path,game) as runner:
            request=plan(runner,[{'op':'decision','value':None}])
            first=runner.workflow.execute('apply-1',request,'human-1')
            self.assertFalse(first['duplicate'])
            duplicate=runner.workflow.execute('apply-1',request,'human-1')
            self.assertTrue(duplicate['duplicate'])
            self.assertEqual(runner.state['revision'],2)
            with self.assertRaises(ValueError):runner.workflow.execute('apply-1',{**request,'public_summary':'Changed'},'human-1')
        with DuelRunner(path,game) as runner:
            self.assertTrue(runner.workflow.execute('apply-1',request,'human-1')['duplicate'])
            self.assertEqual(runner.state['revision'],2)

    def test_state_tools_move_lp_counter_and_shuffle_replay(self):
        initial,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            card=initial['players']['human']['hand'][0]
            request=plan(runner,[{'op':'move','card':card['instance_id'],'to':['players','human','monster_zones',0],
                                 'attributes':{'position':'face-up attack'}},
                                {'op':'lp','player':'human','delta':-100},
                                {'op':'usage','player':'human','effect':'scenario','value':{'used':True,'turn':1}},
                                {'op':'shuffle','player':'agent'}],kind='move')
            runner.workflow.execute('tools-1',request)
            order=deepcopy(runner.state['players']['agent']['deck'])
            runner.workflow.execute('tools-1',request)
            self.assertEqual(order,runner.state['players']['agent']['deck'])
            self.assertEqual(runner.state['players']['human']['lp'],7900)
            self.assertEqual(runner.state['players']['human']['monster_zones'][0]['instance_id'],card['instance_id'])
        with DuelRunner(path,game) as runner:self.assertEqual(order,runner.state['players']['agent']['deck'])

    def test_checkpoint_carries_submissions_and_decision_ids(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            open_window(runner)
            display=runner.workflow.present(packet(runner))
            runner.workflow.submit(display['decision_id'],'queued','any free-text action')
        destination=path.parent.parent/'restored'/'state.json'
        restore(path.with_name('checkpoint.json'),destination,game)
        with DuelRunner(destination,game) as runner:
            self.assertEqual(runner.packet['decision_id'],display['decision_id'])
            self.assertEqual(runner.workflow.data['submissions']['queued']['status'],'submitted')

    def test_failed_save_recovery_then_retry_does_not_repeat_action(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            request=plan(runner,[{'op':'lp','player':'human','delta':-100}],kind='damage')
            with patch('harness.runner.duel.publish_verified',side_effect=OSError('fail')):
                with self.assertRaises(RecoveryRequired):runner.workflow.execute('fault',request)
            runner.recover()
            result=runner.workflow.execute('fault',request)
            self.assertTrue(result['duplicate'])
            self.assertEqual(runner.state['players']['human']['lp'],7900)
            self.assertEqual(runner.state['revision'],1)

    def test_context_rules_guides_and_hidden_boundary(self):
        _,game,path=self.start('blind')
        (game/'rules.md').write_text('Scenario rules: starting player skips the draw.')
        from harness.storage.checkpoint import write_checkpoint
        journal=json.loads(path.with_name('journal.json').read_text())
        write_checkpoint(path,game,journal)
        with DuelRunner(path,game) as runner:
            context=runner.context('agent')
            self.assertIn('skips',context['rules']['text'])
            self.assertTrue(context['guides'])
            self.assertTrue(all('decks/agent/' in name for name in context['guides']))
            moderator=runner.context('moderator')
            self.assertNotIn('human',moderator['deck_inventory'])
            self.assertNotIn('remaining_deck_order',json.dumps(moderator))
            inventory=moderator['deck_inventory']['agent']
            self.assertEqual(inventory,sorted(inventory,key=lambda card:(card['card_id'],card['instance_id'])))

    def test_decision_id_cannot_change_menu_and_opponent_options_stay_private(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            open_window(runner,'agent')
            options=packet(runner);options['recommendations'][0]['label']='OPPONENT_PRIVATE_OPTION'
            display=runner.workflow.present(options)
            self.assertNotIn('OPPONENT_PRIVATE_OPTION',json.dumps(display))
            self.assertNotIn('OPPONENT_PRIVATE_OPTION',json.dumps(runner.context('human')))
            self.assertIn('OPPONENT_PRIVATE_OPTION',json.dumps(runner.context('agent')))
            changed={**options,'decision_id':display['decision_id'],'question':'Changed prompt'}
            with self.assertRaises(ValueError):runner.workflow.present(changed)

    def test_complete_host_driven_duel_and_human_pause(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            def moderator(request):
                if request['stage']=='review_intent':
                    actor=request['intention']['player']
                    if actor=='human':
                        return {'action':plan(runner,[{'op':'decision','value':{'actor':'agent','window':'response'}}])}
                    return {'action':plan(runner,[{'op':'decision','value':None},{'op':'lp','player':'human','delta':-8000},
                                                 {'op':'status','value':'finished'}],kind='finish')}
                if runner.state['pending_decision'] is None:
                    return {'action':plan(runner,[{'op':'decision','value':{'actor':'human','window':'main-phase'}}],
                        automatic=True,option_review={'complete':True,'meaningful_choices':0,'basis':'public-rules-verified',
                                                      'reason':'Scenario initial setup is compulsory.'})}
                return {'packet':packet(runner)}
            agent=CallbackPlayer(lambda context:{'response':'1','request_id':'agent-choice'})
            loop=DuelLoop(runner,moderator,{'agent':agent})
            waiting=loop.run()
            self.assertEqual(waiting['status'],'awaiting_input')
            self.assertIn('**Board:**',waiting['text'])
            runner.workflow.submit(waiting['decision_id'],'human-choice','1')
            result=loop.run()
            self.assertEqual(result['status'],'finished')
            self.assertIn('**Board:**',result['text'])
            self.assertEqual(len(runner.journal['events']),3)
            self.assertTrue(loop.metrics)

    def test_mcp_process_handles_multiple_tools_without_reloading(self):
        _,game,path=self.start('open')
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                  {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'duel_context','arguments':{'player':'human'}}},
                  {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'duel_status','arguments':{}}}]
        result=subprocess.run([sys.executable,'-m','harness.integration.mcp','--state',str(path),'--game-dir',str(game)],
                               input='\n'.join(json.dumps(message) for message in messages)+'\n',text=True,capture_output=True,check=True)
        responses=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses),4)
        self.assertEqual(len(responses[1]['result']['tools']),6)
        self.assertFalse(responses[2]['result']['isError'])

    def test_null_template_id_blind_counts_and_generic_operations(self):
        _,game,path=self.start('blind')
        with DuelRunner(path,game) as runner:
            request=plan(runner,[{'op':'counts','player':'human','deltas':{'hand_count':-1}},
                                {'op':'place','card':{'instance_id':'human-revealed','name':'Publicly declared monster','owner':'human'},
                                 'to':['players','human','monster_zones',0]}],kind='summon')
            runner.workflow.execute('blind-summon',request)
            self.assertEqual(runner.state['players']['human']['hand_count'],4)
            open_window(runner)
            prompt=packet(runner);prompt['decision_id']=None
            shown=runner.workflow.present(prompt)
            self.assertIsInstance(shown['decision_id'],str)
            runner.workflow.submit(shown['decision_id'],'free-text','End my turn')
            runner.workflow.execute('free-text-reviewed',plan(runner,[{'op':'decision','value':None},
                {'op':'set','path':['players','human','normal_summon_used'],'value':True}]),'free-text')
            self.assertTrue(runner.state['players']['human']['normal_summon_used'])
        with self.assertRaises(ValueError):runner.context('human')

    def test_explicit_token_place_remove_and_material_attachment(self):
        initial,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            runner.workflow.execute('create-token',plan(runner,[{'op':'place','card':{'instance_id':'token-example','token':True,'owner':'human'},
                                                               'to':['players','human','monster_zones',0]}]))
            runner.workflow.execute('remove-token',plan(runner,[{'op':'remove','card':'token-example'}]))
            card=initial['players']['human']['hand'][0]
            material=initial['players']['human']['hand'][1]
            runner.workflow.execute('attach',plan(runner,[{'op':'move','card':card['instance_id'],
                'to':['players','human','monster_zones',0],'attributes':{'materials':[]}},
                {'op':'move','card':material['instance_id'],'to':['players','human','monster_zones',0,'materials']}]))
            self.assertEqual(runner.state['players']['human']['monster_zones'][0]['materials'][0]['instance_id'],material['instance_id'])
            runner.workflow.execute('detach',plan(runner,[{'op':'move','card':material['instance_id'],
                                                         'to':['players','human','graveyard']}]))
            self.assertEqual(runner.state['players']['human']['graveyard'][0]['instance_id'],material['instance_id'])

    def test_mcp_end_to_end_input_and_execution_retry(self):
        _,game,path=self.start('open')
        def call(number,name,arguments):
            return {'jsonrpc':'2.0','id':number,'method':'tools/call','params':{'name':name,'arguments':arguments}}
        with DuelRunner(path,game) as runner:
            window=plan(runner,[{'op':'decision','value':{'actor':'human','window':'main-phase'}}])
            options=packet(runner);options['expected_revision']=1;options['decision_id']='mcp-decision'
        resolution={**window,'expected_revision':1,'operations':[{'op':'decision','value':None}]}
        execute={'request_id':'resolve-mcp','submission_id':'input-mcp','request':resolution}
        messages=[call(1,'duel_step',{'request_id':'open-mcp','request':window}),
                  call(2,'duel_present',{'packet':options}),
                  call(3,'duel_submit',{'decision_id':'mcp-decision','request_id':'input-mcp','response':1}),
                  call(4,'duel_step',execute),call(5,'duel_step',execute)]
        result=subprocess.run([sys.executable,'-m','harness.integration.mcp','--state',str(path),'--game-dir',str(game)],
                               input='\n'.join(json.dumps(message) for message in messages)+'\n',text=True,capture_output=True,check=True)
        responses=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertTrue(all(not response['result']['isError'] for response in responses))
        receipt=json.loads(responses[-1]['result']['content'][0]['text'])
        self.assertTrue(receipt['result']['duplicate'])
        self.assertIn('harness_elapsed_ms',receipt)
        with DuelRunner(path,game) as runner:self.assertEqual(runner.state['revision'],2)
