import importlib.util,sys,tempfile,types,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('seed_dispatch',HERE/'controller.py');c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)
calls=[];old=c.subprocess.run;old_here=c.p.HERE
with tempfile.TemporaryDirectory() as tmp:
    c.HERE=Path(tmp)/'p/runs/test';c.HERE.mkdir(parents=True);c.p.HERE=c.HERE
    def fake(args,**kw):
        body=Path(args[-1]).read_text();assert 'controller.py' in body and 'RTX' not in body
        calls.append(args);return types.SimpleNamespace(returncode=0,stdout=str(9000+len(calls)),stderr='')
    c.subprocess.run=fake
    try:
        ids=[c.submit('seed-'+str(s)) for s in [27,127,227]];ev=c.submit('evaluate',ids)
        assert '--dependency=afterok:9001:9002:9003' in calls[-1]
        assert c.submit('seed-27')==ids[0] and len(calls)==4
        assert '--time=7-00:00:00' in (c.HERE/'seed-27.slurm').read_text()
        assert '--time=1-00:00:00' in (c.HERE/'evaluate.slurm').read_text()
    finally:c.subprocess.run=old;c.p.HERE=old_here
previous=HERE.parent/'baseline_remaining_three_v2_20261108'
assert (HERE/'worker.py').read_bytes()==(previous/'worker.py').read_bytes()
assert (HERE/'CONFIG.json').read_bytes()==(previous/'CONFIG.json').read_bytes()
q=json.loads((previous/'TabR_QUALIFY.json').read_text());assert q['estimated_seconds']/3<604800-7200
(HERE/'LOCAL_REGRESSION.json').write_text(json.dumps(dict(status='PASS',independent_seed_jobs=3,afterok_all_three=True,idempotent_submission=True,worker_config_byte_unchanged=True,measured_per_seed_budget_pass=True,scope='scheduler stub; actual GPU evidence reused by SHA'),indent=2));print('PASS: three seed jobs, afterok evaluation, unchanged worker/config, measured budget')
