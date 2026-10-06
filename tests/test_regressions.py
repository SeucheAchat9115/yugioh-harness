"""Regression coverage for privacy, bookkeeping, transport, recovery, and locking."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_session as fixtures
from harness.__main__ import respond
from harness.engine.actions import apply, initialize, replay
from harness.runner.duel import DuelRunner, RecoveryRequired
from harness.views.perspective import view
from test_actions import state, action, change


class IntegrityTests(unittest.TestCase):
    def test_cards_cannot_disappear_appear_or_change_identity(self):
        before = replay(initialize(state()))
        for changes in (
            [change(['players','agent','hand'],before['players']['agent']['hand'],[])],
            [change(['players','agent','graveyard'],[],[{'instance_id':'invented','card_id':123}])],
            [change(['players','agent','hand',0,'card_id'],123,999)],
            [change(['players','agent','monster_zones'],[None],[None,None])],
            [change(['players','agent','deck'],before['players']['agent']['deck'],[None])],
        ):
            with self.assertRaises(ValueError): apply(before,action(before,changes=changes))

    def test_control_changes_and_attached_materials_preserve_cards(self):
        before = replay(initialize(state()))
        card = {**before['players']['agent']['hand'][0], 'owner':'agent', 'controller':'human'}
        after = apply(before,action(before,changes=[
            change(['players','agent','hand'],before['players']['agent']['hand'],[]),
            change(['players','human','monster_zones',0],None,card)]))
        self.assertEqual(after['players']['human']['monster_zones'][0]['owner'],'agent')
        body = {**before['players']['agent']['hand'][0], 'materials':before['players']['agent']['deck']}
        after = apply(before,action(before,changes=[
            change(['players','agent','hand'],before['players']['agent']['hand'],[]),
            change(['players','agent','deck'],before['players']['agent']['deck'],[]),
            change(['players','agent','monster_zones',0],None,body)]))
        self.assertEqual(len(after['players']['agent']['monster_zones'][0]['materials']),1)

    def test_explicit_tokens_can_appear_and_disappear(self):
        before = replay(initialize(state()))
        token = {'instance_id':'token-1','token':True,'name':'Token'}
        after = apply(before,action(before,changes=[change(['players','agent','monster_zones',0],None,token)]))
        apply(after,action(after,changes=[change(['players','agent','monster_zones',0],token,None)]))
        with self.assertRaises(ValueError):
            apply(after,action(after,changes=[change(['players','agent','hand'],after['players']['agent']['hand'],[])]))

    def test_public_projections_drop_internal_fields_everywhere(self):
        current = state()
        current['chain'] = [{'actor':'agent','name':'Public effect','private_notes':'CANARY',
                             'resolution_choices':{'secret':'CANARY'},
                             'costs':[{'kind':'discard','private_notes':'CANARY'}]}]
        current['players']['agent']['graveyard']=[{'instance_id':'visible','card_id':123,'secret_analysis':'CANARY'}]
        current['players']['agent']['effect_usage']={'public-used':{'turn':1,'private_notes':'CANARY'}}
        current['players']['agent']['restrictions']=[{'kind':'public-lock','private_notes':'CANARY'}]
        current['pending_effects']=[{'name':'Public delayed','private_notes':'CANARY'},
                                    {'name':'CANARY','visibility':'private','owner':'agent'}]
        public=view(current,'public')
        self.assertNotIn('CANARY',json.dumps(public))
        self.assertEqual(public['pending_effects'][0]['name'],'Public delayed')
        self.assertIn('CANARY',json.dumps(view(current,'agent')['pending_effects']))


class SessionRegressions(unittest.TestCase):
    setUp=fixtures.SessionTests.setUp
    tearDown=fixtures.SessionTests.tearDown
    start=fixtures.SessionTests.start

    def test_context_includes_visible_text_delayed_effects_and_recent_events(self):
        initial,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            runner.record({'id':'delayed','kind':'choice','actor':'moderator','expected_revision':0,
                'moderator_approved':True,'public_summary_reviewed':True,'public_summary':'Public delayed effect registered.',
                'changes':[change(['pending_effects'],[],[{'name':'Public delayed','phase':'end'},
                            {'name':'OPPONENT_SECRET','visibility':'private','owner':'agent'}])]})
            context=runner.context('human')
            human_card=str(initial['players']['human']['hand'][0]['card_id'])
            self.assertIn('desc',context['cards'][human_card])
            self.assertEqual(context['recent_events'][-1]['id'],'delayed')
            self.assertEqual(context['state']['pending_effects'][0]['name'],'Public delayed')
            self.assertNotIn('OPPONENT_SECRET',json.dumps(context))
            # No card catalog entry for an identity visible only in the opponent's future Deck.
            visible=set(context['cards'])
            allowed=set()
            def collect(value):
                if isinstance(value,dict):
                    if 'card_id' in value:allowed.add(str(value['card_id']))
                    for child in value.values():collect(child)
                elif isinstance(value,list):
                    for child in value:collect(child)
            collect(context['state'])
            self.assertTrue(visible.issubset(allowed))
            permitted_hand={str(c['card_id']) for c in context['state']['players']['human']['hand']}
            self.assertTrue(permitted_hand.issubset(visible))
            self.assertNotIn('remaining_deck_order',json.dumps(context))

    def test_transport_handles_malformed_shapes_then_valid_request(self):
        _,game,path=self.start('open')
        requests=['[]','null','3','"text"','{"op":[]}','{"op":"command","request":[]}',
                  '{"op":"display","packet":null}','{bad','{"op":"capabilities"}']
        result=subprocess.run([sys.executable,'-m','harness','--state',str(path),'--game-dir',str(game)],
                              input='\n'.join(requests)+'\n',text=True, encoding="utf-8",capture_output=True,check=True)
        responses=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses),len(requests))
        self.assertTrue(all(r['error']['code']=='invalid_request' for r in responses[:-1]))
        self.assertTrue(responses[-1]['ok'])

    def test_projection_failure_blocks_and_recovers_recorded_action(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            request={'command':'draw','actor':'agent','expected_revision':0,'moderator_approved':True,'id':'once'}
            with patch('harness.runner.duel.publish_verified',side_effect=OSError('SECRET storage path')):
                response=respond(runner,json.dumps({'op':'command','request':request}))
            self.assertEqual(response['error']['code'],'recovery_required')
            self.assertTrue(response['error']['action_status']['recorded'])
            self.assertNotIn('SECRET',json.dumps(response))
            for operation in (lambda:runner.context('human'),lambda:runner.command(request),
                              lambda:runner.advance(lambda state:None)):
                with self.assertRaises(RecoveryRequired):operation()
            runner.recover()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))['revision'],1)
            self.assertEqual(len(runner.journal['events']),1)
            with self.assertRaises(ValueError):runner.command({**request,'expected_revision':1})
        with DuelRunner(path,game) as resumed:self.assertEqual(resumed.state['revision'],1)

    def test_journal_failure_does_not_claim_action_recorded(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            with patch('harness.runner.duel.save',side_effect=OSError('fail')):
                with self.assertRaises(RecoveryRequired) as failure:
                    runner.command({'command':'draw','actor':'agent','expected_revision':0,
                                    'moderator_approved':True,'id':'not-recorded'})
            self.assertFalse(failure.exception.action_status['recorded'])
            runner.recover()
            self.assertEqual(runner.state['revision'],0)

    def test_every_legacy_writer_respects_runner_lock(self):
        _,game,path=self.start('open')
        draft=path.with_name('action.json')
        draft.write_text('{}', encoding="utf-8")
        packet=path.with_name('decision.json')
        packet.write_text('{}', encoding="utf-8")
        commands=[
            ['harness.engine.actions','replay','--state',str(path),'--game-dir',str(game)],
            ['harness.engine.actions','record','--state',str(path),'--game-dir',str(game),'--action',str(draft)],
            ['harness.engine.session','draw','--state',str(path),'--game-dir',str(game),'--actor','agent'],
            ['harness.storage.checkpoint','save','--state',str(path),'--game-dir',str(game)],
            ['harness.rendering.decision','--state',str(path),'--game-dir',str(game),'--packet',str(packet)],
        ]
        before={p.name:p.read_bytes() for p in path.parent.glob('*.json')}
        with DuelRunner(path,game):
            for args in commands:
                result=subprocess.run([sys.executable,'-m',*args],capture_output=True,text=True, encoding="utf-8")
                self.assertNotEqual(result.returncode,0,args)
                self.assertIn('BlockingIOError',result.stderr,args)
        self.assertEqual(before,{p.name:p.read_bytes() for p in path.parent.glob('*.json')})

    def test_different_private_copy_cannot_write_same_game(self):
        _,game,path=self.start('open')
        import shutil
        copy_dir=path.parent.parent/'private-copy'
        shutil.copytree(path.parent,copy_dir)
        with DuelRunner(path,game):
            with self.assertRaises(BlockingIOError):DuelRunner(copy_dir/'state.json',game)
            result=subprocess.run([sys.executable,'-m','harness.engine.actions','replay',
                                   '--state',str(copy_dir/'state.json'),'--game-dir',str(game)],
                                  capture_output=True,text=True, encoding="utf-8")
            self.assertNotEqual(result.returncode,0)
            self.assertIn('BlockingIOError',result.stderr)

    def test_process_restart_can_recover_partial_projection_write(self):
        _,game,path=self.start('open')
        with DuelRunner(path,game) as runner:
            with patch('harness.runner.duel.publish_verified',side_effect=OSError('projection unavailable')):
                with self.assertRaises(RecoveryRequired):
                    runner.command({'command':'draw','actor':'agent','expected_revision':0,
                                    'moderator_approved':True,'id':'committed-before-crash'})
        subprocess.run([sys.executable,'-m','harness.engine.actions','replay','--state',str(path),
                        '--game-dir',str(game)],check=True,capture_output=True)
        with DuelRunner(path,game) as resumed:
            self.assertEqual(resumed.state['revision'],1)
            self.assertEqual(len(resumed.journal['events']),1)
