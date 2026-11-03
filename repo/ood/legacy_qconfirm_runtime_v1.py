"""Explicit Linux relocation, pinned assets, environment; no installs/downloads."""
from pathlib import Path
import copy,shutil,subprocess
import legacy_qref_common_v1 as c

CATALOG='runs/legacy_reference_sample_preparation_v1_20260917/capture_catalog.json'
DEVICES='runs/legacy_reference_sample_preparation_v1_20260917/devices.json'

def inventory(root,scope,plan,qrecipe):
    """Fail on missing relocated inputs before opening the protected query manifest."""
    from legacy_qconfirm_common_v1 import DESIGN
    assets=c.read(Path(root)/DESIGN/'asset_candidates.json')['assets']
    c.require(set(scope['raw_paths'])=={a['capture_id'] for a in assets},'RAW_INVENTORY_SCOPE')
    for a in assets:
        path=Path(scope['raw_paths'][a['capture_id']])
        c.require(path.is_file() and path.stat().st_size==a['bytes'],'MISSING_RAW_INVENTORY:'+a['capture_id'])
    paths=[c.confined(root,plan['data'][key]['path']) for key in ['query','reference']]
    cache=Path(scope['donor_cache']);spec=qrecipe['data']['cache']['REFERENCE']
    paths.extend([cache/'cache.json',c.confined(cache,spec['metadata']),c.confined(cache,spec['features'])])
    for path in paths:c.require(path.is_file(),'MISSING_INPUT:'+str(path))
    return dict(status='PASS',raw_files=len(assets),manifest_and_cache_files=len(paths),content_reads=False)

def prepare_catalog(root,scope,rows,refs,plan):
    from legacy_qconfirm_common_v1 import DESIGN
    assets=c.read(Path(root)/DESIGN/'asset_candidates.json')['assets'];allowed={a['capture_id']:a for a in assets}
    catalog={r['capture_id']:r for r in c.read(Path(root)/CATALOG)}
    needed={r['capture_id'] for r in rows+refs};c.require(needed<=set(allowed),'UNLISTED_CAPTURE')
    c.require(set(scope['raw_paths'])<=set(allowed) and needed<=set(scope['raw_paths']),'RAW_SCOPE')
    effective={}
    for cid in sorted(needed):
        source=Path(scope['raw_paths'][cid]);a=allowed[cid];s=catalog[cid]
        c.require((s['sha256'],s['bytes'])==(a['sha256'],a['bytes']),'CATALOG_IDENTITY')
        c.require(source.is_file() and source.stat().st_size==a['bytes'],'MISSING_OR_WRONG_RAW:'+cid)
        c.pin(source,a['sha256']);effective[cid]=dict(s,path=str(source.resolve()))
    return effective

def install(root,scope,folder,create=False):
    import legacy_reference_executor_common_v1 as oldc
    import legacy_cic2022_enhancement_prepare_v1 as old
    import legacy_reference_sample_prepare_v1 as prep
    from legacy_reference_hpc_runtime_v1 import environment
    from legacy_qconfirm_common_v1 import Progress
    root=Path(root);folder=Path(folder)
    q=c.load_recipe(root);spec=copy.deepcopy(q['immutable']['legacy']['model'])
    # Use previously validated public HPC installation; arbitrary new model paths are forbidden.
    config=c.read(root/'confirmation_runtime_config.json')
    spec['source_root']=config['model_source'];spec['checkpoint_dir']=config['model_checkpoint']
    vendor=c.read(c.confined(root,q['immutable']['legacy']['model']['vendor_source_manifest']))
    vendor['source_root']=str(Path(config['model_source'])/'src')
    target=folder/'vendor_pins.json'
    if create:folder.mkdir(exist_ok=False);c.write(target,vendor)
    else:c.require(c.read(target)==vendor,'VENDOR_RELOCATION_DRIFT')
    spec['vendor_source_manifest']=str(target.resolve())
    oldc.ROOT=root;old.runtime_dependencies=environment
    env=environment();old.verify_vendor({'model':spec},root=root,verify_checkpoint=True)
    tshark=shutil.which('tshark');c.require(tshark is not None,'TSHARK_MISSING')
    version=subprocess.check_output([tshark,'-v'],text=True,stderr=subprocess.STDOUT)
    c.require(version.startswith('TShark (Wireshark) 4.6.6'),'TSHARK_VERSION')
    prep.TSHARK=Path(tshark)
    # sample_prepare.old.legacy_runtime uses the same frozen parser modules bundled with the executor.
    if create:c.write(folder/'environment.json',env);c.seal(folder)
    else:c.verify(folder)
    return {'legacy':{'model':spec}}
