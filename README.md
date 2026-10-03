# Agentic Yu-Gi-Oh!

An archive for Yu-Gi-Oh! decklists, strategies, game logs, and saved game states
across current, historical, and custom formats.

## Structure

- `decks/<format>/`: Versioned decklists with sources and Main, Extra, and Side Decks.
- `strategies/<format>/`: Deck guides and matchup advice for a particular format.
- `rules/`: Format profiles defining card pools, banlists, and applicable rules.
- `games/<format>/<game-id>/`: Game metadata, turn logs, deck snapshots, and saved states.
- `templates/`: Reusable templates without a default format.

Use a consistent format ID, such as `edison`, `goat`, or `tcg`, in folder names
and JSON metadata. For changing formats, record the banlist date and rules version
as well; a format name alone is not enough to reproduce a game.

## Decklists

All decklists must come exclusively from **https://cardcluster.com/**.
Record the exact deck URL, retrieval date, author, and available source version.
Check legality against the chosen format's card pool and banlist before playing.
Never present an unverified list as an original list from an online source.

Use unique deck IDs that include the format and version, such as
`edison-blackwings-v1`. Save deck changes as new versions.
Before the first turn, copy the exact decklists into the game's `decks/` folder
so later changes do not alter previous game records.

## Saving games

Create `games/<format>/YYYY-MM-DD-001/` and copy the templates.
Use `game.json` for metadata, `log.md` for turns, and `state.json` for a paused game.
Fill in the format, banlist, rules version, starting LP, opening hand size,
first-turn draw rule, and field layout before play. These vary by format.

Complete game states may contain hidden cards. During an active duel,
only show information in chat that the relevant player is allowed to see.
Public logs must not reveal hidden cards. Preserve shuffled card order and
random outcomes when resuming a game.

## Initial content

The first planned matchup is Edison Blackwings versus Lightsworn.
Its format rules and strategy notes are stored in the Edison-specific folders.
Both Cardcluster deck imports are still pending. No games have been played yet.
