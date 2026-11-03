"""Reproduce and fix Git wrapper failure inside the existing two-process Job.

Only Git read-only commands and generated children; no packet/model access.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import issue27frontend_expanded_eval_support_v1 as s
from issue27frontend_inheritance_outer_control_v1 import Job

PY=s.PYTHON
DIRECT=Path('C:/Program Files/Git/mingw64/bin/git.exe')
WRAPPER=Path('C:/Program Files/Git/cmd/git.exe')
OUT=s.ROOT/'runs/frontend_expanded_eval_startup_diagnosis_v2_20260910'


def child_case(executable,command):
    with tempfile.TemporaryDirectory(dir=s.ROOT/'tmp') as d:
        folder=Path(d);gate=folder/'gate';request=folder/'request.json'
        s.atomic_json(request,{'gate':str(gate),'executable':str(executable),'command':command})
        code="import json,pathlib,subprocess,sys,time; x=json.loads(pathlib.Path(sys.argv[1]).read_text()); gate=pathlib.Path(x['gate']);\nwhile not gate.exists(): time.sleep(.01)\np=subprocess.run([x['executable']]+x['command'],capture_output=True,text=True); print(json.dumps({'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})); sys.exit(p.returncode)"
        process=subprocess.Popen([str(PY),'-B','-c',code,str(request)],cwd=s.ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        job=None
        try:
            job=Job(process,512*1024**2);gate.touch();stdout,stderr=process.communicate(timeout=20)
            return {'exit':process.returncode,'child':json.loads(stdout.decode().strip()),'worker_stderr':stderr.decode()}
        finally:
            if process.poll() is None:
                if job:job.terminate()
                else:process.kill()
                process.wait(timeout=10)
            if job:job.close()


def main():
    OUT.mkdir(exist_ok=True)
    tests={
        'wrapper_under_job_reproduces':child_case(WRAPPER,['rev-parse','HEAD']),
        'direct_under_same_job_head':child_case(DIRECT,['rev-parse','HEAD']),
        'direct_under_same_job_branch':child_case(DIRECT,['branch','--show-current']),
        'direct_under_same_job_invalid_ref_fails_closed':child_case(DIRECT,['rev-parse','--verify','refs/heads/nonexistent_expanded_eval_synthetic_ref']),
    }
    s.require(tests['wrapper_under_job_reproduces']['exit']!=0 and 'error launching git' in tests['wrapper_under_job_reproduces']['child']['stderr'],'REPRODUCTION')
    s.require(tests['direct_under_same_job_head']['exit']==0 and tests['direct_under_same_job_head']['child']['stdout'].strip()==s.scope.HEAD,'DIRECT_HEAD')
    s.require(tests['direct_under_same_job_branch']['exit']==0 and tests['direct_under_same_job_branch']['child']['stdout'].strip()=='codex/exp-mainline','DIRECT_BRANCH')
    s.require(tests['direct_under_same_job_invalid_ref_fails_closed']['exit']!=0,'INVALID_REF_NOT_REJECTED')
    result={'status':'PASS','tests_run':4,'tests_passed':4,'tests':tests,
            'direct_git':{'path':str(DIRECT),'sha256':s.sha_file(DIRECT)},
            'root_cause':'cmd/git.exe is a wrapper requiring an additional process; worker+wrapper exhaust Job active-process limit2 before real Git launches.',
            'correction':'Call the pinned mingw64/bin/git.exe directly; keep active-process limit2 and all scientific rules.',
            'raw_decodes':0,'model_loads':0,'model_forwards':0,'real_retries':0}
    s.atomic_json(OUT/'git_entry_test_results.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
