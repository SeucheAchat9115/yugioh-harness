# Monorepo release process

Current releases are built from the repository root. Follow
[the harness release guide](../../docs/releases.md). One `yugioh-harness`
distribution provides both command-line tools and Python import packages; optional
plotting dependencies remain available through `.[plotting]`.

Run both test suites, build the root wheel/source distribution, and verify both
installed imports and entry points. Benchmark fixtures and selected source data
retain their [original notices](../THIRD_PARTY_NOTICES.md). Historical results
retain their original provenance; migration is not a new model evaluation.

The old benchmark repository is retained as a historical source. Its independent
release workflows are no longer used in this monorepo. Do not change repository
visibility, archive the remote, or publish new benchmark scores as part of a source
migration. New live evaluations still require a bounded model transport.
