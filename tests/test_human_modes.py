"""Management modes preserve player privacy and checkpoint compatibility."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import test_session
from harness.engine import session
from harness.engine.actions import validate_no_choice, validate_state
from harness.engine.integrity import validate_transition
from harness.players.isolated import model_request
from harness.rendering.decision import render
from harness.runner.duel import DuelRunner
from harness.storage.checkpoint import verify_checkpoint


class HumanModeTests(unittest.TestCase):
    setUp = test_session.SessionTests.setUp
    tearDown = test_session.SessionTests.tearDown

    def start(self, mode):
        config = deepcopy(self.config)
        config['mode'] = mode
        if mode in ('managed', 'open'):
            config['human_deck'] = 'decks/unassigned/branded-despia'
        return session.start(self.repo, config, self.private)

    def test_managed_perspectives_hide_human_private_cards(self):
        state, _, _ = self.start('managed')
        hidden = {**state['players']['human']['hand'][0], 'hidden': True, 'owner': 'human'}
        state['players']['human']['spell_trap_zones'][0] = hidden
        state['shared_zones']['extra_monster_zones'][0] = hidden
        state['pending_effects'] = [{'id': 'secret', 'owner': 'human', 'visibility': 'private', 'name': 'Secret'}]
        state['players']['human']['effect_usage']['secret'] = state['pending_effects'][0]
        for viewer in ('agent', 'public'):
            projected = session.view(state, viewer)
            self.assertNotIn('hand', projected['players']['human'])
            self.assertNotIn('card_id', projected['players']['human']['spell_trap_zones'][0])
            self.assertNotIn('card_id', projected['shared_zones']['extra_monster_zones'][0])
            self.assertEqual(projected['pending_effects'], [])
            self.assertEqual(projected['players']['human']['effect_usage'], {})
        for viewer in ('human', 'moderator'):
            self.assertEqual(len(session.view(state, viewer)['players']['human']['hand']), 5)
            self.assertEqual(len(session.view(state, viewer)['pending_effects']), 1)

    def test_managed_context_and_resume_preserve_state(self):
        state, game, path = self.start('managed')
        self.assertEqual(verify_checkpoint(json.loads(path.with_name('checkpoint.json').read_text(encoding="utf-8"))), state)
        with DuelRunner(path, game) as runner:
            for actor in ('human', 'agent'):
                context = runner.context(actor)
                self.assertNotIn('remaining_deck_order', context['state']['players']['human'])
                self.assertTrue(all(name.startswith('decks/' + actor + '/') for name in context['guides']))
                self.assertEqual(model_request(context)['tools'], [])
            self.assertTrue(any(name.startswith('decks/human/') for name in runner.context('moderator')['guides']))
        packet = {'expected_revision': 0, 'recommendations': [], 'awaiting_user': True}
        self.assertIn('H1:', render(state, packet))
        self.assertIsNone(state['pending_decision'])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), state)

    def test_self_never_loads_human_deck_and_draws_counts_only(self):
        state, game, path = self.start('self')
        self.assertFalse((game / 'decks/human').exists())
        before = deepcopy(state)
        session.draw(state, 'human', 1)
        validate_state(state)
        validate_transition(before, state)
        for viewer in ('human', 'agent', 'moderator', 'public'):
            human = session.view(state, viewer)['players']['human']
            self.assertNotIn('hand', human)
            self.assertEqual(human['hand_count'], 6)
        self.assertIsNone(state['players']['human']['deck'])
        self.assertIsNotNone(json.loads(path.with_name('checkpoint.json').read_text(encoding="utf-8"))['blind_human_resume'])
        with self.assertRaises(ValueError):
            validate_no_choice(state, {'complete': True, 'meaningful_choices': 0,
                                      'basis': 'open-state-verified', 'reason': 'Unknown hand'})

    def test_self_rejects_deck_before_any_load(self):
        config = deepcopy(self.config)
        config.update(mode='self', human_deck='decks/unassigned/branded-despia')
        with patch.object(session, 'load_bundle') as load:
            with self.assertRaisesRegex(ValueError, 'must not receive'):
                session.start(self.repo, config, self.private)
            load.assert_not_called()

    def test_legacy_open_keeps_original_visibility_on_resume(self):
        state, game, path = self.start('open')
        with DuelRunner(path, game) as runner:
            self.assertEqual(runner.state['mode'], 'open')
            self.assertIn('hand', runner.context('agent')['state']['players']['human'])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), state)
