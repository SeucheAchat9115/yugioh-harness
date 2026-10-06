#!/usr/bin/env python3
"""Duel setup, fixed shuffled draws, and mode-aware views; not a card-effect engine."""

import argparse
from contextlib import nullcontext
from harness.storage.locking import writer_lock
from harness.storage.atomic import save
from harness.views.perspective import view
from harness.modes import MODES, self_managed, managed_cards
from harness.isolation import startup_policy
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import uuid




def load_bundle(repo, relative):
    if not isinstance(relative, str):
        raise ValueError("A deck bundle path is required")
    folder = (repo / relative).resolve()
    if not folder.is_relative_to(repo / "decks"):
        raise ValueError("Deck bundle must be under this repository's decks/")
    for name in ("deck.ydk", "deck.json", "guide.md"):
        if not (folder / name).is_file():
            raise ValueError(f"Missing {folder / name}")
    raw = (folder / "deck.json").read_bytes()
    deck = json.loads(raw)
    sections = {key: [] for key in ("main", "extra", "side")}
    current = None
    for original in (folder / "deck.ydk").read_text(encoding="utf-8-sig").splitlines():
        line = original.strip()
        if line in ("#main", "#extra", "!side"):
            current = line.lstrip("#!")
        elif line and not line.startswith("#"):
            if current is None or not line.isdigit():
                raise ValueError("Malformed YDK")
            sections[current].append(int(line))
    if any(deck[section] != ids for section, ids in sections.items()):
        raise ValueError("YDK and gameplay JSON differ")
    digest = hashlib.sha256(raw).hexdigest()
    if f"deck_json_sha256: {digest}\n" not in (folder / "guide.md").read_text(encoding="utf-8"):
        raise ValueError("Guide hash is stale; review the guide before playing")
    for section in ("main", "extra", "side"):
        if deck["counts"][section] != len(deck[section]):
            raise ValueError("Deck section counts differ from metadata")
        if any(str(card_id) not in deck["cards"] for card_id in deck[section]):
            raise ValueError("Missing gameplay card record")
    return folder, deck


def instances(ids):
    return [{"instance_id": uuid.uuid4().hex, "card_id": card_id} for card_id in ids]


def known_player(deck, settings):
    queue = instances(deck["main"])
    secrets.SystemRandom().shuffle(queue)
    opening = settings["opening_hand_size"]
    if len(queue) < opening:
        raise ValueError("Deck too small for opening hand")
    layout = settings["field_layout"]
    return {
        "lp": settings["starting_lp"], "deck_id": deck["id"],
        "cards": deepcopy(deck["cards"]), "hand": queue[:opening], "deck": queue[opening:],
        "extra_deck": instances(deck["extra"]), "side_deck": instances(deck["side"]),
        "monster_zones": [None] * layout["main_monster_zones"],
        "spell_trap_zones": [None] * layout["spell_trap_zones"],
        "field_spell": None, "graveyard": [], "banished": [],
        "normal_summon_used": False, "effect_usage": {}, "restrictions": [],
    }






