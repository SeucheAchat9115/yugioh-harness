import unittest
from yugioh_benchmark.metering import Meter, cost_for, normalize_usage, summarize, validate_prices
from yugioh_benchmark.evaluation_plots import comparison_points

RATE={'test':{'source':'Offline test rates, not provider pricing','effective_date':'2026-10-09',
    'input_usd_per_million':2,'cached_input_usd_per_million':1,'output_usd_per_million':6}}
class MeteringTests(unittest.TestCase):
    def test_exact_cost_cached_and_reasoning_not_double_counted(self):
        usage=normalize_usage({'input_tokens':1000,'output_tokens':200,'cached_input_tokens':400,'reasoning_tokens':100})
        self.assertEqual(cost_for('test',usage,RATE)['usd'],'0.0028')
        self.assertEqual(usage['total_tokens'],1200)
        self.assertIsNone(cost_for('test',normalize_usage({'input_tokens':1000,'output_tokens':200}),RATE)['usd'])
        self.assertIsNone(cost_for('unknown',usage,RATE)['usd'])
        self.assertEqual(cost_for('unknown',None,{},'0.01')['basis'],'provider_reported')

    def test_bad_prices_and_counts_rejected(self):
        for value in (True,-1,1.5):
            with self.assertRaises(ValueError):normalize_usage({'input_tokens':value})
        for value in ({'input_tokens':3,'output_tokens':2,'total_tokens':9},
                      {'output_tokens':1,'reasoning_tokens':2}):
            with self.assertRaises(ValueError):normalize_usage(value)
        with self.assertRaises(ValueError):validate_prices({'test':{**RATE['test'],'effective_date':'unknown'}})
        with self.assertRaises(ValueError):validate_prices({'test':{**RATE['test'],'input_usd_per_million':-1}})

    def test_timing_roles_and_failures_preserve_usage(self):
        clock=iter([10,12,20,23]);meter=Meter(RATE,clock=lambda:next(clock))
        def good(*a,**k):return {'response':'{}','usage':{'input_tokens':10,'output_tokens':3,'cached_input_tokens':0}}
        def bad(*a,**k):return {'error':'Secret provider detail must never be logged','usage':{'input_tokens':10,'output_tokens':3,'cached_input_tokens':0}}
        meter.call(good,'test',{},case_id='a',role='evaluation')
        with self.assertRaises(RuntimeError):meter.call(bad,'test',{},case_id='a',role='referee')
        summary=summarize(meter.calls)
        self.assertEqual(summary['pipeline']['total_call_seconds'],5)
        self.assertEqual(summary['evaluation']['total_tokens'],13)
        self.assertEqual(summary['referee']['failed_calls'],1)
        self.assertIsNotNone(summary['pipeline']['cost_usd'])
        self.assertNotIn('Secret',str(meter.calls))

    def test_missing_usage_cost_not_zero(self):
        clock=iter([0,1]);meter=Meter(clock=lambda:next(clock))
        meter.call(lambda *a,**k:{'response':'{}'},'test',{},case_id='a',role='evaluation')
        self.assertIsNone(summarize(meter.calls)['pipeline']['cost_usd'])
        self.assertIsNone(summarize(meter.calls)['pipeline']['total_tokens'])
        self.assertEqual(summarize(meter.calls)['pipeline']['unpriced_calls'],1)

    def test_plot_unknown_cost_and_identical_prompts(self):
        report={'model':'test','protocol_sha256':'abc','prompt_manifest':{'a':'xyz'},'wall_seconds':1,
            'score':{'suite_sha256':'suite','weights':{'a':1},'kpis':{k:{'score':1} for k in ('state_recreation','human_move_agreement','rule_correctness')},'final_score_percent':100},
            'measurement_summary':{'evaluation':{'total_call_seconds':60,'cost_usd':None}}}
        points=comparison_points({'reports':[report]})
        self.assertIsNone(points[0]['cost_usd']);self.assertEqual(points[0]['evaluation_minutes'],1)
        with self.assertRaises(ValueError):comparison_points({'reports':[report,{**report,'protocol_sha256':'changed'}]})

    @unittest.skipUnless(__import__('importlib.util',fromlist=['find_spec']).find_spec('matplotlib'),'requires plotting extra')
    def test_four_panel_figures_render_with_unknown_cost(self):
        from pathlib import Path
        import tempfile
        from yugioh_benchmark.evaluation_plots import plot_comparison
        report={'model':'offline-test-only','protocol_sha256':'abc','prompt_manifest':{'a':'xyz'},'wall_seconds':1,
            'score':{'suite_sha256':'suite','weights':{'a':1},'kpis':{k:{'score':1} for k in ('state_recreation','human_move_agreement','rule_correctness')},'final_score_percent':100},
            'measurement_summary':{'evaluation':{'total_call_seconds':60,'cost_usd':None}}}
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'plots';result=plot_comparison({'reports':[report]},output)
            self.assertEqual(len(result['files']),4)
            self.assertTrue((output/'performance-runtime.png').read_bytes().startswith(b'\x89PNG'))
            self.assertIn('cost unavailable',(output/'performance-cost.svg').read_text(encoding='utf-8'))
            self.assertIn('Equal-weight final score',(output/'performance-runtime.svg').read_text(encoding='utf-8'))
            with self.assertRaises(ValueError):plot_comparison({'reports':[report]},output)
