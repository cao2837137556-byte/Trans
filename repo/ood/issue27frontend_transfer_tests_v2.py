"""Regression tests for Windows sharing and the unchanged generated V1 suite."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import issue27frontend_transfer_tests_v1 as old_tests
import issue27frontend_transfer_control_v2 as control
from issue27frontend_transfer_io_v2 import read_json,original_atomic_json
from issue27frontend_transfer_build_v2 import closure

s=control.s
TEST_ROOT=s.ROOT/'tmp/task_knowledge_transfer_synthetic_v2'
TEST_ROOT.mkdir(parents=True,exist_ok=True)


class IOTests(unittest.TestCase):
    def test_original_WinError5_reproduced(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'progress.json';original_atomic_json(path,{'n':1})
            with path.open('r',encoding='utf-8'):
                with self.assertRaises(PermissionError) as caught:original_atomic_json(path,{'n':2})
            self.assertEqual(caught.exception.winerror,5)

    def test_standard_reader_can_stay_open_while_progress_appends(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'progress.json';s.atomic_json(path,{'n':1})
            with path.with_suffix('.jsonl').open('rb') as reader:
                s.atomic_json(path,{'n':2})
                self.assertEqual(json.loads(reader.readline()),{'n':1})
                self.assertEqual(read_json(path),{'n':2})

    def test_multiple_standard_readers_do_not_block_progress(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'progress.json';s.atomic_json(path,{'n':1})
            with path.open('rb') as a,path.with_suffix('.jsonl').open('rb') as b:
                for i in range(50):s.atomic_json(path,{'n':i})
                self.assertEqual(json.load(a)['format'],'append_only_progress_v2')
                self.assertEqual(json.loads(b.readline()),{'n':1})
            self.assertEqual(read_json(path),{'n':49})

    def test_concurrent_read_write_full_json_snapshots(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'progress.json';s.atomic_json(path,{'n':0,'payload':'x'*4096})
            errors=[];done=threading.Event()
            def reader():
                while not done.is_set():
                    try:
                        value=read_json(path)
                        if value['payload']!='x'*4096:raise AssertionError('torn JSON')
                    except Exception as exc:errors.append(str(exc));break
            readers=[threading.Thread(target=reader) for _ in range(3)]
            for thread in readers:thread.start()
            try:
                for i in range(250):s.atomic_json(path,{'n':i,'payload':'x'*4096})
            finally:
                done.set()
                for thread in readers:thread.join(timeout=10)
            self.assertFalse(errors,errors);self.assertEqual(read_json(path)['n'],249)

    def test_partial_last_record_is_ignored(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'progress.json';s.atomic_json(path,{'n':1})
            with path.with_suffix('.jsonl').open('ab') as f:f.write(b'{"n":')
            self.assertEqual(read_json(path),{'n':1})

    def test_malformed_complete_journal_record_raises(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'progress.json';s.atomic_json(path,{'n':1})
            with path.with_suffix('.jsonl').open('ab') as f:f.write(b'{bad}\n')
            with self.assertRaises(json.JSONDecodeError):read_json(path)

    def test_human_status_views_with_open_readers(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            out=Path(td);control.present(out,{'status':'STARTING'})
            with (out/'status.md').open('r',encoding='utf-8'),(out/'status.html').open('r',encoding='utf-8'):
                control.present(out,{'status':'TRAINING','updates':7})
            self.assertIn('7/3940',(out/'status.md').read_text(encoding='utf-8'))

    def test_json_decode_failure_is_not_hidden_or_retried(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            path=Path(td)/'progress.json';path.write_text('{bad')
            with self.assertRaises(json.JSONDecodeError):read_json(path)

    def test_missing_file_raises(self):
        with self.assertRaises(OSError):read_json(TEST_ROOT/'does-not-exist.json')

    def test_namespace_preserves_old_run_and_reuses_P(self):
        self.assertEqual(s.OUTPUTS['P'].name,'frontend_task_knowledge_transfer_p_v1_20260911')
        self.assertEqual(s.OUTPUTS['T'].name,'frontend_task_knowledge_transfer_t_v2_20260911')
        self.assertEqual(s.OUTPUTS['E'].name,'frontend_task_knowledge_transfer_e_v2_20260911')

    def test_old_authorization_does_not_start_new_attempt(self):
        with patch.object(sys,'argv',['v2','run','--stage','T','--authorization',s.TOKENS['T']]),patch.object(control.v1,'supervise') as launch:
            with self.assertRaises(s.Stop):control.main()
            launch.assert_not_called()

    def test_P_is_not_a_V2_launch_stage(self):
        with patch.object(sys,'argv',['v2','run','--stage','P']),patch('sys.stderr',io.StringIO()):
            with self.assertRaises(SystemExit):control.main()

    def test_readiness_requires_exact_P_seal(self):
        with patch.object(control,'_base_readiness',return_value={}),patch.object(s,'manifest') as verify,patch.object(s,'read_json',return_value={'status':'COMPLETE'}):
            control.readiness()
            self.assertEqual(verify.call_args.args[:2],(s.OUTPUTS['P'],control.P_SEAL))

    def test_progress_stress_under_real_supervisor_and_Job(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as td:
            out=Path(td)/'generated-stage'
            command=[str(s.PYTHON),'-B',str(Path(__file__).with_name('issue27frontend_transfer_fixture_v2.py')),'supervise',str(out)]
            value=json.loads(subprocess.check_output(command,cwd=s.ROOT,text=True,encoding='utf-8',timeout=60))
            self.assertEqual(value['status'],'COMPLETE',value)
            s.manifest(out);self.assertEqual(read_json(out/'progress.json')['updates'],499)


if __name__=='__main__':
    sys.addaudithook(old_tests.no_real_numeric)
    pins={p.relative_to(s.ROOT).as_posix():s.sha(p) for p in closure()}
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(old_tests.Tests),
                             unittest.defaultTestLoader.loadTestsFromTestCase(IOTests)])
    stream=io.StringIO();start=time.monotonic()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    print(stream.getvalue())
    s.require(pins=={p.relative_to(s.ROOT).as_posix():s.sha(p) for p in closure()},'CODE_CHANGED_DURING_TESTS')
    out=Path(sys.argv[1])
    s.atomic_json(out,dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
                          tests_passed=result.testsRun-len(result.failures)-len(result.errors),seconds=time.monotonic()-start,
                          real_model_forwards=0,real_teacher_rows=0,real_optimizer_steps=0,numeric_access_guard=True,tested_code_pins=pins))
    raise SystemExit(0 if result.wasSuccessful() else 1)
