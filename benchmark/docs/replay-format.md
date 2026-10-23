# Replay bundle, version 1.0

`replays/<folder>/replay.json` is the manifest. `events/000001.json` and subsequent
files hold one native JSON play each. All strings are UTF-8. The folder is a
readable storage path; the manifest identifies the source as `db-json-<replay ID>`.

| Manifest field | Meaning |
| --- | --- |
| schema_version, id | Schema version and native replay identity |
| source | Viewer URL/ID, canonical selected-source digest, adapter version and retrieval time |
| format | Literal source codes and unreviewed rules fields; external format declarations live in the registry |
| players | Stable p1/p2 slots and source usernames |
| coverage | Completeness/review status; hidden-card and physical-copy gaps |
| source_metadata | Selected native JSON data and coverage audit |
| event_count | Number of native plays |
| events | Ordered `{sequence, path, sha256}` file references |

| Event field | Meaning |
| --- | --- |
| sequence | Consecutive one-based sequence |
| source_index | Zero-based index in the original `plays` array |
| game | Sequential game, incremented on `Begin next duel` |
| kind | Observational grouping such as summon, move, phase or unclassified |
| actor | p1/p2 when the username identifies a player; otherwise null |
| payload | Literal `native` play structure plus observed annotations |

There is one event per native play, including batched opening draws. Equal
elapsed times keep source order; absent times remain null. No missing moves,
card identities or complete game states are invented. `kind` groups observations
for review; it does not assert legal execution or a decision window.

The supported adapter is `duelingbook-json-v1`. The source digest covers canonical
selected gameplay JSON, not raw uploaded whitespace. `load_bundle` verifies
ordered paths, per-file hashes, event count and source derivation. Reconversion
must reproduce the complete manifest data and annotations. `restore_source`
returns a copy of the selected JSON object, without restoring removed cosmetics
or original formatting.

[JSON Schemas](../schemas) document manifests, events and filtered bridge cases.
Python validation additionally checks source integrity and derivation.
[Candidate indexes](../benchmarks/candidates) use `source_index` and
`before_sequence`; candidates remain unreviewed. Read [native JSON](native-json.md)
before resolving runtime references or filtering private data.

Legacy text and API-observation bundles are rejected. Old text sequences/digests
cannot be reassigned to native JSON cases; import the original native response
and reconstruct/review any positions against that source.
