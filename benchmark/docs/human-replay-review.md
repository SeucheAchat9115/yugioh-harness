# Human replay review

The private [Replay Review page](https://yugioh-duel-board.breathtakingcuckoo1.chatgpt.site/review)
starts with five positions from the recorded Edison Blackwing versus Lightsworn
duel. Each shows the acting player's pre-decision board and three reviewed moves.
Select one and save it. You can switch positions and export a partial or complete
set of human answers. The viewer omits the archived choice and future actions.
The live duel stays chat-controlled.

## Run an agent against the review

Use the exact archive and authored catalog that produced the Site's positions.
The catalog digest binds the answers to the same state, options and order.
Run this from the installed monorepo root, using a new output directory:

```sh
yugioh-benchmark prepare-human-review replays/edison/max-edison-20261023/replay.zip \
  --catalog benchmark/benchmarks/reviews/edison-ipad-review-v1.json \
  --answers /path/to/yugioh-human-review.json \
  --output benchmark/imports/edison-human-review

yugioh-benchmark evaluate benchmark/imports/edison-human-review \
  --output benchmark/runs/edison-human-review \
  --models MODEL_ID --referee-model REFEREE_MODEL_ID
```

The evaluation sends the same three move labels in the same order, plus the
permitted player context and pinned rules. The agent returns a structured
intention. The scorer measures agreement with the human choice through the
existing semantic normalization, legality review and harness execution.
A legal alternative contributes to rule correctness while disagreeing with
the human. The selected answer stays in grader data.

## Publish another recorded game

Author a catalog like `benchmark/benchmarks/reviews/edison-ipad-review-v1.json`
against a verified schema-4 archive. Review each recorded decision window and
supply three distinct legal intentions, neutral labels, public facts and any
required activation cost plans. The exporter verifies the replay hash and
checks each intention against a real archived position. It strips coaching
and saved decisions from the display payload.

```sh
yugioh-benchmark export-review-boards path/to/replay.zip \
  --catalog path/to/review-catalog.json \
  --output path/to/site/lib/replay-review-catalog.json
```

The Site's bundled catalog is versioned by the digest of the authored spec.
Export saved answers before changing the active catalog if you want to import
them using the page. Keep answer files and evaluator outputs out of source
control. Offline integration tests simulate agent and referee responses.
