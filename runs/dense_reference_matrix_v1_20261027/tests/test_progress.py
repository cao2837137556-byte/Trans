from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hpc'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import progress_server
import status_sync
from common import write


class ProgressTests(unittest.TestCase):
    def test_no_job_is_not_submitted(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(progress_server.view(temp)['status'], 'NOT_SUBMITTED')

    def fixture(self, path, state, age=0, sync='OK', scheduler='RUNNING'):
        write(path / 'bundle.json', dict(schema='paper04-dense-progress-bundle-v1',
            job_id='123', observed_utc=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
            progress=dict(status=state), scheduler=dict(job_id='123', state=scheduler),
            read_only=True, automatic_retry=False))
        write(path / 'sync.json', dict(status=sync))

    def test_stale_running_becomes_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp), 'RUNNING', 120)
            self.assertEqual(progress_server.view(temp)['status'], 'UNKNOWN')

    def test_complete_survives_lost_transport_and_old_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp), 'COMPLETE', 86400, 'UNKNOWN', 'COMPLETED')
            result = progress_server.view(temp)
            self.assertEqual(result['status'], 'COMPLETE')
            self.assertFalse(result['heartbeat_required'])

    def test_scheduler_failure_is_visible_without_worker_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp), 'RUNNING', scheduler='OUT_OF_MEMORY')
            result = progress_server.view(temp)
            self.assertEqual(result['status'], 'EXCEPTION_STOP')
            self.assertEqual(result['reason'], 'SLURM_OUT_OF_MEMORY')

    def test_job_or_schema_mismatch_is_fatal_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            self.fixture(path, 'RUNNING')
            from common import read
            value = read(path / 'bundle.json')
            status_sync.validate_bundle(value, '123')
            for field, wrong in (('schema', 'OTHER'), ('job_id', '124')):
                mutated = dict(value, **{field: wrong})
                with self.assertRaises(ValueError):
                    status_sync.validate_bundle(mutated, '123')


if __name__ == '__main__':
    unittest.main()
