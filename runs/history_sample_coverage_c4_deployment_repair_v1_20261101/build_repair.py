"""Restore original configuration order before the first C4 scientific run."""
import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import sys
import tarfile
import zlib

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'history_sample_coverage_c4_deployment_20261101'
PACKAGE=HERE.parent/'history_sample_coverage_c4_execution_v1_20261101'
ROOT=HERE.parents[1]
REMOTE='/public/home/jiangxinwei.zr/work/paper04'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def once_replace(s,a,b):
    assert s.count(a)==1,repr(a)
    return s.replace(a,b)

def main():
    assert not (HERE/'REPAIR_MANIFEST.json').exists()
    sys.path.insert(0,str(OLD));sys.path.insert(0,str(PACKAGE))
    from run import semantic,verify
    from hnr.common import digest
    from build_delivery import relocate
    card=verify('evaluate');local=read(PACKAGE/'config/EXECUTION.json')
    ordered=relocate(local,Path(local['devices'][0]['raw']['path']).parent.parent)
    with tarfile.open(OLD/'bundle.tar') as ar:shipped=ar.extractfile('config/EXECUTION.json').read()
    assert ordered==json.loads(shipped)
    assert digest(semantic(json.loads(shipped)))!=card['config_semantic_sha256']
    assert digest(semantic(ordered))==card['config_semantic_sha256']
    payload=(json.dumps(ordered,indent=2)+'\n').encode()
    (HERE/'REMOTE_EXECUTION.json').write_bytes(payload)
    old_manifest=read(OLD/'DELIVERY_MANIFEST.json')
    assert hashlib.sha256(shipped).hexdigest()==old_manifest['files']['config/EXECUTION.json']['sha256']
    repair=dict(before_sha256=hashlib.sha256(shipped).hexdigest(),after_sha256=hashlib.sha256(payload).hexdigest(),
        payload_b64=base64.b64encode(payload).decode(),execution_card_sha256=sha(PACKAGE/'EXECUTION_CARD.json'))
    receiver=(OLD/'receiver.py').read_text(encoding='utf-8')
    receiver=once_replace(receiver,"DEPLOY=ROOT/'runs/history_sample_coverage_c4_deployment_20261101'","DEPLOY=ROOT/'runs/"+HERE.name+"'")
    receiver=receiver.replace('18796','18798').replace('C4_DELIVERY_READY','C4_REPAIR_READY')
    marker="    state=dict(status='READY',submitted=False,candidate='C4_HISTORY_SAMPLE_COVERAGE_TOPUP');lock=threading.Lock()"
    replacement="    repair_receipt=repair_configuration(config['repair'])\n    state=dict(status='INSTALLED',submitted=False,candidate='C4_HISTORY_SAMPLE_COVERAGE_TOPUP',repair=repair_receipt);lock=threading.Lock()"
    receiver=once_replace(receiver,marker,replacement)
    receiver=once_replace(receiver,"if index=='code':return DEPLOY/'bundle.tar',config['bundle']","if index=='code':return ROOT/'runs/history_sample_coverage_c4_deployment_20261101/bundle.tar',config['bundle']")
    # This controlled repair is permitted only before any encode/submission latch.
    helper='''
def repair_configuration(spec):
    import base64
    previous=ROOT/'runs/history_sample_coverage_c4_deployment_20261101'
    state=read(previous/'STATE.json')
    need(state['status']=='PREFLIGHT_FAIL' and state['submitted'] is False,'ONLY_PRE_SUBMISSION_FAILURE')
    need('CONFIG_SEMANTICS' in state['preflight']['tail'],'EXPECTED_FAILURE')
    need(not (previous/'SUBMIT_ATTEMPT.json').exists() and not (PACKAGE/'ENCODE_ATTEMPT.json').exists() and not (PACKAGE/'outputs').exists(),'NO_SCIENCE_OR_SUBMISSION')
    need(sha(PACKAGE/'EXECUTION_CARD.json')==spec['execution_card_sha256'],'UNCHANGED_CARD')
    p=PACKAGE/'config/EXECUTION.json';need(sha(p)==spec['before_sha256'],'EXPECTED_FAILED_CONFIG')
    payload=base64.b64decode(spec['payload_b64']);need(hashlib.sha256(payload).hexdigest()==spec['after_sha256'],'REPAIR_PAYLOAD_PIN')
    need(json.loads(p.read_bytes())==json.loads(payload),'IDENTICAL_CONFIG_VALUES')
    with (DEPLOY/'EXECUTION.failed.json').open('xb') as f:f.write(p.read_bytes())
    temporary=DEPLOY/'EXECUTION.corrected.json';temporary.write_bytes(payload);temporary.replace(p)
    result=dict(status='CONFIG_ORDER_REPAIRED',before_sha256=spec['before_sha256'],after_sha256=sha(p),identical_json_values=True,model_forwards=0,new_distances=0,previous_submissions=0)
    write(DEPLOY/'REPAIR_RECEIPT.json',result);return result
'''
    receiver+=helper+'\nif __name__=="__main__":\n    main(read(Path(__file__).with_name("receiver_config.json")))\n'
    ast.parse(receiver);(HERE/'receiver.py').write_text(receiver,encoding='utf-8')
    client=(OLD/'client.py').read_text(encoding='utf-8').replace('18796','18798')
    (HERE/'client.py').write_text(client,encoding='utf-8')
    pipeline=(OLD/'pipeline.py').read_text(encoding='utf-8')
    pipeline=once_replace(pipeline,"write(HERE/'PROGRESS.json',record)","write(HERE.parent/'history_sample_coverage_c4_deployment_20261101/PROGRESS.json',record)")
    pipeline=once_replace(pipeline,"    progress('UPLOADING');upload(progress)\n    progress('INSTALLING');write(HERE/'INSTALL_RECEIPT.json',request('install'))\n", "    state=request('state');need(state['status']=='INSTALLED' and not state['submitted'],'REPAIRED_READY_STATE')\n")
    pipeline=once_replace(pipeline,"    need(submitted['submitted'],'SUBMISSION_FAILED');job=submitted['job_id'];progress('HPC_RUNNING',job_id=job)","    need(submitted['submitted'],'SUBMISSION_FAILED');job=submitted['job_id'];progress('HPC_RUNNING',job_id=job)\n    with (HERE.parent/'history_sample_coverage_c4_deployment_20261101/SUBMIT_RECEIPT.json').open('x',encoding='utf-8') as f:json.dump(dict(submitted,repair_deployment=HERE.name),f,indent=2)")
    ast.parse(client);ast.parse(pipeline);(HERE/'pipeline.py').write_text(pipeline,encoding='utf-8')
    (HERE/'.private').mkdir(exist_ok=True);connection=dict(token=secrets.token_hex(24),socks_port=read(OLD/'.private/connection.json')['socks_port']);write(HERE/'.private/connection.json',connection)
    cfg=dict(token=connection['token'],bundle=old_manifest['bundle'],files=old_manifest['files'],assets=old_manifest['assets'],repair=repair)
    pack=lambda b:base64.b64encode(zlib.compress(b,9)).decode()
    launch="import base64,zlib,pathlib,subprocess,time; d=pathlib.Path("+repr(REMOTE+'/runs/'+HERE.name)+");d.mkdir(parents=True,exist_ok=True);s=d/'receiver_bootstrap.py';c=d/'receiver_config.json';assert not s.exists() and not c.exists();s.write_bytes(zlib.decompress(base64.b64decode("+repr(pack(receiver.encode()))+")));c.write_bytes(zlib.decompress(base64.b64decode("+repr(pack(json.dumps(cfg).encode()))+")));c.chmod(0o600);log=(d/'receiver.log').open('ab');subprocess.Popen(['/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python','-B',str(s)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);time.sleep(1);print((d/'receiver.log').read_text()[-1500:])"
    command="/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B -c \"import base64,zlib;exec(zlib.decompress(base64.b64decode('"+pack(launch.encode())+"')))\""
    (HERE/'RUN_IN_HPC_TERMINAL.txt').write_text(command+'\n',encoding='utf-8')
    write(HERE/'REPAIR_MANIFEST.json',dict(status='READY_NOT_SUBMITTED',**{k:v for k,v in repair.items() if k!='payload_b64'},
        checks=dict(original_failure_reproduced=True,repaired_order_hash_matches=True,json_values_identical=True,syntax=True),
        files={n:sha(HERE/n) for n in ('receiver.py','client.py','pipeline.py','REMOTE_EXECUTION.json','RUN_IN_HPC_TERMINAL.txt')},
        reused_asset_bytes=sum(a['bytes'] for a in old_manifest['assets']),scientific_code_changed=False))
    print(json.dumps(dict(status='REPAIR_READY',command_characters=len(command),reupload_asset_bytes=0)))

if __name__=='__main__':main()
