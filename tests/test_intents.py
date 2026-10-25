from copy import deepcopy
import json
import unittest
import test_session as fixtures
from harness.runner.intents import parse_intent, translate_intent
from harness.runner.state_tools import build
from harness.engine.actions import apply

class IntentTests(unittest.TestCase):
    setUp = fixtures.SessionTests.setUp
    start = fixtures.SessionTests.start

    def scenario(self):
        state, _, _ = self.start("open")
        state["active_player"] = "agent"
        state["phase"] = "main1"
        state["pending_decision"] = {"actor":"agent","window":"main_phase_action"}
        return state

    def test_slots_allowance_response_and_no_self_approval(self):
        state = self.scenario(); card = state["players"]["agent"]["hand"][0]["instance_id"]
        original = deepcopy(state)
        proposal = translate_intent(state, {"action":"normal_summon","card":card,"zone":"M-3","position":"ATK"})
        self.assertEqual(state, original)
        self.assertNotIn("moderator_approved", proposal)
        with self.assertRaises(ValueError):build(state, proposal)
        proposal.update(moderator_approved=True,public_summary_reviewed=True)
        updated = apply(state, build(state, proposal))
        self.assertEqual(updated["players"]["agent"]["monster_zones"][2]["instance_id"],card)
        self.assertTrue(updated["players"]["agent"]["normal_summon_used"])
        self.assertEqual(updated["pending_decision"],{"actor":"human","window":"summon_negation"})
        self.assertEqual(updated["pending_effects"],original["pending_effects"])

    def test_zone_zero_occupied_and_second_normal_are_rejected(self):
        state = self.scenario(); card = state["players"]["agent"]["hand"][0]["instance_id"]
        for zone in ["S-0","S-999","players/agent/spell_trap_zones/2"]:
            with self.assertRaises(ValueError):translate_intent(state,{"action":"set","card":card,"zone":zone})
        state["players"]["agent"]["spell_trap_zones"][2]={"instance_id":"occupied","card_id":1}
        with self.assertRaises(ValueError):translate_intent(state,{"action":"set","card":card,"zone":"S-3"})
        state["players"]["agent"]["normal_summon_used"]=True
        with self.assertRaises(ValueError):translate_intent(state,{"action":"set","card":card,"zone":"M-3"})
        proposal=translate_intent(state,{"action":"set","card":card,"zone":"S-2"})
        self.assertNotIn("normal_summon",[op["op"] for op in proposal["operations"]])
        self.assertNotIn(card,proposal["public_summary"])

    def test_no_patch_injection_and_no_unselected_cost_repair(self):
        with self.assertRaises(ValueError):parse_intent(json.dumps({"action":"end_turn","operations":[]}))
        state=self.scenario();card=state["players"]["agent"]["hand"][0]["instance_id"]
        intent={"action":"activate","card":card,"zone":"S-3"}
        with self.assertRaises(ValueError):translate_intent(state,intent)
        other=state["players"]["agent"]["hand"][1]["instance_id"]
        review={"cost_operations":[{"op":"move","card":other,"to":["players","agent","graveyard"]}]}
        with self.assertRaises(ValueError):translate_intent(state,intent,reviewed_activation=review)

    def test_end_request_keeps_turn_and_opponent_window(self):
        state=self.scenario()
        proposal=translate_intent(state,{"action":"end_turn"})
        proposal.update(moderator_approved=True,public_summary_reviewed=True)
        result=apply(state,build(state,proposal))
        self.assertEqual(result["turn"],state["turn"])
        self.assertEqual(result["active_player"],"agent")
        self.assertEqual(result["phase"],"end")
        self.assertEqual(result["pending_decision"],{"actor":"human","window":"end_phase_response"})

    def test_activation_costs_are_cumulative_and_preserve_chosen_ids(self):
        state=self.scenario();card=state["players"]["agent"]["hand"][0]["instance_id"]
        other=state["players"]["agent"]["hand"][1]["instance_id"]
        intent={"action":"activate","card":card,"zone":"S-3","cost_cards":[other]}
        review={"effect":"Pending reviewed effect","cost_operations":[
            {"op":"lp","player":"agent","delta":-800},
            {"op":"move","card":other,"to":["players","agent","graveyard"]}]}
        proposal=translate_intent(state,intent,reviewed_activation=review)
        proposal.update(moderator_approved=True,public_summary_reviewed=True)
        result=apply(state,build(state,proposal))
        self.assertEqual(result["players"]["agent"]["lp"],state["players"]["agent"]["lp"]-800)
        self.assertEqual(result["players"]["agent"]["graveyard"][-1]["instance_id"],other)
        self.assertEqual(result["pending_decision"],{"actor":"human","window":"chain_response"})
        self.assertEqual(len(result["chain"]),1)
        cost={"op":"lp","player":"agent","delta":-state["players"]["agent"]["lp"]}
        with self.assertRaises(ValueError):translate_intent(state,{**intent,"cost_cards":[]},reviewed_activation={"cost_operations":[cost,cost]})
        with self.assertRaises(ValueError):translate_intent(state,intent,reviewed_activation={"cost_operations":"invalid"})

    def test_off_turn_chain_response_self_cost_and_no_resolution(self):
        state=self.scenario();state['active_player']='human'
        card=state['players']['agent']['hand'].pop(0)
        state['players']['agent']['graveyard'].append(card)
        identity=card['instance_id']
        original={'id':'intent-chain-2','actor':'human','name':'Pending opponent effect','targets':[]}
        state['chain']=[original]
        state['pending_effects']=[{'id':'pending-attack','owner':'human','kind':'attack'}]
        review={'effect':'Reviewed response','cost_operations':[
            {'op':'move','card':identity,'to':['players','agent','banished']}]}
        intent={'action':'activate','card':identity,'cost_cards':[identity]}
        plan=translate_intent(state,intent,reviewed_activation=review)
        plan.update(moderator_approved=True,public_summary_reviewed=True)
        result=apply(state,build(state,plan))
        self.assertEqual(result['chain'][0],original)
        self.assertEqual(len({link['id'] for link in result['chain']}),2)
        self.assertEqual(result['players']['agent']['banished'][-1]['instance_id'],identity)
        self.assertEqual(result['pending_effects'],state['pending_effects'])
        self.assertEqual(result['active_player'],'human')
        self.assertEqual(result['pending_decision']['actor'],'human')
        passed=translate_intent(state,{'action':'pass'})
        passed.update(moderator_approved=True,public_summary_reviewed=True)
        result=apply(state,build(state,passed))
        self.assertEqual(result['chain'],state['chain'])
        self.assertEqual(result['pending_effects'],state['pending_effects'])
        for intent in ({'action':'end_turn'}, {'action':'phase','phase':'end'}):
            with self.assertRaises(ValueError):translate_intent(state,intent)
        state['pending_decision']['actor']='human'
        with self.assertRaises(ValueError):translate_intent(state,{'action':'pass'})

    def test_lp_cost_cannot_pay_last_point_and_self_cost_requires_choice(self):
        state=self.scenario();card=state['players']['agent']['hand'].pop(0)
        state['players']['agent']['monster_zones'][0]=card;identity=card['instance_id']
        review={'cost_operations':[{'op':'move','card':identity,'to':['players','agent','graveyard']}]}
        with self.assertRaises(ValueError):
            translate_intent(state,{'action':'activate','card':identity},reviewed_activation=review)
        plan=translate_intent(state,{'action':'activate','card':identity,'cost_cards':[identity]},reviewed_activation=review)
        plan.update(moderator_approved=True,public_summary_reviewed=True)
        self.assertIsNone(apply(state,build(state,plan))['players']['agent']['monster_zones'][0])
        with self.assertRaises(ValueError):
            translate_intent(state,{'action':'activate','card':identity},reviewed_activation={
                'cost_operations':[{'op':'lp','player':'agent','delta':-state['players']['agent']['lp']}]})
