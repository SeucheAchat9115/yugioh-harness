#!/usr/bin/env python3
"""Render the fixed human-facing duel format from a permitted perspective."""

import argparse
from harness.storage.locking import writer_lock
import json
from pathlib import Path

from harness.views.perspective import view


def card_label(card):
    if card is None:
        return "empty"
    name = card.get("name", "face-down card" if card.get("hidden") else "revealed card")
    details = [str(card[key]) for key in ("position", "atk", "def") if key in card]
    return name + (" (" + ", ".join(details) + ")" if details else "")


def render(state, packet):
    if type(packet.get("expected_revision")) is not int or packet["expected_revision"] != state.get("revision", 0):
        raise ValueError("Decision packet must match current revision")
    awaiting = packet.get("awaiting_user", True)
    if type(awaiting) is not bool:
        raise ValueError("awaiting_user must be an explicit boolean")
    recommendations = packet.get("recommendations", [])
    if not isinstance(recommendations, list) or len(recommendations) > 2:
        raise ValueError("Show at most two recommended moves")
    for move in recommendations:
        if any(not isinstance(move.get(key), str) or not move[key].strip() for key in ("label", "reason")):
            raise ValueError("Recommendations need a move and a reason")
    if len({move['label'] for move in recommendations}) != len(recommendations):
        raise ValueError("Recommendations must be distinct")
    review = packet.get("option_review", {})
    count = review.get("meaningful_choices")
    complete = review.get("complete") is True
    if complete and (type(count) is not int or count < 0):
        raise ValueError("Complete option review requires a nonnegative choice count")
    if complete and count >= 2 and len(recommendations) != 2:
        raise ValueError("Show two recommendations when two or more choices are available")
    if complete and count < len(recommendations):
        raise ValueError("Do not invent more recommendations than verified choices")
    if complete and count == 0 and awaiting:
        raise ValueError("Do not ask a question when the human has no choice")
    if complete and count == 0 and state["status"] == "active":
        from harness.engine.actions import validate_no_choice
        validate_no_choice(state, review)
    if not awaiting and not (complete and count == 0) and state["status"] not in {"paused", "finished"}:
        raise ValueError("Unknown options cannot be treated as no choice")
    private_menu = (state["mode"] == "agent-vs-agent" or packet.get("observer") is True) and awaiting
    if private_menu:
        recommendations = []
    human = view(state, "public" if state["mode"] == "agent-vs-agent" else "human")
    decision = human.get("pending_decision") or {}
    lines = [f"**Game:** {human['game_id']} | {human['mode']} | {human['status']} | revision {human['revision']}",
             f"**Role:** {packet.get('role', 'Moderator / Coach')}",
             f"**Turn / phase:** {human['turn']} / {human['phase']} | active: {human['active_player']}",
             f"**Decision:** {decision.get('actor', 'none')} / {decision.get('window', 'none')}"]
    players = human["players"]
    lines.append(f"**LP:** You {players['human']['lp']} | Opponent {players['agent']['lp']}")
    for actor, label in (("human", "You"), ("agent", "Opponent")):
        player = players[actor]
        lines.append(f"**{label} counts:** Hand {player['hand_count']} | Deck {player['deck_count']} | Extra {player['extra_count']} | Side {player['side_count']}")
    lines.append("**Your hand:** " + ("; ".join(f"H{i}: {card_label(card)}" for i, card in enumerate(players['human'].get('hand', []), 1))
                 if state["mode"] in ("managed", "open") else ("private; managed by each agent" if state["mode"] == "agent-vs-agent" else "private; managed by you")))
    if state["presentation"].get("show_agent_hand"):
        lines.append("**Opponent hand (agreed visible):** " + "; ".join(card_label(card) for card in players['agent'].get('hand', [])))
    lines.append("**Board:**")
    for actor, label in (("human", "You"), ("agent", "Opponent")):
        player = players[actor]
        for zone, title in (("monster_zones", "monsters"), ("spell_trap_zones", "spells/traps")):
            lines.append(f"- {label} {title}: " + "; ".join(f"{i}: {card_label(card)}" for i, card in enumerate(player[zone], 1)))
        lines.append(f"- {label} Field Zone: {card_label(player['field_spell'])}")
        for zone, title in (("graveyard", "GY"), ("banished", "banished")):
            lines.append(f"- {label} {title}: " + ("; ".join(card_label(card) for card in player[zone]) or "empty"))
    for zone, cards in human["shared_zones"].items():
        lines.append(f"- Shared {zone}: " + "; ".join(f"{i}: {card_label(card)}" for i, card in enumerate(cards, 1)))
    lines.append("**Chain (activation order):**")
    lines.extend(f"- CL{i}: {link.get('actor')} — {link.get('name', 'effect')} — {link.get('effect', '')}; costs: {json.dumps(link.get('costs', []))}; targets: {json.dumps(link.get('targets', []))}"
                 + ("; effect negated" if link.get('effect_negated') else "")
                 for i, link in enumerate(human["chain"], 1))
    if not human["chain"]:
        lines.append("- empty")
    lines.append("**Usage / restrictions:**")
    for actor, label in (("human", "You"), ("agent", "Opponent")):
        player = players[actor]
        lines.append(f"- {label}: Normal Summon used: {player['normal_summon_used']}; effects: {json.dumps(player['effect_usage'], ensure_ascii=False)}; restrictions: {json.dumps(player['restrictions'], ensure_ascii=False)}")
    lines.append("**What happened:**")
    lines.extend(f"- {event}" for event in packet.get("events", []))
    if not packet.get("events"):
        lines.append("- No new actions.")
    lines.append("**Coach — recommended moves:**")
    lines.extend(f"{i}. {move['label']} — {move['reason']}" for i, move in enumerate(recommendations, 1))
    if private_menu:
        lines.append("- Player choices are private; handled by the active agent.")
    elif not recommendations:
        lines.append("- No verified recommendation at this step.")
    elif len(recommendations) == 1:
        lines.append("- Only one verified recommendation; no second move is invented.")
    if private_menu:
        lines.append("**Your choice:** No observer action requested; waiting for the active agent.")
    elif awaiting:
        lines.append("**Your choice:** " + packet.get("question", "What do you do?") + " Reply 1 or 2, or describe any other legal action in your own words.")
    else:
        lines.append("**Your choice:** " + ("Game paused/finished; no action requested." if state["status"] in {"paused", "finished"}
                                          else "No choice at this step; continuing automatically."))
    if packet.get("decision_id"):
        lines.append(f"**Decision ID:** {packet['decision_id']}")
    text = "\n\n".join(lines) + "\n"
    if state["mode"] == "agent-vs-agent":
        text = text.replace("You ", "Agent 1 ").replace("You:", "Agent 1:").replace("Opponent", "Agent 2")
        text = text.replace("Your hand", "Hands").replace("Coach — recommended moves", "Moderator — options")
    return text


def main():
    from harness.integration.stdio import configure_utf8
    configure_utf8()
    from harness.storage.checkpoint import write_checkpoint
    from harness.engine.actions import replay
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    args = parser.parse_args()
    game = args.game_dir.resolve()
    if game.parent.parent.name != "games":
        parser.error("Use games/<format>/<id>")
    repo = game.parent.parent.parent
    if args.state.resolve().is_relative_to(repo) or args.packet.resolve().is_relative_to(repo):
        parser.error("State and human decision packet must be outside repository")
    with writer_lock(args.state, args.game_dir):
        journal = json.loads(args.state.with_name("journal.json").read_text(encoding="utf-8"))
        state = replay(journal)
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        text = render(state, packet)
        # Save the exact numbered choices/card mapping before asking the human.
        packet["hand_refs"] = {f"H{i}": card["instance_id"] for i, card in enumerate(state['players']['human']['hand'] or [], 1)}
        write_checkpoint(args.state, game, journal, packet)
        print(text)


if __name__ == "__main__":
    main()
