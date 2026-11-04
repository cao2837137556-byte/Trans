"""R1-R4 regression: real processes/files; no frozen model or external scoring."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import psutil

from checkpoint import atomic_json, canonical, sha, PackedRoleSpool
import dependency_identity as dep
import engineering_gate as gate
import runtime_control as control
from test_engineering_gate import card_fixture
import worker

GIB = 1024**3
HERE = Path(__file__).resolve().parent


def budget(rss=8*GIB):
    return dict(rss_bytes=rss, disk_bytes=GIB, scratch_bytes=GIB)


def fixture_attempt(root, card='a'*64):
    scratch = root/'scratch'; scratch.mkdir(exist_ok=True)
    attempt = control.Attempt(root/'output', card)
    attempt.allocate_scratch(scratch)
    return attempt


def command(attempt, mode):
    return [sys.executable, '-B', str(HERE/'test_repairs.py'), '--child',
            str(attempt.output), attempt.id, attempt.card_sha, mode]


def live(pid):
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def child(output, attempt_id, card_sha, mode):
    directory = control.attempt_directory(output, attempt_id)
    scratch = control.child_scratch(output, attempt_id, 'main', card_sha)
    (scratch/'numerical.db').write_bytes(b'owned temporary database')
    atomic_json(directory/'PID.json', dict(pid=os.getpid()))
    if mode == 'memory':
        memory = bytearray(64*1024**2)
        atomic_json(directory/'CHILD_MEMORY.json', dict(pid=os.getpid(), rss=psutil.Process().memory_info().rss))
        time.sleep(40)
        return len(memory)
    if mode == 'timeout_tree':
        script = ("import os,time,json,pathlib; "
                  "pathlib.Path(%r).write_text(json.dumps({'pid':os.getpid()})); time.sleep(40)" %
                  str(directory/'GRANDCHILD.json'))
        subprocess.Popen([sys.executable, '-B', '-c', script])
        time.sleep(40)
        return
    if mode == 'prepare_fail':
        raise RuntimeError('INJECTED_PREPARATION_FAILURE')
    atomic_json(directory/'CANDIDATE.json', dict(status='CANDIDATE_SUCCESS',
        attempt_id=attempt_id, card_sha256=card_sha, fixture='NO_MODEL'))
    if mode == 'fail_after_candidate':
        raise RuntimeError('INJECTED_POST_CANDIDATE_FAILURE')


class DependencyRepairTests(unittest.TestCase):
    def test_unlisted_transitive_edit_or_new_shadow_module_is_rejected(self):
        for change in ('edit', 'add', 'delete'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); card, auth, value=card_fixture(root)
                source=root/'repo/ood/fixture.py'
                if change == 'edit': source.write_text('fixture = 2\n')
                elif change == 'add': (source.parent/'shadow.py').write_text('new = 1\n')
                else: source.unlink()
                with self.assertRaisesRegex(ValueError, 'SOURCE_TREE_CHANGED|SOURCE_INVENTORY'):
                    gate.require_engineering_authorization(card, auth, root)

    def test_full_base_member_is_mandatory_in_both_pin_sets(self):
        for field in ('artifact_pins', 'scientific_input_artifact_pins'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); _, _, value=card_fixture(root)
                del value[field]['artifact.py']
                with self.assertRaisesRegex(ValueError, 'DEPENDENCY_NOT_BOUND:artifact.py'):
                    dep.verify(value, root)

    def test_base_bytes_and_manifest_changes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); _, _, value=card_fixture(root)
            p=root/'artifact.py'; original=p.read_bytes()
            p.write_bytes(b'x'*len(original))
            with self.assertRaisesRegex(ValueError, 'DEPENDENCY_FILE_CHANGED'):
                dep.verify(value, root)
            p.write_bytes(original)
            (root/dep.BASE).write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'BASE_MANIFEST_SHA'):
                dep.verify(value, root)

    def test_envelope_cannot_be_omitted_or_remove_an_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); _, _, value=card_fixture(root)
            envelope=value.pop('dependency_envelope')
            with self.assertRaisesRegex(ValueError, 'DEPENDENCY_ENVELOPE_REQUIRED'):
                dep.verify(value, root)
            value['dependency_envelope']=envelope
            del envelope['source_inventories']['repo/ood']
            with self.assertRaisesRegex(ValueError, 'DEPENDENCY_INVENTORY_ROOTS'):
                dep.verify(value, root)

    def test_prepare_inputs_checks_dependencies_before_cached_spool_access(self):
        with patch('dependency_identity.verify', side_effect=ValueError('DEPENDENCY_CHANGED')), \
             patch.object(worker, 'selection_inputs', side_effect=AssertionError('CACHE_MUST_NOT_OPEN')):
            with self.assertRaisesRegex(ValueError, 'DEPENDENCY_CHANGED'):
                worker.prepare_inputs({}, {}, '.', '.', None, {})

    def test_v1_binding_and_changed_envelope_cannot_reuse_v2_spool(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); _, _, card=card_fixture(root)
            source=dict(raw_inputs={r:dict(bytes=1,sha256=r) for r in ('NORMAL','HTTP','UDP')})
            binding=worker.input_binding(card, dict(runtime='fixture'), source)
            uids=['fixture-uid']
            spool=PackedRoleSpool(root/'spool', binding, 'NORMAL', uids)
            spool.append(dict(uid=uids[0],row=dict(uid=uids[0],protocol=6),q14=[0.]*14,
                              body=dict(flow=dict(protocol=6,counts=[1]))))
            spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
            self.assertTrue(PackedRoleSpool(root/'spool', binding, 'NORMAL', uids).is_complete())
            old=dict(binding, schema='EDGE_SCIENTIFIC_INPUT_BINDING_V1');old.pop('dependency_envelope')
            altered=copy.deepcopy(binding);altered['dependency_envelope']['schema']='DIFFERENT'
            for changed in (old, altered):
                with self.assertRaises(ValueError):
                    PackedRoleSpool(root/'spool', changed, 'NORMAL', uids).is_complete()


class SupervisorRepairTests(unittest.TestCase):
    def test_whole_job_memory_includes_retained_parent_while_waiting(self):
        retained = bytearray(64*1024**2)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); attempt=fixture_attempt(root)
            parent_rss=psutil.Process().memory_info().rss
            limit=parent_rss+40*1024**2
            try:
                with self.assertRaisesRegex(ValueError, 'WHOLE_JOB_RSS_BUDGET_STOP'):
                    gate.supervise(attempt, command(attempt,'memory'), time.monotonic()+20, budget(limit))
                receipt=control.current_status(attempt.output)
                self.assertEqual(receipt['status'],'STOP')
                self.assertGreater(receipt['resources']['max_tree_rss_bytes'],limit)
                measured=receipt['resources']['peak_rss_processes']
                self.assertGreaterEqual(len(measured),2)
                self.assertTrue(all(p['rss_bytes']<limit for p in measured))
                self.assertTrue(all(not live(p['pid']) for p in measured if p['pid']!=os.getpid()))
                self.assertTrue(receipt['scratch_cleanup']['complete'])
                self.assertFalse(any((root/'scratch').iterdir()))
            finally: attempt.close()
        self.assertEqual(len(retained),64*1024**2)

    def test_pass_then_preparation_failure_then_pass_has_one_current_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ids=[]
            for mode, status in (('success','PASS'),('prepare_fail','STOP'),('success','PASS')):
                attempt=fixture_attempt(root);ids.append(attempt.id)
                try:
                    if status == 'PASS':
                        gate.supervise(attempt,command(attempt,mode),time.monotonic()+20,budget())
                    else:
                        with self.assertRaisesRegex(ValueError,'WORKER_FAILED'):
                            gate.supervise(attempt,command(attempt,mode),time.monotonic()+20,budget())
                    receipt=control.current_status(attempt.output,attempt_id=attempt.id,card_sha256=attempt.card_sha)
                    self.assertEqual(receipt['status'],status)
                    self.assertEqual(control.read(attempt.output/'PROGRESS.json')['attempt_id'],attempt.id)
                    self.assertEqual(control.read(attempt.output/'ENGINEERING_GATE_RECEIPT.json')['status'],status)
                finally:attempt.close()
            self.assertEqual(len(set(ids)),3)
            self.assertTrue((control.attempt_directory(root/'output',ids[0])/'PASS.json').is_file())
            with self.assertRaisesRegex(ValueError,'CURRENT_ATTEMPT_MISMATCH'):
                control.current_status(root/'output',attempt_id=ids[0])

    def test_child_candidate_then_failure_never_publishes_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt=fixture_attempt(Path(temp))
            try:
                with self.assertRaisesRegex(ValueError,'WORKER_FAILED'):
                    gate.supervise(attempt,command(attempt,'fail_after_candidate'),time.monotonic()+20,budget())
                self.assertEqual(control.current_status(attempt.output)['status'],'STOP')
                self.assertTrue((attempt.directory/'CANDIDATE.json').exists())
                self.assertFalse((attempt.directory/'PASS.json').exists())
            finally:attempt.close()

    def test_final_progress_failure_leaves_stop_authoritative(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt=fixture_attempt(Path(temp)); real=control.atomic_json
            def fail_pass_progress(path,value):
                if Path(path).name=='PROGRESS.json' and value.get('status')=='PASS':
                    raise OSError('INJECTED_PROGRESS_FAILURE')
                return real(path,value)
            try:
                with patch.object(control,'atomic_json',side_effect=fail_pass_progress):
                    with self.assertRaisesRegex(OSError,'INJECTED_PROGRESS_FAILURE'):
                        gate.supervise(attempt,command(attempt,'success'),time.monotonic()+20,budget())
                self.assertEqual(control.current_status(attempt.output)['status'],'STOP')
            finally:attempt.close()

    def test_startup_rejection_invalidates_old_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);attempt=fixture_attempt(root)
            try:gate.supervise(attempt,command(attempt,'success'),time.monotonic()+20,budget())
            finally:attempt.close()
            draft=root/'DRAFT.json';atomic_json(draft,dict(status='DRAFT'))
            with self.assertRaisesRegex(ValueError,'CARD_NOT_READY'):
                gate.run(draft,root/'missing-auth',root/'missing-runtime',root/'output')
            status=control.current_status(root/'output')
            self.assertEqual(status['status'],'STOP');self.assertNotEqual(status['attempt_id'],attempt.id)
            self.assertEqual(status['card_sha256'],sha(draft))

    def test_output_lock_blocks_concurrent_attempt_without_overwriting_current(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt=fixture_attempt(Path(temp))
            try:
                original=(attempt.output/control.CURRENT).read_bytes()
                with self.assertRaisesRegex(ValueError,'ALREADY_ACTIVE'):
                    control.Attempt(attempt.output,'b'*64)
                self.assertEqual((attempt.output/control.CURRENT).read_bytes(),original)
            finally:attempt.cleanup();attempt.close()
            next_attempt=control.Attempt(attempt.output,'b'*64);next_attempt.close()

    def test_missing_card_also_invalidates_old_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);attempt=fixture_attempt(root)
            try:gate.supervise(attempt,command(attempt,'success'),time.monotonic()+20,budget())
            finally:attempt.close()
            with self.assertRaises(FileNotFoundError):
                gate.run(root/'missing-card',root/'auth',root/'runtime',root/'output')
            value=control.current_status(root/'output')
            self.assertEqual(value['status'],'STOP')
            self.assertNotEqual(value['attempt_id'],attempt.id)
            self.assertIsNone(value['card_sha256'])

    def test_published_candidate_tamper_invalidates_current_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt=fixture_attempt(Path(temp))
            try:
                gate.supervise(attempt,command(attempt,'success'),time.monotonic()+20,budget())
                (attempt.directory/'CANDIDATE.json').write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError,'CURRENT_CANDIDATE_IDENTITY'):
                    control.current_status(attempt.output)
            finally:attempt.close()

    def test_receipt_tampering_and_wrong_card_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt=fixture_attempt(Path(temp))
            try:
                with self.assertRaisesRegex(ValueError,'CURRENT_CARD_MISMATCH'):
                    control.current_status(attempt.output,card_sha256='b'*64)
                (attempt.directory/'RUNNING.json').write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError,'CURRENT_RECEIPT_IDENTITY'):
                    control.current_status(attempt.output)
            finally:attempt.cleanup();attempt.close()

    def test_main_deadline_kills_descendants_and_cleans_only_owned_scratch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);attempt=fixture_attempt(root)
            unrelated=root/'scratch/edge-gate-owned-unrelated';unrelated.mkdir()
            (unrelated/'keep.db').write_bytes(b'untouched')
            spool=attempt.output/'spools/NORMAL';spool.mkdir(parents=True)
            (spool/'committed').write_bytes(b'keep durable spool')
            try:
                with self.assertRaisesRegex(ValueError,'HARD_DEADLINE'):
                    gate.supervise(attempt,command(attempt,'timeout_tree'),time.monotonic()+5.5,budget())
                receipt=control.current_status(attempt.output)
                self.assertEqual(receipt['status'],'STOP')
                self.assertTrue(receipt['scratch_cleanup']['complete'])
                self.assertEqual(set((root/'scratch').iterdir()),{unrelated})
                self.assertEqual((spool/'committed').read_bytes(),b'keep durable spool')
                for name in ('PID.json','GRANDCHILD.json'):
                    self.assertFalse(live(control.read(attempt.directory/name)['pid']))
            finally:attempt.close()

    def test_child_never_started_still_has_supervisor_owned_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);attempt=fixture_attempt(root)
            try:
                with self.assertRaises(FileNotFoundError):
                    gate.supervise(attempt,[str(root/'nonexistent-executable')],time.monotonic()+20,budget())
                self.assertFalse(any((root/'scratch').iterdir()))
                self.assertEqual(control.current_status(attempt.output)['status'],'STOP')
            finally:attempt.close()

    def test_unconfirmed_process_exit_preserves_scratch_and_reports_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);attempt=fixture_attempt(root)
            try:
                with patch.object(gate,'bounded_process',side_effect=control.ProcessesNotStopped('fixture')):
                    with self.assertRaises(control.ProcessesNotStopped):
                        gate.supervise(attempt,[],time.monotonic()+20,budget())
                value=control.current_status(attempt.output)
                self.assertEqual(value['status'],'STOP')
                self.assertFalse(value['scratch_cleanup']['complete'])
                self.assertEqual(len(list((root/'scratch').iterdir())),3)
            finally:attempt.cleanup();attempt.close()

    def test_cleanup_refuses_wrong_marker_or_path_and_retains_evidence(self):
        for change in ('owner','path'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);attempt=fixture_attempt(root)
                original=copy.deepcopy(attempt.scratch_plan)
                main=Path(original['phases']['main']['scratch'])
                try:
                    if change=='owner':atomic_json(main/'OWNERSHIP.json',dict(pid=0))
                    else:attempt.scratch_plan['phases']['main']['scratch']=str(root)
                    with self.assertRaisesRegex(ValueError,'OWNED_SCRATCH'):
                        attempt.cleanup()
                    self.assertTrue(main.exists())
                finally:
                    attempt.scratch_plan=original
                    atomic_json(main/'OWNERSHIP.json',original['phases']['main'])
                    attempt.cleanup();attempt.close()


if __name__ == '__main__':
    if len(sys.argv)==6 and sys.argv[1]=='--child':
        child(*sys.argv[2:])
    else:
        unittest.main()
