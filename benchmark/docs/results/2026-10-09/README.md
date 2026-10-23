# GPT-6 Luna checkpoint results

The current plots contain only the completed native `gpt-6-luna` run: 36 tasks
across 18 independently reset, reviewed positions. All tasks are graded.

![Current Luna performance](performance.png)

| KPI | Passed / total | Score |
| --- | ---: | ---: |
| State recreation | 17/18 | 94.44% |
| Human-move agreement | 9/18 | 50.00% |
| Rule correctness | 32/36 | 88.89% |
| **Equal-weight final score** | | **77.78%** |

## Performance versus recorded runtime

![Luna performance versus cumulative recorded collection runtime](performance-runtime.png)

The x-axis is **396.71 minutes** (23,802.77 seconds), the sum of recorded static
collector durations for all 36 canonical player responses. All four metrics use
this same full-run coordinate, rather than a per-KPI duration.

These durations include manual prompt preparation and waiting. Reused archived
answers contribute cached retrieval time, rather than their original generation
latency. Referee calls and excluded transport trials are outside this total.
Parallel call durations are cumulative, so the coordinate is neither elapsed wall
time nor a complete measurement of model inference time. The raw total comes from
the hashed source report; the public measurement summary preserves it without
rounding. The old assisted pilot's runtime coordinates are excluded.

USD cost remains `null`: native subagents did not report token usage or billing.
The previous cost plots have been removed in favor of the recorded-runtime plots.

## Scope and provenance

Players received filtered checkpoint packets in fresh native subagents. Isolation
was cooperative, with tools and shared files exposed. Independent LLM referees
reviewed initiation legality; approved intentions executed through the persistent
harness. An independent replay of the private journals reproduced the score.
One harness execution failure remains reflected in the results. These scores
measure checkpoint tasks; continuous-duel performance remains unevaluated.

Five referee transport trials and one player trial were excluded for incorrect
input. One fresh player dispatch corrected that input; there were zero retries
selected for gameplay performance. Actual provider versions, usage and costs are
unknown. Prompt-delivery evidence is reconstructed supervisor text, without a
direct provider trace. Earlier guarded dispatch failures remain archived locally.

Only [score summaries](luna.score.json), [measurement availability](measurements.json)
and [provenance hashes](provenance.json) are versioned here. Raw responses, journals,
harness saves and full replay logs remain local and ignored. Historical pilot
summaries are retained [separately](../2026-10-08/README.md) and excluded from all
current plots.

## Regenerate

```sh
python docs/results/2026-10-09/plot_results.py
```

Install the optional plotting dependency with `pip install -e '.[plotting]'` if
needed. The script reads only the committed summaries and writes PNG/SVG versions
of the performance overview, the four-panel runtime figure, and each
individual metric. No API access or private run files are needed.

| Plot | PNG | SVG |
| --- | --- | --- |
| All four metrics | [PNG](performance-runtime.png) | [SVG](performance-runtime.svg) |
| State recreation | [PNG](performance-runtime-state-recreation.png) | [SVG](performance-runtime-state-recreation.svg) |
| Human-move agreement | [PNG](performance-runtime-human-move-agreement.png) | [SVG](performance-runtime-human-move-agreement.svg) |
| Rule correctness | [PNG](performance-runtime-rule-correctness.png) | [SVG](performance-runtime-rule-correctness.svg) |
| Final score | [PNG](performance-runtime-final-score.png) | [SVG](performance-runtime-final-score.svg) |
