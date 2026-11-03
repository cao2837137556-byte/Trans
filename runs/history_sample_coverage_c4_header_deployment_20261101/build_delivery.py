"""Create exact C4 code delivery and three pinned Netatmo asset transfers."""
import base64
import io
import json
from pathlib import Path
import secrets
import sys
import tarfile
import zlib
from receiver import sha,read,write,need
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PACKAGE=HERE.parent/'history_sample_coverage_c4_header_repair_v1_20261101'
REMOTE='/public/home/jiangxinwei.zr/work/paper04'

def relocate(v,data):
    if isinstance(v,dict):return {k:('/share/software/tshark-4.6.6/bin/tshark' if k=='tshark' else relocate(x,data)) for k,x in v.items()}
    if isinstance(v,list):return [relocate(x,data) for x in v]
    if isinstance(v,str):
        normalized=v.replace('\\','/')
        for local,remote in ((ROOT.as_posix(),REMOTE),(data.as_posix(),REMOTE+'/data_external/unsw_iotraffic_2025')):
            if normalized==local or normalized.startswith(local+'/'):return remote+normalized[len(local):]
    return v

def main():
    need(not (HERE/'DELIVERY_MANIFEST.json').exists(),'DELIVERY_ALREADY_SEALED')
    sys.path.insert(0,str(PACKAGE));from run import verify,semantic
    from hnr.common import digest
    script=(PACKAGE/'hpc/run_encode.slurm').read_bytes();need(script.startswith(b'#!/bin/bash\n') and b'\r' not in script,'SLURM_REQUIRES_UNIX_LF')
    card=verify('evaluate');need(read(PACKAGE/'IMPLEMENTATION_CHECK.json')['status']=='PASS','IMPLEMENTATION')
    original=read(PACKAGE/'config/EXECUTION.json');data=Path(original['devices'][0]['raw']['path']).parent.parent
    mapped=relocate(original,data);need(digest(semantic(mapped))==card['config_semantic_sha256'],'RELOCATION_SEMANTICS')
    names=sorted(set(card['code_sha256'])|{'EXECUTION_CARD.json','EXECUTION_CARD.json.sha256','config/EXECUTION.json','IMPLEMENTATION_CHECK.json','TESTS.log'})
    bundle=HERE/'bundle.tar';files={}
    with tarfile.open(bundle,'x:') as ar:
        for name in names:
            payload=(json.dumps(mapped,indent=2)+'\n').encode() if name=='config/EXECUTION.json' else (PACKAGE/name).read_bytes()
            import hashlib
            files[name]=dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
            info=tarfile.TarInfo(name);info.size=len(payload);info.mode=0o600;ar.addfile(info,io.BytesIO(payload))
    assets=[]
    net=next(d for d in original['devices'] if d['key']=='NETATMO');remote_net=next(d for d in mapped['devices'] if d['key']=='NETATMO')
    for key in ('raw','packet_index','chronological_order'):
        p=Path(net[key]['path']);need(sha(p)==net[key]['sha256'],'NET_ASSET_PIN')
        assets.append(dict(local_path=str(p),remote_relative=remote_net[key]['path'][len(REMOTE)+1:],bytes=p.stat().st_size,sha256=net[key]['sha256']))
    private=HERE/'.private';private.mkdir(exist_ok=True);connection=read(private/'connection.json')
    write(private/'connection.json',connection)
    config=dict(token=connection['token'],bundle=dict(bytes=bundle.stat().st_size,sha256=sha(bundle)),files=files,
        assets=[{k:v for k,v in a.items() if k!='local_path'} for a in assets])
    source=(HERE/'receiver.py').read_text(encoding='utf-8')+'\nif __name__=="__main__":\n    main(read(Path(__file__).with_name("receiver_config.json")))\n'
    pack=lambda b:base64.b64encode(zlib.compress(b,9)).decode()
    remote_dir=REMOTE+'/runs/'+HERE.name
    launch="import base64,zlib,pathlib,subprocess,time; d=pathlib.Path("+repr(remote_dir)+"); d.mkdir(parents=True,exist_ok=True); s=d/'receiver_bootstrap.py'; c=d/'receiver_config.json'; assert not s.exists() and not c.exists(); s.write_bytes(zlib.decompress(base64.b64decode("+repr(pack(source.encode()))+"))); c.write_bytes(zlib.decompress(base64.b64decode("+repr(pack(json.dumps(config).encode()))+"))); c.chmod(0o600); log=(d/'receiver.log').open('ab'); p=subprocess.Popen(['/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python','-B',str(s)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True); time.sleep(1); print((d/'receiver.log').read_text()[-1000:])"
    # Fixed trusted code; encoded wrapper contains no shell interpolation.
    command="/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B -c \"import base64,zlib;exec(zlib.decompress(base64.b64decode('"+pack(launch.encode())+"')))\""
    (HERE/'RUN_IN_HPC_TERMINAL.txt').write_text(command+'\n',encoding='utf-8')
    write(HERE/'DELIVERY_MANIFEST.json',dict(bundle=config['bundle'],files=files,assets=assets,receiver_sha256=sha(HERE/'receiver.py'),
        execution_card_sha256=sha(PACKAGE/'EXECUTION_CARD.json'),bootstrap_sha256=sha(HERE/'RUN_IN_HPC_TERMINAL.txt'),
        state='READY_NOT_SUBMITTED',command_characters=len(command)))
    print(json.dumps(dict(status='READY_NOT_SUBMITTED',files=len(files),code_bytes=bundle.stat().st_size,total_asset_bytes=sum(a['bytes'] for a in assets),command_characters=len(command))))

if __name__=='__main__':main()
