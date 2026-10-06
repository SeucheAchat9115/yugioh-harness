"""Temporary-fixture replay/cache/context metrics; never modifies a real duel."""
from pathlib import Path
from time import perf_counter
import json
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_session import SessionTests
from harness.runner.duel import DuelRunner
from harness.storage.archive import load_replay

fixture = SessionTests()
fixture.setUp()
try:
    _, game, path = fixture.start('open')
    with DuelRunner(path, game) as runner:
        for index in range(32):
            runner.command({'id': f'shuffle-{index}', 'command': 'shuffle', 'actor': 'agent',
                            'expected_revision': index, 'moderator_approved': True})
        full_bytes = len(json.dumps(runner.context('agent')))
        compact_bytes = len(json.dumps(runner.context('agent', compact=True)))
    with tempfile.TemporaryDirectory() as cache:
        before = perf_counter()
        load_replay(game, cache_dir=cache)
        cold = (perf_counter()-before)*1000
        before = perf_counter()
        load_replay(game, cache_dir=cache)
        warm = (perf_counter()-before)*1000
    print(json.dumps({'revisions':33,'cold_replay_ms':round(cold,2),'warm_replay_ms':round(warm,2),
                      'full_context_bytes':full_bytes,'compact_context_bytes':compact_bytes}, indent=2))
finally:
    fixture.doCleanups()
