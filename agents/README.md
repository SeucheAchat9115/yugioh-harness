# Duel agents

Load one of these definitions into the assistant that will run the duel. They
are reusable instructions for a tool-using conversational agent, not separate
hosted bots or a complete rules engine.

| Mode | Definition | Human cards | Human experience |
| --- | --- | --- | --- |
| Blind | [Blind duel](blind-duel/AGENT.md) | Agent never receives the hidden deck/hand. Human manages draws/searches privately. | Human declares plays; moderator checks revealed actions and plays the opposing deck. |
| Open | [Open duel](open-duel/AGENT.md) | Agent manages both decks and knows all human state. | Human selects a linked YDK; agent explains choices and waits for decisions while playing the opponent. |

Both use [shared moderator instructions](shared/moderator.md) and the
[play protocol](../docs/agent-play.md). A single assistant can adopt the chosen
definition; creating subagents is not required. Labels distinguish Moderator,
Opponent, and, in open mode, Coach. Rule disputes use an agreed source/referee.

## Start a conversation

Blind example:

> Read `agents/blind-duel/AGENT.md` and run a blind duel against me. Use Dracotail
> as your deck. I manage my own hidden cards. Ask for the rules and counts you need.

Open example:

> Read `agents/open-duel/AGENT.md` and guide me through an open duel. Let me select
> a YDK, manage my deck, and play the opposing deck. Explain my legal choices.

Current selectable human YDKs for open mode:

- [Branded Despia](../decks/unassigned/branded-despia/deck.ydk)
- [Dracotail](../decks/unassigned/dracotail/deck.ydk)

The agent discovers all complete bundles, so newly prepared decks can be offered
without editing its definition. Unassigned decks require an agreed format/banlist
or explicit casual rules before play. No duel is started by adding these files.

## Session helper

The stdlib-only helper initializes physical card instances, shuffles with system
randomness, deals opening hands, preserves remaining order, accounts for draws,
and renders public/human/agent/moderator perspectives. It does not adjudicate
card effects, chains, summons, battles, or deck legality.

Copy [duel-config.json](../templates/duel-config.json) to a local setup file and fill
every required value after agreement. Deck values are repo-relative **folder paths**,
such as `decks/unassigned/dracotail`, not YDK paths. Use `human`/`agent` player IDs.

- Blind: `mode: "blind"`, `human_deck: null`, declared `human_deck_counts` only.
- Open: `mode: "open"`, `human_deck` points to the human-selected bundle.
- Set format, banlist, rules profile/version, start player, LP, opening hand size,
  first-turn rules, and numeric field layout: `main_monster_zones`,
  `spell_trap_zones`, `extra_monster_zones`. Extend state for format-specific zones.
- `presentation.show_agent_hand` defaults to false. Enable only for agreed
  all-visible teaching. Open moderator knowledge is distinct from public display.

From the repository root, after preparing the setup file:

```sh
python agents/runtime/session.py start --repo . --config /tmp/duel-config.json --private-dir /tmp/duel-private-001
python agents/runtime/session.py view --state /tmp/duel-private-001/state.json --viewer agent
python agents/runtime/session.py view --state /tmp/duel-private-001/state.json --viewer human
```

The game directory is `games/<format>/<id>/`. First-turn draw is **not** automatically
applied during setup; only opening hands are dealt. When a draw is actually due:

```sh
python agents/runtime/session.py draw --state /tmp/duel-private-001/state.json --game-dir games/<format>/<id> --actor human --count 1 --viewer human
```

Replace placeholders in the command with the real format and ID. In blind mode
this changes human counts only; the human draws privately. In open mode it draws
the fixed next card. Never call `start` again to resume; use the saved private state.
For effects requiring a shuffle, the moderator must perform that shuffle when due
and record it; the helper's draw command does not shuffle automatically.

The private directory must be outside the repository. Commit only public records
during a live game. Prompt instructions and perspective views are not an access-
control sandbox: never give blind mode the human private state. Human hidden data
does not exist in a blind helper session at all.

## Verification

```sh
python -m unittest discover -s agents/runtime/tests -v
```

Tests cover mode boundaries, masked cards, private storage, fixed draw order,
resume behavior, and draw failure. They do not certify Yu-Gi-Oh! effect resolution.
