# Changelog

## Unreleased

- Replace the README bar chart with four performance-versus-runtime
  plots (three KPIs and final score). Publish aggregate timing bounds,
  distinguish workflow spans from model latency, and export standalone PNG/SVGs.

- Read UTF-8 replay fixtures explicitly in tests, review preparation and result
  plotting, fixing Windows failures caused by the default code page.

- Publish aggregate Sol/Luna checkpoint results, a README comparison plot and
  reproducible plotting script. Document host assistance, differing prompts,
  the Sol prompt omission and remaining full-game evaluation gaps. Keep raw
  model logs and harness saves local.

- Review all 185 previously pending replay work items: approve 14 additional
  scoped checkpoints, exclude 77 bookkeeping/substeps, and document 94 blocked
  items. Expand the suite to 18 independent checkpoints / 36 tasks. Preserve
  source-bound findings, privacy filtering and deferred historical rulings.

- Native `view-replay` JSON is the supported replay input. Remove the text fixture,
  bundle, candidate index and converters, plus exact-response scoring and isolated
  operation probes. Reimport old sources as native JSON and review their positions.
- Document replay acquisition through browser Network/Response inspection.
- Preserve 554 native plays across two games, source integrity and unreviewed
  candidates; candidate indexes now identify native `source_index` values.
- Cache current YGOPRODeck names/texts for all 42 observed passcodes separately
  from original replay evidence and historical rules.
- Record the user’s Perfect Circle 2007 format declaration and a September 2007
  reference; historical card text and legality review remain pending.
- Three equally weighted KPIs: state recreation, semantic human-move agreement
  and independently reviewed rule correctness. Expose `score-kpis` in the CLI.
- GPT-6.1 Sol is the default evaluation target. Update CI and source packages
  for the native JSON workflow; scoped results are reported separately from
  complete live-duel evaluation.

## 0.1.0 — initial public toolkit

- Offline conversion of copied Duelingbook duel text, individually or in batches.
- Hashed observation bundles with lossless decoded source text and line references.
- Source registry and unreviewed candidates for replay 40753-85958923.
- Reviewed decision execution through the public yugioh-harness player interface.
- Explicit response-agreement scoring with missing responses counted as zero.

There are no approved decision cases yet. Automatic state reconstruction,
strategic grading, provider transports and full-duel win-rate evaluation are not
implemented.
