"""Explicit Linux relocation and environment contract. No silent dependency bypass."""
from __future__ import annotations
import copy,json,os,platform,shutil,subprocess,sys
from pathlib import Path
import legacy_reference_executor_common_v1 as c
ROOT=Path(__file__).resolve().parents[2]
INPUT_DIR='inputs/reference_learn_dev_inputs_v1_20260918/data'
EXPECTED={'numpy':'2.0.1','torch':'2.5.1','transformers':'4.57.3','tokenizers':'0.22.2','safetensors':'0.6.2','huggingface-hub':'0.36.2','dpkt':'1.9.8'}

def environment():
    from importlib.metadata import version
    c.require(sys.platform=='linux' and platform.python_version()=='3.9.25','LINUX_PYTHON_CONTRACT')
    versions={name:version(name) for name in EXPECTED}
    c.require(versions==EXPECTED,'HPC_DEPENDENCY_DRIFT:'+str(versions))
    import torch
    c.require(str(torch.__version__).split('+')[0]=='2.5.1','TORCH_IMPORT_DRIFT')
    return dict(python=sys.executable,python_version=platform.python_version(),versions=versions,platform=platform.platform())

def bundle_check():
    c.verify_seal(ROOT)
    scope=c.load(ROOT/'hpc_scope.json')
    c.require(scope['execution_authorized'] and scope['stages']==['LEARN_DEV_FEATURES','NINE_TRAIN_ENDPOINTS','LEARN_DEV_EVALUATION'],'HPC_SCOPE')
    c.require(scope['holdout_allowed'] is False and scope['retries']==0 and scope['workers']==8,'HPC_SCOPE_BOUNDARY')
    c.pin(ROOT/'frozen/recipe.json',c.RECIPE_SHA)
    return scope

def relocate(original,root,metadata_dir,model_source,model_checkpoint):
    r=copy.deepcopy(original)
    for role,meta in r['data']['manifests'].items():
        meta['path']='FORBIDDEN_HOLDOUT_QUERY' if role=='DEVICE_HOLDOUT' else (Path(INPUT_DIR)/meta['path'].replace('\\','/')).as_posix()
    r['legacy']['probe_state_path']=(Path(INPUT_DIR)/r['legacy']['probe_state_path'].replace('\\','/')).as_posix()
    r['legacy']['model']['source_root']=str(model_source)
    r['legacy']['model']['checkpoint_dir']=str(model_checkpoint)
    r['legacy']['model']['vendor_source_manifest']=str((metadata_dir/'vendor_pins.json').relative_to(root))
    # Numerical/scientific recipe is preserved; differences are physical paths only.
    restored=copy.deepcopy(r)
    for role,meta in original['data']['manifests'].items():restored['data']['manifests'][role]['path']=meta['path']
    restored['legacy']['probe_state_path']=original['legacy']['probe_state_path']
    for key in ('source_root','checkpoint_dir','vendor_source_manifest'):restored['legacy']['model'][key]=original['legacy']['model'][key]
    c.require(restored==original,'NON_PATH_RECIPE_MUTATION')
    return r

def install(run,create=False):
    scope=bundle_check();environment()
    import legacy_cic2022_enhancement_prepare_v1 as old
    import legacy_reference_sample_prepare_v1 as prep
    run=c.confined(ROOT,run);metadata_dir=run/'runtime_metadata'
    config=c.load(ROOT/'runtime_config.json')
    original=c.load(ROOT/'frozen/recipe.json')
    r=relocate(original,ROOT,metadata_dir,Path(config['model_source']),Path(config['model_checkpoint']))
    inventory=c.load(ROOT/'frozen/input_inventory.json')
    raw={a['capture_id']:a for a in inventory['assets'] if a['kind']=='raw_capture'}
    original_catalog=c.load(ROOT/'frozen/capture_catalog.json')
    catalog=[]
    for x in original_catalog:
        if x['capture_id'] not in raw:continue
        a=raw[x['capture_id']];c.require((x['sha256'],x['bytes'])==(a['sha256'],a['bytes']),'CATALOG_INPUT_IDENTITY')
        row=dict(x,path=str(c.confined(ROOT,Path(INPUT_DIR)/a['bundle_path'])));catalog.append(row)
    c.require(len(catalog)==217,'CAPTURE_SET')
    vendor=c.load(ROOT/'frozen/vendor_pins.json');vendor['source_root']=str(Path(config['model_source'])/'src')
    expected={'capture_catalog.json':catalog,'devices.json':c.load(ROOT/'frozen/devices.json'),'vendor_pins.json':vendor}
    if create:
        metadata_dir.mkdir(exist_ok=False)
        for name,value in expected.items():c.atomic_json(metadata_dir/name,value)
        c.atomic_json(run/'recipe.json',r);c.atomic_json(run/'execution_scope.json',scope)
        c.atomic_json(run/'environment.json',environment());c.seal(metadata_dir)
    else:
        c.verify_seal(metadata_dir)
        for name,value in expected.items():c.require(c.load(metadata_dir/name)==value,'RELOCATION_DRIFT')
        c.require(c.load(run/'recipe.json')==r,'EFFECTIVE_RECIPE_DRIFT')
    c.ROOT=ROOT;c.SAMPLE=metadata_dir;c.recipe=lambda:r
    old.runtime_dependencies=environment
    tshark=shutil.which('tshark');c.require(tshark is not None,'TSHARK_NOT_LOADED')
    version=subprocess.check_output([tshark,'-v'],text=True,stderr=subprocess.STDOUT)
    c.require(version.startswith('TShark (Wireshark) 4.6.6'),'TSHARK_VERSION_DRIFT')
    prep.TSHARK=Path(tshark)
    old.verify_vendor({'model':r['legacy']['model']},verify_checkpoint=True)
    return r

def input_check():
    inventory=c.load(ROOT/'frozen/input_inventory.json');matched=0
    for a in inventory['assets']:
        if a['kind']=='frozen_encoder':continue
        p=c.confined(ROOT,Path(INPUT_DIR)/a['bundle_path'])
        c.require(p.stat().st_size==a['bytes'],'INPUT_BYTES:'+a['bundle_path']);c.pin(p,a['sha256']);matched+=1
    c.require(matched==221,'INPUT_COUNT');return matched
