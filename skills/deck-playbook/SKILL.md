---
name: deck-playbook
description: Analyze gameplay-only deck JSONs into generic guide.md playbooks in named deck folders with card roles, search/recovery maps, synergies, conditional combo lines, and decision guidance for an agent playing against another agent or a human.
---

# Deck playbook

Use after `ydk-to-json` to prepare an agent to pilot a particular deck version.
Read `AGENTS.md`, the chosen JSON, its YDK, and `docs/agent-play.md`. Apply the
selected rules profile if one is known. This skill analyzes existing decks; it
does not import or change decklists.

## Workflow

1. Inventory all three sections, exact copy counts, card names, full text, types,
   and stats. Include Side Deck cards and unusual Extra Deck choices. Use:

   ```sh
   python skills/deck-playbook/scripts/audit.py inventory decks/unassigned/dracotail/deck.json
   ```

2. Read every card's text before assigning roles. Group cards as starters,
   extenders, Fusion enablers/materials, payoff monsters, interaction, recovery,
   hand traps, board breakers, and sideboard choices. A card can have several
   roles. State when to use it, when to save it, and its activation requirements.
3. Build a directional access map. Distinguish Deck-to-hand searches, Deck-to-field
   summons/sets, GY sends, banishes, and recovery. List actual included targets,
   exclusions, costs, trigger timing, and once-per-turn limits. Check names,
   Types, Attributes, Levels/Ranks, named materials, and card-text mentions;
   archetype labels alone do not prove a target is eligible.
4. Identify synergies and conditional combo lines from those maps. Trace each
   action against the exact list, including material location, hand consumption,
   remaining copies, simultaneous triggers, costs, targets, chain order,
   restrictions, and timing. Give the starting hand/state, numbered steps,
   expected remaining board/resources, failure points, and a fallback.
   Never label a line "one card" when it needs another material or discard.
5. Explain first/second play, opponent-turn interaction, resource priorities,
   End Phase follow-up, hand-trap response, and sideboarding. Tactical heuristics
   are conditional advice, not mandatory actions or guaranteed optimal play.
6. Add guidance for an agent: legal actions, information boundaries, turn/chain
   state tracking, usage counters and locks, summon history, opponent response
   windows, lethal checks, and recovery after interrupted or invalid actions.
   Refer to the shared agent protocol rather than treating the guide as a referee.
   Link the self/managed agent definitions where useful. Self guidance can use only
   revealed human information; managed coaching may use full human state while leaving
   human action choices to the human. Opponent knowledge remains limited to legal reveals in both modes.
7. Use `decks/<format>/<deck-name>/` with generic `deck.ydk`, `deck.json`,
   `guide.md`, and optional source/import `README.md`. Save the playbook as
   `guide.md` beside that folder's `deck.json`; the folder carries the deck name.
   Record the deck ID, JSON SHA-256, counts, format/banlist status, and review
   status. Link the exact JSON and YDK. Preserve earlier format-specific guides.
8. Audit coverage, manually review the combo traces, update guide indexes, and
   commit the skill and playbooks to the requested repository:

   ```sh
   python skills/deck-playbook/scripts/audit.py check decks/unassigned/dracotail/deck.json
   ```

The audit checks document structure, deck identity/hash, and card coverage. It
does **not** simulate effects or prove combo legality. State whether a guide was
reviewed against card text, tested in a rules engine, or verified with rulings.
Uncertain interactions must be identified as requiring adjudication; do not
silently turn assumptions into executable lines. If the format is unknown, say
so and do not assert that the deck or particular cards are legal.

## Markdown format

Start with YAML front matter containing `deck_id`, `deck_json`, `ydk`,
`deck_json_sha256`, `format` (null if unknown), `banlist` (null if unknown),
and `review_status`. Use `deck_json: deck.json` and `ydk: deck.ydk`; both are sibling filenames. Use these headings:

1. `## Overview`: exact list size, game plan, limitations, and guide scope.
2. `## Card roles and usage`: group-based tactical descriptions plus an inventory
   table with one row per distinct card. Columns: ID, name, Main/Extra/Side counts,
   role, and when/how to use it. Show absent targets explicitly when relevant.
3. `## Search, summon, and recovery map`: source, destination, eligible included
   targets, timing/cost, and limitations; distinguish searching from sending/setting.
4. `## Synergies`: explain how interactions create value and what breaks them.
5. `## Combo lines`: named, conditional, numbered traces with inputs, outputs,
   interruptions, and fallbacks. Do not assume effects resolve unopposed in live play.
6. `## Going first and going second`: priorities, sequencing, and stopping points.
7. `## Opponent-turn interaction`: activation windows, what to disrupt, and resource costs.
8. `## Resource and timing ledger`: once-per-turn rules, locks, delayed effects,
   recursion, counters, original/summoned state, and material restrictions.
9. `## Sideboarding and matchup notes`: swaps are suggestions; preserve deck sizes
   and relevant card limits. Include opponent-specific advice only where supported.
10. `## Agent piloting checklist`: operational decision steps and shared protocol link.
11. `## Uncertainties and validation`: assumptions, unresolved rulings, source of
    reasoning, and what was/was not mechanically verified.

Avoid unsupported win-rate claims, invented cards, automatic combo guarantees,
and treating effects summarized here as replacements for full JSON card text.
