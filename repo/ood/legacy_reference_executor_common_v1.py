"""Shared identities and durable I/O. Importing this module opens no assets."""
from __future__ import annotations
import gzip, hashlib, json, os, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT/'runs/legacy_reference_sample_preparation_v1_20260917'
RECIPE = ROOT/'runs/mainline_docs/legacy_reference_development_recipe_v1_20260917.json'
RECIPE_SHA = '85dc7138cd43cdef16ab15394b7712eb97b124311c06b4ea63aba853f781560a'
PACKAGE = ROOT/'runs/legacy_reference_executor_implementation_v1_20260917'
STATE_KEYS = ('normalizer_mean','normalizer_scale','p2__0.weight','p2__0.bias','p2__3.weight','p2__3.bias')
class Stop(RuntimeError): pass
def require(condition, message):
    if not condition: raise Stop(message)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def atomic_json(path,value):
    path=Path(path); tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=True,indent=2,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(str(tmp),str(path))
def confined(root,path):
    root=Path(root).resolve(); path=(root/path).resolve()
    require(path.is_relative_to(root),'PATH_OUTSIDE_ROOT')
    return path
def pin(path,expected):
    require(sha(path)==expected,'SHA_DRIFT:'+str(path)); return Path(path)
def recipe():
    pin(RECIPE,RECIPE_SHA); return load(RECIPE)
def rows(path):
    with gzip.open(path,'rt',encoding='utf8') as f:
        for line in f: yield json.loads(line)
def uid_sha(uids): return hashlib.sha256(''.join(u+'\n' for u in sorted(uids)).encode()).hexdigest()
def seal(folder):
    folder=Path(folder); target=folder/'SHA256SUMS'; require(not target.exists(),'SEAL_EXISTS')
    files=sorted(p for p in folder.rglob('*') if p.is_file() and p.name not in ('status.json','PROGRESS.md'))
    with target.open('x',encoding='utf8') as f:
        for p in files: f.write(sha(p)+'  '+p.relative_to(folder).as_posix()+'\n')
        f.flush(); os.fsync(f.fileno())
def verify_seal(folder):
    folder=Path(folder)
    for line in (folder/'SHA256SUMS').read_text(encoding='utf8').splitlines():
        h,name=line.split('  ',1); pin(confined(folder,name),h)
def emit(folder,stage,done=0,total=0,**extra):
    atomic_json(Path(folder)/'status.json',dict(stage=stage,done=done,total=total,updated_epoch=time.time(),**extra))
def scope_metadata():
    import legacy_reference_sample_prepare_v1 as prep
    require(prep.pin_sources()==load(SAMPLE/'input_pins.json'),'ORIGINAL_PINS_DRIFT')
    require(load(SAMPLE/'independent_verification.json')['status']=='PASS','SAMPLE_NOT_VERIFIED')
    sealed=dict((name,h) for h,name in (line.split('  ',1) for line in (SAMPLE/'SHA256SUMS').read_text().splitlines()))
    for name in ['capture_catalog.json','devices.json','input_pins.json','independent_verification.json']:
        pin(SAMPLE/name,sealed[name])
    return recipe()
def check_fixture(path):
    path=confined(PACKAGE/'synthetic',path)
    require(load(path).get('synthetic_only') is True,'SYNTHETIC_MARKER')
    return load(path)
def authorize(scope_path, explicit):
    require(explicit,'EXPLICIT_CHAIN_AUTHORIZATION_REQUIRED')
    scope=load(scope_path)
    require(scope.get('execution_authorized') is True,'SCOPE_NOT_AUTHORIZED')
    require(scope.get('recipe_sha256')==RECIPE_SHA,'SCOPE_RECIPE')
    require(scope.get('stages')==['LEARN_DEV_FEATURES','NINE_TRAIN_ENDPOINTS','DEV','CONDITIONAL_HOLDOUT'],'SCOPE_STAGES')
    require(scope.get('retries')==0 and scope.get('local_only') is True,'SCOPE_LIMITS')
    acceptance=load(PACKAGE/'acceptance.json')
    require(acceptance['status']=='PASS' and acceptance['real_model_forwards']==acceptance['real_optimizer_steps']==0,'IMPLEMENTATION_NOT_ACCEPTED')
    verify_seal(PACKAGE)
    for p,h in load(PACKAGE/'code_pins.json').items(): pin(ROOT/p,h)
    scope_metadata()
    out=confined(ROOT/'runs',scope['output_run_name'])
    require(not out.exists(),'OUTPUT_EXISTS_NO_RETRY')
    return scope,out

