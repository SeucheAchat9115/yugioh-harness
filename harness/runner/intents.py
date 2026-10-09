"""Opt-in semantic intentions; translation is bookkeeping, never rules approval."""
from copy import deepcopy
import json
import re
from harness.runner.state_tools import locate, parent

VERSION = "intent-v1"
POLICY = """Return exactly one JSON intention, no prose or state operations.
Use physical instance IDs supplied in context. Field zones are one-based labels:
M-1..M-5 and S-1..S-5 (or the configured layout), never array indexes.
Supported shapes:
{"action":"set","card":"instance-id","zone":"S-3"}
{"action":"set","card":"instance-id","zone":"M-3"}
{"action":"normal_summon","card":"instance-id","zone":"M-3","position":"ATK"}
{"action":"end_turn"}
{"action":"pass"}
{"action":"phase","phase":"battle"}
{"action":"activate","card":"instance-id","zone":"S-3","target":"target-instance-id","cost_cards":["tribute-or-discard-id"]}
For activation, zone is required only when placing a card from hand.
Optional target and cost_cards must identify your actual chosen target/costs.
Do not invent a target, exceed the saved Normal Summon allowance, activate a
field effect from hand, or assume an opponent response. Choose only one initiation;
stop before summon confirmation, triggers, chain resolution or turn advance.
If needed, return {"action":"unsupported","description":"precise next intention"}.
A moderator separately reviews legality; JSON acceptance is not rules approval.
"""

