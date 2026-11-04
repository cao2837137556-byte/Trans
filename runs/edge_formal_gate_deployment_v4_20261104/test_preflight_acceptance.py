import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'edge_formal_execution_v4_20261104'))
from checkpoint import atomic_json, sha
from runtime_control import Attempt
from real_slice_preflight import SLICE_SHA, STAGES
from preflight_acceptance import inspect, accept, validate_saved


class AcceptanceTests(unittest.TestCase):
    def fixture(self, root):
        card=root/'CARD.json';atomic_json(card, dict(runtime_identity={'fixture':'frozen'}))
        output=root/'outputs/preflight_123'
        attempt=Attempt(output,sha(card))
        candidate=attempt.directory/'CANDIDATE.json'
        atomic_json(candidate,dict(status='CANDIDATE_SUCCESS',kind='V3_REAL_SLICE_E2E',attempt_id=attempt.id,
            card_sha256=sha(card),runtime_identity={'fixture':'frozen'},slice_sha256=SLICE_SHA,
            logical_rows=78,external_quality_retained=False,actual_v3_packed_backend=True,
            replay_resume_probe=dict(status='PASS_REAL_REPLAY_CRASH_RESUME',actual_exit=76,checkpoint_frame=8,resumed_numerical_frames=8,all_snapshots_value_exact=True),
            stages=[dict(name=s,status='PASS',seconds=1) for s in STAGES]))
        attempt.publish('PASS',candidate=candidate.name,candidate_sha256=sha(candidate),
                        cleanup_complete=True,resources=dict(max_tree_rss_bytes=1024,rss_samples=2))
        attempt.close()
        job=dict(job_id='123',phase='preflight',cpu=1,memory_gib=8,wall_seconds=600,
                 output_directory=str(output),card_sha256=sha(card))
        scheduler=dict(returncode=0,stdout='123|COMPLETED|0:0|00:00:10|1M|1|8Gn|00:10:00|\n')
        return card,job,scheduler,candidate

    def test_acceptance_requires_bound_current_candidate_and_cannot_be_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);card,job,scheduler,candidate=self.fixture(root)
            self.assertEqual(accept(root,card,job,scheduler)['status'],'PASS')
            validate_saved(root,card)
            candidate.write_text('{}')
            with self.assertRaisesRegex(ValueError,'CANDIDATE_IDENTITY'):validate_saved(root,card)

    def test_scheduler_failures_and_changed_resource_contract_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);card,job,scheduler,candidate=self.fixture(root)
            for before,after in [('COMPLETED','FAILED'),('0:0','1:0'),('|1|8Gn','|2|8Gn'),('8Gn','16Gn'),('00:10:00','02:00:00')]:
                broken=dict(scheduler,stdout=scheduler['stdout'].replace(before,after))
                with self.assertRaisesRegex(ValueError,'SCHEDULER_CONTRACT'):inspect(root,card,job,broken)

    def test_old_pass_invalidated_by_fresh_running_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);card,job,scheduler,candidate=self.fixture(root)
            attempt=Attempt(job['output_directory'],sha(card))
            try:
                with self.assertRaisesRegex(ValueError,'CURRENT_PASS'):inspect(root,card,job,scheduler)
            finally:attempt.close()
