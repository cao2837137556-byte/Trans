"""Generated progress states: a live monitor is not a live scientific worker."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
import progress


class ProgressTests(unittest.TestCase):
    def test_not_run_is_not_stale_or_falsely_running(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'STATUS.json'
            self.assertEqual(progress.snapshot(path)['technical_status'],'NOT_RUN')
            path.write_text(json.dumps(dict(technical_status='NOT_RUN',phase='IMPLEMENTATION_READY')),encoding='utf-8')
            state=progress.snapshot(path)
            self.assertEqual(state['freshness'],'not_started')
            self.assertNotIn('display_status',state)

    def test_fresh_service_does_not_hide_stale_work_and_terminal_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'STATUS.json'
            now=datetime.now(timezone.utc)
            data=dict(technical_status='RUNNING',work_heartbeat_utc=(now-timedelta(seconds=120)).isoformat(),
                      service_heartbeat_utc=now.isoformat(),raw_packets=8192,total=10000)
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(progress.snapshot(path)['display_status'],'UNKNOWN_WORKER_PROGRESS')
            data['technical_status']='COMPLETED'
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(progress.snapshot(path)['freshness'],'terminal')


if __name__=='__main__':unittest.main()
