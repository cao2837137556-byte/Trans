"""Boundaries and original-wrapper integration, without decoder or model runs."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import launch_preflight as launcher
import worker as repair

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class ScratchTests(unittest.TestCase):
    def test_shared_filesystem_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'NOT_VERIFIED_LOCAL'):
                repair.validate_scratch(temporary, [], filesystem_probe=lambda p: ('lustre', '/public'))

    def test_same_device_is_rejected_even_if_named_tmp(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'SHARES_PERSISTENT_DEVICE'):
                repair.validate_scratch(temporary, [temporary],
                    filesystem_probe=lambda p: ('xfs', '/tmp'))

    def test_insufficient_space_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'LESS_THAN_2_GIB'):
                repair.validate_scratch(temporary, [], filesystem_probe=lambda p: ('ext4', '/'),
                    disk_usage=lambda p: SimpleNamespace(free=1024))

    def test_local_distinct_device_and_space_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            facts = repair.validate_scratch(temporary, [], filesystem_probe=lambda p: ('xfs', '/tmp'),
                    disk_usage=lambda p: SimpleNamespace(free=3 * 1024**3))
            self.assertEqual(facts['filesystem'], 'xfs')
            self.assertEqual(facts['required_free_bytes'], 2 * 1024**3)

    def test_cleanup_rejects_missing_ownership_marker_and_preserves_sibling(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            sibling = parent / 'user_data.txt'
            sibling.write_text('preserve', encoding='ascii')
            owned = repair.OwnedScratch(parent, {})
            owned.marker.unlink()
            with self.assertRaisesRegex(ValueError, 'REFUSE_UNOWNED'):
                owned.cleanup()
            self.assertTrue(owned.path.is_dir())
            self.assertEqual(sibling.read_text(encoding='ascii'), 'preserve')

    def test_cleanup_removes_only_owned_unique_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            sibling = parent / 'preserve'
            sibling.mkdir()
            owned = repair.OwnedScratch(parent, {})
            (owned.path / 'state.sqlite').write_bytes(b'fixture')
            owned.cleanup()
            self.assertFalse(owned.path.exists())
            self.assertTrue(sibling.is_dir())

    @unittest.skipIf(sys.platform == 'win32', 'Linux mount path interpretation')
    def test_mount_probe_uses_longest_real_mount(self):
        content = ('1 0 8:1 / / rw - ext4 /dev/root rw\n'
                   '2 1 0:10 / /public rw - lustre server:/public rw\n'
                   '3 1 8:2 / /tmp rw - xfs /dev/scratch rw\n')
        self.assertEqual(repair.filesystem_for('/tmp/test', content), ('xfs', '/tmp'))
        self.assertEqual(repair.filesystem_for('/public/project', content), ('lustre', '/public'))


class BoundaryTests(unittest.TestCase):
    def test_callback_elapsed_fields_do_not_collide_with_frozen_progress_keys(self):
        saved = []
        def save(stage, **extra):
            dict(status='RUNNING', stage=stage, elapsed_seconds=0., stages=[], **extra)
            saved.append(extra)
        with tempfile.TemporaryDirectory() as temporary:
            started = time.monotonic()
            heartbeat = repair.make_heartbeat(Path(temporary), started+1, started,
                {'progress':SimpleNamespace(save=save)}, lambda:None)
            heartbeat('DECODE', elapsed_seconds=.2, status='ACTIVE', role='NORMAL', frame=99)
            value = json.loads((Path(temporary)/'IO_HEARTBEAT.json').read_text())
            self.assertEqual(value['replay_elapsed_seconds'], .2)
            self.assertEqual(value['frame'], 99)
            self.assertEqual(saved[0]['replay']['elapsed_seconds'], .2)

    def test_supervisor_invokes_new_worker_and_keeps_compatible_output_receipts(self):
        commands = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / 'output'
            class Child:
                def __init__(self, command, **kwargs):
                    commands.append(command)
                    real = Path(command[command.index('--output')+1])
                    real.mkdir()
                    launcher.write(real/'RESULT.json', dict(status='SAME_RUNTIME_REAL_SLICE_E2E_PASS',
                        final_linux_runtime_gate_pass=True, strict_shape_probes={'status':'PASS'}))
                def wait(self, timeout):
                    return 0
                def poll(self):
                    return 0
            with patch.object(launcher, 'verify_sealed_checkout', return_value=(dict(files=863), {})), \
                 patch.object(launcher, 'pinned_execution', return_value=(root/'original.py', {})), \
                 patch.object(launcher, 'sha', return_value='pinned'), \
                 patch.object(launcher.subprocess, 'run') as identity, \
                 patch.object(launcher.subprocess, 'Popen', Child):
                result = launcher.main(['--raw-directory',str(root),'--tshark','/opt/tshark',
                    '--output',str(out),'--slice',str(root),'--frozen-root',str(root)])
            self.assertEqual(result, 0)
            command = commands[0]
            self.assertIn(str(HERE/'worker.py'), command)
            self.assertEqual(command[command.index('--frozen-root')+1], str(root))
            hard = float(command[command.index('--hard-deadline-monotonic')+1])
            cooperative = float(command[command.index('--deadline-monotonic')+1])
            self.assertAlmostEqual(hard-cooperative, 15.)
            actual = json.loads((out/'DELIVERY_RESULT.json').read_text())
            self.assertEqual(actual['status'], 'LINUX_PREFLIGHT_PASS')
            self.assertFalse(actual['full_execution_ready'])
            self.assertLessEqual(actual['deadline_contract']['child_hard_seconds'], 520.)
            self.assertLessEqual(identity.call_args.kwargs['timeout'], 45.)

    def test_verification_deadline_stops_and_writes_outer_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root/'output'
            with patch.object(launcher, 'verify_sealed_checkout',
                    side_effect=TimeoutError('DELIVERY_DEADLINE_FINAL_RECEIPT_RESERVED')):
                code = launcher.main(['--raw-directory',str(root),'--tshark','/opt/tshark',
                    '--output',str(out),'--slice',str(root),'--frozen-root',str(root)])
            self.assertEqual(code, 1)
            actual = json.loads((out/'DELIVERY_RESULT.json').read_text())
            self.assertEqual(actual['status'], 'STOPPED_NO_RETRY')
            self.assertIn('DELIVERY_DEADLINE', actual['error'])

    def test_not_started_or_missing_probes_can_never_pass(self):
        base = dict(status='SAME_RUNTIME_REAL_SLICE_E2E_PASS', final_linux_runtime_gate_pass=True)
        self.assertFalse(launcher.acceptance(0, base))
        for status in ('NOT_STARTED', 'FAIL', 'RUNNING'):
            self.assertFalse(launcher.acceptance(0, dict(base, strict_shape_probes={'status': status})))
        self.assertTrue(launcher.acceptance(0, dict(base, strict_shape_probes={'status': 'PASS'})))
        self.assertFalse(launcher.acceptance(1, dict(base, strict_shape_probes={'status': 'PASS'})))

    def test_relocated_slice_must_have_identical_pinned_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / launcher.PACKAGE_RELATIVE
            package.mkdir(parents=True)
            relocated = root / 'repair' / 'ACTIVE_SLICE_CARD.json'
            relocated.parent.mkdir()
            relocated.write_text('{"fixed":true}\n', encoding='ascii')
            digest = launcher.sha(relocated)
            entry = 'runs/original/run.py'
            contract = dict(active_slice='runs/old/SLICE_CARD.json', active_slice_sha256=digest,
                            preflight_entry=entry, total_preflight_logical_with_probes=91)
            (package / 'PACKAGE_CONTRACT.json').write_text(json.dumps(contract), encoding='ascii')
            manifest = dict(files={contract['active_slice']:dict(sha256=digest), entry:{}})
            self.assertEqual(launcher.pinned_execution(root, manifest, relocated)[0], root / entry)
            relocated.write_text('{"fixed":false}\n', encoding='ascii')
            with self.assertRaisesRegex(ValueError, 'ACTIVE_SLICE_SHA256'):
                launcher.pinned_execution(root, manifest, relocated)

    def test_already_expired_worker_writes_stop_receipt_without_scratch(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'result'
            args = SimpleNamespace(output=str(out), deadline_monotonic=time.monotonic()-1,
                                   hard_deadline_monotonic=time.monotonic()+15)
            self.assertEqual(repair.worker(args), 1)
            result = json.loads((out / 'RESULT.json').read_text())
            self.assertEqual(result['status'], 'STOPPED_NO_RETRY')
            self.assertFalse(result['final_linux_runtime_gate_pass'])
            self.assertEqual(result['strict_shape_probes']['status'], 'NOT_STARTED')
            self.assertIn('COOPERATIVE_PREFLIGHT_DEADLINE', result['error'])

    def test_per_frame_guard_checks_deadline_without_repeated_process_scans(self):
        calls = []
        class Original:
            def __init__(self, out, seconds=600):
                self.started = time.monotonic()
            def guard(self):
                calls.append(1)
        observed = {}
        progress = repair.progress_class(Original, time.monotonic()+1, observed)('.')
        for _ in range(10000):
            progress.guard()
        self.assertEqual(len(calls), 1)

    @unittest.skipUnless(hasattr(repair.signal, 'setitimer'), 'POSIX alarm only')
    def test_slow_operation_receives_cooperative_stop_before_hard_deadline(self):
        started = time.monotonic()
        with self.assertRaises(repair.DeadlineExceeded):
            with repair.alarm_deadline(started + .03):
                time.sleep(.5)
        self.assertLess(time.monotonic()-started, .4)


class OriginalWrapperTests(unittest.TestCase):
    def test_original_probe_runner_called_and_progress_proxy_is_module_local(self):
        previous_path = list(sys.path)
        original_global = importlib.util.spec_from_file_location
        try:
            probe = repair.load_probe(ROOT)
            self.assertEqual(Path(probe.__file__).resolve(),
                ROOT / 'runs/edge_query_selection_v1_20261103/run_preflight_with_probes.py')
            with tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                old = work / 'old'
                old.mkdir()
                # Replace only expensive old engine execution with a tiny fixture.
                # The actual sealed strict-probe run_worker is still called.
                (old / 'run_preflight.py').write_text(
                    'import json, time\nfrom pathlib import Path\n'
                    'class Progress:\n'
                    ' def __init__(self,out,seconds=600): self.started=time.monotonic(); self.seconds=seconds\n'
                    ' def guard(self): pass\n'
                    'def worker(args):\n'
                    ' progress=Progress(args.output)\n'
                    ' progress.guard()\n'
                    ' Path(args.output,"RESULT.json").write_text(json.dumps(dict(status="SAME_RUNTIME_REAL_SLICE_E2E_PASS",final_linux_runtime_gate_pass=True,original_worker_called=True)))\n'
                    ' return 0\n', encoding='ascii')
                probe.OLD = old
                output = work / 'output'
                output.mkdir()
                card = work / 'slice.json'
                card.write_text(json.dumps(dict(slices=[dict(frames=[1])],
                    shape_expansion={'required':{'representatives':[{'shape':[6,2,1]}]}})), encoding='ascii')
                args = SimpleNamespace(output=str(output), slice=str(card))
                observed = {}
                engine = SimpleNamespace(encode_snapshots=lambda *a: None)
                with patch.dict(sys.modules, {'engine': engine}):
                    with repair.inject_progress(probe, time.monotonic()+1, observed):
                        self.assertIs(importlib.util.spec_from_file_location, original_global)
                        self.assertEqual(probe.run_worker(args), 1)
                    self.assertIs(probe.importlib, importlib)
                result = json.loads((output / 'RESULT.json').read_text())
                self.assertTrue(result['original_worker_called'])
                self.assertEqual(result['strict_shape_probes']['status'], 'NOT_STARTED')
                self.assertEqual(result['status'], 'STOPPED_NO_RETRY')
                self.assertIn('progress', observed)
                self.assertLess(observed['progress'].seconds, 1.01)
                self.assertIs(importlib.util.spec_from_file_location, original_global)
                # The same actual wrapper must persist STOP when a slow old
                # worker reaches the cooperative deadline, before outer kill.
                fixture = old / 'run_preflight.py'
                source = fixture.read_text(encoding='ascii')
                fixture.write_text(source.replace(' progress.guard()\n',
                    ' time.sleep(.03)\n progress.guard()\n'), encoding='ascii')
                output2 = work / 'deadline_output'
                output2.mkdir()
                args.output = str(output2)
                with patch.dict(sys.modules, {'engine': engine}):
                    with repair.inject_progress(probe, time.monotonic()+.01, {}):
                        self.assertEqual(probe.run_worker(args), 1)
                stopped = json.loads((output2 / 'RESULT.json').read_text())
                self.assertEqual(stopped['status'], 'STOPPED_NO_RETRY')
                self.assertIn('COOPERATIVE_PREFLIGHT_DEADLINE', stopped['error'])
                self.assertEqual(stopped['strict_shape_probes']['status'], 'NOT_STARTED')
        finally:
            sys.path[:] = previous_path


if __name__ == '__main__':
    unittest.main(verbosity=2)
