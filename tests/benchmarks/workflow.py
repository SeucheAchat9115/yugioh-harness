"""Temporary integrated workflow benchmark; includes durable receipt/checkpoint saves."""
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_session import SessionTests
from harness.runner.duel import DuelRunner

fixture=SessionTests();fixture.setUp()
try:
    _,game,path=fixture.start('open')
    with DuelRunner(path,game) as runner:
        samples=[]
        for index in range(20):
            started=perf_counter()
            runner.workflow.execute(f'benchmark-{index}',{'kind':'shuffle','actor':'moderator',
                'expected_revision':runner.state['revision'],'moderator_approved':True,
                'public_summary_reviewed':True,'public_summary':'Temporary shuffle benchmark.',
                'operations':[{'op':'shuffle','player':'agent'}]})
            samples.append((perf_counter()-started)*1000)
        samples.sort()
        print(json.dumps({'actions':len(samples),'median_workflow_ms':round(statistics.median(samples),2),
                          'p95_workflow_ms':round(samples[int(.95*(len(samples)-1))],2)},indent=2))
finally:fixture.doCleanups()
