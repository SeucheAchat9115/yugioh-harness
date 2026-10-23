# Code license and selected source data

Repository code and documentation use the MIT license in `LICENSE`. This
license does not grant rights to third-party game text, replay content,
usernames or chat. Replay fixtures, their derived observation bundles and
candidate indexes are separately attributed source data.

`fixtures/duelingbook/aco77-sdesowitz02-2026-10-07.json` is the user-supplied
Duelingbook `view-replay` export for the same match, supplied on 2026-10-08.
It is now the primary selected source. Account/display metadata was removed;
gameplay entries, private/public logs and card definitions remain source data.
Its uploaded-byte digest and selected fixture/canonical payload digests are
recorded separately in the registry. The former copied-text fixture and derived
bundle were removed from the current dataset; they remain in Git history with
their original attribution to this same user-supplied replay.
The JSON includes both players' private card observations and must never be
passed directly to an evaluated player. These source data are not MIT licensed.
No artwork is included; this notice does not claim ownership of Yu-Gi-Oh
card names or game text.

The fixture preserves the participants' displayed usernames and match chat;
it is not anonymized. Its source URL is attribution, not a license statement.
No separate third-party redistribution license was supplied.

Git history also contains the removed `replays/db-2178594` archive fixture from
`nedhmn/duel-tools`, originally supplied under MIT. Its original attribution,
license notice and pinned provenance remain in the commits containing it.

`benchmarks/card-metadata/db-json-40753-85958923.json` contains selected card
names, descriptions and statistics retrieved from the YGOPRODeck v7 API on
2026-10-08. Source: https://db.ygoprodeck.com/api/v7/cardinfo.php ; documentation:
https://ygoprodeck.com/api-guide/ . Retrieval timestamp, exact passcode query and
response/selected-data digests are stored in the snapshot. This third-party
game material is not relicensed under MIT; no separate redistribution license
was established. No artwork, prices or set lists are included.
