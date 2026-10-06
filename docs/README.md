# Documentation map

Use the linked page for each topic instead of maintaining competing copies.

| Page | Owns |
| --- | --- |
| [Quickstart](quickstart.md) | Installation, generated host configuration, readiness, and starting a duel |
| [Orchestration](orchestration.md) | Provider-neutral MCP tools and the single-conversation task workflow |
| [Harness](harness.md) | Maintainer architecture, direct CLI transport, state updates, and recovery |
| [Agent play](agent-play.md) | Rules agreement, card legality, chains, response windows, and adjudication |
| [Duel experience](duel-experience.md) | Fixed display, human recommendations, automatic continuation, and private checkpoints |
| [Natural-language actions](natural-language-actions.md) | Translating intentions into approved internal action records |
| [Player isolation](player-isolation.md) | Cooperative/enforced boundaries, child attempts, deadlines, and cancellation |
| [Agent versus agent](agent-vs-agent.md) | Two managed player slots and optional role-bound process deployment |
| [Game storage](game-storage.md) | Archive schema, shared snapshots, selective replay, and compatibility |
| [Releases](releases.md) | Packaging validation and versioned publication |

Runnable agent policies live in [agents/](../agents/README.md); reusable workflows
live in `skills/`. Deck-specific advice belongs in each bundle's `guide.md`,
format rules in `rules/`, and exact historical assets in `snapshots/`.
