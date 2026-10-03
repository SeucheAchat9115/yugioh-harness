import json
from pathlib import Path
import sys
import tempfile
import unittest
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from actions import append, initialize, publish, replay


def state():
    player = {"lp": 8000, "hand": [{"instance_id": "copy-1", "card_id": 123}],
              "deck": [{"instance_id": "copy-2", "card_id": 456}], "extra_deck": [],
              "side_deck": [], "monster_zones": [None], "spell_trap_zones": [None],
              "field_spell": None, "graveyard": [], "banished": [], "cards": {},
              "normal_summon_used": False, "effect_usage": {}, "restrictions": []}
    human = deepcopy(player)
    human["hand"] = []
    human["deck"] = []
    return {"game_id": "test", "mode": "open", "status": "active", "turn": 1,
            "phase": "main1", "active_player": "agent", "chain": [],
            "players": {"agent": player, "human": human}, "shared_zones": {},
            "presentation": {"show_agent_hand": False}, "pending_effects": []}


def action(current, kind="choice", changes=None, identity="a1"):
    return {"id": identity, "kind": kind, "actor": "agent",
            "expected_revision": current["revision"], "moderator_approved": True,
            "public_summary_reviewed": True, "public_summary": "Decision recorded.",
            "changes": changes or []}


def change(path, before, after):
    return {"path": path, "before": before, "after": after}


class ActionsTests(unittest.TestCase):
    def test_move_and_replay_exact_copies(self):
        journal = initialize(state())
        current = replay(journal)
        card = current["players"]["agent"]["hand"][0]
        changes = [change(["players", "agent", "hand"], [card], []),
                   change(["players", "agent", "graveyard"], [], [card])]
        journal, final = append(journal, action(current, "move", changes))
        self.assertEqual(replay(journal), final)
        self.assertEqual(final["players"]["agent"]["graveyard"][0]["instance_id"], "copy-1")

    def test_reject_stale_duplicate_and_partial_failure(self):
        journal = initialize(state())
        current = replay(journal)
        original = deepcopy(journal)
        bad = action(current, changes=[change(["phase"], "main1", "end"), change(["turn"], 99, 2)])
        with self.assertRaises(ValueError):
            append(journal, bad)
        self.assertEqual(journal, original)
        journal, _ = append(journal, action(current))
        with self.assertRaises(ValueError):
            append(journal, action(current))
        with self.assertRaises(ValueError):
            append(journal, action(current, identity="new"))

    def test_chain_decisions_do_not_resolve_early(self):
        journal = initialize(state())
        current = replay(journal)
        link = {"id": "chain-1", "actor": "agent", "effect": "Declared effect"}
        journal, current = append(journal, action(current, "activate", [
            change(["chain"], [], [link]), change(["pending_decision"], None,
                                                  {"actor": "human", "window": "response"})]))
        with self.assertRaises(ValueError):
            append(journal, action(current, "resolve", [change(["chain"], [link], [])], "early"))
        journal, current = append(journal, action(current, "pass", [
            change(["pending_decision"], current["pending_decision"], None)], "pass"))
        self.assertEqual(current["chain"], [link])
        journal, current = append(journal, action(current, "resolve", [change(["chain"], [link], [])], "resolve"))
        self.assertEqual(current["chain"], [])

    def test_duplicate_physical_card_rejected(self):
        journal = initialize(state())
        current = replay(journal)
        with self.assertRaises(ValueError):
            append(journal, action(current, "move", [change(["players", "agent", "graveyard"], [],
                                                          current["players"]["agent"]["hand"])]))

    def test_blind_identities_and_negative_counts_rejected(self):
        initial = state()
        initial["mode"] = "blind"
        human = initial["players"]["human"]
        for zone in ("hand", "deck", "extra_deck", "side_deck"):
            human[zone] = None
            human[zone.replace("_deck", "") + "_count"] = 5
        journal = initialize(initial)
        current = replay(journal)
        for changes in ([change(["players", "human", "hand"], None, [{"card_id": 999}])],
                        [change(["players", "human", "hand_count"], 5, -1)],
                        [change(["players", "human", "spell_trap_zones", 0], None,
                                {"instance_id": "unknown", "hidden": True, "name": "Secret"})]):
            with self.assertRaises(ValueError):
                append(journal, action(current, changes=changes))

    def test_publication_excludes_private_changes(self):
        journal = initialize(state())
        current = replay(journal)
        journal, current = append(journal, action(current, "draw", [
            change(["players", "agent", "hand"], current["players"]["agent"]["hand"],
                   current["players"]["agent"]["hand"] + current["players"]["agent"]["deck"]),
            change(["players", "agent", "deck"], current["players"]["agent"]["deck"], [])]))
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "game"
            folder.mkdir()
            (folder / "game.json").write_text(json.dumps({"id": "test", "mode": "open"}))
            publish(journal, Path(root) / "state.json", folder)
            for name in ("events.json", "state.json", "actions.md"):
                text = (folder / name).read_text()
                self.assertNotIn("copy-2", text)
                self.assertNotIn("456", text)
            self.assertEqual(json.loads((Path(root) / "state.json").read_text()), current)

    def test_history_tampering_detected(self):
        journal = initialize(state())
        journal, _ = append(journal, action(replay(journal)))
        journal["events"][0]["action"]["changes"] = [change(["turn"], 1, 9)]
        with self.assertRaises(ValueError):
            replay(journal)

    def test_protected_overlapping_and_unapproved_rejected(self):
        journal = initialize(state())
        current = replay(journal)
        for changes in ([change(["mode"], "open", "blind")],
                        [change(["phase"], "main1", "end"), change(["phase"], "end", "draw")]):
            with self.assertRaises(ValueError):
                append(journal, action(current, changes=changes))
        bad = action(current)
        bad["moderator_approved"] = False
        with self.assertRaises(ValueError):
            append(journal, bad)


if __name__ == "__main__":
    unittest.main()
