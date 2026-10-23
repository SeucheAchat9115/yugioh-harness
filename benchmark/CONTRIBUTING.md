# Contributing

Use Python 3.11 or newer. Install from the monorepo root and test both packages:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m unittest discover -s benchmark/tests -v
yugioh-benchmark inspect benchmark/replays/db-json-40753-85958923
```

Tests run offline against the same root-installed harness. See the
[root contribution guide](../CONTRIBUTING.md) and
[shared environment](../docs/architecture-and-roadmap.md).

Keep converters generic. Preserve selected native data, observation order, source
references and information gaps. An observed operation is not a verified legal
move. Do not invent hidden cards, effect resolutions or strategic labels.

Raw imports, model outputs and actual harness game saves belong outside source
control. Do not include API keys, browser cookies or private player packets in
issues, commits or screenshots. Use synthetic data to demonstrate a bug.
Report suspected credential exposures privately to the repository owner first.

For a new selected replay fixture, provide its source, acquisition date, content
digest, attribution and known information gaps. Include redistribution permission
or license information when available; a viewer link alone does not establish
permission. Update the source registry deliberately rather than committing every
raw import.

Reviewed cases must pin source digests and verify the position, historical rules,
decision boundary, player visibility and grading criteria. Full replays and
grading keys must never enter an agent's player packet. Keep complete matches
together when assigning dataset splits.

Keep PRs focused and describe changed behavior and relevant offline checks.
Code contributions are accepted under the repository's MIT license; source
fixtures need their own attribution and rights statements.
