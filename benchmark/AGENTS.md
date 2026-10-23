# Benchmark repository instructions

- Keep the converter generic and independent of a coded card-effects engine.
- Preserve original source event order and physical-copy identifiers. Do not
  infer missing cards, costs, chains, legal response opportunities or strategic labels.
- A simulator operation is not a certified legal move. Imported replays are
  unreviewed until their state/rules/decision boundaries have been checked.
- Keep source URLs, payload digests, adapter versions and known information gaps.
- Player agents receive only a reviewed, filtered packet. Never give them complete
  replays, future actions/outcomes, grading keys or opponent hidden cards.
- Keep raw replay imports and model-run logs local and ignored. Version
  selected benchmark fixtures and reviewed cases deliberately; no harness game saves.
- The orchestrator runs tools internally; users can request imports/evaluation in
  natural language. Maintainer commands are not steps a duel player must perform.
- Run meaningful offline converter/privacy/integrity tests. Importing supplied native
  JSON runs offline, without browser credentials or an automated capture.

