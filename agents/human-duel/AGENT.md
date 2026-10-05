# Human duels: managed and self

Use `agents/orchestrator/AGENT.md`, `skills/duel-orchestrator/SKILL.md`, and
`agents/shared/moderator.md`. The user speaks to one orchestrator; it operates
all tools internally and delegates opponent decisions to isolated player children.
The LLM adjudicates rules; the harness persists state and checks its structure.

## Managed

Set `mode: "managed"`. The human selects a complete repository deck bundle.
Snapshot both decks, independently shuffle and deal once, and preserve their
orders. Manage the human's draws, searches, moves, costs, and effects after their
choices are reviewed. Show their actual numbered hand and the public state.

The orchestrator knows both private states. The opponent child sees its own
cards and legally revealed human information only: never the human's hand,
face-down cards, private effects, full decklist, guide, or future draws. Managing
cards is not permission for the opponent to know them. Coach the human with two
legal recommendations when available and accept free text. The human decides
activations, responses, targets, materials, searches, and optional effects.
Do not choose their moves unless explicitly delegated.

## Self

Set `mode: "self"`. The human uses physical cards or another private simulator
and manages their own shuffling, draws, hand, and hidden zones. Ask for deck,
Extra, and Side counts, never their YDK, full list, hand, or set identities.
Do not load their previously uploaded bundle even if its name is known.

Track LP, counts, public cards, actions, targets, and required reveals. For a set,
record an anonymous physical-copy reference and its public position; ask for its
identity only when legally revealed. A hidden draw updates counts only. Record
information disclosed by a rule/effect only to its entitled viewer and duration;
do not infer permission to inspect the rest of the hand or deck. Request public
costs, targets, and declarations needed to adjudicate a move. Legality of unseen
cards is human-attested rather than verified against a private deck snapshot.

Offer suggestions from known information with stated conditions. Never claim a
complete inventory of hidden responses. Ask for a response/pass at applicable
windows; advance only on verified public no-choice facts or a human-confirmed
absence of options. The human must preserve their hidden cards and order to resume.

## Shared behavior

Use the fixed decision-v1 display for every outward gameplay message. Explain
intervening actions, preserve response windows, accept free text, and stop at
actual choices. Never revise an opponent's committed move after a human reply.
Save locally after each action and before asking, including pending choices,
chains, paid costs, effects, rules, random outcomes, and all managed hidden state.
Resume from the checkpoint; never redeal or reshuffle. Never commit or push game
records without an explicit request, including on save, pause, or finish.

`agent-vs-agent` remains a separate participant arrangement: both player slots
are managed and each child receives its own private view. Existing `open` saves
retain their explicitly shared human information; existing `blind` saves behave
as self. Do not silently convert an existing game's mode or visibility.

Follow [game storage](../../docs/game-storage.md): the repository archive includes
known hidden states for review. Never give it directly to player subagents or use
it as a public display. Save one replayable `events.json`, not duplicate logs.
