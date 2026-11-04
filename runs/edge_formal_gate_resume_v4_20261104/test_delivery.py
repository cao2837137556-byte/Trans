import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pipeline
import remote_receiver as remote


def fixture(root,runner=None):
    config=dict(files={'archive':dict(filename='delivery.tar',bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())},
        allowed_jobs=1,allowed_preflight_jobs=1,preflight_wall_seconds=1800,cpu=1,memory_gib=8,wall_seconds=21600,members={},card_sha256='a'*64)
    return remote.Receiver(config,root=root,runner=runner or (lambda *a,**k:None))


class DeliveryTests(unittest.TestCase):
    def test_gate_never_submits_after_failed_or_unknown_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            calls=[]
            r=fixture(Path(temp),lambda *a,**k:calls.append(a))
            remote.write(r.here/'PREFLIGHT_SUBMIT_RECEIPT.json',dict(job_id='100',phase='preflight'))
            r.state=lambda:dict(job=dict(job_id='100'),result_ready=False)
            with self.assertRaisesRegex(ValueError,'PREFLIGHT_TERMINAL'):r.submit()
            self.assertEqual(calls,[])
            self.assertFalse((r.here/'SUBMIT_ATTEMPT.json').exists())

    def test_real_preflight_script_has_separate_budget_and_entry(self):
        source=(remote.HERE/'preflight.slurm').read_text()
        for field in ('--cpus-per-task=1','--mem=8192M','--time=00:30:00','--no-requeue','--preflight'):
            self.assertIn(field,source)
        self.assertNotIn('06:00:00',source)

    def test_resource_contract_cannot_expand(self):
        with tempfile.TemporaryDirectory() as temp:
            r=fixture(Path(temp));c=copy.deepcopy(r.config)
            for key,value in (('allowed_jobs',2),('cpu',2),('memory_gib',9),('wall_seconds',21601),('allowed_preflight_jobs',2),('preflight_wall_seconds',1801)):
                bad=dict(c,**{key:value})
                with self.assertRaisesRegex(ValueError,'RESOURCE_CONTRACT'):remote.Receiver(bad,root=Path(temp))

    def test_upload_requires_exact_offset_and_final_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            r=fixture(Path(temp))
            self.assertEqual(r.upload('archive',b'a',0,hashlib.sha256(b'a').hexdigest())['offset'],1)
            with self.assertRaisesRegex(ValueError,'UPLOAD_OFFSET'):r.upload('archive',b'b',0,hashlib.sha256(b'b').hexdigest())
            self.assertTrue(r.upload('archive',b'bc',1,hashlib.sha256(b'bc').hexdigest())['complete'])
            self.assertEqual(r.path('archive').read_bytes(),b'abc')

    def test_wrong_chunk_never_written(self):
        with tempfile.TemporaryDirectory() as temp:
            r=fixture(Path(temp))
            with self.assertRaisesRegex(ValueError,'CHUNK_SHA'):r.upload('archive',b'abc',0,'0'*64)
            self.assertEqual(r.file_state('archive')['offset'],0)

    def test_archive_paths_cannot_escape(self):
        for name in ('../x','/absolute','a\\x','C:/x',''):
            with self.assertRaisesRegex(ValueError,'MEMBER_PATH'):remote.member_path(name)

    def test_remote_submit_once_and_no_retry_after_ambiguous_response(self):
        for good in (True,False):
            with self.subTest(good=good),tempfile.TemporaryDirectory() as temp:
                calls=[]
                def runner(command,**kwargs):
                    calls.append(command);return subprocess.CompletedProcess(command,0 if good else 1,'123456\n' if good else '', 'fixture')
                r=fixture(Path(temp),runner);r.validate=lambda:dict(status='PASS');r.validate_site_adapter=lambda prepared,phase:None; r.accept_preflight=lambda:dict(status='PASS')
                remote.write(r.here/'PREFLIGHT_SUBMIT_RECEIPT.json',dict(job_id='123455'))
                wrapper=r.here/'SUBMIT_ONCE.sh';wrapper.write_text('fixture')
                script=r.checkout/'runs'/remote.HERE.name/'engineering.slurm';script.parent.mkdir(parents=True);script.write_text('fixture')
                remote.write(r.here/'PREPARE_RECEIPT.json',dict(status='PREPARED_NOT_SUBMITTED',submit_wrapper_sha256=remote.sha(wrapper),slurm_sha256=remote.sha(script)))
                if good:
                    self.assertEqual(r.submit()['job_id'],'123456');self.assertEqual(r.submit()['job_id'],'123456')
                else:
                    with self.assertRaisesRegex(ValueError,'SBATCH_UNCERTAIN'):r.submit()
                    with self.assertRaisesRegex(ValueError,'UNCERTAIN_SUBMISSION'):r.submit()
                self.assertEqual(len(calls),1)
                self.assertTrue((r.here/'SUBMIT_ATTEMPT.json').exists())

    def test_local_uncertain_submit_never_reposts(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(pipeline,'HERE',Path(temp)):
            calls=[]
            def action(route,**kwargs):
                calls.append(route)
                if route=='state':return {'preflight_job':None}
                raise OSError('lost response')
            with self.assertRaisesRegex(RuntimeError,'OUTCOME_UNKNOWN'):pipeline.submit_once(action)
            with self.assertRaisesRegex(ValueError,'UNCERTAIN'):pipeline.submit_once(action)
            self.assertEqual(calls.count('submit'),1)

    def test_confirmed_remote_receipt_reconciles_lost_response(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(pipeline,'HERE',Path(temp)):
            calls=[]
            def action(route,**kwargs):
                calls.append(route)
                if route=='submit':raise OSError('lost response')
                return {'preflight_job':None if len(calls)==1 else {'job_id':'123456','phase':'preflight'}}
            self.assertEqual(pipeline.submit_once(action)['job_id'],'123456')
            self.assertEqual(pipeline.submit_once(action)['job_id'],'123456')
            self.assertEqual(calls.count('submit'),1)

    def test_promotion_preserves_scientific_pins_and_budget(self):
        card=remote.read(remote.HERE/'ENGINEERING_CARD.json')
        original=remote.read(pipeline.ROOT/'runs/edge_formal_execution_v4_20261104/ENGINEERING_GATE_CARD_DRAFT.json')
        for key in ('scientific_input_artifact_pins','dependency_envelope','runtime_identity'):
            self.assertEqual(card[key],original[key])
        self.assertEqual(card['budget']['wall_seconds'],21600)
        self.assertEqual(remote.read(remote.HERE/'AUTHORIZATION.json')['card_sha256'],remote.sha(remote.HERE/'ENGINEERING_CARD.json'))

    def test_tmpdisk_adapter_changes_only_one_unsupported_directive(self):
        source=(remote.HERE/'engineering.slurm').read_bytes()
        adapted=remote.without_unconfigured_tmpdisk(source)
        self.assertEqual(source.replace(b'#SBATCH --tmp=32768\n',b''),adapted)
        for field in (b'--cpus-per-task=1',b'--mem=8192M',b'--time=06:00:00',b'--no-requeue'):
            self.assertIn(field,adapted)
        with self.assertRaisesRegex(ValueError,'EXACT_TMPDISK'):remote.without_unconfigured_tmpdisk(adapted)

    def test_site_adapter_identity_rejects_memory_or_time_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            def runner(command,**kwargs):return subprocess.CompletedProcess(command,0,'0\n','')
            r=fixture(Path(temp),runner)
            original=r.checkout/'runs'/remote.HERE.name/'engineering.slurm';original.parent.mkdir(parents=True)
            original.write_bytes((remote.HERE/'engineering.slurm').read_bytes())
            adapter=r.site_adapter(original);prepared={'site_adapter':adapter}
            r.validate_site_adapter(prepared)
            target=Path(adapter['path']);target.write_bytes(target.read_bytes().replace(b'8192M',b'16384M'))
            with self.assertRaisesRegex(ValueError,'SITE_ADAPTER_IDENTITY'):r.validate_site_adapter(prepared)


if __name__=='__main__':unittest.main()
