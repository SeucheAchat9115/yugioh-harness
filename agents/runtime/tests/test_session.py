from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "session.py"
sys.path.insert(0, str(SCRIPT.parent))
REPO = SCRIPT.parents[2]
spec = importlib.util.spec_from_file_location("duel_session", SCRIPT)
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.repo, self.private = root / "repo", root / "private"
        for slug in ("dracotail", "branded-despia"):
            shutil.copytree(REPO / "decks/unassigned" / slug,
                            self.repo / "decks/unassigned" / slug)
        self.config = {
            "id": "test-001", "mode": "blind", "format": "test-casual",
            "banlist": "explicit-test-rules", "rules_profile": "test-fixture",
            "rules_version": "1", "agent_deck": "decks/unassigned/dracotail",
            "human_deck": None, "human_deck_counts": {"main": 40, "extra": 15, "side": 15},
            "starting_player": "human", "presentation": {"show_agent_hand": False},
            "settings": {"starting_lp": 8000, "opening_hand_size": 5,
                         "starting_player_draws": False, "starting_player_battle_phase": False,
                         "field_layout": {"main_monster_zones": 5, "spell_trap_zones": 5,
                                          "extra_monster_zones": 2}},
        }

    def tearDown(self):
        self.temp.cleanup()

    def start(self, mode="blind"):
        config = deepcopy(self.config)
        config["mode"] = mode
        if mode == "open":
            config["human_deck"] = "decks/unassigned/branded-despia"
        return session.start(self.repo, config, self.private)

    def test_blind_human_identity_never_stored_or_exposed(self):
        state, game, _ = self.start()
        self.assertIsNone(state["players"]["human"]["hand"])
        self.assertIsNone(state["players"]["human"]["deck"])
        self.assertFalse((game / "decks/human").exists())
        for viewer in ("public", "human", "agent", "moderator"):
            human = session.view(state, viewer)["players"]["human"]
            self.assertNotIn("hand", human)
            self.assertNotIn("remaining_deck_order", human)
            self.assertEqual(human["hand_count"], 5)

    def test_blind_rejects_human_deck_before_loading(self):
        self.config["human_deck"] = "decks/unassigned/branded-despia"
        with patch.object(session, "load_bundle") as load:
            with self.assertRaisesRegex(ValueError, "must not receive"):
                session.start(self.repo, self.config, self.private)
            load.assert_not_called()

    def test_open_agent_knows_human_but_human_view_hides_agent(self):
        state, _, _ = self.start("open")
        agent = session.view(state, "agent")["players"]
        self.assertEqual(len(agent["human"]["hand"]), 5)
        self.assertEqual(len(agent["human"]["remaining_deck_order"]), 48)
        human = session.view(state, "human")["players"]
        self.assertEqual(len(human["human"]["hand"]), 5)
        self.assertNotIn("hand", human["agent"])
        self.assertNotIn("remaining_deck_order", human["human"])
        self.assertNotIn("hand", session.view(state, "public")["players"]["human"])

    def test_draws_preserve_order_across_save_resume(self):
        state, _, path = self.start("open")
        expected = deepcopy(state["players"]["agent"]["deck"][:2])
        resumed = json.loads(path.read_text())
        session.draw(state, "agent", 2)
        session.draw(resumed, "agent", 2)
        self.assertEqual(state, resumed)
        self.assertEqual(state["players"]["agent"]["hand"][-2:], expected)

    def test_blind_draw_only_changes_counts(self):
        state, _, _ = self.start()
        session.draw(state, "human", 1)
        player = state["players"]["human"]
        self.assertIsNone(player["hand"])
        self.assertEqual((player["hand_count"], player["deck_count"]), (6, 34))

    def test_set_cards_and_shared_zones_mask_identities(self):
        state, _, _ = self.start("open")
        hidden = {**state["players"]["human"]["hand"][0], "hidden": True, "owner": "human",
                  "original_name": "Private name", "atk": 3000, "private_notes": "Secret"}
        state["players"]["human"]["spell_trap_zones"][0] = hidden
        state["shared_zones"]["extra_monster_zones"][0] = hidden
        public = session.view(state, "public")
        self.assertNotIn("card_id", public["players"]["human"]["spell_trap_zones"][0])
        self.assertNotIn("name", public["shared_zones"]["extra_monster_zones"][0])
        self.assertNotIn("original_name", public["players"]["human"]["spell_trap_zones"][0])
        self.assertNotIn("atk", public["players"]["human"]["spell_trap_zones"][0])
        self.assertIn("card_id", session.view(state, "agent")["players"]["human"]["spell_trap_zones"][0])

    def test_private_state_in_repo_and_restart_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            session.start(self.repo, self.config, self.repo / "private")
        self.start()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.start()

    def test_failed_draw_does_not_mutate_state(self):
        state, _, _ = self.start()
        original = deepcopy(state)
        with self.assertRaisesRegex(ValueError, "Insufficient cards"):
            session.draw(state, "agent", 100)
        self.assertEqual(state, original)

    def test_invalid_visibility_option_cannot_reveal_agent_hand(self):
        self.config["presentation"]["show_agent_hand"] = "false"
        with self.assertRaisesRegex(ValueError, "explicit boolean"):
            session.start(self.repo, self.config, self.private)

    def test_cli_draw_and_replay_recover_exact_state(self):
        initial, game, path = self.start("open")
        expected = initial["players"]["agent"]["deck"][0]
        subprocess.run([sys.executable, str(SCRIPT), "draw", "--state", str(path),
                        "--game-dir", str(game), "--actor", "agent"], check=True, capture_output=True)
        final = json.loads(path.read_text())
        self.assertEqual(final["revision"], 1)
        self.assertEqual(final["players"]["agent"]["hand"][-1], expected)
        journal = json.loads(path.with_name("journal.json").read_text())
        self.assertEqual(len(journal["events"]), 1)
        path.write_text("{}")
        (game / "events.json").unlink()
        subprocess.run([sys.executable, str(SCRIPT.with_name("actions.py")), "replay",
                        "--state", str(path), "--game-dir", str(game)], check=True, capture_output=True)
        self.assertEqual(json.loads(path.read_text()), final)
        self.assertEqual(len(json.loads((game / "events.json").read_text())["events"]), 1)

    def test_cli_record_decision_and_reject_retry(self):
        _, game, path = self.start()
        draft = self.private / "action.json"
        draft.write_text(json.dumps({"id": "phase-1", "kind": "phase", "actor": "moderator",
            "expected_revision": 0, "moderator_approved": True, "public_summary_reviewed": True,
            "public_summary": "Advance to Standby Phase.", "changes": [
                {"path": ["phase"], "before": "draw", "after": "standby"}]}))
        command = [sys.executable, str(SCRIPT.with_name("actions.py")), "record",
                   "--state", str(path), "--game-dir", str(game), "--action", str(draft)]
        subprocess.run(command, check=True, capture_output=True)
        journal_before = path.with_name("journal.json").read_text()
        self.assertEqual(json.loads(path.read_text())["phase"], "standby")
        retry = subprocess.run(command, capture_output=True)
        self.assertNotEqual(retry.returncode, 0)
        self.assertEqual(path.with_name("journal.json").read_text(), journal_before)


if __name__ == "__main__":
    unittest.main()
