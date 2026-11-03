"""Disposable supervisor tests; no torch import into controller memory."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
import issue27frontend_paired_train_control_v1 as c
import issue27frontend_paired_train_support_v1 as s
import issue27frontend_paired_metadata_tests_v1 as inherited


class SingleWorkerTests(unittest.TestCase):
    def test_job_rejects_extra_process(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'attempt'
            code=('import pathlib,time,subprocess,sys,json; p=pathlib.Path('+repr(str(folder))+');\n'
                'while not (p/"worker_gate.json").exists(): time.sleep(.01)\n'
                'denied=False\n'
                'try:\n'
                ' child=subprocess.Popen([sys.executable,"-B","-c","import time; time.sleep(10)"],creationflags=subprocess.CREATE_NO_WINDOW)\n'
                ' code=child.wait(timeout=2); denied=(code!=0)\n'
                'except OSError: denied=True\n'
                '(p/"worker_terminal.json").write_text(json.dumps({"denied":denied}))')
            def validate(receipt,*args):
                s.require(receipt['denied'],'EXTRA_PROCESS_ALLOWED')
                return {'status':'SINGLE_WORKER_ENFORCED'}
            out=c.supervise([sys.executable,'-B','-c',code],folder,{'caps':dict(s.CAPS,wall_seconds=10)},True,validate)
            self.assertEqual(out['status'],'SINGLE_WORKER_ENFORCED');self.assertTrue(c.status(folder)['seal_verified'])


if __name__=='__main__':
    inherited.c,inherited.s=c,s
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SingleWorkerTests)
    names=[n for n in unittest.defaultTestLoader.getTestCaseNames(inherited.ControllerTests)
           if n not in ('test_generated_decoder_child_is_killed_with_worker','test_explicit_gate_rejects_before_readiness')]
    for name in names:suite.addTest(inherited.ControllerTests(name))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report=dict(tests_run=result.testsRun,tests_passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
                errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),
                real_feature_bytes_decoded=0,real_optimizer_steps=0,scope='generated disposable processes; standard-library controller')
    print('SYNTHETIC_RESULT '+json.dumps(report),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
