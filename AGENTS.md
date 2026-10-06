# Repository guidelines

- Keep the repository generic: support current, historical, and custom Yu-Gi-Oh!
  formats. Do not assume a default format in shared documentation or templates.
- Store each deck in `decks/<format>/<deck-name>/`, using a readable lowercase
  hyphenated deck-name folder and generic `deck.ydk`, `deck.json`, `guide.md`,
  and optional `README.md` filenames. Keep strategy/matchup guidance in `guide.md`. Keep rules in separate format profiles.
  Record each game's format, banlist, and rules version.
- Configure starting LP, opening hand size, first-turn draws, and field layout
  from the selected rules profile rather than hardcoding them in shared templates.
- Use English for repository documentation and template text. Use English card
  names in deck files; optional localized display names may be added.
- Accept user-supplied YDKs or decklists from a source selected for the task.
  Record author, retrieval date, source URL when available, and version information.
- If a requested decklist cannot be retrieved, mark the import as pending.
  Do not present invented lists as researched lists.
- Create a new version when changing a deck. Previously played games retain
  their original deck snapshots.
- Save game actions, random outcomes, and game states so they can be reviewed.
  Keep live displays/player contexts filtered. Local replay archives deliberately contain
  known hidden states for full replay; follow `docs/game-storage.md`. Never give
  an omniscient archive to a player child.
- Save games locally after each action. `games/` and the shared `snapshots/` store
  are ignored local data; never stage, force-add, commit or push them as part of
  repository work. “Save”, pause and finish update local state only. Keep private
  runtime files outside the checkout and out of Git. For backups or a requested
  export, preserve archive/snapshot references and known hidden state separately
  from source control; do not expose archives to a player child.

- Enriched deck JSON must contain gameplay data only: deck identity, format/banlist,
  ordered Main/Extra/Side IDs, and card names, text, types, and applicable stats.
  Follow schema 2.0 in `skills/ydk-to-json/SKILL.md`. Do not include prices,
  printings, artwork URLs, API miscellany, or import provenance in these JSONs.
  Preserve available provenance in the YDK headers and deck-folder README.

- Aim to enable an agent to pilot a deck against another agent or a human.
  Use `skills/deck-playbook/SKILL.md` to write each deck folder's `guide.md`
  from gameplay JSON, covering every card, searches, synergies, conditional combos,
  interaction, resources, and agent decisions. Tie each guide to the JSON hash.
- Check all combo inputs, costs, material locations, targets, restrictions, and
  timing against the exact card text/list. Mark unresolved rulings explicitly;
  structural audits do not prove combo legality or optimality.
- Follow `docs/agent-play.md` during play. Give human/agent opponents response
  opportunities, keep private information private, and use an agreed authoritative
  state/referee. Never treat the playbook as automatic permission for a legal action.

- Use `agents/human-duel/AGENT.md` for both human modes, together with shared
  moderator instructions. `managed` handles the human's selected deck and declared
  moves, while keeping their hidden cards out of the opponent's context. `self`
  never loads the human's hidden deck/hand; the human handles their own cards.
  Coach without choosing human moves unless explicitly delegated. Label roles.
  Preserve legacy `open`/`blind` saves and their original visibility semantics.
- Store live private session state outside the repository. Use the session
  helper for fixed shuffled draws and perspective views; it is not an effect engine.
  Never reshuffle on resume, skip responses, or change rulings to favor the agent.
- Follow `docs/natural-language-actions.md`: translate human language into private,
  approved action records. Use `harness/engine/actions.py` for updates and replay;
  never edit journaled state directly. Review public narration for hidden data.
  Use one moderator writer and preserve physical-copy IDs and response windows.
- Follow `docs/duel-experience.md` for every gameplay message: fixed decision-v1
  state display, two distinct legal recommendations when available, and free-text
  input. Record and explain compulsory/no-choice steps automatically; stop at the
  next actual human option. Self unknown options are not no options.
- Persist complete local checkpoints after updates and before questions, including
  managed-mode hidden states, numbered choices, rules/snapshots, costs/effects, and
  shuffled orders. Verify before resuming; never restart or reshuffle a saved game.

