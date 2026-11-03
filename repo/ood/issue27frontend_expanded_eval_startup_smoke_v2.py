"""Full sealed V2 readiness inside the unchanged Job; no evaluation execution."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
import issue27frontend_expanded_eval_support_v1 as s
from issue27frontend_inheritance_outer_control_v1 import Job


def main():
    out=s.ROOT/'runs/frontend_expanded_eval_v2_startup_verification_20260910'
    out.mkdir()
    with tempfile.TemporaryDirectory(dir=s.ROOT/'tmp') as d:
        gate=Path(d)/'gate'
        code="import pathlib,sys,time; gate=pathlib.Path(sys.argv[1]);\nwhile not gate.exists():time.sleep(.01)\nsys.path.insert(0,sys.argv[2]);import issue27frontend_expanded_eval_control_v2 as c;c.readiness();print('FULL_V2_READINESS_INSIDE_TWO_PROCESS_JOB_PASS')"
        process=subprocess.Popen([str(s.PYTHON),'-B','-c',code,str(gate),str(s.ROOT/'repo/ood')],cwd=s.ROOT,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        job=None
        try:
            job=Job(process,512*1024**2);gate.touch();stdout,stderr=process.communicate(timeout=60)
            s.require(process.returncode==0 and b'FULL_V2_READINESS_INSIDE_TWO_PROCESS_JOB_PASS' in stdout,stderr.decode())
        finally:
            if process.poll() is None:
                if job:job.terminate()
                else:process.kill()
                process.wait(timeout=10)
            if job:job.close()
    # Run mode must refuse an unspecified new authorization before creating a namespace.
    refused=subprocess.run([str(s.PYTHON),'-B',str(s.ROOT/'repo/ood/issue27frontend_expanded_eval_control_v2.py'),'run'],
                           cwd=s.ROOT,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=60)
    s.require(refused.returncode!=0 and 'NEW_ATTEMPT_NOT_AUTHORIZED' in refused.stderr,'AUTHORIZATION_GUARD')
    s.require(not (s.ROOT/'runs/frontend_expanded_eval_v2_20260910').exists(),'UNEXPECTED_REAL_NAMESPACE')
    for folder in (s.PACKAGE,s.REAL):
        for line in (folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
            digest,rel=line.split('  ',1);s.require(s.sha_file(folder/rel)==digest,'V1_SEAL_CHANGED')
    config=s.read_json(s.PACKAGE/'config.json')
    for rel,h in config['unrelated_tracked_sha256'].items():s.require(s.sha_file(s.ROOT/rel)==h,'UNRELATED_CHANGED')
    s.atomic_json(out/'verification.json',{'status':'PASS','full_readiness_under_original_two_process_job':True,
                  'new_attempt_without_authorization_rejected':True,'v1_input_and_failed_run_seals_unchanged':True,
                  'unrelated_tracked_unchanged':True,'stdout':stdout.decode(),'stderr':stderr.decode(),
                  'real_raw_decodes':0,'real_model_loads':0,'real_model_forwards':0,'real_retries':0})
    s.seal(out)
    print('V2 FULL STARTUP VERIFICATION PASS; NO REAL RESTART')


if __name__=='__main__':main()
