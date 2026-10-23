# Automated, metered checkpoint evaluation

The `evaluate` command runs the 36 reviewed tasks from the supplied Duelingbook
match through `yugioh-harness`: 18 declared-state tasks and 18 independent move
choices, with legality reviewed for all 36. All models receive identical archived
requests. This replaces the shortened, model-specific prompts of the assisted
pilots with a reproducible protocol, `structured-checkpoints-v1`.

## What runs

1. Verify every reviewed position, filtered packet and pinned rules/card/banlist
   hash before any model call. Blocked replay positions remain blocked.
2. Reset the real persistent harness to the reviewed checkpoint. Present and
   reserve its player task under enforced isolation, and bind the dispatch handle.
3. Send a fresh tool-free request containing only permitted player information.
   Explicit phase, allowance and physical-card locations reduce repeated work.
   Visible card texts and pinned rules remain available; preserve set timing
   events and the latest 12 public events. No full replay, grading keys, future
   outcome or hidden opponent identities reach the player.
4. Receive one semantic JSON intention. A separate stateless referee call reviews
   that exact initiation against the pinned context, without the human reference
   or expected state. It cannot repair the agent's choice. An uncertain ruling
   remains ungraded and blocks the final score.
5. Translate approved intentions through the harness's optional `intent-v1`
   interface, then execute through its existing sole-writer workflow and journal.
   Stop at the opponent response window. Declared state is checked exactly against
   its reviewed target, human agreement uses the versioned deterministic semantic
   normalizer, and legality uses the independently bound referee verdict.
6. Save each attempt and receipt immediately, with no automatic model retries.
   A missing/timeout attempt scores zero. Failed provider calls remain in the
   timing/usage totals. A rejected action records a no-op for auditable state
   grading; it never applies a corrected move.

Semantic translation intentionally removes low-level patch-writing from the
player task. State recreation now measures the agent plus this harness interface.
Therefore new scores must be labeled with the protocol and **cannot be directly
compared to the old assisted pilots as an isolated model improvement**.
An independent LLM referee can make mistakes and share model biases. Review its
saved justifications for important results; it is not expert rules certification.
This remains a checkpoint benchmark, not uninterrupted duel play or win rate.

## Maintainer setup and execution

The host/orchestrator manages these commands internally. The monorepo installs
both engine and benchmark from its root; no sibling checkout is needed:

```sh
python -m pip install -e '.[plotting]'
yugioh-benchmark evaluate benchmark/benchmarks/review/db-json-40753-85958923 \
  --output benchmark/runs/comparison-new \
  --models PROVIDER_SOL_MODEL_ID PROVIDER_LUNA_MODEL_ID \
  --referee-model PROVIDER_REFEREE_MODEL_ID \
  --prices /private/provider-prices.json
```

Historical pinned harness commits in prior reports identify those runs only.
Current CI tests the benchmark and harness together from the same monorepo commit.

Use actual supported provider IDs; the native chat labels `gpt-6.1-sol` and
`gpt-6-luna` are not a promise that those names exist on an API. The adapter supports
an OpenAI-compatible **Chat Completions** endpoint (`--endpoint`), an API-key
environment-variable name (`--key-env`, default `OPENAI_API_KEY`), and providers
supporting JSON-object responses. Credentials never belong in a command argument,
price book or repository. No API key is needed for offline tests.

Default budgets are 512 output tokens for the evaluated player, 1,024 for the
referee, and a 90-second per-call deadline. Override them explicitly when needed;
the local worker watchdog must match the saved harness deadline (1–120 seconds).
The process is killed and waited for on a local timeout. Remote billing after a
timeout may still be unknown. There are no silent retries. Unsupported reasoning
or sampling options can be supplied through `--options /private/options.json`;
they are pinned and identical across evaluated models. Options cannot override
messages, tools, output budgets or isolation controls. Use a common referee model
and the same options for both models, and pin both repository versions.

Outputs must be new directories. Each model gets `run.json`, `score.json`,
`report.json`, private harness state/journals and exact requests. The comparison
contains safe aggregate reports rather than raw responses. If interrupted, partial
attempts remain saved; this version does not resume or reroll them. Run a fresh
comparison rather than mixing protocols or excluding failures. Models run
sequentially, so provider load can affect timing; repeat entire comparisons to
assess variability, without selecting only successful attempts.

## Tokens, timing and costs

Every call records UTC start/end, monotonic elapsed seconds, requested/reported
model IDs, request/options hashes, status, and reported input/output/total tokens,
cached input tokens and reasoning tokens when supplied. Reasoning tokens are
part of output tokens, never billed twice. Evaluation and referee calls have
separate totals, median and p95; pipeline totals and overall wall time are also
saved. Time includes network and worker startup, and is not provider inference time.

Prices are optional. Without reported billing or sufficient usage and sourced
prices, USD cost is `null`, never zero. A price book is keyed by the **reported
provider model ID** (requested ID if unavailable). Each entry requires:

- `source`: provider pricing URL or identifiable supplied source;
- `effective_date`: ISO date when the prices applied;
- `input_usd_per_million` and `output_usd_per_million`: nonnegative USD rates;
- optionally `cached_input_usd_per_million` when the provider has a cache rate.

Supply real provider rates rather than invented Sol/Luna pricing. The price book follows [pricing.schema.json](../schemas/pricing.schema.json), is
archived privately as `pricing.json`, and each entry is hashed into its cost record. If a discounted cache rate applies but the cache
count is unreported, the cost stays unavailable. Custom trusted transports may
return `cost_usd` for provider-reported billing; the supplied Chat Completions
adapter only estimates from usage and the price book. Unknown calls prevent a
complete cost total; a separate known subtotal and unpriced-call count remain
available. Costs include failed calls where usage is reported. Old chat pilots
have no recoverable token/billing telemetry and remain unpriced.

## Performance plots

```sh
yugioh-benchmark plot-evaluation runs/comparison-new/comparison.json \
  --output runs/comparison-new/plots
# Optionally show evaluation + referee costs:
yugioh-benchmark plot-evaluation runs/comparison-new/comparison.json \
  --output runs/comparison-new/plots-pipeline --cost-scope pipeline
```

This produces two four-panel figures, PNG and SVG: state recreation, human
agreement, legality and final score against total evaluated-model call time, and
those same four metrics against USD cost. Defaults use evaluated-model costs;
`pipeline` includes referee calls. The companion `measurements.json` contains
role-separated tokens, costs and times. Pending scores or unavailable costs are
labeled rather than plotted as zero. Comparisons reject different prompt manifests,
protocols, harness versions, suites or weights. Archive aggregate reports and plots
for publication; keep raw requests, responses and harness saves local and ignored.

The offline tests include actual harness execution, identical prompts, hidden-state
filtering, invalid/uncertain/timeout cases, usage arithmetic and a local HTTP worker.
Scripted fixture successes are integration checks, never claimed as model accuracy.
A fresh live comparison still requires supported model IDs, a configured provider
transport, and real prices for cost plots. No new live score is claimed by this change.