def validate_config(config):
    startup_policy(config)
    if config.get("mode") not in MODES:
        raise ValueError("Choose managed, self, or agent-vs-agent mode (open/blind are legacy)")
    for key in ("id", "format"):
        if not isinstance(config.get(key), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", config[key]):
            raise ValueError(f"Set a lowercase hyphenated {key}")
    for key in ("banlist", "rules_profile", "rules_version"):
        if config.get(key) is None:
            raise ValueError(f"Agree on {key} before starting")
    if config.get("starting_player") not in ("human", "agent"):
        raise ValueError("Choose human or agent as starting player")
    if type(config.get("presentation", {}).get("show_agent_hand", False)) is not bool:
        raise ValueError("show_agent_hand must be an explicit boolean")
    if config["mode"] == "agent-vs-agent" and config.get("presentation", {}).get("show_agent_hand", False):
        raise ValueError("Agent-vs-agent mode requires private hands")
    if config.get("storage", {}).get("game_commits", "explicit-user-request-only") != "explicit-user-request-only":
        raise ValueError("Game commits require an explicit user request")
    interaction = config.get("interaction", {})
    if interaction.get("decision_format", "decision-v1") != "decision-v1" or type(interaction.get("recommended_moves", 2)) is not int or interaction.get("recommended_moves", 2) != 2:
        raise ValueError("Use decision-v1 and two recommended moves")
    if interaction.get("automatic_continue_when_no_choice", True) is not True:
        raise ValueError("Verified no-choice progression must be enabled")
    settings = config.get("settings", {})
    for key in ("starting_lp", "opening_hand_size"):
        if type(settings.get(key)) is not int or settings[key] <= 0:
            raise ValueError(f"Set positive {key}")
    for key in ("starting_player_draws", "starting_player_battle_phase"):
        if type(settings.get(key)) is not bool:
            raise ValueError(f"Set {key} explicitly")
    layout = settings.get("field_layout")
    if not isinstance(layout, dict):
        raise ValueError("Set the field layout")
    for key in ("main_monster_zones", "spell_trap_zones", "extra_monster_zones"):
        if type(layout.get(key)) is not int or not 0 <= layout[key] <= 10:
            raise ValueError(f"Set field layout {key}")
    if self_managed(config["mode"]):
        if config.get("human_deck") is not None:
            raise ValueError("Self/blind mode must not receive a human deck path")
        counts = config.get("human_deck_counts", {})
        for key in ("main", "extra", "side"):
            if type(counts.get(key)) is not int or counts[key] < 0:
                raise ValueError(f"Declare human {key} count without card identities")
        if counts["main"] < settings["opening_hand_size"]:
            raise ValueError("Human Deck too small for opening hand")


def start(repo, config, private_dir):
    repo, private_dir = repo.resolve(), private_dir.resolve()
    validate_config(config)
    if private_dir.is_relative_to(repo):
        raise ValueError('Private session state must be outside the repository')
    private_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    with writer_lock(private_dir / 'state.json', repo / 'games' / config['format'] / config['id']):
        return _start(repo, config, private_dir)


def _start(repo, config, private_dir):
    config = deepcopy(config)
    config['player_isolation'] = startup_policy(config)
    repo, private_dir = repo.resolve(), private_dir.resolve()
    validate_config(config)
    if private_dir.is_relative_to(repo):
        raise ValueError("Private session state must be outside the repository")
    game_dir = repo / "games" / config["format"] / config["id"]
    private_state = private_dir / "state.json"
    if game_dir.exists() or private_state.exists():
        raise ValueError("Session already exists; resume it instead of reshuffling")
    agent_folder, agent_deck = load_bundle(repo, config["agent_deck"])
    bundles = {"agent": agent_folder}
    players = {"agent": known_player(agent_deck, config["settings"])}
    if managed_cards(config["mode"]):
        human_folder, human_deck = load_bundle(repo, config["human_deck"])
        bundles["human"] = human_folder
        players["human"] = known_player(human_deck, config["settings"])
    else:
        counts, layout = config["human_deck_counts"], config["settings"]["field_layout"]
        opening = config["settings"]["opening_hand_size"]
        players["human"] = {
            "lp": config["settings"]["starting_lp"], "deck_id": None,
            "hand": None, "deck": None, "extra_deck": None, "side_deck": None,
            "hand_count": opening, "deck_count": counts["main"] - opening,
            "extra_count": counts["extra"], "side_count": counts["side"],
            "monster_zones": [None] * layout["main_monster_zones"],
            "spell_trap_zones": [None] * layout["spell_trap_zones"],
            "field_spell": None, "graveyard": [], "banished": [],
            "normal_summon_used": False, "effect_usage": {}, "restrictions": [],
        }
    state = {
        "game_id": config["id"], "mode": config["mode"], "status": "active",
        "player_isolation": config["player_isolation"],
        "turn": 1, "active_player": config["starting_player"], "phase": "draw",
        "chain": [], "players": players, "pending_effects": [],
        "revision": 0, "pending_decision": None,
        "shared_zones": {"extra_monster_zones": [None] * config["settings"]["field_layout"]["extra_monster_zones"]},
        "presentation": {"show_agent_hand": config.get("presentation", {}).get("show_agent_hand", False)},
    }
    metadata = deepcopy(config)
    metadata.setdefault("interaction", {"decision_format": "decision-v1", "recommended_moves": 2,
                                         "automatic_continue_when_no_choice": True})
    metadata.setdefault("storage", {"game_commits": "explicit-user-request-only"})
    metadata.update({"status": "active", "date": datetime.now(timezone.utc).isoformat(),
                     "legality_checks": {"agent": "pending_format_verification",
                                         "human": "self_attested" if self_managed(config["mode"]) else "pending_format_verification"},
                     "deck_snapshots": {actor: f"decks/{actor}/{folder.name}/" for actor, folder in bundles.items()}})
    game_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    for actor, folder in bundles.items():
        target = game_dir / "decks" / actor / folder.name
        target.mkdir(parents=True)
        for name in ("deck.ydk", "deck.json", "guide.md", "README.md"):
            if (folder / name).is_file():
                shutil.copyfile(folder / name, target / name)
    save(private_state, state)
    from harness.engine.actions import initialize
    save(private_state.with_name("journal.json"), initialize(state))
    save(game_dir / "game.json", metadata)
    from harness.storage.archive import write_archive
    write_archive(initialize(state), state, game_dir)
    from harness.storage.checkpoint import write_checkpoint
    write_checkpoint(private_state, game_dir, initialize(state))
    return state, game_dir, private_state


def draw(state, actor, count):
    if actor not in ("human", "agent") or type(count) is not int or count <= 0:
        raise ValueError("Choose a player and a positive draw count")
    player = state["players"][actor]
    remaining = len(player["deck"]) if player["deck"] is not None else player["deck_count"]
    if remaining < count:
        raise ValueError("Insufficient cards; moderator must adjudicate the required draw/deck-out")
    if player["deck"] is None:
        player["deck_count"] -= count
        player["hand_count"] += count
    else:
        player["hand"].extend(player["deck"][:count])
        del player["deck"][:count]


def main():
    from harness.integration.stdio import configure_utf8
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("start")
    setup.add_argument("--repo", type=Path, required=True)
    setup.add_argument("--config", type=Path, required=True)
    setup.add_argument("--private-dir", type=Path, required=True)
    for command in ("view", "draw"):
        sub = commands.add_parser(command)
        sub.add_argument("--state", type=Path, required=True)
        sub.add_argument("--viewer", choices=("public", "human", "agent", "moderator"), default="public")
        if command == "draw":
            sub.add_argument("--actor", choices=("human", "agent"), required=True)
            sub.add_argument("--count", type=int, default=1)
            sub.add_argument("--game-dir", type=Path, required=True)
    args = parser.parse_args()
    with writer_lock(args.state, args.game_dir) if args.command == 'draw' else nullcontext():
        if args.command == "start":
            state, game_dir, _ = start(args.repo, json.loads(args.config.read_text(encoding="utf-8")), args.private_dir)
            print(json.dumps({"game_dir": str(game_dir), "public_state": view(state, "public")}, indent=2))
        else:
            state = json.loads(args.state.read_text(encoding="utf-8"))
            if args.command == "draw":
                metadata = json.loads((args.game_dir / "game.json").read_text(encoding="utf-8"))
                if metadata["id"] != state["game_id"] or metadata["mode"] != state["mode"]:
                    raise ValueError("Game directory does not match private state")
                from harness.engine.actions import append, initialize, publish, replay
                journal_path = args.state.with_name("journal.json")
                journal = json.loads(journal_path.read_text(encoding="utf-8")) if journal_path.exists() else initialize(state)
                state.setdefault("revision", 0)
                state.setdefault("pending_decision", None)
                if state != replay(journal):
                    raise ValueError("State differs from journal; use actions.py replay to recover")
                if args.state.resolve().is_relative_to(args.game_dir.resolve().parent.parent.parent):
                    raise ValueError("Private session state must be outside the repository")
                updated = deepcopy(state)
                draw(updated, args.actor, args.count)
                changes = [{"path": ["players", args.actor, key], "before": state["players"][args.actor][key],
                            "after": value} for key, value in updated["players"][args.actor].items()
                           if value != state["players"][args.actor][key]]
                action = {"id": uuid.uuid4().hex, "kind": "draw", "actor": args.actor,
                          "expected_revision": state["revision"], "moderator_approved": True,
                          "public_summary_reviewed": True,
                          "public_summary": f"Drew {args.count} card(s); identities private.", "changes": changes}
                journal, state = append(journal, action)
                save(journal_path, journal)
                publish(journal, args.state, args.game_dir)
            print(json.dumps(view(state, args.viewer), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
