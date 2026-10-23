from copy import deepcopy
import json
import unittest
from pathlib import Path
import subprocess
import sys
import tempfile
from yugioh_benchmark.extraction import extract_observations, extraction_summary, write_extraction
from yugioh_benchmark.native_json import convert_json

SOURCE = Path(__file__).resolve().parents[1]/'fixtures/duelingbook/aco77-sdesowitz02-2026-10-07.json'
URL = 'https://www.duelingbook.com/replay?id=40753-85958923'

def extract(data):
    return extract_observations(convert_json(data, URL, '2026-10-08'))

class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(SOURCE.read_text(encoding='utf-8')); cls.result=extract(cls.data)
        cls.records=cls.result['records']

    def test_order_and_candidates(self):
        self.assertEqual(len(self.records),554)
        self.assertEqual([r['source_index'] for r in self.records],list(range(554)))
        self.assertEqual(sum(r['candidate'] for r in self.records),174)
        self.assertEqual({r['game'] for r in self.records},{1,2})

    def test_opening_uses_only_preceding_observations(self):
        state=self.records[10]['before']
        self.assertEqual(state['players']['sdesowitz02']['hand'],sorted([
            'Scapegoat','Monster Gate','Destiny Draw','Reasoning','Trade-In','Divine Sword - Phoenix Blade']))
        self.assertNotIn('Gold Sarcophagus',state['players']['sdesowitz02']['hand'])
        self.assertEqual(state['players']['Aco77']['deck_count'],35)
        self.assertEqual(state['players']['sdesowitz02']['deck_count'],34)
        self.assertIsNone(state['players']['sdesowitz02'].get('deck_order'))

    def test_hand_inventory_counts_and_second_game_reset(self):
        self.assertEqual([g['source_index'] for g in self.result['gaps']],[313])
        reset=self.records[326]['after']
        for player in reset['players'].values():
            self.assertEqual(player['hand'],[]); self.assertEqual(player['field'],{})
            self.assertEqual(player['graveyard'],[]); self.assertEqual(player['lp'],8000)
        self.assertEqual(self.records[327]['after']['players']['Aco77']['deck_count'],35)
        self.assertEqual(len(self.records[327]['after']['players']['Aco77']['hand']),5)

    def test_control_transfer_and_owner_return_issue(self):
        field=self.records[211]['after']['players']['sdesowitz02']['field']
        self.assertEqual(field['M-2']['owner'],'Aco77')
        field=self.records[212]['after']['players']['sdesowitz02']['field']
        self.assertEqual(field['S-3']['name'],'Dekoichi the Battlechanted Locomotive')
        self.assertEqual(self.records[313]['gaps'][0]['source_index'],313)
        self.assertIn(313,self.records[319]['unresolved_prior_source_indexes'])
        self.assertNotIn(313,self.records[327]['unresolved_prior_source_indexes'])
        pile=self.records[414]['after']['players']['Aco77']['banished']
        self.assertIn('Breaker the Magical Warrior',[c['name'] for c in pile])

    def test_unknown_draw_is_not_filled_from_future_reveal(self):
        data=deepcopy(self.data); data['plays'][4].pop('card')
        data['plays'][4]['log'].pop('private_log')
        result=extract(data)
        self.assertIn(None,result['records'][4]['after']['players']['sdesowitz02']['hand'])
        self.assertTrue(any(g['reason']=='Unnamed draw' for g in result['gaps']))
        self.assertNotEqual(result['source_payload_sha256'],self.result['source_payload_sha256'])

    def test_reviewer_only_and_no_copy_mapping_or_legality(self):
        self.assertEqual(self.result['status'],'unreviewed_observation_reconstruction')
        self.assertIn('reviewer_only',self.result['audience'])
        self.assertNotIn('legal_actions',self.records[10])
        self.assertNotIn('physical_copy_id',self.records[10]['observed_action'])
        self.assertTrue(self.records[551]['after_concession'])

    def test_selected_summary_is_reproducible(self):
        path=SOURCE.parents[2]/'benchmarks/extractions/db-json-40753-85958923.json'
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')),extraction_summary(self.result))

    def test_unknown_operations_are_flagged(self):
        data=deepcopy(self.data)
        data['plays'][9]['play']='Unknown manual operation'
        result=extract(data)
        self.assertTrue(any(g['source_index']==9 and 'Unsupported' in g['reason'] for g in result['gaps']))

    def test_source_annotation_tampering_is_rejected(self):
        replay=convert_json(self.data, URL)
        replay['events'][10]['actor']='p1'
        with self.assertRaises(ValueError): extract_observations(replay)

    def test_writer_refuses_overwrite_and_cli_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/'extraction'
            summary=write_extraction(self.result,directory)
            self.assertEqual(summary['source_events'],554)
            with self.assertRaises(FileExistsError): write_extraction(self.result,directory)
            self.assertEqual(json.loads((directory/'states-and-actions.json').read_text(encoding='utf-8')),self.result)
            command=[sys.executable,'-m','yugioh_benchmark','extract',
                     str(SOURCE.parents[2]/'replays/db-json-40753-85958923'),
                     '--output',str(Path(temporary)/'cli')]
            run=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(json.loads(run.stdout),summary)

if __name__=='__main__': unittest.main()
