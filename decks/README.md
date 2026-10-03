# Deck bundles

Each deck has its own folder, named after the deck:

```text
decks/<format>/<deck-name>/
  deck.ydk
  deck.json
  guide.md
  README.md          # optional source/import notes
```

Use lowercase hyphenated names such as `branded-despia` and `dracotail`.
Use `unassigned` as the format folder until the format/banlist is confirmed.
The JSON's deck ID/version remains stable when files move. Name separate variants
or versions explicitly when multiple bundles must coexist; never overwrite game snapshots.

`deck.ydk` preserves the Cardcluster export. `deck.json` contains gameplay-only
card data and ordered sections, produced by the [conversion skill](../skills/ydk-to-json/SKILL.md).
`guide.md` contains card roles, access maps, synergies, conditional combos, matchup
notes, and agent decisions, produced by the [playbook skill](../skills/deck-playbook/SKILL.md).
Store source links/author/import notes in the optional folder `README.md` and original
YDK header. Use `templates/deck.json` for initial metadata if needed.

Indexes: [Unassigned decks](unassigned/README.md) and [Edison](edison/README.md).
Preliminary guides can exist before imports, but must say that `deck.ydk`/`deck.json`
are pending; never fabricate those files.
