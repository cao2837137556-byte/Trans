import ast
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(1,str(Path(__file__).resolve().parent.parent/'edge_formal_execution_v4_20261104'))
from worker import input_binding
from real_slice_preflight import validate_candidate
import test_preflight_acceptance as fixtures
import engineering_gate
HERE=Path(__file__).resolve().parent
CODE=HERE.parent/'edge_formal_execution_v4_20261104'
class ExtensionTests(unittest.TestCase):
    def test_scientific_binding_identical_to_actual_parent(self):
        old=json.loads((HERE.parent/'edge_formal_gate_deployment_v4_20261104/ENGINEERING_CARD.json').read_text())
        new=json.loads((HERE/'ENGINEERING_CARD.json').read_text())
        raw={'raw_inputs':{r:{'bytes':1,'sha256':'frozen'} for r in ('NORMAL','HTTP','UDP')}}
        self.assertEqual(input_binding(old,old['runtime_identity'],raw),input_binding(new,new['runtime_identity'],raw))
        self.assertEqual(new['budget'],dict(old['budget'],wall_seconds=21600))
    def test_engineering_gate_only_budget_bootstrap_and_stop_metadata_change(self):
        original=(CODE/'engineering_gate.py').read_text()
        revised=(HERE/'engineering_gate.py').read_text()
        bootstrap="import sys\nfrom pathlib import Path\nsys.path.insert(1,str(Path(__file__).resolve().parent.parent/'edge_formal_execution_v4_20261104'))\n\n"
        revised=revised.replace(bootstrap,'',1).replace('21600','7200').replace(', durable_replay_checkpoint_requires_validation=True','')
        self.assertEqual(original,revised)
    def test_no_hidden_two_hour_gate_cap_or_short_transport(self):
        values=[n.value for n in ast.walk(ast.parse((HERE/'engineering_gate.py').read_text())) if isinstance(n,ast.Constant)]
        self.assertNotIn(7200,values);self.assertEqual(values.count(21600),3)
        self.assertIn('12*3600',(HERE/'pipeline.py').read_text())
        self.assertIn('threading.Timer(12 * 3600, server.shutdown)',(HERE/'remote_receiver.py').read_text())
    def test_actual_restore_is_mandatory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            card,job,scheduler,candidate=fixtures.AcceptanceTests().fixture(Path(tmp))
            value=json.loads(candidate.read_text());value.pop('prior_checkpoint_restore')
            with self.assertRaisesRegex(ValueError,'ACTUAL_PRIOR_CHECKPOINT_RESTORE_REQUIRED'):
                validate_candidate(value,value['card_sha256'],value['runtime_identity'])
if __name__=='__main__':unittest.main()
