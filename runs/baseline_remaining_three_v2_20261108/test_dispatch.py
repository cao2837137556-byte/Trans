"""Reproduce legacy import shadowing, then exercise the actual submit wrapper."""
import importlib,inspect,json,sys,tempfile,types
from pathlib import Path
import worker as w
# w adds the frozen parent to sys.path; bootstrap adds yet more parent paths.
w.p.bootstrap()
legacy=importlib.import_module('controller')
assert Path(legacy.__file__).resolve()==w.OLD/'controller.py'
assert list(inspect.signature(legacy.submit).parameters)==['method','seconds']
try:legacy.submit('DisentAD')
except TypeError as e:assert "seconds" in str(e)
else:raise AssertionError('ORIGINAL_FAILURE_NOT_REPRODUCED')
# Import preflight by an exact path as well, so the test does not accidentally
# certify another package with the same basename.
spec=importlib.util.spec_from_file_location('dispatch_preflight',Path(__file__).with_name('preflight.py'));pre=importlib.util.module_from_spec(spec);spec.loader.exec_module(pre)
ctrl=pre.load_controller();assert ctrl is not legacy
old_here=w.p.HERE;old_run=ctrl.subprocess.run;calls=[]
with tempfile.TemporaryDirectory() as tmp:
    dest=Path(tmp)/'project/runs/dispatch';dest.mkdir(parents=True);ctrl.HERE=dest;w.p.HERE=dest
    def fake_run(args,**kw):
        assert args[:2]==['sbatch','--parsable'];body=Path(args[2]).read_text();assert str(dest/'controller.py') in body and '--gres=gpu:nvidia_geforce_rtx_4090:1' in body
        calls.append(args);return types.SimpleNamespace(returncode=0,stdout='987654\n',stderr='')
    ctrl.subprocess.run=fake_run
    try:
        r=ctrl.submit('DisentAD');assert r['job_id']=='987654';assert ctrl.submit('DisentAD')==r and len(calls)==1
    finally:ctrl.subprocess.run=old_run;w.p.HERE=old_here
out=dict(status='PASS',original_failure_reproduced=True,legacy_module=str(Path(legacy.__file__).resolve()),exact_local_module=str(Path(pre.load_controller().__file__).resolve()),submit_wrapper_exercised=True,one_submission_idempotency=True,scheduler_stub_only=True)
name='DISPATCH_REGRESSION.json' if sys.platform=='win32' else 'LINUX_DISPATCH_REGRESSION.json'
Path(__file__).with_name(name).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
