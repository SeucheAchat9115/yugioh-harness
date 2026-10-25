# Blackwing vs. Lightsworn chat duel

[Download the replay](replay.zip) · [SHA-256 checksum](SHA256SUMS)

| Field | Value |
| --- | --- |
| Game ID | `max-edison-20261023` |
| Format | Edison, March 1, 2010 TCG list |
| Rules snapshot | `edison-2026-10-06`, with the agreed historical overrides |
| Mode | Managed human Blackwing vs. agent Lightsworn; human starts |
| Result | Lightsworn wins on Turn 12; human 0 LP, agent 500 LP |
| Recorded transitions | 190, final revision 190 |
| Immutable assets | 9 rules, deck and guide snapshots |
| Player isolation | Cooperative, fresh native player agents |

The ZIP contains a self-contained schema-4 archive: `game.json`, `events.json`,
190 indexed event records, and every referenced snapshot under the extracted
game's own `snapshots/` store. Saved decisions and prompts are preserved where
recorded, including the archive's original decision-evidence coverage labels.

This is an **omniscient post-game replay** containing known hidden hands and set
identities. Active pilots must receive filtered runtime contexts instead.
Remaining decks are unordered physical-copy inventories; recorded draw, mill and
shuffle outcomes reproduce the played trajectory. Live checkpoints, shuffled
future draw queues, session files and host credentials are not included.

## Replay

From the repository root, extract outside the checkout and use the existing
archive reader:

```sh
python -m zipfile -e replays/edison/max-edison-20261023/replay.zip ../yugioh-replay-export
python -m harness.storage.archive replay --game-dir ../yugioh-replay-export/max-edison-20261023 --revision 190 --perspective human
python -m harness.storage.archive log --game-dir ../yugioh-replay-export/max-edison-20261023
```

Use any revision from 0 through 190 to inspect an earlier position. Full hidden
state is available through the reader's `moderator` perspective. The replay
reader creates disposable caches outside the extracted game directory.

## Validation

The ZIP was extracted into a fresh temporary directory and replayed without the
original shared snapshot store or replay cache. All 190 transitions and referenced
asset hashes were verified. The reconstructed final state exactly matched the
archive-normalized private final checkpoint: finished, Turn 12, human 0 LP and
agent 500 LP. ZIP integrity and the published SHA-256 checksum were also checked.

These checks establish replay integrity and physical-card accounting. Card rules
and response windows were adjudicated by the conversational referee; the archive
is a record of that duel, not an independent rules-engine certification.
