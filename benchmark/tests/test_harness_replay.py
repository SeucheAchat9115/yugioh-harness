"""Real archive import, privacy projection, and shared-runtime objective execution."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from yugioh_benchmark.harness_replay import audit_harness, prepare_harness
from yugioh_benchmark.evaluation import evaluate
from yugioh_benchmark.kpis import digest, score_kpis
from yugioh_benchmark.review_cases import load_reviewed_case

ROOT=Path(__file__).resolve().parents[2]
REVIEW=ROOT/'benchmark/benchmarks/reviews/max-edison-20261023.json'
ZIP=ROOT/'replays/edison/max-edison-20261023/replay.zip'

class OracleTransport:
    timeout_seconds=90
    boundary={'method':'context-only','parent_history':False,'tools':[],'filesystem':False,
              'evidence':'Offline scripted integration oracle; no actual model.'}
    config={'backend':'offline-test-only'}
    def __init__(self, answers, verdict='valid', fail=False):
        self.answers=answers;self.verdict=verdict;self.index=-1;self.requests=[];self.fail=fail
    def preflight(self, options):pass
    def __call__(self,model,request,*,role,options):
        self.requests.append((role,deepcopy(request)))
        if role=='evaluation':
            self.index+=1
            if self.fail:raise TimeoutError('Offline timeout')
            value=self.answers[self.index]['reference_intent']
        else:
            value={'verdict':self.verdict,'reason':'Offline fixture verdict, not expert certification',
                   'activation':self.answers[self.index].get('reference_activation')}
        return {'response':json.dumps(value),'usage':{'input_tokens':100,'output_tokens':20},'reported_model':model}

class HarnessReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures=tempfile.TemporaryDirectory()
        cls.data=Path(cls.fixtures.name)/'reviewed'
        prepare_harness(ZIP,json.loads(REVIEW.read_text()),cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.spec=json.loads(REVIEW.read_text())
        self.answers=self.spec['checkpoints']

    def test_import_reproducible_scoped_and_source_gaps_retained(self):
        audit=audit_harness(ZIP)
        self.assertEqual(audit['status'],'unreviewed')
        self.assertEqual(audit['event_count'],190)
        self.assertEqual(audit['decision_evidence']['status'],'partial')
        out=self.root/'fresh';report=prepare_harness(ZIP,self.spec,out)
        self.assertEqual(report['cases'],6)
        actual={p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()}
        expected={p.relative_to(self.data):p.read_bytes() for p in self.data.rglob('*') if p.is_file() and p.suffix=='.json'}
        self.assertEqual(actual,expected)
        for case in json.loads((out/'suite.json').read_text())['cases']:
            bridge,state=load_reviewed_case(out,case['id'])
            self.assertEqual(state['pending_decision']['actor'],'agent')
            self.assertEqual(state['revision'],0)
            context=bridge['player_context'];opponent=context['state']['players']['human']
            self.assertTrue(context['state']['game_id'].startswith('checkpoint-'))
            self.assertNotIn(case['id'].removesuffix('-choice'),json.dumps(context))
            for key in ('hand','extra_deck','side_deck','deck','cards','remaining_deck_order'):
                self.assertNotIn(key,opponent)
            visible=set()
            def check(value):
                if isinstance(value,dict):
                    if 'card_id' in value:visible.add(str(value['card_id']))
                    for child in value.values():check(child)
                elif isinstance(value,list):
                    for child in value:check(child)
            check(context['state'])
            self.assertEqual(set(context['cards']),visible)
            for card in opponent['monster_zones']+opponent['spell_trap_zones']:
                if card and card.get('hidden'):
                    self.assertNotIn('card_id',card);self.assertNotIn('name',card)
            self.assertEqual(context['guides'],{})
            self.assertEqual(context['recent_events'],[])
            self.assertNotIn('recommendations',json.dumps(context))
            self.assertFalse(context['rules']['truncated'])
            self.assertGreater(len(context['rules']['text']),8000)

    def test_bad_hash_unapproved_and_missing_boundary_rejected(self):
        for field,value in [('source_index_sha256','0'*64),('review',{'status':'pending'})]:
            spec=deepcopy(self.spec);spec[field]=value
            with self.assertRaises(ValueError):prepare_harness(ZIP,spec,self.root/'bad')
            self.assertFalse((self.root/'bad').exists())
        spec=deepcopy(self.spec);spec['checkpoints'][0]['revision']=169
        with self.assertRaises(ValueError):prepare_harness(ZIP,spec,self.root/'gap')
        self.assertFalse((self.root/'gap').exists())

    def test_archive_tampering_and_zip_path_traversal_rejected(self):
        for name in ('../game.json','/game.json','C:/game.json','a\\game.json'):
            path=self.root/'bad.zip'
            with zipfile.ZipFile(path,'w') as archive:archive.writestr(name,'{}')
            with self.assertRaises(ValueError):audit_harness(path)
        directory=self.root/'source';directory.mkdir()
        with zipfile.ZipFile(ZIP) as archive:archive.extractall(directory)
        event=next(directory.rglob('000010.json'));data=json.loads(event.read_text())
        data['action']['public_summary']='tampered';event.write_text(json.dumps(data))
        with self.assertRaises(ValueError):audit_harness(next(directory.rglob('game.json')).parent)

    def test_privacy_projection_checked_even_if_packet_digest_is_recomputed(self):
        data=self.root/'data';shutil.copytree(self.data,data)
        suite=json.loads((data/'suite.json').read_text());case=suite['cases'][0]
        path=data/case['player_packet'];packet=json.loads(path.read_text())
        hidden=packet['player_context']['state']['players']['human']
        # A malicious hidden identity embedded in an otherwise allowed public field.
        hidden['monster_zones'][0]={'instance_id':'injected','hidden':True,'name':'PRIVATE CANARY'}
        case['player_context_sha256']=digest(packet['player_context'])
        path.write_text(json.dumps(packet));(data/'suite.json').write_text(json.dumps(suite))
        with self.assertRaises(ValueError):load_reviewed_case(data,case['id'])

    def test_shared_runner_oracle_not_model_result_and_private_grading(self):
        transport=OracleTransport(self.answers)
        report=evaluate(self.data,self.root/'oracle',['offline-oracle'],transport,referee_model='offline-referee')[0]
        self.assertEqual(report['protocol'],'harness-objectives-v1')
        self.assertEqual(report['score']['final_score_percent'],100)
        self.assertEqual(report['score']['kpis']['rule_correctness']['score'],1)
        self.assertEqual(len(transport.requests),12)
        for role,request in transport.requests:
            payload=json.dumps(request)
            for forbidden in ('acceptable_moves','reference_intent','reference_activation','rationale','source_state_sha256','grading'):
                self.assertNotIn('"'+forbidden+'"',payload)
        run=json.loads((self.root/'oracle/model-1/run.json').read_text())
        for row in run['results']:
            self.assertIsNotNone(row['execution_plan'])
            self.assertEqual(len(row['journal']['events']),1)
        # A plausible semantic signature and bound plan cannot hide a different action.
        row=run['results'][1];row['normalized_move']={'kind':'pass'}
        row['move_normalization_review']['move_sha256']=digest(row['normalized_move'])
        row['legality_review']['attempt_sha256']=digest({k:v for k,v in row.items() if k!='legality_review'})
        with self.assertRaises(ValueError):score_kpis(json.loads((self.data/'suite.json').read_text()),run)

    def test_wrong_legal_action_invalid_uncertain_timeout_and_execution_failure(self):
        for label,verdict,fail in [('invalid','invalid',False),('uncertain','uncertain',False),('timeout','valid',True),('wrong','valid',False)]:
            answers=deepcopy(self.answers)
            if label=='wrong':
                for answer in answers:answer.update(reference_intent={'action':'pass'},reference_activation=None)
            report=evaluate(self.data,self.root/label,['offline'],OracleTransport(answers,verdict,fail),referee_model='referee')[0]
            score=report['score']['final_score_percent']
            if label=='uncertain':self.assertIsNone(score)
            else:self.assertAlmostEqual(score,100/3 if label=='wrong' else 0)
        # Correct card signature but missing the required self-cost fails execution.
        answers=deepcopy(self.answers);answers[-1]['reference_intent'].pop('cost_cards')
        report=evaluate(self.data,self.root/'bad-cost',['offline'],OracleTransport(answers),referee_model='referee')[0]
        self.assertAlmostEqual(report['score']['final_score_percent'],100*5/6)
