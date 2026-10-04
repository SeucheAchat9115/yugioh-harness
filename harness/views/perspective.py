"""Permitted information views; no future draw order for player adapters."""
from copy import deepcopy

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
        for key in ("atk", "def", "level", "attribute", "type", "scale", "linkval", "linkmarkers"):
            if key in card:
                result.setdefault(key, card[key])
    elif visible and entry.get("name"):
        result["name"] = entry["name"]
    return result


def view(state, viewer):
    if viewer not in ("public", "human", "agent", "moderator"):
        raise ValueError("Unknown perspective")
    result = {key: deepcopy(state[key]) for key in
              ("game_id", "mode", "status", "turn", "active_player", "phase", "chain")}
    result["revision"] = state.get("revision", 0)
    decision = state.get("pending_decision")
    result["pending_decision"] = ({key: decision[key] for key in ("actor", "window") if key in decision}
                                  if decision else None)
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

