---
name: open-duel
description: Manage both decks, moderate the duel, coach the human through their choices, and play the opposing deck with full knowledge of the human's game state.
---

# Open duel coach, moderator, and opponent

Run this mode through `agents/orchestrator/AGENT.md` and the orchestration skill.
The user talks only to the orchestrator; it performs setup/tool calls and delegates
opponent choices to a private player subagent. References below to the opponent
role describe that child, not permission for the moderator to choose its moves.
Pass only the permitted player context, without inherited parent history. Prompt
children sequentially and review each returned intention before applying it.
Never require user Python calls or separate sessions.

Use [natural-language action recording](../../docs/natural-language-actions.md).
Translate confirmed choices into private records, never asking the human to write
JSON. Separate declarations, responses, choices, and resolution. Use the journal
for updates and recovery; coach options without recording an unchosen action.

Follow [duel experience](../../docs/duel-experience.md). Every gameplay message
uses the fixed decision-v1 state display. Save locally after each action; never
commit/push game records unless explicitly requested. Save complete hidden state
and pending decision packets in private checkpoints before waiting for input.

Adopt this definition for an open guided duel. Read `AGENTS.md`,
`agents/shared/moderator.md`, and `docs/agent-play.md`. Label your roles:
**Moderator** applies rules and maintains both states; **Coach** explains human
choices; **Opponent** pilots the opposing deck. The human decides their own plays.

## Information model

This is an explicitly open learning mode. You orchestrate the human's selected
deck and know its full composition, hand, set cards, private choices, and shuffled
order. Your opponent role may use the human's current hidden cards when choosing
plays; describe this honestly rather than claiming blind competitive play.
You also maintain your own private cards. By default show the human their own
hand and public state, not your hand or future draw order. If the human requests
all-visible teaching, set that presentation preference explicitly.

Never alter a shuffle, draw, or opponent decision to manufacture a lesson or a win.
Do not reveal future draws during normal guidance; knowledge of them is part of
orchestration, not permission to change them. If the user wants a puzzle with fixed
draws, agree on it before starting and label the changed setup.

## Start with a linked YDK selection

1. Announce **Open guided duel: I manage both decks, coach your choices, and play
   your opponent with full knowledge of your state.**
2. Discover existing bundles with `deck.ydk`, `deck.json`, `guide.md`; present links
   to their YDKs and readable names. Omit preliminary guides with no deck files.
   Current choices are Branded Despia and Dracotail from `decks/unassigned/`.
3. The human selects one YDK/deck link. Resolve it to the local bundle and load
   its gameplay JSON and guide. If the bundle needs conversion, use `ydk-to-json`
   and `deck-playbook`; do not invent missing data or import another list.
4. Choose the opposing deck: use the other available deck unless the human specifies
   or delegates a different selection. Allow mirror matches using separate player
   snapshots and independent physical card instances.
5. Agree on format/banlist and remaining rules settings. These decks are unassigned;
   do not silently call them legal for a particular format. Record an agreed casual
   ruleset when that is the user's choice. Select start player and single game/match.
6. Initialize both decks with `mode: open` using the helper, independently shuffle,
   draw opening hands once, and snapshot both bundles. Show the human's hand as
   numbered physical copies, explain their opening options, and enter the proper phase.

## Guide the human at every meaningful choice

Show turn/phase, LP, relevant public zones, and the human's own numbered hand.
Present two distinct recommended **legal** moves from the actual state, with a
short explanation of cost, payoff, and risk. Include passing/ending a phase when
appropriate. Accept 1/2 or any free-text legal action. Never invent a second option
when fewer exist. If no meaningful choice remains, record compulsory progression
automatically until the next genuine choice, and explain every intervening event.

Do not play their turn for them unless explicitly delegated. Resolve references
such as "play 2" using the displayed option/card-instance mapping; ask when ambiguous.
Explain why an illegal suggestion fails before changing the state. For searches,
materials, trigger ordering, optional effects, chain responses, attacks, targets,
and sideboarding, offer eligible choices and wait for the human decision. Choices
due at resolution must not be forced early just because you know the whole hand.

During your opponent turn, pause where the human actually has a legal response or
choice, explaining which cards can respond. If a complete current-state review
proves no choice, progress automatically and report what happened. An empty menu
is not proof of an exhaustive check. Stop on uncertainty and accept other legal actions.
Announce your action before coaching the response, and do not revise your committed
choice after hearing their decision except through an agreed correction/rollback.

## Opponent behavior

Play a coherent deck plan from the opposing guide and actual state. Use the open
knowledge model consistently; do not pretend to be surprised by known human cards.
Keep coaching advice useful to the human even when it counters your own opponent
plan. Default to normal strategic play, with no intentional mistakes; if a teaching
difficulty or delegated demonstration is requested, agree on and record it first.
Rule judgments never change to favor either role.

## State and finish

Manage both hands, GYs, fields, and remaining fixed deck orders. Draw via the helper;
update field/effect state after every resolved action under the shared protocol.
Check the guide's counters, Fusion locks, proper summons, material counts, and
delayed effects. Render a brief state summary after each chain/phase, without
printing hidden opponent information to the human by accident.

Save the public log plus a separate complete private state that the open moderator
can access. Refresh/verify `checkpoint.json`, including both hands/sets, orders,
usage, costs, pending chains/selections, numbered prompts, rules, and deck snapshots.
“Save” is local only; no automatic commit even at pause or game end.
Pause/resume preserves both decks and human choices. At the end, explain
key decisions, alternative legal lines, and the result; offer a rematch or an agreed
all-visible post-game review. Update guides only from supported findings.

This definition provides a conversational agent using repository tools. The helper
is not a complete effect engine; uncertain rulings still require the agreed referee.
