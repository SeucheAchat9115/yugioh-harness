# Yu-Gi-Oh! Harness

An agentic environment for humans and LLMs to play Yu-Gi-Oh!, with a shared
headless runtime and replay benchmarks in one repository.
The LLM interprets card text and rules, adjudicates effects and battles, and chooses
plays. The runtime manages random draws, authoritative state, permitted views,
local saves, and replay records. A full coded card-rules engine is outside the
project's scope.

Current, historical, and custom formats use their own rules profile and banlist.
Prepared [rules profiles](rules/README.md) cover modern TCG, Edison, Goat, and Perfect Circle,
with sourced rule summaries, historical changes, and dated banlist JSONs.

## Headless environment and benchmarks

This monorepo includes the former `yugioh-benchmark` project under
[`benchmark/`](benchmark/README.md), including its pinned source provenance, reviewed cases,
importers and historical results. Install once from this root:

```sh
python -m pip install -e .
yugioh-harness duel --repo .
yugioh-benchmark inspect benchmark/replays/db-json-40753-85958923
```

The headless command accepts versioned JSON lines for a trusted host/orchestrator.
It uses the same persisted decisions and writer as MCP. Execution-capable chat hosts
can drive it internally, including fresh opponent agents, without the human running
commands. A GUI can later consume structured filtered `interaction` data.
See [headless/chat integration](docs/headless.md) and the
[agreed architecture and staged roadmap](docs/architecture-and-roadmap.md).
Edison is the first full-duel validation scope; pilots use open intentions.
RL adapters and the GUI are planned, not implemented.

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
| `harness/` | Shared environment, runtime, state updates, player tasks, views, and persistence |
| [`benchmark/`](benchmark/README.md) | Replay sources, reviewed cases, metered evaluation, and historical results |
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
CI checks Python 3.11–3.13, benchmark integration on Linux/Windows, runtime tests, packaging, and all three duel
modes through installed stdio smoke tests. These checks verify the harness;
card legality, tactics, and real host subagent facilities require separate review.

For evaluations or structured player clients, the optional
[intent-v1 interface](docs/structured-intents.md) translates semantic card choices
into unapproved bookkeeping proposals. Independent rules review and the existing
persistent moderator workflow still govern execution and response windows.