- The harness owns live state. Use `harness/runner/duel.py` as the single persistent
  writer; player adapters receive permitted context and return intentions, never
  guarded state patches. No network, Git, or model calls inside engine execution.
- Keep this an agentic play harness: the LLM interprets rules/card text, reviews
  legality, resolves effects/battles, and manages gameplay windows. The runtime
  provides structural safeguards and persistence; a full coded game engine is
  not required or the default roadmap.
- The LLM adjudicates card effects and submits approved action records. No empty
  effect registry or alternative callback play loop is needed. Pause on uncertain
  rulings; structural validation is not independent rules certification.
- Preserve existing journals/checkpoints and archive readers. Maintainer CLIs use
  `python -m harness.<module>`; removed `agents/runtime/` wrappers are not supported. Test with
  `python -m unittest discover -s tests -v`; benchmark with
  `python tests/benchmarks/runner.py`. Never run benchmarks against a real duel.

- Use `docs/orchestration.md` for integrated sessions: persist numbered decisions with
  IDs, submit input before reviewing it, and execute stable request IDs through
  the workflow. Identical retries must not apply actions twice. Bind H/A hand
  references to saved prompts. Never show opponent packets or moderator context
  to the human. MCP tools are trusted moderator tools, not a player-facing API.

- Use `mode: "agent-vs-agent"` and `docs/agent-vs-agent.md` for two managed AI
  players. Legacy IDs `human`/`agent` identify slots only. Each player gets its own
  private view and guide; the moderator gets both. Never apply legacy open-mode shared human
  visibility, publish private player menus, or share player/moderator histories.
- Independent player clients use role-bound arena credentials and tools. They must
  not receive moderator credentials or direct filesystem access to private state,
  mailboxes, or another role's credentials. Host restrictions are required beyond
  the tool interface. Preserve both decks' hidden state and receipts on resume.

- All duel modes use `agents/orchestrator/AGENT.md` and
  `skills/duel-orchestrator/SKILL.md`: one user-facing moderator conversation.
  Operate setup, runtime, and resume internally. Never require user Python calls,
  JSON preparation, credential handling, or separate player sessions during play.
- Delegate each active AI player's choice to a host-native subagent sequentially,
  using only its task's permitted context and no inherited moderator/sibling
  history. Store the returned intention, review legality, then apply it as the
  sole moderator writer. Human choices are asked in the same conversation.
  Never substitute moderator reasoning for a player child silently. Use the saved
  cooperative/enforced policy in `docs/player-isolation.md`.
  Cooperative children must obey context-only/no-tools instructions; record actual
  available capabilities. Enforced requires verified restrictions or a tool-free
  transport; pause when unavailable. Never silently downgrade an enforced save.
- The role-bound arena is an optional deployment backend, not the default user
  workflow. Any separate clients are managed internally by the orchestrator/host.

- Follow `docs/player-isolation.md`: reserve each player attempt with its saved
  isolation policy and an honest host capability declaration. Spawn only when
  authorized, save its native handle, and submit both
  task/attempt IDs. A declaration is host evidence, not sandbox attestation.
  A timeout does not kill a child: stop it and acknowledge termination before
  retrying. Preserve deadlines on resume and bound retries to three per decision.
  Never evade the limit by changing a menu or silently replace a player's choice.

- Use the schema-4 `events.json` index and `events/<revision:06d>.json` as the sole archived action log. Reconstruct states and
  readable logs on demand; do not persist game-folder state/actions/log/resume duplicates.
  Preserve exact rules, deck snapshots, all known hidden zones and gameplay bookkeeping.
  Self/blind archives must declare unknown human hidden-state coverage.

- Intern immutable rules/deck/catalog assets in the shared `snapshots/` content-addressed
  store; keep readable logical references in archives instead of per-game copies.
  Never modify/delete referenced objects. Keep replay revision caches outside Git.
- Use compact `duel_agent_context` for routine play and focused/full permitted context
  for missing details. Preserve filters before compaction and label decision-evidence gaps.
