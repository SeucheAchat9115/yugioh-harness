"""Informational local latency benchmark; no real game files or network calls."""
from pathlib import Path
import json
import statistics
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_session import SessionTests
from harness.runner.duel import DuelRunner

fixture = SessionTests()
fixture.setUp()
try:
    _, game, path = fixture.start('open')
    started = perf_counter()
    with DuelRunner(path, game) as runner:
        startup = (perf_counter() - started) * 1000
        for i in range(20):
            runner.command({'id': f'shuffle-{i}', 'command': 'shuffle', 'actor': 'agent',
                            'expected_revision': i, 'moderator_approved': True})
        samples = sorted(runner.timings)
        print(json.dumps({'actions': len(samples), 'startup_ms': round(startup, 2),
                          'median_action_ms': round(statistics.median(samples), 2),
                          'p95_action_ms': round(samples[int(.95 * (len(samples)-1))], 2)}, indent=2))
finally:
    fixture.doCleanups()
