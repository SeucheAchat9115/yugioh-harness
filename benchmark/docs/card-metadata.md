# Current card references from YGOPRODeck

The selected [card reference snapshot](../benchmarks/card-metadata/db-json-40753-85958923.json)
resolves all 42 distinct passcodes explicitly defined in the supplied native
Duelingbook replay. Names match every corresponding replay definition; 10 card
texts differ from the embedded export text. These differences are retained for
review, rather than used to rewrite the original replay.

The [YGOPRODeck v7 API](https://ygoprodeck.com/api-guide/) accepts a comma-separated
list of card passcodes in its `id` parameter and returns names and descriptions.
The lookup uses Duelingbook `serial_number`, normalized to an eight-digit passcode.
Duelingbook's `card.id`, `object_id`, hand and deck references are different
identifiers and are never submitted as card passcodes. An API lookup cannot fill
unobserved deck slots or establish complete decklists from those runtime IDs.

The snapshot is a current API reference, not a historical ruling source. It does
not establish the replay's format, banlist or pre-errata card texts. In particular,
Dark Magician of Chaos's current text refers to End Phase recovery, whereas this
replay records immediate recovery. Keep historical rules review pending.

Maintainer commands:

```sh
# One batched network request, cached to a new output path:
yugioh-benchmark card-metadata replays/db-json-40753-85958923 --retrieved-at 2026-10-08T00:00:00Z --output imports/card-reference.json
# Use a previously saved cardinfo.php JSON response without network access:
yugioh-benchmark card-metadata replays/db-json-40753-85958923 --response imports/api-response.json --retrieved-at 2026-10-08T00:00:00Z --output imports/card-reference-offline.json
```

Use the actual response retrieval timestamp. Existing output files are refused;
repeat evaluations reuse the pinned snapshot without contacting the API. Missing
passcodes, malformed replay passcodes and differing names/texts are explicit.
Ambiguous duplicate API IDs or malformed responses are rejected. Each snapshot
binds the replay payload hash, request URL, response-byte hash and canonical
selected card-data hash. The selected fixture omits artwork, prices and set lists.
The raw API response remains local, so its byte hash is a provenance record;
offline consistency checks use the selected data hash and source binding.

The whole snapshot is evaluator data: its replay-derived names and differences
can reveal future/opponent cards. Player packets must filter by information
available at that checkpoint and the independently reviewed card-text version.
Adding references does not certify legal moves or produce a model score.

Names and game text are separately attributed third-party material; see
[third-party notices](../THIRD_PARTY_NOTICES.md).
