"""Submission, frozen identity and full summary acceptance regressions."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(1,str(HERE.parent/'edge_formal_execution_v4_20261104'))
from checkpoint import atomic_json,canonical,sha
from worker import read
from formal_job import require_engineering_authorization
from formal_acceptance import validate_outputs,METHODS
from reporting import HEADS
from runtime_control import Attempt,current_status

class Contract(unittest.TestCase):
    def test_frozen_source_and_authorization(self):
        card=require_engineering_authorization(HERE/'ENGINEERING_CARD.json',HERE/'AUTHORIZATION.json')
        parent=read(HERE.parent/'edge_formal_gate_resume_v4_20261104/ENGINEERING_CARD.json')
        for key in ('dependency_envelope','scientific_input_artifact_pins','selection_seal_sha256','runtime_identity'):
            self.assertEqual(card[key],parent[key])
        self.assertNotIn('replay_checkpoint_source',card)
        self.assertNotIn('complete_role_adoption',card)
    def test_engineering_authorization_cannot_score(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'auth.json';a=read(HERE/'AUTHORIZATION.json');a['scope']='EDGE_FORMAL_WORKER_ENGINEERING_GATE';atomic_json(p,a)
            with self.assertRaisesRegex(RuntimeError,'USER_EVALUATION_AUTHORIZATION'):
                require_engineering_authorization(HERE/'ENGINEERING_CARD.json',p)
    def test_quality_publication_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            attempt=Attempt(d,'test')
            self.assertFalse(current_status(d)['external_quality_computed'])
            attempt.publish('STOP',external_quality_computed=False);attempt.close()
            self.assertFalse(current_status(d)['external_quality_computed'])
    def test_full_summary_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'encoded').mkdir();(out/'evaluation').mkdir()
            uids=['fixture-%06d'%i for i in range(64124)]
            # Number of batches matches real shape splitting, without fake arrays.
            sizes=[16]*4046
            excess=sum(sizes)-len(uids)
            for i in range(excess):sizes[i]-=1
            batches=[];start=0
            for i,n in enumerate(sizes):batches.append(dict(batch_id=str(i),uids=uids[start:start+n]));start+=n
            binding=dict(identity=dict(execution_card_sha256='fixture-card'))
            atomic_json(out/'encoded/BINDING.json',binding)
            atomic_json(out/'encoded/COMPLETE.json',dict(rows=64124,batches=batches,binding_sha256=hashlib.sha256(canonical(binding)).hexdigest(),ordered_uids_sha256=hashlib.sha256(canonical(uids)).hexdigest()))
            report=dict(query_rows=60000,ordered_query_uids=uids[:60000],external_quality_used_for_selection=False,
                ht_renormalized=False,ht_clamped=False,references_in_query_denominator=0,
                methods={m:dict(heads={h:dict(roles={r:dict(selected_rows=20000,metric='FPR' if r=='NORMAL' else 'ATTACK_ASSOCIATED_RECALL') for r in ('NORMAL','HTTP','UDP')}) for h in HEADS}) for m in METHODS})
            atomic_json(out/'evaluation/METRICS.json',report)
            complete=dict(metrics_sha256=sha(out/'evaluation/METRICS.json'),query_rows=60000,reference_rows=4124,methods=sorted(METHODS),training=False,
                pairs_full_upper=324756408,ordered_query_uids_sha256=hashlib.sha256(canonical(report['ordered_query_uids'])).hexdigest())
            atomic_json(out/'evaluation/COMPLETE.json',complete)
            self.assertEqual(validate_outputs(out,'fixture-card')['status'],'PASS_STRUCTURAL_VALIDATION')
            with self.assertRaisesRegex(ValueError,'ENCODE_CARD_BINDING'):validate_outputs(out,'wrong-card')
            complete['reference_rows']=4123;atomic_json(out/'evaluation/COMPLETE.json',complete)
            with self.assertRaisesRegex(ValueError,'EVAL_COMPLETE'):validate_outputs(out,'fixture-card')
            complete['reference_rows']=4124
            report['methods']['C5_P3']['heads']['ensemble']['roles']['UDP']['selected_rows']=19999
            atomic_json(out/'evaluation/METRICS.json',report);complete['metrics_sha256']=sha(out/'evaluation/METRICS.json');atomic_json(out/'evaluation/COMPLETE.json',complete)
            with self.assertRaisesRegex(ValueError,'METRIC_ROLE_DENOMINATOR'):validate_outputs(out,'fixture-card')
    def test_delivery_members_and_slurm(self):
        import tarfile
        delivery=read(HERE/'DELIVERY.json')
        with tarfile.open(delivery['archive_local_path']) as tar:
            self.assertEqual(set(tar.getnames()),set(delivery['members']))
            for m in tar.getmembers():
                self.assertTrue(m.isfile());self.assertEqual(hashlib.sha256(tar.extractfile(m).read()).hexdigest(),delivery['members'][m.name]['sha256'])
        self.assertIn('#SBATCH --time=1-00:00:00',(HERE/'engineering.slurm').read_text())
        self.assertIn('#SBATCH --time=00:30:00',(HERE/'preflight.slurm').read_text())
    def test_preflight_new_import_required(self):
        from real_slice_preflight import validate_candidate,STAGES,SLICE_SHA
        c=dict(status='CANDIDATE_SUCCESS',card_sha256='card',kind='V3_REAL_SLICE_E2E',runtime_identity={},slice_sha256=SLICE_SHA,logical_rows=78,
            external_quality_retained=False,actual_v3_packed_backend=True,accepted_complete_import=dict(status='PASS_COMPLETE_IMPORT',logical_rows=64124,source_pointer_unchanged=True),
            replay_resume_probe=dict(status='PASS_REAL_REPLAY_CRASH_RESUME',actual_exit=76,checkpoint_frame=8,resumed_numerical_frames=8,all_snapshots_value_exact=True),
            stages=[dict(name=n,status='PASS',seconds=1) for n in STAGES])
        c['monitor_regression']=dict(status='PASS_RENAME_AND_REAL_BINDING');c['encoding_import']=dict(status='PASS_VALIDATED_COMMITTED_ENCODING_IMPORT',rows=1)
        validate_candidate(c,'card',{})
        c['accepted_complete_import']['logical_rows']=64123
        with self.assertRaisesRegex(ValueError,'ACCEPTED_COMPLETE_IMPORT_REQUIRED'):validate_candidate(c,'card',{})

if __name__=='__main__':unittest.main(verbosity=2)
