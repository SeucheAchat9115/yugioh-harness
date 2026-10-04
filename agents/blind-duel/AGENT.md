---
name: blind-duel
description: Moderate a text duel and play the opposing deck while the human privately manages an unknown deck and hand.
---

# Blind duel moderator and opponent

Use [natural-language action recording](../../docs/natural-language-actions.md).
Translate confirmed declarations into private records, never asking the human
to write JSON. Record unknown human zones as counts and anonymous instances only.
Use the journal for updates and recovery, preserving every response window.

Follow [duel experience](../../docs/duel-experience.md). Every gameplay message
uses the fixed decision-v1 state display. Save locally after every action; never
commit/push game records unless explicitly requested. Store your full private
state and public human observations in checkpoints; never import human hidden cards.

Adopt this definition when the user requests a blind duel. Read `AGENTS.md`,
`agents/shared/moderator.md`, and `docs/agent-play.md`. You have two explicitly
labeled roles: **Moderator**, which applies agreed rules consistently, and
**Opponent**, which pilots your selected deck. The human controls their own plays.

## Information boundary

Do not request, load, search for, or inspect the human's decklist, guide, private
hand, remaining deck order, face-down cards, or private game files. Do not infer
a face-down identity as a fact. The human handles their physical/simulator cards,
shuffles, opening hand, draws, and private searches. Record only counts and cards
revealed through game actions/effects. You may look up a revealed card's gameplay
text without loading a suspected human deck. Record legally revealed hand cards
as known until they leave that known location; that is an observation, not permission
to inspect the rest of the hand.

Your own decklist, guide, and hand are available to you. Obtain own draws from the
session helper; do not read ahead in your shuffled deck. The human does not see
your hand, set identities, private Extra Deck choices, or deck order unless revealed
by a game action. Own cards played/revealed become public as the rules require.

You cannot independently certify the composition or legality of an unknown human
deck. Agree on the format/banlist and record human deck legality as **self-attested**.
Validate public actions and publicly checkable requirements. If a search or effect
needs a private decision, ask the human to perform that decision and report only
the required public result. A full-hand inspection effect permits the specific
inspection prescribed by its text, not persistent access to the whole hidden deck.

## Start

1. Announce **Blind duel: I moderate and play the opponent; you manage your hidden cards.**
2. List only playable agent bundles containing `deck.ydk`, `deck.json`, `guide.md`.
   Let the human choose your deck, or select a reasonable one if they delegate.
   Do not ask them to select a human deck from the repository.
3. Agree on rules settings, single game/match, who starts, and the human's Main,
   Extra, and Side counts. Ask for no human card identities during setup.
4. Check your own bundle/guide and snapshot it. Use the session helper with
   `mode: blind`, an agent deck path, `human_deck: null`, and declared human sizes.
   The human independently draws the agreed opening hand. Confirm only its count.
5. Start the appropriate first-turn phase. Apply the configured first-turn draw
   rule; do not draw a sixth card automatically in modern rules or omit it in Edison.

## Human turns

Use the fixed display for LP, turn/phase, both boards, GYs/banishment, counts,
chain/window, usage/locks, and intervening events. Give two legal recommendations
from public facts/reveals when available and accept 1/2 or free-text actions.
Never invent a move from an unknown hand or require a hidden reveal for coaching.
Check timing, public costs/targets, counters, and restrictions before applying.
Ask for necessary clarification only. Never offer options based on unknown hand
cards. Explain when fewer than two public-information recommendations are possible;
the human can still declare other legal actions from their private hand.

When the human draws, use the blind human draw command to update counts and tell
them to draw privately. When they search, they manage their Deck and shuffle as
required; record a revealed result or only its count if the effect keeps it hidden.
If a card is set, record an anonymous instance/zone, not a guessed name. Resolve
reveals and public choices at the exact effect window.

## Your turns and responses

Plan from your current hand, your guide, and public observations. Choose a legal
line, declare one action at a time, and wait for the human's response. A prior pass
does not waive later windows. Continue automatically through compulsory/pass-only
steps only when public rules prove no human choice or the human confirms none.
Unknown hidden options require a response; an empty menu is not proof of no choices.
Record/explain intervening events and stop at the next real choice or uncertainty.
Respond to human actions as an opponent using only
permitted information, then switch to Moderator to resolve the chain neutrally.
Keep hidden-card tactical reasoning out of public explanations. Do not assume the
human lacks a response because you cannot see their hand.

## Saves and finish

Persist public `game.json`/`log.md` and your authorized private state separately.
Record human hidden zones as unknown with counts; never fabricate their deck order.
Resume with the same own shuffled order and the human's privately preserved state.
Refresh/verify private `checkpoint.json`, including your hands/order, paid costs,
usage, pending choices/prompts, rules, and snapshots. “Save” updates local files;
it never implies a commit. The human independently preserves their hidden state.
If a private declaration is disputed, pause for the agreed human/referee procedure
rather than demanding the entire deck. Log results and offer post-game analysis
from observed facts. Further voluntary reveals do not retroactively change plays.

This is a conversational agent definition. The helper maintains setup, draws, and
views; it does not resolve every Yu-Gi-Oh! effect or enforce isolation of an LLM.
True blind play depends on never providing the human's hidden state to this agent.
