"""Run only the changed delivery layer, on a fresh final-archive install."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    out = HERE / 'linux_validation'
    out.mkdir(exist_ok=False)
    build = json.loads((HERE/'build_receipt.json').read_text())
    installed = HERE / 'linux_clean_install'
    process = subprocess.run([sys.executable, str(HERE/'onboarding_install_v1.py'), 'install',
        '--archive', str(HERE/build['archive']), '--destination', str(installed)],
        text=True, capture_output=True, timeout=30)
    (out/'install.log').write_text(process.stdout+process.stderr)
    assert process.returncode == 0, process.stderr
    seal = subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=installed,
                          text=True,capture_output=True,timeout=30)
    (out/'seal.log').write_text(seal.stdout+seal.stderr)
    assert seal.returncode == 0
    assert sha(installed/'SHA256SUMS') == build['package_seal_sha256']
    os.environ['ONBOARDING_TEST_BUNDLE'] = str(installed)
    module = load(HERE/'test_submit_linux.py','onboarding_fixed_submit')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(module))
    (out/'job_tests.log').write_text(stream.getvalue())
    # A single original regression fixture confirms the reported failure.
    original = load(HERE.parent/'onboarding_configured_v1_20261017/test_submit_linux.py',
                    'onboarding_original_submit')
    fixture = original.SubmitTests()
    fixture.setUp()
    try:
        fixture.env['MOCK_MODE']='export_fail'
        prior=fixture.run_job()
        before=dict(experiment_mock='success',export_mock_exit=35,job_exit=prior.returncode,
            saved_exit=int((fixture.root/'exit_code.txt').read_text()),
            error_reported='EXPORT_FAILED' in prior.stdout)
        assert before['job_exit']==before['saved_exit']==0 and before['error_reported']
    finally:
        fixture.doCleanups()
    receipt=dict(status='PASS' if result.wasSuccessful() and not result.skipped else 'FAIL',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        original_bug_reproduced=before,
        platform=platform.platform(),python=sys.version,
        archive_sha256=sha(HERE/build['archive']),installed_seal_sha256=sha(installed/'SHA256SUMS'),
        installed_files_verified=seal.stdout.count(': OK'),tested_root=str(installed),
        logs={p.name:sha(p) for p in sorted(out.glob('*.log'))},
        scope='Local fake Python/scheduler only; no HPC/network/model/PCAP activity',
        real_experiment=False,resource_budget_recalculated=False)
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    return 0 if receipt['status']=='PASS' else 1


if __name__=='__main__': sys.exit(main())
