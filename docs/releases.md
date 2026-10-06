# Versioned releases

`pyproject.toml` is the version source; update `CHANGELOG.md` with each release.
Version runtime features independently of private-journal and archive schema numbers.
A new release must keep documented old formats readable or provide a verified
migration. Never migrate or publish someone's local duel during a code release.

## Local release validation

Run from a fresh clone. The following commands are for maintainers/CI, not players:

```sh
python -m venv .venv
.venv/bin/python -m pip install build
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s skills/ydk-to-json/tests -v
.venv/bin/python -m build
.venv/bin/python -m pip install --no-deps dist/yugioh_harness-0.1.0-py3-none-any.whl
.venv/bin/python -I tests/smoke_install.py --repo .
.venv/bin/yugioh-harness doctor --repo .
```

Use the current version's wheel filename. The smoke test copies resources to a
clean temporary checkout (including a path with spaces), excluding `.git`, games,
snapshots, private state and build products. It runs the installed MCP module in
isolated Python processes outside the source working directory. It checks all
three modes, preflight, filtered player tasks, simulated dispatch, decisions,
pause/resume with identical hidden queues, cancellation and schema-4 records.
It does not run model calls or certify rules adjudication/native host integration.

CI runs unit tests and installed-wheel smoke tests on Windows with Python
3.11, 3.12 and 3.13. Real host trials should additionally record app/version,
mode, actual child capabilities, pause/resume and observed latency. Do not label
untested app versions as verified or include private opponent cards in reports.

## Publish

After the release checks pass, use **Actions → Release harness → Run workflow**
on the reviewed commit to publish its package version, or create a tag matching `v<project-version>` and push
that tag. The release workflow independently tests, builds the wheel and sdist,
verifies the tag/version, and publishes a GitHub Release with SHA-256 checksums.
A manual run creates the matching version tag at that reviewed commit; an existing
release is not overwritten. It does not publish to PyPI or upload game/private files. The source archive holds
the resource checkout; the wheel holds the runtime. Users need both.

The workflow's scoped `contents: write` is for that requested versioned release,
not permission to include local duels. Games and shared snapshots are ignored
local data; see [game storage](game-storage.md). For a maintainer-approved release,
`gh release create <tag> dist/* --notes-file <release-notes>` can publish the same
reviewed artifacts; preserve exact release notes in a file.

On Windows, use `.venv\Scripts\python.exe` for the commands above. The release
workflow uses Git Bash on a Windows runner for its scripts.
