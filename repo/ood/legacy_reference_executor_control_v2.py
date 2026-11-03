"""Versioned Windows venv-launcher quota fix; original scientific worker unchanged."""
from __future__ import annotations
import argparse,ctypes,os,sys
from pathlib import Path
import legacy_reference_executor_common_v1 as c
import legacy_reference_executor_control_v1 as base
import issue27frontend_inheritance_outer_control_v1 as jobs
OriginalJob=jobs.Job
PATCH=c.ROOT/'runs/legacy_reference_executor_launch_fix_v2_20260917'
class Job(OriginalJob):
    def __init__(self,process,limit):
        runtime=c.recipe()['runtime'];python=Path(process.args[0]).resolve()
        encoder=python==Path(runtime['encoder_python']).resolve()
        c.require(encoder or python==Path(runtime['training_python']).resolve(),'UNREVIEWED_PYTHON_LAUNCHER')
        super().__init__(process,limit)
        try:
            info=self.Extended()
            c.require(self.kernel.QueryInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info),None),'JOB_QUERY')
            original=int(info.BasicLimitInformation.ActiveProcessLimit)
            c.require(original==2,'ORIGINAL_JOB_SLOT_DRIFT')
            info.BasicLimitInformation.ActiveProcessLimit=3 if encoder else 2
            c.require(self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)),'JOB_LAUNCHER_ALLOWANCE')
            self.process_limit=3 if encoder else 2
            if '--request' in process.args:
                request=Path(process.args[process.args.index('--request')+1])
                c.atomic_json(request.with_suffix('.job_limits.json'),dict(active_process_limit=self.process_limit,
                    job_memory_bytes=int(info.JobMemoryLimit),process_memory_bytes=int(info.ProcessMemoryLimit),
                    flags=int(info.BasicLimitInformation.LimitFlags),venv_launcher_allowance=encoder,
                    model_workers=1,decoder_workers=1,
                    explanation='One extra process slot only for the pinned Windows venv redirector; no extra model or decoder worker.'))
        except BaseException:
            self.close();raise
def verify_patch():
    c.verify_seal(PATCH);a=c.load(PATCH/'acceptance.json')
    c.require(a['status']=='PASS' and a['real_model_forwards']==a['real_optimizer_steps']==0,'PATCH_ACCEPTANCE')
    for path,h in c.load(PATCH/'code_pins.json').items():c.pin(c.ROOT/path,h)
def install():jobs.Job=Job
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['validate','run']);p.add_argument('--scope',required=True);p.add_argument('--authorize-chain',action='store_true');a=p.parse_args()
    verify_patch()
    scope=c.load(a.scope)
    c.require(scope.get('launch_fix_version')=='windows-venv-process-slot-v2','PATCH_SCOPE_VERSION')
    if a.command=='validate':
        c.authorize(a.scope,a.authorize_chain);print('AUTHORIZED_SCOPE_AND_LAUNCH_FIX_VALID')
    else:
        install();base.run_chain(a.scope,a.authorize_chain)
if __name__=='__main__':main()

