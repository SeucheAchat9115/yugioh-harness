# Games

Use the [action workflow](../docs/natural-language-actions.md) for natural-language
decisions. Private journals stay outside the repo. Public `events.json` and
`actions.md` record reviewed narration; `state.json` is a public projection.

Store each game in `games/<format>/YYYY-MM-DD-001/`.
Use a consistent format ID and fill in the metadata from `templates/game.json`.
Record the banlist and rules version so the game remains reproducible.

Before play, snapshot each deck bundle in `decks/<deck-name>/` under the game's
folder, retaining `deck.ydk`, `deck.json`, and `guide.md`,
select a format profile, and configure the starting LP, hand size, first-turn
rules, and field layout. Shared templates leave these settings unset.

Turn logs record actions, costs, targets, chains, resolutions, and Life Points.
Saved states preserve hidden cards, card order, and random outcomes for resuming.
Public logs keep unknown cards unknown. Put post-game analysis in a separate section.

No games have started yet. Current user-selected matchup:
[Branded Despia versus Dracotail](planned/branded-despia-vs-dracotail.json).
Player assignments, format, banlist, and rules are pending.

## Duel mode

Record `mode: blind` or `mode: open` before starting. Use the
[duel agents](../agents/README.md) and `templates/duel-config.json` for guided setup.
Snapshot known bundles under `decks/<player>/<deck-name>/` to support mirrors.
Blind mode records only human public counts/reveals and no human deck snapshot.
Open mode manages both player states; public logs still hide private card identities.
Live private helper state stays outside the shared repository.
