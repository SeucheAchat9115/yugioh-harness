from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.engine.actions import append, initialize, publish, replay
from harness.storage.checkpoint import restore, verify_checkpoint, write_checkpoint
from harness.rendering.decision import render
from test_actions import action, change, state


def fixture(mode="open"):
    result = replay(initialize(state()))
    result["active_player"] = "human"
    result["pending_decision"] = {"actor": "human", "window": "main-phase-open"}
    human = result["players"]["human"]
    human["hand"] = [{"instance_id": "human-1", "card_id": 789}]
    human["deck"] = [{"instance_id": "human-future", "card_id": 999}]
    human["cards"] = {"789": {"name": "Human starter"}, "999": {"name": "Future secret"}}
    result["players"]["agent"]["cards"] = {"123": {"name": "Opponent secret"}, "456": {"name": "Opponent future"}}
    result["mode"] = mode
    if mode == "blind":
        for zone, count in (("hand", "hand_count"), ("deck", "deck_count"), ("extra_deck", "extra_count"), ("side_deck", "side_count")):
            human[count] = len(human[zone])
            human[zone] = None
        del human["cards"]
    return result


def packet(current):
    return {"expected_revision": current["revision"], "role": "Moderator / Coach",
            "events": ["A recorded action finished."], "awaiting_user": True,
            "recommendations": [{"label": "Summon the starter", "reason": "Develop your board."},
                                {"label": "End the phase", "reason": "Preserve your hand."}],
            "question": "Which move?", "option_review": {"complete": True, "meaningful_choices": 2}}


