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
- Always obtain decklists exclusively from https://cardcluster.com/.
  Do not substitute other deck archives. Record the exact source URL,
  retrieval date, author, and any available version information.
- If Cardcluster is unavailable, mark the import as pending.
  Do not present invented lists as researched lists.
- Create a new version when changing a deck. Previously played games retain
  their original deck snapshots.
- Save game actions, random outcomes, and game states so they can be reviewed.
  Do not reveal hidden information in public game logs.

- Enriched deck JSON must contain gameplay data only: deck identity, format/banlist,
  ordered Main/Extra/Side IDs, and card names, text, types, and applicable stats.
  Follow schema 2.0 in `skills/ydk-to-json/SKILL.md`. Do not include prices,
  printings, artwork URLs, API miscellany, or import provenance in these JSONs.
  Preserve Cardcluster source links in the YDK headers and deck-folder README.

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

- Use `agents/blind-duel/AGENT.md` for blind duels and
  `agents/open-duel/AGENT.md` for guided open duels, together with the shared
  moderator instructions. Blind mode must never load the human's hidden deck/hand.
  Open mode explicitly knows all human state and coaches choices without taking
  over the human's actions unless delegated. Label moderator/opponent/coach roles.
- Store live private session state outside the repository. Use the session
  helper for fixed shuffled draws and perspective views; it is not an effect engine.
  Never reshuffle on resume, skip responses, or change rulings to favor the agent.
