#!/usr/bin/env python3
"""Duel setup, fixed shuffled draws, and mode-aware views; not a card-effect engine."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import tempfile
import uuid


def save(path, data):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     delete=False) as handle:
        temp = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


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
    if f"deck_json_sha256: {digest}\n" not in (folder / "guide.md").read_text():
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


def render_card(entry, player, reveal=False):
    if entry is None:
        return None
    visible = reveal or not entry.get("hidden", False)
    if not visible:
        # Stats/current names can identify a hidden card just as surely as its ID.
        return {key: entry[key] for key in ("instance_id", "owner", "position", "hidden") if key in entry}
    result = {key: value for key, value in entry.items()
              if key not in ("card_id", "name", "effect_text", "private_notes")}
    if visible and entry.get("card_id") is not None:
        result["card_id"] = entry["card_id"]
        card = player.get("cards", {}).get(str(entry["card_id"]), {})
        if card.get("name") or entry.get("name"):
            result["name"] = card.get("name", entry.get("name"))
    return result


def view(state, viewer):
    if viewer not in ("public", "human", "agent", "moderator"):
        raise ValueError("Unknown perspective")
    result = {key: deepcopy(state[key]) for key in
              ("game_id", "mode", "status", "turn", "active_player", "phase", "chain")}
    result["players"] = {}
    result["shared_zones"] = {}
    for zone, entries in state.get("shared_zones", {}).items():
        result["shared_zones"][zone] = []
        for entry in entries:
            if entry is None:
                result["shared_zones"][zone].append(None)
                continue
            owner = entry.get("owner")
            if owner not in state["players"]:
                raise ValueError("Shared-zone card needs a human/agent owner")
            reveal = viewer == owner or (viewer == "moderator" and (owner == "agent" or state["mode"] == "open")) or (
                state["mode"] == "open" and owner == "human" and viewer == "agent")
            result["shared_zones"][zone].append(render_card(entry, state["players"][owner], reveal))
    for actor, player in state["players"].items():
        known = player["hand"] is not None
        own = viewer == actor
        open_human = state["mode"] == "open" and actor == "human" and viewer in ("agent", "moderator")
        agent_access = actor == "agent" and viewer == "moderator"
        reveal_hand = own or open_human or agent_access or (
            actor == "agent" and state["presentation"]["show_agent_hand"])
        reveal_zones = own or open_human or agent_access
        output = {"lp": player["lp"], "hand_count": len(player["hand"]) if known else player["hand_count"],
                  "deck_count": len(player["deck"]) if known else player["deck_count"],
                  "extra_count": len(player["extra_deck"]) if known else player["extra_count"],
                  "side_count": len(player["side_deck"]) if known else player["side_count"]}
        if known and reveal_hand:
            output["hand"] = [render_card(card, player, True) for card in player["hand"]]
            output["extra_deck"] = [render_card(card, player, True) for card in player["extra_deck"]]
            output["side_deck"] = [render_card(card, player, True) for card in player["side_deck"]]
        for zone in ("monster_zones", "spell_trap_zones", "graveyard", "banished"):
            output[zone] = [render_card(card, player, reveal_zones) for card in player[zone]]
        output["field_spell"] = render_card(player["field_spell"], player, reveal_zones)
        output["normal_summon_used"] = player["normal_summon_used"]
        output["effect_usage"] = deepcopy(player["effect_usage"])
        output["restrictions"] = deepcopy(player["restrictions"])
        # Unknown human cards are never represented in blind state, for ANY viewer.
        if open_human:
            output["remaining_deck_order"] = [render_card(card, player, True) for card in player["deck"]]
        result["players"][actor] = output
    return result


def validate_config(config):
    if config.get("mode") not in ("blind", "open"):
        raise ValueError("Choose blind or open mode")
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
    if config["mode"] == "blind":
        if config.get("human_deck") is not None:
            raise ValueError("Blind mode must not receive a human deck path")
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
        raise ValueError("Private session state must be outside the repository")
    game_dir = repo / "games" / config["format"] / config["id"]
    private_state = private_dir / "state.json"
    if game_dir.exists() or private_state.exists():
        raise ValueError("Session already exists; resume it instead of reshuffling")
    agent_folder, agent_deck = load_bundle(repo, config["agent_deck"])
    bundles = {"agent": agent_folder}
    players = {"agent": known_player(agent_deck, config["settings"])}
    if config["mode"] == "open":
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
        "turn": 1, "active_player": config["starting_player"], "phase": "draw",
        "chain": [], "players": players, "pending_effects": [],
        "shared_zones": {"extra_monster_zones": [None] * config["settings"]["field_layout"]["extra_monster_zones"]},
        "presentation": {"show_agent_hand": config.get("presentation", {}).get("show_agent_hand", False)},
    }
    metadata = deepcopy(config)
    metadata.update({"status": "active", "date": datetime.now(timezone.utc).isoformat(),
                     "legality_checks": {"agent": "pending_format_verification",
                                         "human": "self_attested" if config["mode"] == "blind" else "pending_format_verification"},
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
    save(game_dir / "game.json", metadata)
    save(game_dir / "state.json", view(state, "public"))
    (game_dir / "log.md").write_text(f"# {config['id']}\n\nMode: {config['mode']}. Opening hands prepared; hidden identities omitted.\nFirst-turn draw has not been applied.\n")
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
    if args.command == "start":
        state, game_dir, _ = start(args.repo, json.loads(args.config.read_text()), args.private_dir)
        print(json.dumps({"game_dir": str(game_dir), "public_state": view(state, "public")}, indent=2))
    else:
        state = json.loads(args.state.read_text())
        if args.command == "draw":
            metadata = json.loads((args.game_dir / "game.json").read_text())
            if metadata["id"] != state["game_id"] or metadata["mode"] != state["mode"]:
                raise ValueError("Game directory does not match private state")
            draw(state, args.actor, args.count)
            save(args.state, state)
            save(args.game_dir / "state.json", view(state, "public"))
            with (args.game_dir / "log.md").open("a") as log:
                log.write(f"\n{args.actor} drew {args.count} card(s); identities private.\n")
        print(json.dumps(view(state, args.viewer), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