class ExperienceTests(unittest.TestCase):
    def test_fixed_format_and_human_view_hide_opponent_and_future(self):
        current = fixture()
        text = render(current, packet(current))
        labels = ["**Game:**", "**Role:**", "**Turn / phase:**", "**Decision:**", "**LP:**",
                  "**You counts:**", "**Opponent counts:**", "**Your hand:**", "**Board:**",
                  "**Chain (activation order):**", "**Usage / restrictions:**", "**What happened:**",
                  "**Coach — recommended moves:**", "**Your choice:**"]
        positions = [text.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("H1: Human starter", text)
        self.assertIn("your own words", text)
        for secret in ("Opponent secret", "Opponent future", "Future secret", "human-future", "copy-1"):
            self.assertNotIn(secret, text)

    def test_blind_format_never_reads_human_hand(self):
        current = fixture("blind")
        current["players"]["human"]["graveyard"] = [{"instance_id": "revealed", "name": "Revealed monster"}]
        draft = packet(current)
        draft["recommendations"] = [{"label": "End the phase", "reason": "Keep your hidden resources."}]
        draft["option_review"] = {"complete": False, "meaningful_choices": None}
        text = render(current, draft)
        self.assertIn("private; managed by you", text)
        self.assertIn("Revealed monster", text)
        self.assertNotIn("Human starter", text)

    def test_two_distinct_recommendations_and_revision_required(self):
        current = fixture()
        draft = packet(current)
        draft["recommendations"].pop()
        with self.assertRaises(ValueError):
            render(current, draft)
        draft = packet(current)
        draft["recommendations"][1] = draft["recommendations"][0]
        with self.assertRaises(ValueError):
            render(current, draft)
        draft = packet(current)
        draft["expected_revision"] = 100
        with self.assertRaises(ValueError):
            render(current, draft)

    def test_empty_menu_does_not_prove_no_choice(self):
        current = fixture()
        draft = packet(current)
        draft.update(recommendations=[], awaiting_user=False, option_review={"complete": False})
        with self.assertRaises(ValueError):
            render(current, draft)

    def test_no_choice_packet_cannot_default_to_a_question_or_invent_moves(self):
        current = fixture()
        review = {"complete": True, "meaningful_choices": 0, "basis": "open-state-verified", "reason": "No legal response."}
        draft = packet(current)
        draft.update(recommendations=[], option_review=review)
        del draft["awaiting_user"]
        with self.assertRaises(ValueError):
            render(current, draft)
        draft = packet(current)
        draft.update(awaiting_user=False, option_review=review)
        with self.assertRaises(ValueError):
            render(current, draft)

    def test_verified_no_choice_continuation_is_recorded_and_explained(self):
        current = fixture()
        review = {"complete": True, "meaningful_choices": 0, "basis": "open-state-verified",
                  "reason": "No legal response exists under the current restrictions."}
        automatic = action(current, "pass", [change(["pending_decision"], current["pending_decision"], None)])
        automatic.update(automatic=True, option_review=review)
        journal, final = append(initialize(current), automatic)
        self.assertTrue(journal["events"][0]["action"]["automatic"])
        self.assertEqual(replay(journal), final)
        draft = packet(final)
        draft.update(recommendations=[], awaiting_user=False, option_review=review,
                     events=["No legal response was available; advanced automatically."])
        text = render(final, draft)
        self.assertIn("advanced automatically", text)
        self.assertIn("No choice at this step", text)

    def test_auto_continuation_rejects_unknown_blind_options_and_actual_choices(self):
        for mode, review in (("blind", {"complete": True, "meaningful_choices": 0, "basis": "open-state-verified", "reason": "Unknown hand"}),
                            ("open", {"complete": True, "meaningful_choices": 2, "basis": "open-state-verified", "reason": "Two legal choices"}),
                            ("open", {"complete": False, "meaningful_choices": 0, "basis": "open-state-verified", "reason": "Incomplete review"})):
            current = fixture(mode)
            automatic = action(current, "pass")
            automatic.update(automatic=True, option_review=review)
            with self.assertRaises(ValueError):
                append(initialize(current), automatic)

    def test_checkpoint_restores_hidden_state_rules_and_pending_decision(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            game = root / "repo/games/casual/test"
            game.mkdir(parents=True)
            (game / "game.json").write_text(json.dumps({"id": "test", "mode": "open", "rules_version": "test-v1"}), encoding="utf-8")
            (game / "rules.md").write_text("Agreed test rules.\n", encoding="utf-8")
            deck = game / "decks/human/test"
            deck.mkdir(parents=True)
            (deck / "deck.ydk").write_text("#main\n789\n999\n#extra\n!side\n", encoding="utf-8")
            private = root / "private"
            private.mkdir()
            current = fixture()
            current["status"] = "paused"
            journal = initialize(current)
            publish(journal, private / "state.json", game)
            context = packet(current)
            context["hand_refs"] = {"H1": "human-1"}
            saved = write_checkpoint(private / "state.json", game, journal, context)
            data = json.loads(saved.read_text(encoding="utf-8"))
            self.assertEqual(verify_checkpoint(data), current)
            self.assertEqual(data["state"]["players"]["human"]["hand"], current["players"]["human"]["hand"])
            self.assertEqual(data["state"]["players"]["agent"]["deck"], current["players"]["agent"]["deck"])
            destination = root / "other-repo/games/casual/test"
            resumed = restore(saved, root / "resumed/state.json", destination)
            self.assertEqual(resumed, current)
            from harness.storage.snapshots import collect
            self.assertEqual(collect(destination)["rules.md"]["content"], "Agreed test rules.\n")
            self.assertEqual(json.loads((root / "resumed/checkpoint.json").read_text(encoding="utf-8"))["decision_packet"], context)
            with self.assertRaises(ValueError):
                restore(saved, root / "resumed/state.json", destination)
            from harness.storage.archive import load_replay, archive_state
            self.assertEqual(load_replay(destination), archive_state(current))
            public = load_replay(destination, perspective='public')
            self.assertNotIn("Opponent secret", json.dumps(public))
            for name in ("state.json", "actions.md", "log.md", "resume.md"):
                self.assertFalse((destination / name).exists())

    def test_checkpoint_blind_human_remains_unknown_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            game = root / "game"
            game.mkdir()
            (game / "game.json").write_text(json.dumps({"id": "test", "mode": "blind"}), encoding="utf-8")
            private = root / "private"
            private.mkdir()
            current = fixture("blind")
            saved = write_checkpoint(private / "state.json", game, initialize(current))
            data = json.loads(saved.read_text(encoding="utf-8"))
            self.assertIsNone(data["state"]["players"]["human"]["hand"])
            self.assertIsNotNone(data["blind_human_resume"])
            data["state"]["turn"] += 1
            with self.assertRaises(ValueError):
                verify_checkpoint(data)

    def test_pending_numbered_choices_survive_pause_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            game = root / "game"
            game.mkdir()
            (game / "game.json").write_text(json.dumps({"id": "test", "mode": "open"}), encoding="utf-8")
            private = root / "private"
            private.mkdir()
            current = fixture()
            journal = initialize(current)
            context = packet(current)
            context["hand_refs"] = {"H1": "human-1"}
            write_checkpoint(private / "state.json", game, journal, context)
            for status in ("paused", "active"):
                decision = action(current, "choice", [change(["status"], current['status'], status)], status)
                journal, current = append(journal, decision)
                publish(journal, private / "state.json", game)
                saved = json.loads((private / "checkpoint.json").read_text(encoding="utf-8"))
                self.assertEqual(saved["decision_packet"]["hand_refs"], context["hand_refs"])
                self.assertEqual(saved["decision_packet"]["recommendations"], context["recommendations"])
                self.assertEqual(saved["decision_packet"]["expected_revision"], current["revision"])

    def test_checkpoint_assets_reject_hash_and_path_changes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            game = root / "game"
            game.mkdir()
            (game / "game.json").write_text(json.dumps({"id": "test", "mode": "open"}), encoding="utf-8")
            (game / "rules.md").write_text("Rules", encoding="utf-8")
            private = root / "private"
            private.mkdir()
            path = write_checkpoint(private / "state.json", game, initialize(fixture()))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["assets"]["rules.md"]["content"] = "Changed"
            with self.assertRaises(ValueError):
                verify_checkpoint(data)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["assets"]["../outside"] = data["assets"].pop("rules.md")
            with self.assertRaises(ValueError):
                verify_checkpoint(data)


if __name__ == "__main__":
    unittest.main()