def parse_intent(response):
    if not isinstance(response, str) or len(response) > 8192:
        raise ValueError("One bounded JSON intention is required")
    value = json.loads(response)
    if not isinstance(value, dict):
        raise ValueError("Intention must be an object")
    fields = {
        "set": {"action", "card", "zone"},
        "normal_summon": {"action", "card", "zone", "position", "cost_cards"},
        "activate": {"action", "card", "zone", "target", "cost_cards"},
        "end_turn": {"action"}, "pass": {"action"}, "phase": {"action", "phase"},
        "unsupported": {"action", "description"},
    }
    kind = value.get("action")
    if kind not in fields or set(value) - fields[kind]:
        raise ValueError("Unknown intention fields or action")
    required = {"set": {"card", "zone"}, "normal_summon": {"card", "zone", "position"},
                "activate": {"card"}, "phase": {"phase"}, "unsupported": {"description"}}
    if not required.get(kind, set()) <= set(value):
        raise ValueError("Missing intention fields")
    for key in ("card", "zone", "target", "position", "phase", "description"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError("Intention references must be nonempty strings")
    costs = value.get("cost_cards", [])
    if (not isinstance(costs, list) or any(not isinstance(c, str) or not c for c in costs)
            or len(set(costs)) != len(costs)):
        raise ValueError("Cost cards must be unique physical IDs")
    return value

def _card(state, identity):
    path = locate(state, identity)
    container, key = parent(state, path)
    return path, container[key]

def _zone(state, actor, label, required=None):
    match = re.fullmatch(r"([MS])-([1-9][0-9]*)", label)
    if not match:
        raise ValueError("Use a one-based M-n or S-n zone label")
    zone = "monster_zones" if match[1] == "M" else "spell_trap_zones"
    if required and zone != required:
        raise ValueError("Wrong field zone type")
    index = int(match[2]) - 1
    slots = state["players"][actor][zone]
    if index >= len(slots) or slots[index] is not None:
        raise ValueError("Field zone unavailable")
    return ["players", actor, zone, index]

def _costs(state, actor, intent, reviewed):
    if reviewed is not None and not isinstance(reviewed, dict):
        raise ValueError("Reviewed costs must be an object")
    operations = deepcopy((reviewed or {}).get("cost_operations", []))
    if not isinstance(operations,list) or any(not isinstance(op,dict) for op in operations):
        raise ValueError("Reviewed costs must be an operation list")
    chosen = set(intent.get("cost_cards", []))
    moved = set()
    balance = state["players"][actor]["lp"]
    for op in operations:
        if op.get("op") == "lp":
            if (op.get("player") != actor or type(op.get("delta")) is not int
                    or op["delta"] >= 0 or balance + op["delta"] < 0):
                raise ValueError("Invalid reviewed LP cost")
            balance += op["delta"]
        elif op.get("op") == "move":
            card = op.get("card")
            path, _ = _card(state, card)
            dest = op.get("to")
            if (card not in chosen or card == intent.get("card") or card in moved
                    or path[:2] != ["players", actor] or not isinstance(dest, list)
                    or len(dest) != 3 or dest[:2] != ["players", actor]
                    or dest[2] not in {"graveyard", "banished"}):
                raise ValueError("Reviewed costs must consume chosen own cards")
            op["attributes"] = {"hidden": False, "position": None}
            moved.add(card)
        else:
            raise ValueError("Unsupported cost operation; moderator clarification required")
    if moved != chosen:
        raise ValueError("Chosen cost cards differ from reviewed costs")
    return operations

def translate_intent(state, intent, *, actor="agent", reviewed_activation=None):
    """Return an UNAPPROVED proposal; execute only after independent rules review."""
    intent = parse_intent(json.dumps(intent))
    if (actor not in ("agent", "human") or state["active_player"] != actor
            or (state.get("pending_decision") or {}).get("actor") != actor
            or state["status"] != "active"):
        raise ValueError("Not this player's active initiation window")
    opponent = "human" if actor == "agent" else "agent"
    action = intent["action"]
    operations = []
    window = "after_set"
    if action in {"set", "normal_summon"}:
        if state["phase"] not in {"main1", "main2"} or state["chain"]:
            raise ValueError("No Main Phase initiation window")
        path, card = _card(state, intent["card"])
        if path[:3] != ["players", actor, "hand"]:
            raise ValueError("Summon/Set card is not in own hand")
        dest = _zone(state, actor, intent["zone"],
                     "monster_zones" if action == "normal_summon" else None)
        monster = dest[2] == "monster_zones"
        if monster and state["players"][actor]["normal_summon_used"]:
            raise ValueError("Normal Summon/Set allowance already used")
        if action == "normal_summon" and intent["position"] != "ATK":
            raise ValueError("This initiation protocol supports ATK Normal Summons")
        operations = _costs(state, actor, intent, reviewed_activation)
        attrs = {"hidden": action == "set"}
        if monster: attrs["position"] = "DEF" if action == "set" else "ATK"
        operations.append({"op": "move", "card": intent["card"], "to": dest, "attributes": attrs})
        if monster:
            operations.append({"op": "normal_summon", "player": actor, "used": True})
        window = "summon_negation" if action == "normal_summon" else "after_set"
        kind = "summon" if action == "normal_summon" else "set"
        summary = "Player attempts a Normal Summon; opponent may negate." if kind == "summon" else "Player sets a card face-down; opponent may respond."
    elif action in {"end_turn", "pass", "phase"}:
        if state["chain"] or state["pending_effects"]:
            raise ValueError("Resolve pending chain/effects before phase initiation")
        if action == "end_turn":
            operations.append({"op": "phase", "value": "end"})
            window = "end_phase_response"
        elif action == "phase":
            if intent["phase"] not in {"standby", "main1", "battle", "main2", "end"}:
                raise ValueError("Unsupported phase")
            operations.append({"op": "phase", "value": intent["phase"]})
            window = "phase_response"
        else:
            window = "end_phase_response" if state["phase"] == "end" else "action_response"
        kind = "pass" if action == "pass" else "phase"
        summary = "Player requests a phase/priority transition; opponent may respond."
    elif action == "activate":
        if state["chain"]:
            raise ValueError("This protocol supports initiations, not chain responses")
        if reviewed_activation is None:
            raise ValueError("Activation needs independent effect/cost review")
        path, card = _card(state, intent["card"])
        if path[:2] != ["players", actor]:
            raise ValueError("Cannot activate an opponent card")
        if path[2] == "hand":
            dest = _zone(state, actor, intent.get("zone", ""), "spell_trap_zones")
            operations.append({"op": "move", "card": intent["card"], "to": dest, "attributes": {"hidden": False}})
        elif path[2] in {"monster_zones", "spell_trap_zones", "graveyard", "banished"}:
            operations.append({"op": "card", "card": intent["card"], "attributes": {"hidden": False}})
        else:
            raise ValueError("Unsupported activation location")
        operations.extend(_costs(state, actor, intent, reviewed_activation))
        targets = []
        if "target" in intent:
            target_path, target = _card(state, intent["target"])
            if target_path[2] not in {"monster_zones", "spell_trap_zones", "graveyard", "banished", "field_spell"}:
                raise ValueError("Target is not in a visible selectable zone")
            targets = [{"instance_id": target["instance_id"], "owner": target_path[1],
                        "zone": target_path[2], "index": target_path[-1]}]
        link = {"id": "intent-chain-1", "actor": actor, "card": intent["card"],
                "effect": reviewed_activation.get("effect", "Pending independently reviewed activation"),
                "targets": targets}
        operations.append({"op": "chain", "value": [link]})
        window, kind = "chain_response", "activate"
        summary = "Player declares an activation and pays reviewed costs; opponent may respond."
    else:
        raise ValueError("Intention requires moderator support outside this initiation protocol")
    operations.append({"op": "decision", "value": {"actor": opponent, "window": window}})
    return {"kind": kind, "actor": actor, "expected_revision": state["revision"],
            "public_summary": summary, "operations": operations}
