# Legacy open duel policy

New human duels use [managed/self policy](../human-duel/AGENT.md) through the
[orchestrator](../orchestrator/AGENT.md). Select `managed` for new games.

Preserve `open` in existing checkpoints and journals; never rewrite their mode.
Legacy `open` additionally permits the opponent to see human hidden cards.
This differs from new `managed`, which keeps them private from the opponent.
