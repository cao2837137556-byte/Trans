"""Synthetic monitor, commit durability, corruption and unchanged batch tests."""
import contextlib
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

import legacy_unsw_archival_common_v1 as c
import legacy_unsw_archival_runtime_v2 as rt
import legacy_unsw_archival_runner_v2 as runner

LIMITS = dict(wall_seconds=60,memory_gib=128,disk_gib=10)


class Missing:
    def __init__(self,name,exc=FileNotFoundError): self.name,self.exc = name,exc
    def stat(self): raise self.exc('synthetic')


class FakeProcess:
    def __init__(self): self.returncode = None
    def poll(self): return self.returncode
    def kill(self): self.returncode = -9
    def wait(self,timeout=None): return self.returncode


class Embed:
    @staticmethod
    def embed_flows(translator,model,tokenizer,collator,flows,device,batch_size):
        assert device == 'cpu' and batch_size == 16
        # Batch-sensitive stand-in detects accidental changes to the frozen batch boundary.
        mean = sum(f['value'] for f in flows)/len(flows)
        return np.stack([np.arange(768,dtype=np.float32)+f['value']+mean for f in flows])


class RecoveryTests(unittest.TestCase):
    def source_fixture(self, folder, duplicate=False):
        source = folder/'source'; source.mkdir()
        c.write(source/'identity.json',dict(synthetic=True)); c.seal(source)
        (source/'job.id').write_text('176411\n')
        c.write(source/'export_manifest.json',dict(synthetic=True))
        c.write(source/'runs/real_evaluation/status.json',dict(status='STOPPED_NO_RETRY',stage='E3_FEATURES'))
        manifests = source/'runs/real_evaluation/manifests'; manifests.mkdir()
        queries = [dict(uid=str(i),label=int(i>=75763)) for i in range(148316)]
        refs = [dict(uid=str(i),label=0) for i in range(148316,148408)]
        c.save_rows(manifests/'queries.jsonl.gz',queries); c.save_rows(manifests/'references.jsonl.gz',refs)
        c.write(manifests/'manifest.json',dict(status='IDENTITIES_SEALED_BEFORE_ANY_FORWARD',queries=148316,references=92,recipe_sha256=c.RECIPE_SHA))
        c.seal(manifests)
        flows = source/'runs/real_evaluation/flows'; flows.mkdir(); shards=[]
        for shard in range(4):
            name = 'shard_%02d.jsonl.gz'%shard
            rows = [dict(uid=str(0 if duplicate and i==148407 else i),flow={}) for i in range(shard,148408,4)]
            c.save_rows(flows/name,rows); shards.append(dict(file=name,count=len(rows)))
        c.write(flows/'index.json',dict(shards=shards,total=148408,manifest_seal_sha256=c.sha(manifests/'SHA256SUMS'),immutable_causal_snapshots=True))
        c.seal(flows)
        root=folder/'recovery'; root.mkdir()
        pins = {p.relative_to(source).as_posix():dict(sha256=c.sha(p),bytes=p.stat().st_size)
                for sub in (manifests,flows) for p in sub.rglob('*') if p.is_file()}
        c.write(root/'recovery_contract.json',dict(source_root=str(source),source_package_seal_sha256=c.sha(source/'SHA256SUMS'),
            export_manifest_sha256=c.sha(source/'export_manifest.json'),input_pins=pins,
            source_identity_pins={name:c.sha(source/name) for name in ('job.id','runs/real_evaluation/status.json')}))
        return root, source

    def test_sealed_recovery_preserves_all_uids_without_old_features(self):
        class Quiet:
            def guard(self): pass
            def tick(self,*args): pass
        with tempfile.TemporaryDirectory() as tmp:
            root,source = self.source_fixture(Path(tmp))
            out=root/'runs/real_evaluation';out.mkdir(parents=True)
            recipe=dict(counts=dict(total_feature_targets=148408))
            with patch.object(c,'contracts',return_value=(recipe,None,None,None)):
                q,r=runner.recover_inputs(root,out,Quiet())
            self.assertEqual((len(q),len(r)),(148316,92))
            self.assertEqual(c.sha(out/'flows/SHA256SUMS'),c.sha(source/'runs/real_evaluation/flows/SHA256SUMS'))
            self.assertFalse(c.read(out/'recovery_receipt.json')['old_partial_features_reused'])

    def test_sealed_but_duplicate_flow_uid_rejected(self):
        class Quiet:
            def guard(self): pass
            def tick(self,*args): pass
        with tempfile.TemporaryDirectory() as tmp:
            root,source=self.source_fixture(Path(tmp),duplicate=True)
            out=root/'runs/real_evaluation';out.mkdir(parents=True)
            with patch.object(c,'contracts',return_value=(dict(counts=dict(total_feature_targets=148408)),None,None,None)):
                with self.assertRaisesRegex(RuntimeError,'RECOVERY_FLOW_UID'): runner.recover_inputs(root,out,Quiet())

    def test_changed_source_identity_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,source=self.source_fixture(Path(tmp))
            (source/'job.id').write_text('999\n')
            out=root/'runs/real_evaluation';out.mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError,'SHA_MISMATCH'): runner.recover_inputs(root,out,None)
            self.assertFalse((out/'manifests').exists())

    def test_atomic_json_temporary_can_disappear(self):
        with patch.object(Path,'rglob',return_value=iter([Missing('status.json.next')])):
            self.assertEqual(rt.disk_bytes('.'),0)

    def test_real_missing_input_still_fails(self):
        with patch.object(Path,'rglob',return_value=iter([Missing('features.npy')])):
            with self.assertRaises(FileNotFoundError): rt.disk_bytes('.')

    def test_permission_error_is_not_ignored(self):
        with patch.object(Path,'rglob',return_value=iter([Missing('status.json.next',PermissionError)])):
            with self.assertRaises(PermissionError): rt.disk_bytes('.')

    def test_single_stat_per_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'data'; p.write_bytes(b'abc')
            self.assertEqual(rt.disk_bytes(tmp),3)

    def test_first_failure_survives_secondary_error(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            progress = rt.Progress(Path(tmp)/'run',LIMITS)
            progress.record_failure(OSError('first'),'watchdog')
            progress.record_failure(RuntimeError('secondary'),'main')
            progress.stop('STOPPED_NO_RETRY','generic')
            self.assertIn('first',c.read(progress.out/'status.json')['first_failure']['exception'])
            self.assertEqual(c.read(progress.out/'first_failure.json')['origin'],'watchdog')

    def test_failed_error_file_has_stderr_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as stderr:
            progress = rt.Progress(Path(tmp)/'run',LIMITS)
            try:
                with patch.object(c,'write',side_effect=OSError('disk write failed')):
                    progress.record_failure(RuntimeError('original failure'),'watchdog')
                self.assertIn('original failure',stderr.getvalue())
                self.assertIn('FAILURE_RECORD_WRITE_ERROR',stderr.getvalue())
            finally: progress.stop('STOPPED_NO_RETRY','test')

    def test_watchdog_kill_all_preserves_cause_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            root = Path(tmp); c.write(root/'runtime_contract.json',dict(workers=4))
            progress = rt.Progress(root/'out',LIMITS)
            c.write(progress.out/'flows/index.json',dict(total=8))
            processes = []
            def spawn(*a,**kw):
                p = FakeProcess(); processes.append(p); return p
            def fail(*a):
                progress.record_failure(FileNotFoundError('original monitor failure'),'watchdog')
                for p in processes: p.kill()
            try:
                with patch.object(rt.subprocess,'Popen',side_effect=spawn), patch.object(rt.time,'sleep',side_effect=fail):
                    with self.assertRaisesRegex(RuntimeError,'original monitor failure'):
                        rt.launch_features(root,progress.out,progress)
                record = c.read(progress.out/'worker_exits.json')
                self.assertEqual(record['final'],[-9]*4)
                self.assertEqual(record['first_failure']['origin'],'watchdog')
                states = c.read(progress.out/'worker_terminal_states.json')
                self.assertTrue(all(s['effective_status']=='STOPPED_NO_RETRY' for s in states))
            finally: progress.stop('STOPPED_NO_RETRY','test')

    def test_completion_cannot_override_failure(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            progress = rt.Progress(Path(tmp)/'run',LIMITS)
            progress.record_failure(RuntimeError('limit'),'watchdog')
            try:
                with self.assertRaisesRegex(RuntimeError,'limit'): progress.stop('COMPLETE')
            finally: progress.stop('STOPPED_NO_RETRY','test')

    def test_user_stop_still_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress = rt.Progress(Path(tmp)/'run',LIMITS)
            try:
                (progress.out/'STOP_REQUESTED').touch()
                with self.assertRaisesRegex(RuntimeError,'USER_STOP'): progress.guard()
            finally: progress.stop('STOPPED_NO_RETRY','test')

    def block(self,folder):
        return rt.commit_block(folder,0,0,['a','b'],np.ones((2,768),np.float32),{'model':'synthetic'})

    def test_committed_roundtrip_and_order_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = self.block(tmp)
            values = rt.read_block(block,['a','b'],0,{'model':'synthetic'})
            self.assertTrue(np.array_equal(values,np.ones((2,768),np.float32)))
            with self.assertRaisesRegex(RuntimeError,'UID_ORDER'): rt.read_block(block,['b','a'],0,{'model':'synthetic'})

    def test_different_model_or_offset_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = self.block(tmp)
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'): rt.read_block(block,['a','b'],0,{'model':'other'})
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'): rt.read_block(block,['a','b'],2,{'model':'synthetic'})

    def test_corruption_and_extra_files_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = self.block(tmp)
            (block/'extra').touch()
            with self.assertRaisesRegex(RuntimeError,'FILE_SET'): rt.read_block(block,['a','b'],0,{'model':'synthetic'})
            (block/'extra').unlink()
            with (block/'features.npy').open('r+b') as f: f.seek(-4,os.SEEK_END); f.write(b'xxxx')
            with self.assertRaisesRegex(RuntimeError,'SHA_MISMATCH'): rt.read_block(block,['a','b'],0,{'model':'synthetic'})

    def test_interruption_before_marker_is_not_a_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            write = c.write
            def stop_before_commit(path,*a,**kw):
                if Path(path).name == 'COMMITTED.json': raise OSError('synthetic interruption')
                return write(path,*a,**kw)
            with patch.object(c,'write',side_effect=stop_before_commit):
                with self.assertRaisesRegex(OSError,'interruption'): self.block(tmp)
            with self.assertRaisesRegex(RuntimeError,'NOT_COMMITTED'):
                rt.read_block(Path(tmp)/'block_000000',['a','b'],0,{'model':'synthetic'})

    def test_committed_block_survives_abrupt_process_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = "import os,sys,numpy as np; import legacy_unsw_archival_runtime_v2 as r; r.commit_block(sys.argv[1],0,0,['a','b'],np.ones((2,768),np.float32),{'model':'synthetic'}); os._exit(7)"
            result = subprocess.run([sys.executable,'-c',code,tmp],cwd=Path(rt.__file__).parent,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,7,result.stderr)
            self.assertEqual(rt.read_block(Path(tmp)/'block_000000',['a','b'],0,{'model':'synthetic'}).shape,(2,768))

    def test_feature_worker_keeps_batch16_and_final_partial_batch(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            root = Path(tmp); out = root/'runs/real_evaluation'; out.mkdir(parents=True)
            (root/'SHA256SUMS').write_bytes(b'synthetic-package-identity')
            c.write(root/'runtime_contract.json',dict(limits=LIMITS,checkpoint_sha256=c.sha(Path(rt.__file__))))
            model = root/'vendor/netFound-base/model.safetensors'; model.parent.mkdir(parents=True)
            model.write_bytes(Path(rt.__file__).read_bytes())
            c.write(out/'launch.json',dict(recipe_sha256=c.RECIPE_SHA,scope='SEALED_INPUTS_FROZEN_RECOVERY_V2'))
            (out/'manifests').mkdir(); (out/'manifests/SHA256SUMS').write_bytes(b'')
            count = 1041
            c.write(out/'flows/index.json',dict(shards=[dict(file='flow.gz',count=count)],total=count))
            with gzip.open(out/'flows/flow.gz','wt') as f:
                for i in range(count): f.write(json.dumps(dict(uid=str(i),flow=dict(value=i)))+'\n')
            with patch.object(c,'verify',return_value=0), patch.object(rt,'e3_runtime',return_value=(Embed,None,None,None,None)), patch.object(rt.old,'tree_rss',return_value=0):
                rt.feature_worker(root,out,0,True)
            actual = np.load(out/'worker_00/features.npy',allow_pickle=False)
            expected = np.concatenate([Embed.embed_flows(None,None,None,None,[dict(value=i) for i in range(start,min(start+16,count))],'cpu',16) for start in range(0,count,16)])
            self.assertTrue(np.array_equal(actual,expected))
            self.assertEqual(c.read(out/'worker_00/status.json')['committed_rows'],count)
            c.verify(out/'worker_00')

    def test_no_real_authority_before_reads(self):
        with patch.object(c,'read',side_effect=AssertionError('read forbidden')):
            with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'): runner.execute(Path('missing'),False)
            with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'): rt.feature_worker('missing','missing',0,False)

    def test_existing_output_cannot_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'runs/real_evaluation').mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError,'NO_RETRY'): runner.execute(root,True)

    def test_export_keeps_diagnostics_omits_large_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c.write(root/'runs/real_evaluation/first_failure.json',dict(error='synthetic'))
            p = root/'runs/real_evaluation/worker_00/blocks/block_000000'
            p.mkdir(parents=True); (p/'features.npy').write_bytes(b'fake')
            c.write(p/'COMMITTED.json',dict(synthetic=True))
            runner.export(root)
            manifest = c.read(root/'export_manifest.json')
            self.assertIn('runs/real_evaluation/first_failure.json',manifest['included'])
            self.assertIn('runs/real_evaluation/worker_00/blocks/block_000000/COMMITTED.json',manifest['included'])
            self.assertIn('runs/real_evaluation/worker_00/blocks/block_000000/features.npy',manifest['omitted'])
            self.assertNotIn(b'\r',Path(str(root/'evaluation_pullback.tar.gz')+'.sha256').read_bytes())


if __name__ == '__main__': unittest.main(verbosity=2)
