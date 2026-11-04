"""Freeze the user's explicit 1CPU/8GiB/2h authorization and small delivery."""
import base64
import hashlib
import io
import json
from pathlib import Path
import secrets
import shlex
import tarfile
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CODE=ROOT/'runs/edge_formal_execution_v4_20261104'
REMOTE='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name
PYTHON='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    private=HERE/'.private';private.mkdir(exist_ok=True)
    parent=ROOT/'runs/edge_formal_gate_deployment_v4_20261104/ENGINEERING_CARD.json'
    assert sha(parent)=='a102bf35b20797971bf25803f274689631bf84f630fba532c7b1ea1d573274a3'
    card=read(parent)
    card['budget']['wall_seconds']=21600
    card['replay_checkpoint_source']='/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_gate_deployment_v4_20261104/outputs/gate_181856'
    pointer=read(ROOT/'runs/edge_formal_gate_deployment_v4_20261104/retrieved/outputs/gate_181856/replay_checkpoints/UDP/CURRENT.json')
    card['resume_plan']=dict(parent_card_sha256=sha(parent),checkpoint_pointer=pointer,expected_frame=2877608,real_restore_probe_required=True)
    card['same_runtime_preflight']['wall_seconds']=1800
    for name in ('engineering_gate.py','real_slice_preflight.py','persistent_probe.py','job_entry.py','preflight_acceptance.py'):
        card['artifact_pins'][(HERE/name).relative_to(ROOT).as_posix()]=sha(HERE/name)
    card['promotion']=dict(change='Authorized six-hour execution budget and exact stopped v4 checkpoint; scientific binding unchanged',parent_card_sha256=sha(parent))
    write(HERE/'ENGINEERING_CARD.json',card)
    auth=dict(scope='EDGE_FORMAL_WORKER_ENGINEERING_GATE',user_authorized=True,card_sha256=sha(HERE/'ENGINEERING_CARD.json'),
        authorization_quote='？又出问题了，能不能一次修好，时间不够多给点时间不行嘛？我不希望再出什么交上去，等好久看不到结果报错。', time_budget_interpretation='User authorized more time; choose bounded 6h gate and 30min real preflight, retain 1CPU/8GiB',
        review_waived=True, review_waiver_sha256=sha(CODE/'REVIEW_WAIVER.json'),
        real_slice_preflight_required=True,preflight_wall_seconds=1800,allowed_preflight_jobs=1,
        connection_confirmation='我已经连接了超算。继续吧',allowed_jobs=1,cpu=1,memory_gib=8,wall_seconds=21600,
        automatic_resubmit=False,automatic_extension=False,formal_external_evaluation_authorized=False)
    write(HERE/'AUTHORIZATION.json',auth)
    slurm='''#!/usr/bin/env bash
#SBATCH --job-name=edge-v4-gate
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8192M
#SBATCH --time=06:00:00
#SBATCH --tmp=32768
#SBATCH --no-requeue
#SBATCH --output=gate-%j.out
#SBATCH --error=gate-%j.err
set -euo pipefail
umask 077
exec PYTHON_LITERAL -X utf8 -B ENTRY_LITERAL
'''.replace('PYTHON_LITERAL',shlex.quote(PYTHON)).replace('ENTRY_LITERAL',shlex.quote(REMOTE+'/checkout/runs/'+HERE.name+'/job_entry.py'))
    (HERE/'engineering.slurm').write_text(slurm,encoding='utf-8',newline='\n')
    (HERE/'preflight.slurm').write_text(slurm.replace('edge-v4-gate','edge-v4-preflight').replace('06:00:00','00:30:00').replace('gate-%j','preflight-%j').rstrip()+' --preflight\n',encoding='utf-8',newline='\n')
    prior=read(CODE/'DELIVERY_DELTA_MANIFEST.json');assert sha(ROOT/prior['archive']['path'])==prior['archive']['sha256']
    paths={name:ROOT/name for name in prior['files']}
    for name,pin in prior['files'].items():assert sha(paths[name])==pin['sha256']
    for name in ('ENGINEERING_CARD.json','AUTHORIZATION.json','job_entry.py','engineering.slurm','preflight.slurm','preflight_acceptance.py','engineering_gate.py','real_slice_preflight.py','persistent_probe.py'):
        paths[(HERE/name).relative_to(ROOT).as_posix()]=HERE/name
    pins={name:dict(bytes=p.stat().st_size,sha256=sha(p)) for name,p in paths.items()}
    archive=private/'delivery.tar'
    with tarfile.open(archive,'w') as tar:
        for name,p in sorted(paths.items()):
            data=p.read_bytes();info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0;tar.addfile(info,io.BytesIO(data))
    raw=read(ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/DELIVERY.json')['files']
    config=dict(files={'archive':dict(filename='delivery.tar',bytes=archive.stat().st_size,sha256=sha(archive))},
        members=pins,raw_inputs={role:{k:v for k,v in raw[role].items() if k!='path'} for role in ('NORMAL','HTTP','UDP')},
        allowed_jobs=1,allowed_preflight_jobs=1,preflight_wall_seconds=1800,cpu=1,memory_gib=8,wall_seconds=21600,card_sha256=auth['card_sha256'])
    write(HERE/'DELIVERY.json',dict(config,receiver_source_sha256=sha(HERE/'remote_receiver.py'),remote_port=18829,
        archive_local_path=str(archive),status='AUTHORIZED_PREPARED_LOCALLY_NOT_SUBMITTED'))
    token=secrets.token_hex(32)
    write(private/'connection.json',dict(token=token,socks_port=56142,remote_port=18829))
    config['token']=token
    contents={'remote_receiver.py':base64.b64encode((HERE/'remote_receiver.py').read_bytes()).decode(),
              '.receiver_private.json':base64.b64encode(json.dumps(config).encode()).decode()}
    payload=base64.b64encode(zlib.compress(json.dumps(contents).encode(),9)).decode()
    bootstrap='''import base64,hashlib,json,os,pathlib,platform,subprocess,zlib
assert platform.system()=='Linux'
here=pathlib.Path(REMOTE_LITERAL)
contents=json.loads(zlib.decompress(base64.b64decode(PAYLOAD_LITERAL)))
if here.exists():
 for name,data in contents.items(): assert (here/name).read_bytes()==base64.b64decode(data),'EXISTING_BOOTSTRAP_DIFFERS'
 if (here/'RECEIVER_PID.json').exists():
  pid=json.loads((here/'RECEIVER_PID.json').read_text())['pid'];os.kill(pid,0);print('EDGE_V4_RECEIVER_ALREADY_RUNNING');raise SystemExit(0)
else: here.mkdir(mode=0o700)
for name,data in contents.items():
 if not (here/name).exists():
  with os.fdopen(os.open(here/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as out: out.write(base64.b64decode(data))
with (here/'receiver.log').open('ab') as out:
 child=subprocess.Popen([PYTHON_LITERAL,'-X','utf8','-B',str(here/'remote_receiver.py')],cwd=here,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
(here/'RECEIVER_PID.json').write_text(json.dumps({'pid':child.pid,'port':18829}))
print('EDGE_V4_RECEIVER_STARTED',flush=True)
'''.replace('REMOTE_LITERAL',repr(REMOTE)).replace('PAYLOAD_LITERAL',repr(payload)).replace('PYTHON_LITERAL',repr(PYTHON))
    compile(bootstrap,'bootstrap','exec')
    (private/'bootstrap.py').write_text(bootstrap,encoding='utf-8')
    packed=base64.b64encode(zlib.compress(bootstrap.encode(),9)).decode()
    command=shlex.quote(PYTHON)+' -X utf8 -B -c '+shlex.quote("import base64,zlib;exec(compile(zlib.decompress(base64.b64decode("+repr(packed)+")),'<edge-v4-bootstrap>','exec'))")
    (private/'RUN_IN_HPC_TERMINAL.txt').write_text(command+'\n',encoding='utf-8')
    write(HERE/'BOOTSTRAP_MANIFEST.json',dict(bootstrap_sha256=sha(private/'bootstrap.py'),receiver_sha256=sha(HERE/'remote_receiver.py'),
        command_bytes=len(command),contains_temporary_transport_token=True,private_not_for_git=True,new_jobs_submitted=0))
    print(json.dumps(dict(status='AUTHORIZED_DELIVERY_PREPARED',members=len(pins),bytes=archive.stat().st_size,
                         card_sha256=auth['card_sha256'],bootstrap_command_bytes=len(command))))


if __name__=='__main__':main()
