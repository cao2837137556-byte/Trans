"""Regression checks for the conditional continuation and formal submission guard."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import dispatch
from motion_ingress import REPAIR_RUN, RESUME_RUN, RUN, TIMEOUT_PREP_JOB


def reply(stdout=''):
    return dict(returncode=0,stdout=stdout,stderr='')


class TimeoutContinuation(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.project = Path(folder.name)
        self.parent = self.project/'runs'/REPAIR_RUN
        self.package = self.parent/'package'
        self.package.mkdir(parents=True)
        self.target = self.parent.with_name(RESUME_RUN)
        self.target.mkdir()
        manifest = b'{"files":{}}'
        (self.package/'PACKAGE_MANIFEST.json').write_bytes(manifest)
        sha = sha256(manifest).hexdigest()
        dispatch.write(self.parent/'INSTALL.json',dict(package_manifest_sha256=sha))
        dispatch.write(self.parent/'SBATCH_prepare.json',reply(TIMEOUT_PREP_JOB+'\n'))
        dispatch.write(self.package/'CONTINUATION_SOURCE_PINS.json',dict(
            job=TIMEOUT_PREP_JOB, predecessor_run=REPAIR_RUN,predecessor_package_manifest_sha256=sha))

    def test_running_does_not_release_then_timeout_does(self):
        responses=[
            reply('183987|p04-k8192-prepare|RUNNING|0:0|63000\n'),
            reply('183987|p04-k8192-prepare|RUNNING\n'),
            reply('183987|p04-k8192-prepare|TIMEOUT|0:0|64800\n'),
            reply(),
        ]
        with patch.object(dispatch,'PACKAGE',self.package), patch.object(
                dispatch,'command',side_effect=responses) as scheduler, patch.object(
                dispatch.time,'sleep',lambda _:None):
            outcome=dispatch.wait_for_timeout(self.project,self.target)
        self.assertEqual([x.args[0][0] for x in scheduler.call_args_list],['sacct','squeue','sacct','squeue'])
        self.assertEqual(outcome['mechanism'],'SLURM_TIME_LIMIT')
        self.assertEqual(dispatch.read(self.target/'CHAIN_STATE.json')['stage'],'WAITING_FOR_183987_TIMEOUT')
        self.assertEqual(dispatch.read(self.target/'PREDECESSOR_TIMEOUT.json'),outcome)

    def test_completed_or_non_time_failure_has_no_retry(self):
        with patch.object(dispatch,'PACKAGE',self.package):
            with patch.object(dispatch,'command',side_effect=[
                    reply('183987|p04-k8192-prepare|COMPLETED|0:0|64000\n'),reply()]):
                self.assertIsNone(dispatch.wait_for_timeout(self.project,self.target))
            with patch.object(dispatch,'command',side_effect=[
                    reply('183987|p04-k8192-prepare|FAILED|1:0|64000\n'),reply()]):
                with self.assertRaisesRegex(ValueError,'PREDECESSOR_TERMINAL_WITHOUT_TIMEOUT'):
                    dispatch.wait_for_timeout(self.project,self.target)
        self.assertFalse((self.target/'PREDECESSOR_TIMEOUT.json').exists())

    def test_existing_worker_wall_limit_needs_terminal_scheduler(self):
        dispatch.write(self.parent/'FAILURE_prepare.json',dict(error='COMPUTE_WALL_HEADROOM',
                       wall_seconds=64625))
        with patch.object(dispatch,'PACKAGE',self.package),patch.object(
                dispatch,'command',side_effect=[reply('183987|p04-k8192-prepare|FAILED|1:0|64626\n'),reply()]):
            outcome=dispatch.wait_for_timeout(self.project,self.target)
        self.assertEqual(outcome['mechanism'],'WORKER_WALL_LIMIT')

    def test_global_formal_submission_guard(self):
        other = self.target.with_name(RESUME_RUN+'_extra')
        other.mkdir()
        calls=[]
        def scheduler(argv):
            calls.append(argv[1])
            return reply('183999\n' if argv[1]=='--parsable' else '')
        with patch.object(dispatch,'command',side_effect=scheduler):
            job=dispatch.submit(self.target,self.project,self.parent/'archive','replay',12288,3600)
            self.assertEqual(job,'183999')
            with self.assertRaises(FileExistsError):
                dispatch.submit(other,self.project,self.parent/'archive','replay',12288,3600)
        self.assertEqual(calls.count('--parsable'),1)
        self.assertTrue((self.project/'runs'/('.'+RUN+'_formal_submission.json')).is_file())


if __name__ == '__main__':
    unittest.main()
