"""Synthetic tar, process and one-submit boundaries; never call Slurm or science."""
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock,patch

import controller


def digest(value):return hashlib.sha256(value).hexdigest()


def tar_bytes(items):
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w') as ar:
        for name,payload in items:
            member=tarfile.TarInfo(name);member.size=len(payload);ar.addfile(member,io.BytesIO(payload))
    return buffer.getvalue()


class ControllerChecks(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name);self.here=self.root/'deployment';self.package=self.root/'science'
        self.card=b'{"candidate":"synthetic"}\n';self.items=[('EXECUTION_CARD.json',self.card),('code.py',b'# synthetic\n')]
        self.bundle=tar_bytes(self.items);self.clock=[100.];self.wallclock=[1700000100.]
        config=dict(token='a'*48,execution_card_sha256=digest(self.card),bundle=dict(bytes=len(self.bundle),sha256=digest(self.bundle)),
            files={n:dict(bytes=len(b),sha256=digest(b)) for n,b in self.items})
        self.control=controller.BudgetController(config,root=self.root,here=self.here,package=self.package,
            clock=lambda:self.clock[0],wallclock=lambda:self.wallclock[0])

    def install(self):
        self.control.upload(0,self.bundle,digest(self.bundle));self.control.install()

    def test_code_transfer_can_resume_only_at_the_exact_byte_offset(self):
        cut=101;self.control.upload(0,self.bundle[:cut],digest(self.bundle[:cut]))
        self.assertEqual(self.control.transfer()['offset'],cut)
        with self.assertRaisesRegex(ValueError,'OFFSET'):
            self.control.upload(cut-1,self.bundle[cut:],digest(self.bundle[cut:]))
        self.control.upload(cut,self.bundle[cut:],digest(self.bundle[cut:]))
        self.assertTrue(self.control.transfer()['complete']);self.assertFalse(self.package.exists())

    def test_bad_upload_digest_does_not_write_bytes(self):
        with self.assertRaisesRegex(ValueError,'CHUNK_PIN'):self.control.upload(0,self.bundle,'0'*64)
        self.assertFalse((self.here/'bundle.part').exists())

    def test_install_matches_every_hash_and_never_overwrites_a_package(self):
        self.install();before=(self.package/'code.py').read_bytes()
        self.assertEqual(controller.sha(self.package/'EXECUTION_CARD.json'),digest(self.card))
        with self.assertRaisesRegex(ValueError,'ONE_NEW_INSTALL'):self.control.install()
        self.assertEqual((self.package/'code.py').read_bytes(),before)

    def test_archive_escape_duplicate_link_and_extra_members_are_rejected(self):
        for name in ('../escape','/absolute','C:/escape','folder\\escape','folder//duplicate'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                b=tar_bytes([(name,b'x')])
                with tarfile.open(fileobj=io.BytesIO(b),mode='r:') as ar:
                    controller.validate_archive(ar,{name:dict(bytes=1,sha256=digest(b'x'))})
        b=tar_bytes([('same',b'x'),('same',b'x')])
        with tarfile.open(fileobj=io.BytesIO(b),mode='r:') as ar:
            with self.assertRaisesRegex(ValueError,'EXACT_ARCHIVE'):controller.validate_archive(ar,{'same':dict(bytes=1,sha256=digest(b'x'))})
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w') as ar:
            member=tarfile.TarInfo('link');member.type=tarfile.SYMTYPE;member.linkname='../other';ar.addfile(member)
        with tarfile.open(fileobj=io.BytesIO(buffer.getvalue()),mode='r:') as ar:
            with self.assertRaisesRegex(ValueError,'REGULAR'):controller.validate_archive(ar,{'link':dict(bytes=0,sha256=digest(b''))})

    def test_successful_submit_is_idempotent_and_sbatch_is_called_once(self):
        self.install();self.control.state['status']='PREFLIGHT_PASS'
        with patch.object(controller,'run_group',return_value=subprocess.CompletedProcess([],0,'180999;cluster\n','')) as command:
            first=self.control.submit();second=self.control.submit()
        self.assertEqual(first['job_id'],'180999');self.assertEqual(second['job_id'],'180999');self.assertEqual(command.call_count,1)

    def test_uncertain_submit_never_retries(self):
        self.install();self.control.state['status']='PREFLIGHT_PASS'
        with patch.object(controller,'run_group',side_effect=subprocess.TimeoutExpired('sbatch',30)) as command:
            with self.assertRaises(subprocess.TimeoutExpired):self.control.submit()
            with self.assertRaisesRegex(ValueError,'ONE_SUBMIT'):self.control.submit()
        self.assertEqual(command.call_count,1);self.assertEqual(self.control.state['status'],'SUBMISSION_UNCERTAIN_NO_RETRY')
        self.assertTrue((self.here/'SUBMIT_ATTEMPT.json').exists())

    def test_non_numeric_sbatch_success_is_uncertain_and_cannot_be_resubmitted(self):
        self.install();self.control.state['status']='PREFLIGHT_PASS'
        with patch.object(controller,'run_group',return_value=subprocess.CompletedProcess([],0,'unparseable','')) as command:
            with self.assertRaisesRegex(ValueError,'UNCERTAIN'):self.control.submit()
            with self.assertRaisesRegex(ValueError,'ONE_SUBMIT'):self.control.submit()
        self.assertEqual(command.call_count,1)

    def test_finished_preflight_always_cleans_its_process_group(self):
        child=MagicMock();child.poll.return_value=0;child.returncode=0
        self.control.child=child;self.control.state['status']='PREFLIGHT_RUNNING'
        controller.write(self.here/'PREFLIGHT_RESULT.json',dict(status='PASS'))
        with patch.object(controller,'stop_group') as stop:self.control.poll_preflight()
        stop.assert_called_once_with(child);self.assertEqual(self.control.state['status'],'PREFLIGHT_PASS')

    def test_preflight_timeout_kills_group_and_stays_failed(self):
        child=MagicMock();child.poll.return_value=None
        self.control.child=child;self.control.preflight_started=0;self.control.state['status']='PREFLIGHT_RUNNING';self.clock[0]=601
        with patch.object(controller,'stop_group') as stop:self.control.poll_preflight()
        stop.assert_called_once_with(child);self.assertEqual(self.control.state['status'],'PREFLIGHT_FAIL')

    def test_run_group_cleans_descendants_even_after_leader_exits(self):
        child=MagicMock();child.communicate.return_value=('out','err');child.returncode=0
        with patch.object(controller.subprocess,'Popen',return_value=child) as popen,patch.object(controller,'stop_group') as stop:
            result=controller.run_group(['synthetic'],timeout=3)
        stop.assert_called_once_with(child);self.assertEqual(result.stdout,'out');self.assertTrue(popen.call_args.kwargs['start_new_session'])

    def test_queue_has_no_budget_clock_and_started_clock_cannot_be_extended(self):
        self.control.observe_budget({});self.assertIsNone(self.control.budget_remaining())
        started=datetime.fromtimestamp(1700000000,timezone.utc).isoformat()
        self.control.observe_budget(dict(started_utc=started));first=self.control.deadline
        self.clock[0]+=100;self.wallclock[0]+=100;self.control.observe_budget(dict(started_utc=started))
        self.assertEqual(self.control.deadline,first);self.assertEqual(self.control.budget_remaining(),17800)
        self.wallclock[0]-=10;self.control.observe_budget(dict(started_utc=started));self.assertEqual(self.control.deadline,first)

    def test_expired_budget_cancels_only_this_new_job_once(self):
        self.install();self.control.state.update(submitted=True,status='SUBMITTED',job_id='180999');self.control.deadline=99
        with patch.object(controller,'run_group',return_value=subprocess.CompletedProcess([],0,'','')) as command:
            self.control.cancel_if_expired();self.control.cancel_if_expired()
        self.assertEqual(command.call_count,1);self.assertEqual(command.call_args.args[0],['scancel','180999'])
        self.assertEqual(self.control.state['status'],'BUDGET_EXPIRED')

    def test_transient_scheduler_query_failure_preserves_running_state(self):
        self.install();self.control.state.update(submitted=True,status='SUBMITTED',job_id='180999')
        with patch.object(controller,'run_group',side_effect=subprocess.TimeoutExpired('squeue',15)):
            state=self.control.snapshot()
        self.assertEqual(state['status'],'SUBMITTED');self.assertIn('scheduler_error',state)

    def make_result(self,*,extra_name=None):
        self.install();source=self.package/'outputs/encoding';source.mkdir(parents=True)
        payloads={'RESULT.json':json.dumps(dict(execution_card_sha256=digest(self.card))).encode(),
            'history/NETATMO/encoded/references.npz':b'synthetic arrays',
            'history/NETATMO/encoded/batches/000001.npz':b'synthetic persisted batch'}
        if extra_name:payloads[extra_name]=b'synthetic scratch'
        for name,payload in payloads.items():
            p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(payload)
        controller.write(source/'STATUS.json',dict(technical_status='COMPLETED'))
        controller.write(source/'STAGE_RECEIPT.json',dict(technical_status='COMPLETED',scientific_status='C4_ENCODING_COMPLETE',
            outputs={n:digest(b) for n,b in payloads.items()}))
        return source,payloads

    def test_result_keeps_all_pinned_batches_without_large_scratch(self):
        source,payloads=self.make_result();path=self.control.result_archive()
        with tarfile.open(path,'r:') as ar:
            self.assertEqual(set(ar.getnames()),set(payloads)|{'STATUS.json','STAGE_RECEIPT.json'})
        self.assertLess(path.stat().st_size,512*2**20)

    def test_result_rejects_pinned_raw_scratch_instead_of_silently_dropping_it(self):
        self.make_result(extra_name='history/NETATMO/candidates.sqlite')
        with self.assertRaisesRegex(ValueError,'REPLAY_SCRATCH'):self.control.result_archive()
        self.assertFalse((self.here/'result.tar').exists())

    def test_tampered_pinned_output_is_not_exported(self):
        source,payloads=self.make_result();(source/'history/NETATMO/encoded/references.npz').write_bytes(b'mutated')
        with self.assertRaisesRegex(ValueError,'OUTPUT_PIN'):self.control.result_archive()


if __name__=='__main__':unittest.main(verbosity=2)
