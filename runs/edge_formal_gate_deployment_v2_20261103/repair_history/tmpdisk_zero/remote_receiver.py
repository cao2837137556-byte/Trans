"""Single authorized engineering job; existing assets and authenticated tunnel."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import threading
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT/'runs/edge_linux_preflight_deployment_v1_20261103'
CODE = 'runs/edge_formal_execution_v2_20261103'
BASE = 'runs/edge_linux_preflight_package_v1_20261103/PACKAGE_MANIFEST.json'
BASE_SHA = 'f61af6ca64c629565e6914ef520c85352b65a5987e7af6d9515d1848cc4ccbd6'
OLD_RECEIVER_SHA = 'e33aae00c97ab52d8ed51a9c4650c00cea845890755f26b0ba71bf8412892a80'
assert hashlib.sha256((OLD/'remote_receiver.py').read_bytes()).hexdigest() == OLD_RECEIVER_SHA
spec = importlib.util.spec_from_file_location('_edge_gate_transport_base', OLD/'remote_receiver.py')
base = importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
read, write, sha, need = base.read, base.write, base.sha, base.need
SOURCE_SHA = sha(__file__)
TERMINAL = {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def member_path(name):
    p = PurePosixPath(name)
    need(name and not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name,
         'DELIVERY_MEMBER_PATH')
    return p


class Receiver(base.Receiver):
    def __init__(self, config, root=ROOT, runner=subprocess.run):
        self.root, self.here = Path(root), Path(root)/'runs'/HERE.name
        self.config, self.runner = config, runner
        self.lock, self.last_error = threading.RLock(), None
        self.receiver_source_sha256 = SOURCE_SHA
        self.incoming, self.outputs = self.here/'incoming', self.here/'outputs'
        self.checkout, self.raw = self.here/'checkout', Path(root)/'runs'/OLD.name/'raw'
        self.prior_checkout = Path(root)/'runs'/OLD.name/'unpacked/edge_preflight_checkout'
        need(set(config['files'])=={'archive'} and config['allowed_jobs']==1 and
             config['cpu']==1 and config['memory_gib']==8 and config['wall_seconds']==7200,
             'AUTHORIZED_RESOURCE_CONTRACT')
        for p in (self.here,self.incoming,self.outputs):p.mkdir(parents=True,exist_ok=True)
        binding={k:v for k,v in config.items() if k!='token'}
        target=self.here/'DELIVERY_BINDING.json'
        if target.exists():need(read(target)==binding,'DELIVERY_BINDING_CHANGED')
        else:write(target,binding)

    def environment(self):
        return self.shell_environment()+('export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 '
            'NUMEXPR_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES=""\n')

    def runtime_command(self, code, timeout=300):
        shell=self.environment()+'exec '+shlex.quote(base.PYTHON)+' -X utf8 -B -c '+shlex.quote(code)
        result=self.runner(['bash','-c',shell],capture_output=True,text=True,timeout=timeout)
        need(result.returncode==0,'RUNTIME_VALIDATION_FAILED:'+result.stderr[-2000:])
        return json.loads(result.stdout.strip().splitlines()[-1])

    def validate(self):
        deploy=self.checkout/'runs'/HERE.name
        code=('import sys,json;sys.path.insert(0,'+repr(str(self.checkout/CODE))+');'
              'from engineering_gate import require_engineering_authorization;'
              'from worker import runtime_identity;'
              'c=require_engineering_authorization('+repr(str(deploy/'ENGINEERING_CARD.json'))+','+
              repr(str(deploy/'AUTHORIZATION.json'))+');'
              'identity=runtime_identity('+repr(base.TSHARK)+');'
              'assert identity==c["runtime_identity"],"RUNTIME_IDENTITY";'
              'print(json.dumps(dict(status="PASS",runtime_identity=identity,artifact_pins=len(c["artifact_pins"]))))')
        return self.runtime_command(code)

    def prepare(self):
        with self.lock:
            receipt=self.here/'PREPARE_RECEIPT.json'
            if receipt.exists():return read(receipt)
            need(self.file_state('archive')['complete'],'DELTA_UPLOAD_REQUIRED')
            self.phase('VERIFY_AND_CLONE_BASE')
            manifest=self.prior_checkout/BASE
            need(sha(manifest)==BASE_SHA,'BASE_MANIFEST_IDENTITY')
            files=read(manifest)['files']
            self.checkout.mkdir(exist_ok=True)
            for name,pin in files.items():
                member_path(name);source=self.prior_checkout/name;target=self.checkout/name
                need(source.is_file() and source.stat().st_size==pin['bytes'] and sha(source)==pin['sha256'],
                     'BASE_FILE_PIN:'+name)
                target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():need(sha(target)==pin['sha256'],'EXISTING_CLONE_CHANGED:'+name)
                else:os.link(source,target)  # immutable source assets; no model duplication
            self.phase('VERIFY_AND_INSTALL_DELTA')
            with tarfile.open(self.path('archive')) as tar:
                members=tar.getmembers();pins=self.config['members']
                need(len(members)==len(pins) and {m.name for m in members}==set(pins),'DELTA_MEMBER_SET')
                for m in members:
                    member_path(m.name);need(m.isfile() and m.size==pins[m.name]['bytes'],'DELTA_MEMBER_TYPE_SIZE')
                    data=tar.extractfile(m).read();need(hashlib.sha256(data).hexdigest()==pins[m.name]['sha256'],'DELTA_MEMBER_SHA')
                    target=self.checkout/m.name;target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists():need(sha(target)==pins[m.name]['sha256'],'NO_OVERWRITE_DIFFERENT_ASSET')
                    else:
                        with target.open('xb') as out:out.write(data)
            need(shutil.disk_usage(self.here).free>=26*1024**3,'DURABLE_DISK_HEADROOM_26_GIB')
            raw={}
            for role,pin in self.config['raw_inputs'].items():
                p=self.raw/pin['filename'];need(p.is_file() and p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'RAW_PIN:'+role)
                raw[role]=str(p)
            self.phase('VERIFY_FROZEN_RUNTIME_AND_AUTHORIZATION')
            validated=self.validate()
            deploy=self.checkout/'runs'/HERE.name
            write(self.here/'RAW_PATHS.json',raw)
            slurm=deploy/'engineering.slurm'
            syntax=self.runner(['bash','-n',str(slurm)],capture_output=True,text=True,timeout=10)
            need(syntax.returncode==0,'SLURM_SYNTAX')
            command=self.environment()+'cd '+shlex.quote(str(self.here))+'\nexec sbatch --parsable --partition=amd '+shlex.quote(str(slurm))+'\n'
            wrapper=self.here/'SUBMIT_ONCE.sh';wrapper.write_text('#!/usr/bin/env bash\nset -euo pipefail\numask 077\n'+command)
            test=self.runner(['bash','-c',self.environment()+'sbatch --test-only --partition=amd '+shlex.quote(str(slurm))],
                             capture_output=True,text=True,timeout=30)
            need(test.returncode==0,'SLURM_RESOURCE_REQUEST_REJECTED:'+test.stderr[-1500:])
            value=dict(status='PREPARED_NOT_SUBMITTED',base_files=len(files),delta_members=len(pins),
                validated=validated,submit_wrapper_sha256=sha(wrapper),slurm_sha256=sha(slurm),
                raw_inputs_verified=True,shared_free_is_not_personal_quota=True,
                scheduler_test_only=dict(returncode=test.returncode,stdout=test.stdout,stderr=test.stderr),
                cpu=1,memory_gib=8,wall_seconds=7200,scratch_reservation_mib=32768,formal_external_evaluation=False)
            write(receipt,value);return value

    def submit(self):
        with self.lock:
            receipt=self.here/'SUBMIT_RECEIPT.json';intent=self.here/'SUBMIT_ATTEMPT.json'
            if receipt.exists():return read(receipt)
            need(not intent.exists(),'UNCERTAIN_SUBMISSION_NO_AUTOMATIC_RETRY')
            prepared=read(self.here/'PREPARE_RECEIPT.json');wrapper=self.here/'SUBMIT_ONCE.sh'
            need(prepared['status']=='PREPARED_NOT_SUBMITTED' and sha(wrapper)==prepared['submit_wrapper_sha256'],'SUBMISSION_BINDING')
            need(sha(self.checkout/'runs'/HERE.name/'engineering.slurm')==prepared['slurm_sha256'],'SLURM_CHANGED')
            self.validate()
            write(intent,dict(status='INTENT_PERSISTED_NO_RETRY',allowed_jobs=1,cpu=1,memory_gib=8,
                wall_seconds=7200,utc=datetime.now(timezone.utc).isoformat()))
            result=self.runner(['bash',str(wrapper)],capture_output=True,text=True,timeout=30)
            lines=result.stdout.strip().splitlines()
            need(result.returncode==0 and lines and re.fullmatch(r'\d+(;[A-Za-z0-9_.-]+)?',lines[-1]),'SBATCH_UNCERTAIN_NO_RETRY')
            job=lines[-1].split(';')[0]
            value=dict(status='SUBMITTED',job_id=job,cpu=1,memory_gib=8,wall_seconds=7200,
                automatic_resubmit=False,output_directory=str(self.outputs/('gate_'+job)),
                card_sha256=self.config['card_sha256'],utc=datetime.now(timezone.utc).isoformat())
            write(receipt,value);return value

    def state(self):
        # Read-only polling must not block on a long prepare operation's lock.
        def maybe(p):
            try:return read(p)
            except FileNotFoundError:return None
        job=maybe(self.here/'SUBMIT_RECEIPT.json')
        value=dict(receiver_source_sha256=SOURCE_SHA,namespace=HERE.name,files={'archive':self.file_state('archive')},
            job=job,prepare_receipt=maybe(self.here/'PREPARE_RECEIPT.json'),
            prepare_status=maybe(self.here/'PREPARE_STATUS.json'),last_error=self.last_error,
            submission_intent=maybe(self.here/'SUBMIT_ATTEMPT.json'),result_ready=False,status='READY')
        if job:
            output=Path(job['output_directory'])
            current=maybe(output/'CURRENT_ENGINEERING_ATTEMPT.json')
            value.update(current=current,progress=maybe(output/'PROGRESS.json'),launch_stop=maybe(output/'LAUNCH_STOP.json'))
            result=self.runner(['sacct','-j',job['job_id'],'--noheader','--parsable2',
                '--format=JobIDRaw,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem,Timelimit'],capture_output=True,text=True,timeout=10)
            value['scheduler']=dict(returncode=result.returncode,stdout=result.stdout[-12000:],stderr=result.stderr[-1000:])
            rows=[x.split('|') for x in result.stdout.splitlines()]
            primary=[x for x in rows if len(x)>=3 and x[0]==job['job_id']]
            state=primary[0][1].split()[0].rstrip('+') if len(primary)==1 else 'PENDING_ACCOUNTING'
            value.update(status=state,result_ready=state in TERMINAL)
            if current:
                value['attempt_receipt']=maybe(output/current['receipt'])
                if current['status']=='PASS':
                    value['candidate']=maybe(output/Path(current['receipt']).parent/'CANDIDATE.json')
        return value

    def results(self):
        state=self.state();need(state['result_ready'],'JOB_NOT_TERMINAL')
        output=Path(state['job']['output_directory'])
        files=[p for p in self.here.glob('*.json') if not p.name.startswith('.')]
        files += [p for p in output.glob('*.json') if p.is_file()]
        files += [p for p in (output/'engineering_attempts').rglob('*') if p.is_file() and p.suffix in ('.json','.log')]
        files += [p for p in self.here.glob('gate-'+state['job']['job_id']+'.*') if p.suffix in ('.out','.err')]
        files=sorted(set(files));need(all(not p.is_symlink() and p.stat().st_size<=8*1024**2 for p in files),'SMALL_RECEIPTS_ONLY')
        need(sum(p.stat().st_size for p in files)<32*1024**2,'RECEIPT_TOTAL_LIMIT')
        pins={p.relative_to(self.here).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}
        manifest=dict(files=pins,scheduler=state['scheduler'],job=state['job'],raw_arrays_exported=False)
        target=self.here/'results.tar'
        with tarfile.open(target.with_suffix('.part'),'w') as tar:
            for p in files:tar.add(p,arcname=p.relative_to(self.here).as_posix(),recursive=False)
            data=json.dumps(manifest,sort_keys=True).encode();info=tarfile.TarInfo('RESULT_MANIFEST.json');info.size=len(data);tar.addfile(info,io.BytesIO(data))
        target.with_suffix('.part').replace(target);return target


if __name__=='__main__':
    base.PORT=18821
    base.Receiver=Receiver
    base.main(read(HERE/'.receiver_private.json'))
