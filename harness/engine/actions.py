#!/usr/bin/env python3
"""Record moderator-approved decisions; replay state changes without rerunning effects."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from harness.storage.atomic import save
from harness.views.perspective import view

KINDS = {"activate", "respond", "resolve", "pass", "summon", "set", "move",
         "search", "shuffle", "draw", "attack", "damage", "phase", "turn",
         "reveal", "usage", "choice", "finish", "correction"}
PROTECTED = {"game_id", "mode", "presentation", "revision"}


def validate_no_choice(state, review):
    if (review.get("complete") is not True or type(review.get("meaningful_choices")) is not int
            or review["meaningful_choices"] != 0 or not isinstance(review.get("reason"), str)
            or not review["reason"].strip()):
        raise ValueError("Automatic continuation requires a complete no-choice review")
    if review.get("basis") not in {"open-state-verified", "public-rules-verified", "human-confirmed-none"}:
        raise ValueError("Specify the basis for automatic continuation")
    if state["mode"] == "blind" and review["basis"] == "open-state-verified":
        raise ValueError("Unknown blind human state cannot prove absence of options")


def digest(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode()).hexdigest()


def initialize(state):
    state = deepcopy(state)
    state.setdefault("revision", 0)
    state.setdefault("pending_decision", None)
    return {"schema_version": "1.0", "initial_state": state, "events": []}


def validate_state(state):
    seen = set()
    for actor, player in state["players"].items():
        if type(player["lp"]) is not int or player["lp"] < 0:
            raise ValueError("LP must be a nonnegative integer")
        if state["mode"] == "blind" and actor == "human":
            if any(player[key] is not None for key in ("hand", "deck", "extra_deck", "side_deck")):
                raise ValueError("Blind human hidden card identities must remain absent")
            for key in ("hand_count", "deck_count", "extra_count", "side_count"):
                if type(player[key]) is not int or player[key] < 0:
                    raise ValueError("Unknown-zone counts must be nonnegative integers")
        def visit(value):
            if isinstance(value, dict):
                if "instance_id" in value:
                    if state["mode"] == "blind" and actor == "human" and value.get("hidden"):
                        if set(value) - {"instance_id", "owner", "position", "hidden"}:
                            raise ValueError("Blind human face-down cards must be anonymous")
                    identity = value["instance_id"]
                    if identity in seen:
                        raise ValueError("A physical card cannot occupy two locations")
                    seen.add(identity)
                if "materials" in value:
                    visit(value["materials"])
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        for zone in ("hand", "deck", "extra_deck", "side_deck", "monster_zones",
                     "spell_trap_zones", "field_spell", "graveyard", "banished"):
            visit(player.get(zone))
        for entries in state.get("shared_zones", {}).values():
            visit([card for card in entries if card and card.get("owner") == actor])


def apply(state, action):
    """Apply an explicit set of guarded replacements to a copy, never partially."""
    if action.get("kind") not in KINDS or action.get("actor") not in {"human", "agent", "moderator"}:
        raise ValueError("Unknown kind or actor")
    if not isinstance(action.get("id"), str) or not action["id"].strip():
        raise ValueError("A unique action ID is required")
    if type(action.get("expected_revision")) is not int or action["expected_revision"] != state["revision"]:
        raise ValueError("Stale decision; inspect current state before recording")
    if action.get("moderator_approved") is not True or action.get("public_summary_reviewed") is not True:
        raise ValueError("Moderator approval and hidden-information review are required")
    if not isinstance(action.get("public_summary"), str) or not action["public_summary"].strip():
        raise ValueError("Supply a reviewed public summary")
    if "automatic" in action and type(action["automatic"]) is not bool:
        raise ValueError("automatic must be an explicit boolean")
    if action.get("automatic") is True:
        validate_no_choice(state, action.get("option_review", {}))
    changes = action.get("changes")
    if not isinstance(changes, list):
        raise ValueError("Changes must be a list")
    result = deepcopy(state)
    paths = []
    for change in changes:
        path = change.get("path")
        if not isinstance(path, list) or not path or path[0] in PROTECTED:
            raise ValueError("Invalid or protected state path")
        if any(type(key) not in (str, int) or (type(key) is int and key < 0) for key in path):
            raise ValueError("Paths use string keys and nonnegative indexes")
        if any(path[:len(old)] == old or old[:len(path)] == path for old in paths):
            raise ValueError("Overlapping changes are ambiguous")
        paths.append(path)
        parent = result
        try:
            for key in path[:-1]:
                parent = parent[key]
            key = path[-1]
            if isinstance(parent, list) and (type(key) is not int or key < 0):
                raise ValueError("Use nonnegative list indexes")
            if parent[key] != change["before"]:
                raise ValueError("Expected previous value does not match")
            parent[key] = deepcopy(change["after"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Change path/value is missing or invalid") from exc
    if action["kind"] in {"activate", "respond"}:
        if len(result["chain"]) != len(state["chain"]) + 1 or result["chain"][:-1] != state["chain"]:
            raise ValueError("Activation records exactly one new chain link")
        if result.get("pending_decision") is None:
            raise ValueError("Activation must leave an explicit response decision")
    if action["kind"] == "resolve":
        if state.get("pending_decision") is not None:
            raise ValueError("Finish response decisions before resolving")
        if not state["chain"] or result["chain"] != state["chain"][:-1]:
            raise ValueError("Resolve exactly the last chain link")
    if action["kind"] == "pass" and result["chain"] != state["chain"]:
        raise ValueError("Passing does not resolve a chain")
    result["revision"] += 1
    validate_state(result)
    return result


def replay(journal):
    state = deepcopy(journal["initial_state"])
    ids = set()
    for event in journal["events"]:
        action = event["action"]
        if action["id"] in ids or event["before_sha256"] != digest(state):
            raise ValueError("Duplicate or inconsistent event history")
        ids.add(action["id"])
        state = apply(state, action)
        if event["after_sha256"] != digest(state):
            raise ValueError("Event result hash mismatch")
    return state


def append(journal, action):
    state = replay(journal)
    if any(event["action"]["id"] == action.get("id") for event in journal["events"]):
        raise ValueError("Action already recorded; do not apply it twice")
    updated = apply(state, action)
    event = {"recorded_at": datetime.now(timezone.utc).isoformat(),
             "before_sha256": digest(state), "after_sha256": digest(updated),
             "action": deepcopy(action)}
    result = deepcopy(journal)
    result["events"].append(event)
    return result, updated


def publish(journal, state_path, game_dir):
    return publish_verified(journal, replay(journal), state_path, game_dir)


def publish_verified(journal, state, state_path, game_dir, assets=None):
    """Internal persistence for a state already validated by apply/replay."""
    metadata = json.loads((game_dir / "game.json").read_text())
    if metadata["id"] != state["game_id"] or metadata["mode"] != state["mode"]:
        raise ValueError("Game directory does not match session")
    if state_path.resolve().is_relative_to(game_dir.resolve()):
        raise ValueError("Private state cannot be inside public game directory")
    # Journal is authoritative. These disposable projections can be regenerated.
    save(state_path, state)
    public = view(state, "public")
    public["revision"] = state["revision"]
    save(game_dir / "state.json", public)
    metadata["status"] = state["status"]
    metadata["resume"] = {"revision": state["revision"], "turn": state["turn"], "phase": state["phase"],
                          "pending_actor": (state.get("pending_decision") or {}).get("actor"),
                          "pending_window": (state.get("pending_decision") or {}).get("window"),
                          "private_checkpoint_saved": True}
    save(game_dir / "game.json", metadata)
    events = [{"revision": n, "id": event["action"]["id"],
               "kind": event["action"]["kind"], "actor": event["action"]["actor"],
               "summary": event["action"]["public_summary"],
               "recorded_at": event["recorded_at"]}
              for n, event in enumerate(journal["events"], 1)]
    save(game_dir / "events.json", {"schema_version": "1.0", "events": events})
    lines = [f"# {state['game_id']}", "", "Structured decisions (hidden changes omitted).", ""]
    lines.extend(f"{event['revision']}. {event['actor']}: {event['summary']}" for event in events)
    (game_dir / "actions.md").write_text("\n".join(lines) + "\n")
    from harness.storage.checkpoint import write_checkpoint
    write_checkpoint(state_path, game_dir, journal, _verified_state=state, _assets=assets)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record", "replay"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--action", type=Path)
    args = parser.parse_args()
    # Require the standard games/<format>/<id> layout and private files outside repo.
    game_dir = args.game_dir.resolve()
    if game_dir.parent.parent.name != "games":
        raise ValueError("Use games/<format>/<id>")
    repo = game_dir.parent.parent.parent
    state_path = args.state.resolve()
    if state_path.is_relative_to(repo) or (args.action and args.action.resolve().is_relative_to(repo)):
        raise ValueError("Private state and action drafts must be outside repository")
    journal_path = state_path.with_name("journal.json")
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else initialize(json.loads(state_path.read_text()))
    if args.command == "record":
        if args.action is None:
            raise ValueError("record requires --action")
        cached = json.loads(state_path.read_text())
        cached.setdefault("revision", 0)
        cached.setdefault("pending_decision", None)
        if cached != replay(journal):
            raise ValueError("State cache differs from journal; replay to recover, do not edit directly")
        journal, _ = append(journal, json.loads(args.action.read_text()))
    metadata = json.loads((game_dir / "game.json").read_text())
    current = replay(journal)
    if metadata["id"] != current["game_id"] or metadata["mode"] != current["mode"]:
        raise ValueError("Game directory does not match session")
    save(journal_path, journal)
    state = publish(journal, state_path, game_dir)
    print(json.dumps({"revision": state["revision"], "public_state": view(state, "public")}, indent=2))


if __name__ == "__main__":
    main()
