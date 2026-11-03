"""Keep TShark preparation and the frozen encoder in disjoint child lifetimes."""
import gc
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
from hnr.common import PACKAGE,read,write,sha,require
from hnr.runtime import Runtime
from recovery import previous_status,reuse_member,KEYS

def launch(stage,key,runtime,cap):
    folder=runtime.output/'workers';folder.mkdir(exist_ok=True);status=folder/(key+'_'+stage+'.json')
    remaining=runtime.limits['wall_seconds']-(time.monotonic()-runtime.started)
    require(remaining>0,'TOTAL_WALL_LIMIT')
    command=[sys.executable,'-B',str(PACKAGE/'member_worker.py'),stage,'--key',key,'--status',str(status),'--wall-seconds',str(remaining),'--encoded-cap',str(cap)]
    with (folder/(key+'_'+stage+'.log')).open('x',encoding='utf-8') as log:
        p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);runtime.children.append(p);heartbeat=None
        while p.poll() is None:
            if status.exists():
                s=read(status)
                allowed={k:v for k,v in s.items() if k not in ('phase','elapsed_seconds','encoded_charged','work_heartbeat_utc','service_heartbeat_utc','limits','technical_status')}
                if s.get('work_heartbeat_utc')!=heartbeat:
                    runtime.update(s.get('phase',stage.upper()),worker_encoded_charged=s.get('encoded_charged',0),**allowed)
                    heartbeat=s.get('work_heartbeat_utc')
            runtime.guard();time.sleep(.5)
        require(p.returncode==0,'ISOLATED_'+key+'_'+stage+'_FAILED: see '+str(log.name))
    require(read(status.with_name(status.stem+'_COMPLETE.json'))['status']=='COMPLETE','WORKER_COMPLETION')
    # Reap before launching the next process, releasing model/allocator memory.
    runtime.children.remove(p)

def encode():
    import run
    card=run.verify('encode');cfg=read(PACKAGE/'config/EXECUTION.json');prior=previous_status();run.latch('encode')
    runtime=Runtime(PACKAGE/'outputs/encoding')
    runtime.limits['wall_seconds']=card['limits']['total_wall_seconds']-card['recovery']['prior_wall_seconds_charged']
    with runtime:
        write(runtime.output/'ENVIRONMENT.json',dict(system=platform.system(),python=platform.python_version(),numpy=np.__version__,encoder_environment_verified_by_preflight=True))
        write(runtime.output/'PREVIOUS_FAILURE.json',prior)
        runtime.update('RECOVERY_VALIDATION',prior_wall_seconds_charged=card['recovery']['prior_wall_seconds_charged'],reused_encoded_rows=20480,completed_devices_reused=3)
        runtime.encoded(20480);members={}
        for key in KEYS:
            members[key]=reuse_member(key,runtime.output/'history'/key)
        for spec in cfg['devices']:
            key=spec['key']
            if key in KEYS:continue
            require(shutil.disk_usage(runtime.output).free>spec['raw']['bytes']*3+2*2**30,'SCRATCH_HEADROOM')
            runtime.update('PREPARATION_PROCESS_START',device=spec['display_name'])
            launch('prepare',key,runtime,0)
            member=runtime.output/'history'/key;selection=read(member/'selection/SELECTION.json')
            n=selection['ref_rows']['rows']+selection['dev_rows']['rows'];runtime.encoded(n)
            runtime.update('ENCODING_PROCESS_START',device=spec['display_name'])
            launch('encode',key,runtime,n)
            members[key]=dict(new_references=selection['ref_rows']['rows'],new_dev=selection['dev_rows']['rows'],selection_sha256=sha(member/'selection/SELECTION.json'),encode_sha256=sha(member/'encoded/ENCODE_RESULT.json'))
            run.cleanup(member);gc.collect()
        runtime.finish(dict(status='C4_ENCODING_COMPLETE',members=members,execution_card_sha256=sha(PACKAGE/'EXECUTION_CARD.json'),model_training=0,AB_evaluations=0,old_DEV_encodings_reused=True,reused_encoded_rows=20480,prior_wall_seconds_charged=card['recovery']['prior_wall_seconds_charged'],isolated_preparation_and_encoding=True))
