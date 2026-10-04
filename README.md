# Yu-Gi-Oh! Harness

This repository is an **agentic harness for an LLM to play Yu-Gi-Oh! against
another agent or a human**. The LLM interprets card text and rules, checks legal
moves, resolves effects and battles, moderates response windows, and chooses or
explains plays. The harness supplies the decklists, card data, guides, reliable
state tools, and reproducible records that support those decisions.

A complete coded game engine is not the project goal or a prerequisite for play.
The LLM performs game adjudication against the agreed rules and ruling sources;
the harness records and checks the structural consistency of its state updates.

The repository supports current, historical, and custom formats. Each game selects
its own format, banlist, and rules version.

## Start a duel by talking to one agent

Open this repository in a tool-capable Codex, Claude, or Gemini environment and say:

> Read `agents/orchestrator/AGENT.md`. Start an open duel: I play Branded Despia
> against Dracotail. Guide me through setup and play.

You always speak to the **orchestrator**. It handles configuration, runtime calls,
local saves, and resumption. It asks you for human choices and launches player
subagents sequentially with their respective contexts. In agent-versus-agent
mode it manages both private player children while you watch public state.
Dispatch reserves durable attempts with deadlines, saved child handles, and
bounded retries; [player isolation](docs/player-isolation.md) requires verified
host restrictions or a tool-free model request.
No Python commands, JSON preparation, or separate player sessions are required
from you during a duel. See [conversational play](docs/codex-play.md) and the
[orchestration skill](skills/duel-orchestrator/SKILL.md).

The host needs runtime tools and safe native subagent support; plain chat apps
cannot execute this workflow just by reading the repo. MCP can be installed once,
or the orchestrator can operate the backend through its execution tools.

## From a decklist to a playable agent

1. **Import the deck:** obtain a YDK and preserve its original contents.
2. **Prepare card data:** use [YDK to JSON](skills/ydk-to-json/SKILL.md) to create a
   `deck.json` in the deck folder with ordered Main/Extra/Side IDs and gameplay-only card
   records: names, full text, types, stats, and applicable Link/Pendulum details.
3. **Prepare decisions:** use [Deck playbook](skills/deck-playbook/SKILL.md) to create
   `guide.md` in that folder with card roles, search/recovery maps, synergies, conditional
   combo lines, first/second play, interactions, and agent-specific state tracking.
4. **Agree on the game:** select a rules profile, check deck legality, assign players,
   and assign the LLM moderator; the harness stores the authoritative state.
5. **Play and record:** follow the [agent play protocol](docs/agent-play.md), respect
   response windows and hidden information, and save the public turn log and authorized
   game state. Use post-game analysis to improve future guide versions.

## Duel modes and agents

| Mode | Agent | How the human plays | Agent knowledge |
| --- | --- | --- | --- |
| Agent vs agent | [Isolated AI players and moderator](agents/agent-duel/AGENT.md) | Two independent agents choose plays; the moderator manages both decks. | Each player sees its own hidden state; the moderator knows both. |
| Blind | [Blind orchestrator/player](agents/blind-duel/AGENT.md) | Human privately manages their own deck/hand and declares actions. | Own cards plus legally revealed human information; no human deck/hand import. |
| Open | [Open orchestrator/coach/player](agents/open-duel/AGENT.md) | Human selects a linked YDK, then chooses from guided options; the agent manages both decks. | Full human state, explicitly including hidden cards. |

Read [agent setup and usage](agents/README.md) for invocation examples and the
session helper. In open mode choose [Branded Despia](decks/unassigned/branded-despia/deck.ydk)
or [Dracotail](decks/unassigned/dracotail/deck.ydk). Human choices and response
opportunities are preserved in human modes. [Agent-vs-agent setup](docs/agent-vs-agent.md)
uses one conversational orchestrator and two private player subagents.

The persistent Python harness coordinates authoritative state, player views,
structural action validation, local persistence, and decision rendering. Player
contexts include visible card text, pending effects, and recent reviewed events.
The orchestrator operates the runtime internally; command-line entry points are
backend interfaces for maintainers.
See [harness architecture and commands](docs/harness.md) for setup and the JSON-lines
moderator interface. Human chat and model clients connect through player adapters.
[Codex play integration](docs/codex-play.md) provides a persistent MCP server,
durable decision IDs, safe retries, convenient state tools, and a host-driven
player/moderator loop.

The LLM moderator records its adjudicated actions through guarded state updates.
Deterministic draw/shuffle commands handle bookkeeping and randomness. Optional
coded effect helpers can reduce repeated work, but a card needs no Python handler
to be played: the LLM resolves it using its exact text and the agreed rules, then
records the result. Uncertain rulings pause for the agreed source or referee.

Humans declare actions in natural language. The moderator uses
[internal action records](docs/natural-language-actions.md) for confirmed decisions,
guarded state updates, response tracking, and replay. Private changes stay outside
the repository; public logs contain reviewed narration and permitted views.

