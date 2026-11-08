import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,indent=2)+'\n').encode())
def main():
    assert not (HERE/'START_INTENT.json').exists()
    assert json.loads((HERE/'LOCAL_REGRESSION.json').read_text())['status']=='PASS'
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    old=ROOT/'runs/baseline_split_resource_v1_20261107';deps=json.loads((old/'INPUT_PINS.json').read_text())
    for n in ['metrics.py','reporting.py']:
        p=ROOT/'runs/device_context_evaluation_v1_20261105'/n
        # reporting is imported from the legacy runtime if absent in this directory.
        if p.exists():deps[p.relative_to(ROOT).as_posix()]=sha(p)
    write(HERE/'INPUT_PINS.json',deps)
    files=[p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and '.private' not in p.parts and '__pycache__' not in p.parts and (p.suffix in ['.py','.json','.toml','.yaml','.md','.ipynb'] or p.name=='LICENSE') and p.name not in ['DELIVERY.json','PREFLIGHT_DETAIL.json','PROGRESS.json']]
    cfg=dict(token=secrets.token_hex(32),pins={n:sha(HERE/n) for n in sorted(files)})
    write(HERE/'.private/config.json',cfg)
    conn=json.loads((HERE/'.private/connection_previous.json').read_text());conn.update(token=cfg['token'],remote_port=18876);write(HERE/'.private/connection.json',conn)
    remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
    code="import base64,os,socket,subprocess,shutil,hashlib\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_VERSION_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18876));s.close()\np.mkdir(parents=True)\n(p/'receiver.py').write_bytes(base64.b64decode("+repr(base64.b64encode((HERE/'receiver.py').read_bytes()).decode())+"))\n(p/'.private.json').write_text("+repr(json.dumps(cfg))+")\n(p/'assets').mkdir()\n"
    for name,spec in json.loads((HERE/'ASSETS.json').read_text()).items():
        code+="src=Path('/public/home/jiangxinwei.zr/work/paper04/runs/baseline_training_readiness_v6_20261107/assets')/"+repr(name)+"\nassert src.stat().st_size=="+str(spec['bytes'])+" and hashlib.sha256(src.read_bytes()).hexdigest()=="+repr(spec['sha256'])+"\nshutil.copyfile(src,p/'assets'/"+repr(name)+")\n"
    code+="with (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('AUTHOR_DEFAULTS_RECEIVER_STARTED',proc.pid,18876)\n"
    encoded=base64.b64encode(zlib.compress(code.encode(),9)).decode()
    (HERE/'.private/RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))'),encoding='utf-8')
    write(HERE/'DELIVERY.json',dict(status='PREPARED',pins=cfg['pins'],receiver_sha256=sha(HERE/'receiver.py'),preflight=dict(cpu=1,memory_gib=12,hours=2),automatic_formal_after_gates=True,formal_candidates=['DTE-C','SLAD','CatBoost'],pending=['TabM','TabR','DisentAD','ModernNCA'],main_model_changed=False))
    print('PREPARED',len(files),'files',len(deps),'dependencies')
if __name__=='__main__':main()
