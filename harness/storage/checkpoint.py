#!/usr/bin/env python3
"""Self-contained private duel checkpoints; never commit these files."""

from harness.modes import self_managed
from harness.isolation import saved_policy
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from harness.storage.atomic import save
from harness.storage.locking import writer_lock


def write_checkpoint(state_path, game_dir, journal, decision_packet=None, *, _verified_state=None, _assets=None):
    if _verified_state is not None:
        return _write_checkpoint(state_path, game_dir, journal, decision_packet, _verified_state=_verified_state, _assets=_assets)
    with writer_lock(state_path, game_dir):
        return _write_checkpoint(state_path, game_dir, journal, decision_packet, _assets=_assets)


def _write_checkpoint(state_path, game_dir, journal, decision_packet=None, *, _verified_state=None, _assets=None):
    from harness.engine.actions import replay
    state_path, game_dir = Path(state_path).resolve(), Path(game_dir).resolve()
    if state_path.is_relative_to(game_dir):
        raise ValueError("Checkpoint must be outside public game directory")
    # For normal sessions, enforce separation from the entire repository.
    if game_dir.parent.parent.name == "games" and state_path.is_relative_to(game_dir.parent.parent.parent):
        raise ValueError("Checkpoint must be outside repository")
    state = replay(journal) if _verified_state is None else _verified_state
    config = json.loads((game_dir / "game.json").read_text())
    if (config["id"] != state["game_id"] or config["mode"] != state["mode"]
            or saved_policy(config) != saved_policy(state)):
        raise ValueError("Checkpoint/game mismatch")
    path = state_path.with_name("checkpoint.json")
    if decision_packet is None and path.exists():
        previous = json.loads(path.read_text())
        before = {key: value for key, value in previous["state"].items() if key not in {"revision", "status"}}
        after = {key: value for key, value in state.items() if key not in {"revision", "status"}}
        same_rules = all(previous["configuration"].get(key) == config.get(key)
                         for key in ("format", "rules_profile", "rules_version", "banlist", "settings"))
        if before == after and same_rules and previous.get("decision_packet") is not None:
            decision_packet = deepcopy(previous["decision_packet"])
            decision_packet["expected_revision"] = state["revision"]
    if decision_packet is not None and decision_packet.get("expected_revision") != state["revision"]:
        raise ValueError("Decision packet is stale")
    from harness.storage.snapshots import collect
    assets = collect(game_dir) if _assets is None else _assets
    checkpoint = {"schema_version": "1.0", "saved_at": datetime.now(timezone.utc).isoformat(),
                  "configuration": config, "state": state, "journal": journal,
                  "decision_packet": decision_packet, "assets": assets,
                  "blind_human_resume": "Human must preserve their own hidden cards/order independently."
                  if self_managed(state["mode"]) else None}
    workflow_path = state_path.with_name("workflow.json")
    if workflow_path.exists():
        checkpoint["workflow"] = json.loads(workflow_path.read_text())
    save(path, checkpoint)
    path.chmod(0o600)
    return path


def verify_checkpoint(checkpoint):
    from harness.engine.actions import replay, validate_state
    state = replay(checkpoint["journal"])
    if state != checkpoint["state"]:
        raise ValueError("Checkpoint state differs from journal")
    validate_state(state)
    config = checkpoint["configuration"]
    if (config["id"] != state["game_id"] or config["mode"] != state["mode"]
            or saved_policy(config) != saved_policy(state)):
        raise ValueError("Checkpoint configuration differs from state")
    packet = checkpoint.get("decision_packet")
    if packet is not None and packet.get("expected_revision") != state["revision"]:
        raise ValueError("Checkpoint decision is stale")
    for name, asset in checkpoint["assets"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in {"decks", "rules.md"}:
            raise ValueError("Unsafe checkpoint asset path")
        if hashlib.sha256(asset["content"].encode("utf-8")).hexdigest() != asset["sha256"]:
            raise ValueError("Checkpoint asset hash mismatch")
    return state


def restore(checkpoint_path, state_path, game_dir):
    Path(state_path).parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with writer_lock(state_path, game_dir):
        return _restore(checkpoint_path, state_path, game_dir)


def _restore(checkpoint_path, state_path, game_dir):
    from harness.engine.actions import publish
    checkpoint_path, state_path, game_dir = Path(checkpoint_path).resolve(), Path(state_path).resolve(), Path(game_dir).resolve()
    checkpoint = json.loads(checkpoint_path.read_text())
    state = verify_checkpoint(checkpoint)
    if game_dir.parent.parent.name != "games":
        raise ValueError("Use games/<format>/<id>")
    repo = game_dir.parent.parent.parent
    if state_path.is_relative_to(repo) or checkpoint_path.is_relative_to(repo):
        raise ValueError("Private checkpoint/state must remain outside repository")
    if game_dir.exists():
        metadata = json.loads((game_dir / "game.json").read_text())
        if metadata["id"] != state["game_id"] or metadata["mode"] != state["mode"]:
            raise ValueError("Refusing to replace a different game")
        public_path = game_dir / "state.json"
        if public_path.exists() and json.loads(public_path.read_text()).get("revision", 0) > state["revision"]:
            raise ValueError("Refusing to overwrite a newer local game")
    if (game_dir / "events.json").exists():
        from harness.storage.records import load as read_archive
        archived = read_archive(game_dir)
        archived_revision = archived.get('initial_state', {}).get('revision', 0) + len(archived.get('events', []))
        if archived_revision > state['revision']:
            raise ValueError("Refusing to overwrite a newer local game")
    # Restore into a new private directory to avoid overwriting a newer session.
    if state_path.exists() or state_path.with_name("journal.json").exists():
        raise ValueError("Restore into a fresh private directory")
    for name in checkpoint["assets"]:
        if not (game_dir / name).resolve().is_relative_to(game_dir):
            raise ValueError("Restore asset escapes game directory")
    state_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    game_dir.mkdir(parents=True, exist_ok=True)
    for name, asset in checkpoint["assets"].items():
        target = game_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(asset["content"].encode("utf-8"))
    save(game_dir / "game.json", checkpoint["configuration"])
    save(state_path.with_name("journal.json"), checkpoint["journal"])
    if "workflow" in checkpoint:
        save(state_path.with_name("workflow.json"), checkpoint["workflow"])
    save(state_path.with_name("checkpoint.json"), checkpoint)
    publish(checkpoint["journal"], state_path, game_dir)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("save", "verify", "restore"))
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--game-dir", type=Path)
    args = parser.parse_args()
    if args.command == "verify":
        if args.checkpoint is None:
            parser.error("verify requires --checkpoint")
        state = verify_checkpoint(json.loads(args.checkpoint.read_text()))
    else:
        if args.state is None or args.game_dir is None:
            parser.error("save/restore require --state and --game-dir")
        if args.command == "restore":
            if args.checkpoint is None:
                parser.error("restore requires --checkpoint")
            state = restore(args.checkpoint, args.state, args.game_dir)
        else:
            with writer_lock(args.state, args.game_dir):
                journal = json.loads(args.state.with_name("journal.json").read_text())
                path = write_checkpoint(args.state, args.game_dir, journal)
                state = verify_checkpoint(json.loads(path.read_text()))
    print(json.dumps({"game_id": state["game_id"], "revision": state["revision"], "status": state["status"],
                      "verified": True}))


if __name__ == "__main__":
    main()