Every gameplay message uses a [fixed state/decision display](docs/duel-experience.md),
with two legal recommendations when available and free-text input. Verified
compulsory/no-choice steps advance automatically until the next real choice and
are explained in the next display. Game updates save locally; no commit/push
without an explicit request. Private checkpoints preserve managed hidden cards,
orders, pending choices, rules, and snapshots for exact resumption. Managed cards
are conserved across updates, writers share locks, and failed saves require
recovery before play continues. Public projections omit private annotations.

## Structure

- `decks/<format>/<deck-name>/`: `deck.ydk`, `deck.json`, `guide.md`, and optional `README.md`.
- `decks/unassigned/`: Imported decks awaiting a confirmed format and banlist.
- `skills/`: Reusable card-data conversion and strategic-analysis workflows.
- `harness/`: Persistent runner, engine, effect registry, player adapters, views, storage, and rendering.
- `agents/`: Blind/open policies and moderator instructions; legacy CLI compatibility wrappers.
- `tests/`: State/replay, runner, information-boundary, resume, and transport tests plus benchmarks.
- `docs/agent-play.md`: Shared action, response, information, and recording protocol.
- `rules/`: Format profiles for card pools, banlists, and applicable rules.
- `games/<format>/<game-id>/`: Metadata, turn logs, deck snapshots, and saved states.
- `templates/`: Format-neutral starting points for deck/game records.

Use a consistent format ID such as `edison`, `goat`, or `tcg`. Record a banlist date
and rules version for changing formats. Keep each guide tied to its JSON hash and
refresh it when the deck or relevant text changes.

## Current decks

| Deck | Main / Extra / Side | Gameplay data | Agent playbook |
| --- | --- | --- | --- |
| Branded Despia | 53 / 14 / 12 | [JSON](decks/unassigned/branded-despia/deck.json) | [Guide](decks/unassigned/branded-despia/guide.md) |
| Dracotail | 40 / 15 / 15 | [JSON](decks/unassigned/dracotail/deck.json) | [Guide](decks/unassigned/dracotail/guide.md) |

Both decks were supplied as user-uploaded YDKs. Author and import notes remain
in the [deck index](decks/unassigned/README.md). The guides are
reviewed against the exact stored card text and inventory; their combo lines have
not been comprehensively validated through played scenarios. Format and banlist
assignment remain pending.
An [open Branded Despia versus Dracotail duel](games/casual-modern/2026-10-03-open-001/resume.md)
is locally saved during Turn 1 under agreed casual modern rules. No completed game is
recorded. The [original planning file](games/planned/branded-despia-vs-dracotail.json)
remains separate from the actual session.

Preliminary [Edison Blackwings](decks/edison/blackwings/guide.md) and
[Lightsworn](decks/edison/lightsworn/guide.md) notes live beside their deck index;
their deck imports are pending.

## Sources and versioning

Use user-supplied YDKs or decklists from the selected source. Record available
source URLs, author, retrieval information, and source version in the
accompanying documentation. YGOPRODeck supplies card data, not replacement lists.
Enriched gameplay JSON excludes prices, images, printings, and import/API metadata.

Use unique deck/version IDs and create a new version for deck changes. Preserve
exact deck, card-text, guide, and rule snapshots for each game so later updates
do not alter historical records. A card-data refresh alone does not change deck
composition, but can require a guide review.

## Game records and agent information

Create `games/<format>/YYYY-MM-DD-001/` from the templates. Record format, banlist,
rules version, LP/hand/first-turn settings, field layout, players, and start player.
The live state also needs effect counters, locks, summon history, materials, delayed
effects, and card-instance identities; the shared templates are starting points.

Blind mode uses own permitted information and public observations; the human
never supplies hidden deck/hand data to the agent. Open mode deliberately allows
the moderator/opponent to know all human state while guiding their decisions.
Keep live public logs separate from private states, preserve shuffled order when
resuming, and archive complete records only by agreement. Human and agent opponents
receive response opportunities under the same agreed protocol.

## Automation and checks

[Enrich YDK decks](.github/workflows/enrich-ydk.yml) runs conversion tests, fetches
YGOPRODeck data, generates gameplay-only JSON, and commits successful results on
relevant changes to `main`. It also supports manual runs.

Deck playbooks are reasoned analyses. Run the bundled audit to check a guide's
structure, exact card inventory, counts, and JSON hash:

```sh
python skills/deck-playbook/scripts/audit.py check decks/unassigned/dracotail/deck.json
```

This audit does not simulate combos or certify legality; unresolved rulings must
be checked before an agent uses a dependent line.

[Duel agent helper checks](.github/workflows/duel-agents.yml) test blind/open
information boundaries, hidden-card masking, private storage, fixed draws, and
resume behavior. These tests do not adjudicate card effects. Run `python tests/benchmarks/runner.py`
for local engine latency measurements; model latency is measured separately.
