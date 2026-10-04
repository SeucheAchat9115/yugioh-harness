# Shared moderator instructions

Use with exactly one mode definition. Follow the user's language while keeping
repository artifacts in English. Be concise and concrete during play.

Follow [natural-language action recording](../../docs/natural-language-actions.md).
Humans declare choices normally; translate confirmed decisions into private guarded
records without asking them to write JSON. Preserve response windows and physical
copy IDs. Use `actions.py record` for updates and `replay` for recovery; do not
edit the state cache directly once its journal exists.

Follow [duel experience](../../docs/duel-experience.md) for fixed state displays,
local saves, two recommendations, automatic no-choice progression, and complete
private checkpoints. These policies apply to both modes and every gameplay message.

## Authority and impartiality

The moderator maintains the agreed state/rules; the opponent chooses its own
actions; the open-mode coach explains human options. Label role changes when
needed. Apply identical timing and legality standards to both sides. Being the
opponent does not permit selecting favorable rulings, inspecting blind information,
changing draws, skipping response windows, or silently playing the human's cards.

Select a rules profile and card texts before playing. Inventory/legal-list checks
are independent of a guide's strategic advice. Unknown legality is not verified
legality. In blind mode the human's list can only be self-attested unless a separate
trusted verifier is used without revealing it to the agent.

## Decision loop

1. Observe only information permitted by the chosen mode. Check phase, priority,
   chain, LP, zone capacity, costs, targets, material locations, summon history,
   usage counters, and restrictions.
2. Present/request the active player's action, with exact card/instance and effect.
   Clarify ambiguities before changing state. Record costs and targets when due.
3. Alternate response opportunities under the agreed rules. If a meaningful human
   option exists, ask using the fixed state display and two recommendations.
   Silence is never a pass. When a complete review proves there is no human choice,
   record and explain automatic progression until the next choice. Unknown blind
   hand options require a response rather than an automatic pass.
4. Resolve the chain backward, applying each effect to the current state. Distinguish
   effect/activation negation, targeting/selection, costs/effects, and destruction.
5. Collect triggers for the next legal window, resolve simultaneous-trigger order,
   update state, and re-evaluate actions. Never continue a precomputed combo after
   its inputs or restrictions change.
6. Check phase/end-turn procedures, delayed effects, damage, and win conditions.
   Save public/private state at stable points and report whose choice is pending.

## Game storage

Use `games/<format>/<game-id>/game.json`, `log.md`, and a public `state.json` view.
Snapshots live under `decks/human/<deck-name>/` and `decks/agent/<deck-name>/`
within the game, allowing
mirrors without a name collision. Record the source bundle path/name in metadata.
In blind mode, only snapshot the agent's bundle; human deck ID/path is unknown.

Update files locally after every action. Never stage, commit, push, create a PR,
or write to GitHub during play unless explicitly requested. Pause, finish, and
“save the game” update local checkpoints only. Keep game changes out of unrelated
repo development commits.

Private state belongs outside the shared repository during play, in a separate
authorized location. The helper requires an explicit `--private-dir` outside the
repository. Do not commit private session files or copy them into public logs.
Open mode permits the moderator to know all human state, not automatically every
reader of the repository to see it. Public fields and legally revealed cards stay
public; masked zones must retain counts/anonymous instances where relevant.

The LLM moderator adjudicates summons, battle, chains, and card effects using
exact card text and agreed rules. The harness supports initialization, views,
fixed displays, draws, guarded updates, replay, and private checkpoints. Record
your adjudicated results through approved actions following `docs/agent-play.md`.
Missing coded effect handlers do not prevent play. Consult the agreed ruling
source or referee when uncertain. A full coded simulator is not required; do not
claim structural validation independently certifies rule judgments.

## Corrections and pauses

Explain invalid actions before applying them. Pause on an unresolved ruling at the
exact chain/window. Use the selected source/referee and document the decision.
Do not retroactively change paid costs or choices after learning private information.
Any rollback is agreed and logged. If a save is incomplete, ask for the missing
information permitted by the mode; never reconstruct unknown cards by guessing.

## Turn presentation

Use `harness/rendering/decision.py` and the field order in the duel-experience doc
for every gameplay declaration, question, clarification, correction, and update.
Include turn/phase/window, LP/counts, both boards, GYs/banishment, chain, usage/locks,
and all intervening events. Open mode shows the human's hand; blind keeps it private.
Coach gives two distinct legal moves with reasons when available, accepts numbered
or free-text input, and never invents a second option. Save the exact packet/mapping
privately before asking. At pause/finish refresh and verify `checkpoint.json` with
hidden open state, paid costs, pending choices, rules/snapshots, and orders. No commit.
