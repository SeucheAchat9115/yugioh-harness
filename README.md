# Yu-Gi-Oh! Harness

An agentic harness for an LLM to play Yu-Gi-Oh! against a human or another agent.
The LLM interprets card text and rules, adjudicates effects and battles, and chooses
plays. The runtime manages random draws, authoritative state, permitted views,
local saves, and replay records. A full coded card-rules engine is outside the
project's scope.

Current, historical, and custom formats use their own rules profile and banlist.

## Start a duel

Follow the [quickstart](docs/quickstart.md) for one-time installation and host setup.
Use a tool-capable environment with execution/MCP and fresh native player subagents;
a plain chat app cannot run the harness just by reading the repository.

Then tell your orchestrator:

> Read `agents/orchestrator/AGENT.md`. Start a managed Edison duel: I play Blackwing
> against Lightsworn. Check setup, ask who starts, and guide me through play.

| Mode | Experience |
| --- | --- |
| `managed` | Select your deck and choose guided moves or free text. The orchestrator manages your cards; the opponent sees only permitted information. |
| `self` | Manage physical cards privately and declare what a real opponent would see. The orchestrator does not import your hidden deck or hand. |
| `agent-vs-agent` | Watch one orchestrator dispatch two private player subagents sequentially and report public events. |

You talk to the same orchestrator throughout. It operates all runtime tools;
you never run Python commands, prepare JSON, or relay player messages during a duel.
Ask to save/pause or resume by game ID. Game saves are local; game archives and shared snapshots stay out of Git.

Player isolation defaults to cooperative instructions. Enforced isolation requires
verified host restrictions or a tool-free model transport. See
[player isolation](docs/player-isolation.md) for capabilities and limitations.

## Prepared decks

| Deck | Main / Extra / Side | Card data | Playbook |
| --- | --- | --- | --- |
| Branded Despia | 53 / 14 / 12 | [JSON](decks/unassigned/branded-despia/deck.json) | [Guide](decks/unassigned/branded-despia/guide.md) |
| Dracotail | 40 / 15 / 15 | [JSON](decks/unassigned/dracotail/deck.json) | [Guide](decks/unassigned/dracotail/guide.md) |
| Blackwing (Edison) | 40 / 15 / 15 | [JSON](decks/edison/blackwing/deck.json) | [Guide](decks/edison/blackwing/guide.md) |
| Lightsworn (Edison) | 40 / 15 / 15 | [JSON](decks/edison/lightsworn/deck.json) | [Guide](decks/edison/lightsworn/guide.md) |

Unassigned decks need an agreed format/banlist or explicit casual rules. Edison
bundles use the March 2010 banlist; their guides identify historical text differences.
Guides are reasoned advice, not comprehensive proof of combo legality.

To add a deck, use the [YDK conversion skill](skills/ydk-to-json/SKILL.md), then the
[playbook skill](skills/deck-playbook/SKILL.md). Each bundle contains `deck.ydk`,
`deck.json`, `guide.md`, and optional provenance in `README.md`. Card-data changes
require guide review and a matching JSON hash before the bundle is playable.

## Repository map

| Location | Purpose |
| --- | --- |
| [agents/](agents/README.md) | Orchestrator, human/player policies, and shared moderator instructions |
| [docs/](docs/README.md) | Setup, orchestration protocol, gameplay, storage, and maintainer references |
| [decks/](decks/README.md) | Prepared bundles grouped by format and deck name |
| [rules/](rules/README.md) | Format profiles and ruling sources |
| `skills/` | Deck preparation and conversational orchestration workflows |
| `harness/` | Runtime, state updates, player tasks, views, and persistence |
| `games/` (ignored) | Local metadata and schema-4 event archives |
| `snapshots/` (ignored) | Local immutable assets referenced by replay archives |
| `templates/` | Runtime input skeletons: duel configuration, action, decision, and host capabilities |
| `tests/` | Runtime/information-boundary tests, installed smoke tests, and temporary benchmarks |

Replay archives include known hidden state for review; player contexts stay
filtered. Future shuffled order remains in private checkpoints outside Git.
Game archives and snapshots are local, ignored data; back them up with the
external private save directory. Existing saved modes and archive schemas remain readable. See
[game storage](docs/game-storage.md) for the exact contract.

## Contribute

See [contributing](CONTRIBUTING.md), [release validation](docs/releases.md),
[changelog](CHANGELOG.md), [MIT license](LICENSE), and
[third-party notices](THIRD_PARTY_NOTICES.md).
Windows CI checks Python 3.11–3.13, runtime tests, packaging, and all three duel
modes through installed stdio smoke tests. These checks verify the harness;
card legality, tactics, and real host subagent facilities require separate review.
