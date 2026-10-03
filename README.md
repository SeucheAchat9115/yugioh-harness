# Agentic Yu-Gi-Oh!

The goal of this repository is to let an **agent play a Yu-Gi-Oh! deck against
another agent or a human**. It brings together the exact decklist, gameplay card
data, strategic guidance, agreed rules, and reproducible game records an agent
needs to choose and explain its actions.

The repository supports current, historical, and custom formats. Each game selects
its own format, banlist, and rules version.

## From a decklist to a playable agent

1. **Import the deck:** obtain a Cardcluster YDK and preserve its original contents.
2. **Prepare card data:** use [YDK to JSON](skills/ydk-to-json/SKILL.md) to create a
   same-basename `.json` with ordered Main/Extra/Side IDs and gameplay-only card
   records: names, full text, types, stats, and applicable Link/Pendulum details.
3. **Prepare decisions:** use [Deck playbook](skills/deck-playbook/SKILL.md) to create
   a same-basename `.md` with card roles, search/recovery maps, synergies, conditional
   combo lines, first/second play, interactions, and agent-specific state tracking.
4. **Agree on the game:** select a rules profile, check deck legality, assign players,
   and choose a game engine, referee agent, or human to maintain authoritative state.
5. **Play and record:** follow the [agent play protocol](docs/agent-play.md), respect
   response windows and hidden information, and save the public turn log and authorized
   game state. Use post-game analysis to improve future guide versions.

A playbook supplies candidate decisions; full card text and the agreed rules decide
whether an action is legal in the actual state. The repository currently provides
assets and a play protocol. It does not yet implement a duel simulator, a complete
rules engine, or autonomous agent orchestration.

## Structure

- `decks/<format>/`: Deck bundles: `<deck>.ydk`, `<deck>.json`, and `<deck>.md`.
- `decks/unassigned/`: Imported decks awaiting a confirmed format and banlist.
- `skills/`: Reusable card-data conversion and strategic-analysis workflows.
- `docs/agent-play.md`: Shared action, response, information, and recording protocol.
- `rules/`: Format profiles for card pools, banlists, and applicable rules.
- `strategies/<format>/`: Additional format/matchup notes.
- `games/<format>/<game-id>/`: Metadata, turn logs, deck snapshots, and saved states.
- `templates/`: Format-neutral starting points for deck/game records.

Use a consistent format ID such as `edison`, `goat`, or `tcg`. Record a banlist date
and rules version for changing formats. Keep each guide tied to its JSON hash and
refresh it when the deck or relevant text changes.

## Current decks

| Deck | Main / Extra / Side | Gameplay data | Agent playbook |
| --- | --- | --- | --- |
| Branded Despia | 53 / 14 / 12 | [JSON](decks/unassigned/branded-despia-v1.json) | [Guide](decks/unassigned/branded-despia-v1.md) |
| Dracotail | 40 / 15 / 15 | [JSON](decks/unassigned/dracotail.json) | [Guide](decks/unassigned/dracotail.md) |

Both original exports came from Cardcluster via user uploads. Source links remain
in the YDK headers and [deck index](decks/unassigned/README.md). The guides are
reviewed against the exact stored card text and inventory; their combo lines have
not been executed in a duel engine. Format and banlist assignment remain pending.
The [planned Branded Despia versus Dracotail matchup](games/planned/branded-despia-vs-dracotail.json)
has not started. No games have been played yet.

Earlier Edison Blackwings/Lightsworn notes remain in their format-specific folders;
their Cardcluster deck imports are pending.

## Sources and versioning

Decklists must come exclusively from **https://cardcluster.com/**. Record the exact
source URL, author, retrieval information when available, and source version in the
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

An agent uses its own permitted information and public observations. Opponent
private hand/deck order and hidden cards belong to the referee or authorized player.
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
python skills/deck-playbook/scripts/audit.py check decks/unassigned/dracotail.json
```

This audit does not simulate combos or certify legality; unresolved rulings must
be checked before an agent uses a dependent line.
