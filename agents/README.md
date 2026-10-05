# Duel agents

The user talks only to the [orchestrator](orchestrator/AGENT.md) throughout every
mode. It moderates, manages local state, guides setup/resume, asks human questions,
and dispatches active agent players to private subagents sequentially. It reviews
returned intentions before changing the game. Follow the
[orchestration skill](../skills/duel-orchestrator/SKILL.md).

| Mode | Policy | Human experience |
| --- | --- | --- |
| Managed | [Human duel](human-duel/AGENT.md) | Select a linked YDK; choose guided moves or free text. Orchestrator manages human state; the opponent sees only legal reveals. |
| Self | [Human duel](human-duel/AGENT.md) | Manage hidden cards privately and declare actions to the orchestrator. |
| Agent vs agent | [Agent duel](agent-duel/AGENT.md) | Watch public events while the orchestrator prompts both player children. |

All modes use [shared moderator policy](shared/moderator.md). The LLM interprets
rules and card text; the harness supplies structural checks and reliable saves.
Player children get only their respective contexts, never parent/sibling history
or permission to use moderator tools. Cooperative native children may have
shared tools/files but must follow the no-tools/context-only instructions.
Enforced isolation requires host restrictions or a tool-free transport. The
selected policy is saved and preserved on resume.

## Start or resume conversationally

> Read `agents/orchestrator/AGENT.md`. Start an managed duel with me playing Branded
> Despia against Dracotail. Ask for any missing rules and guide me through play.

> Start a self duel. Your deck is Dracotail; I manage my own hidden cards.

> Run an agent-versus-agent duel with Branded Despia against Dracotail.

> Resume our saved duel `<game-id>`.

Current selectable bundles are [Branded Despia](../decks/unassigned/branded-despia/deck.ydk),
[Dracotail](../decks/unassigned/dracotail/deck.ydk),
[Blackwing](../decks/edison/blackwing/deck.ydk), and
[Lightsworn](../decks/edison/lightsworn/deck.ydk). The orchestrator discovers
new complete bundles automatically and resolves deck names/YDK links internally.
Unassigned decks need agreed format/banlist or explicit casual rules.

Users need no Python commands, JSON setup files, credential handling, or separate
player sessions during play. The host needs execution or MCP tools and safe native
subagent support; an ordinary chat app without them cannot run the harness.
See [host integration](../docs/codex-play.md) for one-time setup and backend tools.
[Harness internals](../docs/harness.md) retain command references for maintainers;
they are operated by the orchestrator, not the human player.

Saves, pause, and finish are local. No game commit/push without an explicit request.
Private checkpoints preserve managed hidden state, task IDs, prompts, and receipts.
Legacy `agents/runtime/` commands remain compatibility interfaces.
