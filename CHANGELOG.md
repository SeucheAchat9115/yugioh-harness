# Changelog

## Unreleased

- Keep games and shared game snapshots local and ignored by Git; existing files
  are untracked without deleting local saves. Earlier Git history is unchanged.
- Remove obsolete agent CLI wrappers, open/blind policy stubs, unused record
  templates, static host examples, callback play/advancement hooks, and the empty effect
  registry. Module CLIs and historical save/archive readers remain supported.
- Remove direct-to-main deck enrichment automation; conversion and guide/hash
  review now use normal pull requests.
- Consolidate setup and architecture documentation; use `docs/orchestration.md`
  for the provider-neutral MCP protocol.

## 0.1.0 — 2026-10-06

Initial packaged release of the agentic harness:

- Conversational managed, self and agent-versus-agent orchestration.
- Durable decisions, sequential player tasks, retries, private checkpoints and
  perspective-filtered compact contexts.
- Schema-4 indexed event archives, shared immutable snapshots and replay caches;
  schema-2/3 archives and schema-1 private journals remain compatible.
- Installable runtime, portable MCP configuration generator and pre-deal checks.
- Fresh-install transport smoke tests, contributor guidance and release workflow.

The LLM adjudicates gameplay. Unit/smoke tests validate runtime behavior and
information boundaries, not comprehensive card legality or vendor app integration.
Python 3.11–3.13; native Windows and POSIX writer locks. CI runs on Windows.
