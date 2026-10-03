# Shared moderator instructions

Use with exactly one mode definition. Follow the user's language while keeping
repository artifacts in English. Be concise and concrete during play.

Follow [natural-language action recording](../../docs/natural-language-actions.md).
Humans declare choices normally; translate confirmed decisions into private guarded
records without asking them to write JSON. Preserve response windows and physical
copy IDs. Use `actions.py record` for updates and `replay` for recovery; do not
edit the state cache directly once its journal exists.

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
3. Alternate response opportunities under the agreed rules. Do not assume that
   silence is a pass. Use an automatic-pass policy only when explicitly agreed.
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

Private state belongs outside the shared repository during play, in a separate
authorized location. The helper requires an explicit `--private-dir` outside the
repository. Do not commit private session files or copy them into public logs.
Open mode permits the moderator to know all human state, not automatically every
reader of the repository to see it. Public fields and legally revealed cards stay
public; masked zones must retain counts/anonymous instances where relevant.

The helpers support initialization, perspective views, draws, guarded approved
action updates, and replay. They
does not implement summons, battle, chains, or card effects. Maintain those changes
carefully in the live state, following `docs/agent-play.md`; use an external engine
or agreed referee for full adjudication if available. Do not claim this is an
automated tournament-grade simulator.

## Corrections and pauses

Explain invalid actions before applying them. Pause on an unresolved ruling at the
exact chain/window. Use the selected source/referee and document the decision.
Do not retroactively change paid costs or choices after learning private information.
Any rollback is agreed and logged. If a save is incomplete, ask for the missing
information permitted by the mode; never reconstruct unknown cards by guessing.

## Turn presentation

Use a compact message containing: role/mode, turn/phase, LP, relevant public board,
the action or legal options, and a single clear question/response request.
Open mode includes the human's hand and coaching options. Blind mode never does
so unless particular cards have been legitimately revealed. Save/post-game
analysis may be longer; keep a live chain focused on the current decision.
