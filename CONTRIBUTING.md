# Contributing

Use Python 3.11–3.13 on Windows, Linux or macOS. CI runs on Windows. Clone the repository, create
`.venv`, and install with `python -m pip install -e .`. Follow `AGENTS.md`.

Keep the LLM responsible for rules interpretation and tactical play. Contributions
should improve orchestration, context, persistence or evaluation; a complete coded
effect engine is not required. Original contributions are submitted under MIT;
retain attribution for imported third-party content.

All files are owned by `@SeucheAchat9115` in `.github/CODEOWNERS`.
The protection rule or ruleset for `main` must enable **Require review from
Code Owners** to enforce that owner's approval. CODEOWNERS alone does not
block direct pushes or merges. Submit changes through pull requests.

Before a pull request:

- Run `python -m unittest discover -s tests -v` and
  `python -m unittest discover -s skills/ydk-to-json/tests -v`.
- For packaging/transport changes, build a wheel and run the installed smoke test
  as described in `docs/releases.md`.
- Explain the behavior change, relevant validation and compatibility impact.
- Do not include private session/checkpoint files, credentials or unrelated duels.
  Game publication requires the player's explicit request. Archives are omniscient.

Deck contributions use `decks/<format>/<name>/deck.ydk`, `deck.json`, `guide.md`
and optional README provenance. Run the YDK conversion and deck-playbook skills,
record format/banlist, and verify the guide hash. Do not label uncertain legality
or unplayed combos as certified. Historical games retain immutable snapshots.

Rules profiles state card pool, banlist, starting rules, historical text differences
and ruling sources. State/archive changes require compatibility tests; never edit
referenced snapshot objects or overwrite historical event records.

Report a bug with host/version, harness version, mode, public reproduction steps,
expected behavior and the safe error code. Attach a sanitized minimal fixture;
do not upload a raw private checkpoint or a live opponent's hidden state. Discuss
larger changes in an issue before implementation. Keep review communication clear
and respectful.
