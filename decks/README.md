# Decklists

Organize decklists under `decks/<format>/` using a consistent format ID.
Use `templates/deck.json` and record the format, applicable banlist, unique deck ID,
and deck version. Check card availability and copy limits for that format.

Every decklist must be obtained from https://cardcluster.com/. Record the exact
source URL, retrieval date, author, and available source version. Document changes
from the imported list and create a new deck version for each revision.
Optional `.ydk` exports may be saved alongside JSON once card IDs are available.

Available format folders: [Edison](edison/README.md).

User-provided Cardcluster exports awaiting format assignment:
[Branded Despia and Dracotail](unassigned/README.md).

## Enriched YDK exports

Use the [YDK-to-JSON skill](../skills/ydk-to-json/SKILL.md) to convert a YDK to
a same-basename JSON containing gameplay-only YGOPRODeck card data. This enriched schema
uses ordered ID arrays and a `cards` lookup table; it is documented in the skill.
The generic import template remains available for manually documented lists.

## Playbooks

Use the [Deck playbook skill](../skills/deck-playbook/SKILL.md) to produce
`<deckname>.md` beside each gameplay JSON/YDK. It explains card roles, access maps,
synergies, conditional combo traces, and agent decisions for the exact deck.
Keep strategy and matchup notes in the deck's sibling playbook.
