"""Bounded validation only. This does not invoke run_chain or production fit."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
START=time.monotonic()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',
         MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
results=[]
for name,command in (
    ('original_tests',[sys.executable,'-B','-m','unittest','discover','-s',
        str(HERE/'staging/runs/learned_onboarding_v1_20261023/tests'),'-v']),
    ('numeric_tests',[sys.executable,'-B',str(HERE/'test_numeric_revision.py')]),
    ('source_forward',[sys.executable,'-B',str(HERE/'validate_source.py')])):
    log=HERE/(name+'.log')
    tick=time.monotonic()
    with log.open('x') as stream:
        process=subprocess.run(command,cwd=HERE,env=env,stdout=stream,stderr=subprocess.STDOUT)
    row=dict(stage=name,returncode=process.returncode,elapsed_seconds=time.monotonic()-tick,
             log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    results.append(row)
    print(json.dumps(row),flush=True)
    if process.returncode:
        break
passed=len(results)==3 and all(row['returncode']==0 for row in results)
with (HERE/'VALIDATION_RECEIPT.json').open('x') as stream:
    json.dump(dict(schema='paper04-numeric-revision-validation-run-v3',
        status='PASS_VALIDATION_ONLY' if passed else 'VALIDATION_EXCEPTION_STOP',
        production_training_started=False,experiment_resumed=False,automatic_retry=False,
        target_queries_read=0,results=results,elapsed_seconds=time.monotonic()-START),stream,indent=2)
sys.exit(0 if passed else 1)
