"""Offline protocol checks; scripted oracle scores are never model results."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from yugioh_benchmark.evaluation import evaluate, request_for

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'benchmarks/review/db-json-40753-85958923'
try:
    HAVE_INTENTS=importlib.util.find_spec('harness.runner.intents') is not None
except ModuleNotFoundError:
    HAVE_INTENTS=False

class ScriptedTransport:
    timeout_seconds=90
    boundary={'method':'context-only','parent_history':False,'tools':[],'filesystem':False,
              'evidence':'Offline deterministic test transport; no live model or inherited history.'}
    config={'backend':'offline-test'}
    def __init__(self,answers,verdict='valid',fail=False):
        self.answers=answers;self.verdict=verdict;self.fail=fail;self.index=0;self.requests=[]
    def preflight(self,options):pass
    def __call__(self,model,request,*,role,options):
        self.requests.append((model,role,deepcopy(request)))
        if role=='evaluation':
            if self.fail:raise TimeoutError('Offline timeout')
            response=self.answers[self.index%len(self.answers)];self.index+=1
        else:response=json.dumps({'verdict':self.verdict,'reason':'Scripted offline verdict for integration testing only'})
        return {'response':response,'usage':{'input_tokens':100,'output_tokens':10},'reported_model':model}

@unittest.skipUnless(HAVE_INTENTS,'requires structured-intent harness')
class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=self.root/'dataset';shutil.copytree(DATA,self.data)
        self.suite=json.loads((self.data/'suite.json').read_text(encoding='utf-8'))
        self.suite['cases']=self.suite['cases'][:2]  # Choice + declared-state tasks, same reviewed boundary.
        (self.data/'suite.json').write_text(json.dumps(self.suite),encoding='utf-8')
        from yugioh_benchmark.review_cases import load_reviewed_case
        self.bridge,self.state=load_reviewed_case(self.data,self.suite['cases'][0]['id'])
        card=next(c for c in self.state['players']['agent']['hand'] if
            self.state['players']['agent']['cards'][str(c['card_id'])]['name']=='D.D. Warrior Lady')
        self.answer=json.dumps({'action':'set','card':card['instance_id'],'zone':'M-3'})

    def test_real_harness_same_prompts_private_grading_and_metering(self):
        transport=ScriptedTransport([self.answer,self.answer])
        reports=evaluate(self.data,self.root/'run',['sol-test','luna-test'],transport,referee_model='referee-test')
        self.assertEqual([r['score']['final_score_percent'] for r in reports],[100,100])
        self.assertEqual(reports[0]['prompt_manifest'],reports[1]['prompt_manifest'])
        evaluation=[req for _,role,req in transport.requests if role=='evaluation']
        self.assertEqual(evaluation[:2],evaluation[2:])
        for _,role,request in transport.requests:
            text=json.dumps(request)
            for key in ('expected_state','human_move','grading','payload_sha256','recorded_action'):
                self.assertNotIn('"'+key+'"',text)
            context=json.loads(request['messages'][1]['content'])
            if role=='referee':context=context['context']
            self.assertNotIn('hand',context['state']['players']['human'])
            self.assertNotIn('deck',context['state']['players']['agent'])
        self.assertEqual(reports[0]['measurement_summary']['pipeline']['total_tokens'],440)
        self.assertIsNone(reports[0]['measurement_summary']['pipeline']['cost_usd'])
        run=json.loads((self.root/'run/model-1/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['retry_count'],0)
        self.assertTrue(run['results'][1]['journal']['events'])
        with self.assertRaises(ValueError):evaluate(self.data,self.root/'run',['test'],transport,referee_model='r')

    def test_uncertain_review_blocks_final_and_invalid_does_not_apply_action(self):
        for verdict in ('uncertain','invalid'):
            report=evaluate(self.data,self.root/verdict,['test'],ScriptedTransport([self.answer],verdict),referee_model='r')[0]
            self.assertEqual(report['score']['kpis']['state_recreation']['score'],0)
            self.assertEqual(report['score']['kpis']['human_move_agreement']['score'],1)
            self.assertEqual(report['score']['kpis']['rule_correctness']['score'],None if verdict=='uncertain' else 0)
            if verdict=='uncertain':self.assertIsNone(report['score']['final_score_percent'])

    def test_timeout_scores_zero_without_retry_and_unknown_billing(self):
        transport=ScriptedTransport([self.answer],fail=True)
        report=evaluate(self.data,self.root/'timeout',['test'],transport,referee_model='r')[0]
        self.assertEqual(report['score']['final_score_percent'],0)
        self.assertEqual(len(transport.requests),2)
        self.assertEqual(report['measurement_summary']['evaluation']['failed_calls'],2)
        self.assertIsNone(report['measurement_summary']['pipeline']['cost_usd'])

    def test_transport_cannot_silently_claim_isolation(self):
        transport=ScriptedTransport([self.answer]);transport.boundary={**transport.boundary,'tools':['shell']}
        with self.assertRaises(ValueError):evaluate(self.data,self.root/'unsafe',['test'],transport,referee_model='r')
        self.assertFalse((self.root/'unsafe').exists())

    def test_bad_json_is_a_failed_choice_not_pending_normalization(self):
        report=evaluate(self.data,self.root/'bad',['test'],ScriptedTransport(['not json'],verdict='invalid'),referee_model='r')[0]
        self.assertEqual(report['score']['final_score_percent'],0)
