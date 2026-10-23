from copy import deepcopy
from importlib.util import find_spec
import json
import unittest
from yugioh_benchmark.harness_bridge import prepare_case, run_case


@unittest.skipUnless(find_spec('harness'), 'Optional harness is not installed')
class HarnessBridgeTests(unittest.TestCase):
    def runner(self, leak=False):
        class Runner:
            def context(self, actor, compact=False):
                context={'perspective':actor, 'decision':{'actor':actor},
                         'state':{'mode':'managed','players':{
                             'human':{},'agent':{'hand':[]}}}}
                if leak: context['state']['players']['human']['hand']=['secret']
                return context
        return Runner()

    def case(self, runner=None):
        return prepare_case(runner or self.runner(),case_id='synthetic-test',
                            source='db-123',sequence=2,actor='agent',
                            review={'status':'approved','reviewer':'unit-test'},
                            grading={'hidden_answer':'SECRET_FUTURE_MOVE'})

    def test_only_player_context_reaches_real_harness_transport(self):
        case=self.case()
        original=deepcopy(case)
        requests=[]
        def transport(request):
            requests.append(request)
            return {'response':'Pass'}
        result=run_case(case,transport)
        self.assertEqual(result['response'],'Pass')
        self.assertGreaterEqual(result['latency_seconds'],0)
        self.assertNotIn('SECRET_FUTURE_MOVE',json.dumps(requests))
        self.assertEqual(requests[0]['tools'],[])
        self.assertEqual(json.loads(requests[0]['messages'][1]['content']),case['player_context'])
        self.assertEqual(case,original)

    def test_opponent_hidden_hand_rejected(self):
        with self.assertRaisesRegex(ValueError,'hidden zones'): self.case(self.runner(leak=True))

    def test_unreviewed_position_rejected(self):
        with self.assertRaises(ValueError):
            prepare_case(self.runner(),case_id='x',source='db-123',sequence=1,
                         actor='agent',review={'status':'pending'},grading={})


if __name__ == '__main__': unittest.main()
