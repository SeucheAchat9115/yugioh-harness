# Games

Use the [action workflow](../docs/natural-language-actions.md) for natural-language
decisions. Private journals stay outside the repo. Public `events.json` and
`actions.md` record reviewed narration; `state.json` is a public projection.

Update all game records locally after each action. Do not stage/commit/push games
unless explicitly requested. “Save”, pause, finish, and automatic continuation
refresh local records/checkpoints only. Keep games out of unrelated code commits.
See [duel experience](../docs/duel-experience.md) for fixed displays, two recommended
moves, automatic verified no-choice steps, and complete private checkpoint recovery.

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

Current paused game: [Branded Despia versus Dracotail](casual-modern/2026-10-03-open-001/resume.md).
The human plays Branded Despia under agreed casual modern rules. The chain remains
unresolved at the saved human response window. Complete private state is outside
the repository. The earlier [planned matchup](planned/branded-despia-vs-dracotail.json)
remains a planning artifact.

## Duel mode

Record `mode: blind` or `mode: open` before starting. Use the
[duel agents](../agents/README.md) and `templates/duel-config.json` for guided setup.
Snapshot known bundles under `decks/<player>/<deck-name>/` to support mirrors.
Blind mode records only human public counts/reveals and no human deck snapshot.
Open mode manages both player states; public logs still hide private card identities.
Live private helper state stays outside the shared repository.
