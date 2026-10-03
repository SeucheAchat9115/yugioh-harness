# Games

Store each game in `games/<format>/YYYY-MM-DD-001/`.
Use a consistent format ID and fill in the metadata from `templates/game.json`.
Record the banlist and rules version so the game remains reproducible.

Before play, save immutable decklist copies in the game's `decks/` subfolder,
select a format profile, and configure the starting LP, hand size, first-turn
rules, and field layout. Shared templates leave these settings unset.

Turn logs record actions, costs, targets, chains, resolutions, and Life Points.
Saved states preserve hidden cards, card order, and random outcomes for resuming.
Public logs keep unknown cards unknown. Put post-game analysis in a separate section.

No games have started yet. Current user-selected matchup:
[Branded Despia versus Dracotail](planned/branded-despia-vs-dracotail.json).
Player assignments, format, banlist, and rules are pending.
