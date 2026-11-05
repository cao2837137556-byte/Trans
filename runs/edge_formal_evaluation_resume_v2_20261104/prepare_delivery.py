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
    parent=CODE/'FORMAL_EXECUTION_CARD_DRAFT.json'
    prior_gate=ROOT/'runs/edge_formal_gate_resume_v4_20261104'
    verified=read(prior_gate/'VERIFIED_ACCEPTANCE.json')
    assert verified['status']=='PASS_VERIFIED_ENGINEERING_ACCEPTANCE'
    candidate=prior_gate/'retrieved/outputs/gate_181905/engineering_attempts/41c1896f2008410eaa8f8ebc230b51f6/CANDIDATE.json'
    assert sha(candidate)=='474c97b36b9f55513089dc0a98b9422d9488426777da94fd66b83779b69fa55f'
    import sys
    from collections import Counter
    sys.path.insert(0,str(CODE))
    from budget import encoding_scenario,measured_rates
    census=ROOT/'runs/edge_query_selection_v1_20261103/shapes_v2/SHAPE_CENSUS.json'
    counts=Counter()
    for role in read(census)['roles'].values(): counts.update(role['target_shape_counts'])
    estimate=encoding_scenario(counts,measured_rates(read(candidate)['throughput']))
    assert estimate['logical_rows']==64124 and estimate['batches']==4046 and estimate['unmeasured_shape_rows']==0
    write(HERE/'BUDGET_EVIDENCE.json',dict(status='MEASURED_SCENARIO_NOT_GUARANTEED_BOUND',encoding=estimate,
        engineering_candidate_sha256=sha(candidate),shape_census_sha256=sha(census),
        encoding_slowdown_factor=2.5,encoding_conservative_seconds=estimate['estimated_seconds']*2.5,
        wall_limit_seconds=86400,cpu=1,memory_gib=8,reporting_and_io_margin_included_in_wall_limit=True))
    quote='修复后重交'
    card=read(parent)
    for key in ('complete_role_adoption','replay_checkpoint_source'):card.pop(key,None)
    card.update(status='FROZEN_ENGINEERING_READY_FOR_AUTHORIZATION',execution_card_frozen=True,execution_ready=True,
        formal_external_evaluation_authorized=True,blockers=[],full_streaming_resume_worker='PASS_VALIDATED')
    card['budget'].update(cpu=1,rss_bytes=8*1024**3,disk_bytes=24*1024**3,scratch_bytes=24*1024**3,wall_seconds=86400)
    card['formal_worker_linux_recovery']=dict(status='PASS',job_id='181905',evidence_sha256=sha(prior_gate/'VERIFIED_ACCEPTANCE.json'))
    card['same_runtime_preflight'].update(status='REAL_SLICE_E2E_PASS',runtime_identity=card['runtime_identity'],
        prior_job_id='181902',wall_seconds=1800,fresh_formal_preflight_required=True)
    card['independent_review']=dict(status='USER_DIRECTED_EXECUTION_WITHOUT_NEW_INDEPENDENT_REVIEW',independent_review_performed=False,
        execution_quote=quote,scope='User directly instructed execution after accepted engineering; no fabricated independent review PASS')
    card['accepted_complete_source']=dict(output='/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_gate_resume_v4_20261104/outputs/gate_181905',
        card_sha256='d990035cf7d880e68358292cc2689b96c22db05f6b3af5b4a52c55c3f5be452f',candidate_sha256=sha(candidate),roles=['NORMAL','HTTP','UDP'])
    card['checkpoint_compatibility']['default']='ACCEPTED_COMPLETE_THREE_ROLE_IMPORT_ONLY'
    card['progress_io_optimization']['integrated_linux_gate']='PASS_181905'
    card['budget_evidence']=dict(path=(HERE/'BUDGET_EVIDENCE.json').relative_to(ROOT).as_posix(),sha256=sha(HERE/'BUDGET_EVIDENCE.json'))
    previous=ROOT/'runs/edge_formal_evaluation_v1_20261104'
    pointer=previous/'retrieved/outputs/gate_181931/CURRENT_ENGINEERING_ATTEMPT.json'
    card['encoding_resume_source']=dict(output='/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_evaluation_v1_20261104/outputs/gate_181931',parent_card='runs/edge_formal_evaluation_v1_20261104/ENGINEERING_CARD.json',card_sha256=sha(previous/'ENGINEERING_CARD.json'),pointer_sha256=sha(pointer))
    runtime_names=('formal_job.py','formal_acceptance.py','runtime_control.py','real_slice_preflight.py','job_entry.py','preflight_acceptance.py','BUDGET_EVIDENCE.json','disk_scan.py','encoding_resume.py','test_race_resume.py')
    extra_paths=[HERE/n for n in runtime_names]+[prior_gate/'VERIFIED_ACCEPTANCE.json',candidate,previous/'ENGINEERING_CARD.json',pointer,previous/'FINAL_ACCEPTANCE.json']
    card['artifact_pins'].update(read(previous/'ENGINEERING_CARD.json')['artifact_pins'])
    for path in extra_paths:card['artifact_pins'][path.relative_to(ROOT).as_posix()]=sha(path)
    write(HERE/'ENGINEERING_CARD.json',card)
    auth=dict(scope='EDGE_EXTERNAL_TEST_1_FULL_EVALUATION',user_authorized=True,card_sha256=sha(HERE/'ENGINEERING_CARD.json'),
        authorization_quote=quote,time_budget_interpretation='User explicitly requested repair and resubmission; retain authorized 1CPU/8GiB/24h cap and validate/reuse committed encoding',
        real_slice_preflight_required=True,preflight_wall_seconds=1800,allowed_preflight_jobs=1,
        connection_confirmation='我已经连接了超算。继续吧',allowed_jobs=1,cpu=1,memory_gib=8,wall_seconds=86400,
        automatic_resubmit=False,automatic_extension=False,formal_external_evaluation_authorized=True,training_authorized=False)
    write(HERE/'AUTHORIZATION.json',auth)
    slurm='''#!/usr/bin/env bash
#SBATCH --job-name=edge-formal-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8192M
#SBATCH --time=1-00:00:00
#SBATCH --tmp=32768
#SBATCH --no-requeue
#SBATCH --output=gate-%j.out
#SBATCH --error=gate-%j.err
set -euo pipefail
umask 077
exec PYTHON_LITERAL -X utf8 -B ENTRY_LITERAL
'''.replace('PYTHON_LITERAL',shlex.quote(PYTHON)).replace('ENTRY_LITERAL',shlex.quote(REMOTE+'/checkout/runs/'+HERE.name+'/job_entry.py'))
    (HERE/'engineering.slurm').write_text(slurm,encoding='utf-8',newline='\n')
    (HERE/'preflight.slurm').write_text(slurm.replace('edge-formal-eval','edge-formal-preflight').replace('1-00:00:00','00:30:00').replace('gate-%j','preflight-%j').rstrip()+' --preflight\n',encoding='utf-8',newline='\n')
    prior=read(CODE/'DELIVERY_DELTA_MANIFEST.json');assert sha(ROOT/prior['archive']['path'])==prior['archive']['sha256']
    paths={name:ROOT/name for name in prior['files']}
    for name,pin in prior['files'].items():assert sha(paths[name])==pin['sha256']
    for path in [HERE/n for n in ('ENGINEERING_CARD.json','AUTHORIZATION.json','engineering.slurm','preflight.slurm')]+extra_paths:
        paths[path.relative_to(ROOT).as_posix()]=path
    # Every exact artifact pin must be in either the base or the sealed delta.
    basefiles=read(ROOT/'runs/edge_linux_preflight_package_v1_20261103/PACKAGE_MANIFEST.json')['files']
    for name,pin in card['artifact_pins'].items():
        assert sha(ROOT/name)==pin, 'ARTIFACT_CHANGED:'+name
        if name not in basefiles:paths[name]=ROOT/name
    pins={name:dict(bytes=p.stat().st_size,sha256=sha(p)) for name,p in paths.items()}
    archive=private/'delivery.tar'
    with tarfile.open(archive,'w') as tar:
        for name,p in sorted(paths.items()):
            data=p.read_bytes();info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0;tar.addfile(info,io.BytesIO(data))
    raw=read(ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/DELIVERY.json')['files']
    config=dict(files={'archive':dict(filename='delivery.tar',bytes=archive.stat().st_size,sha256=sha(archive))},
        members=pins,raw_inputs={role:{k:v for k,v in raw[role].items() if k!='path'} for role in ('NORMAL','HTTP','UDP')},
        allowed_jobs=1,allowed_preflight_jobs=1,preflight_wall_seconds=1800,cpu=1,memory_gib=8,wall_seconds=86400,card_sha256=auth['card_sha256'])
    write(HERE/'DELIVERY.json',dict(config,receiver_source_sha256=sha(HERE/'remote_receiver.py'),remote_port=18833,
        archive_local_path=str(archive),status='AUTHORIZED_PREPARED_LOCALLY_NOT_SUBMITTED'))
    token=secrets.token_hex(32)
    write(private/'connection.json',dict(token=token,socks_port=56142,remote_port=18833))
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
(here/'RECEIVER_PID.json').write_text(json.dumps({'pid':child.pid,'port':18833}))
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
