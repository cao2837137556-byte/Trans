"""Once-only archival materialization, frozen scoring and export. Never trains."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time

import legacy_unsw_archival_common_v1 as c


def authorize(root,out,explicit):
    # Reject before any recipe/raw/checkpoint read.
    c.require(explicit is True,'REAL_EXECUTION_NOT_AUTHORIZED')
    root,out=Path(root).resolve(),Path(out).resolve()
    c.require(out==root/'runs/real_evaluation','OUTPUT_SCOPE')
    c.require(not out.exists(),'OUTPUT_EXISTS_NO_RETRY')
    c.verify(root,exact=False)
    c.contracts(root)
    return root,out


def preflight(root,out,target=True):
    from importlib.metadata import version
    import platform
    import legacy_unsw_archival_runtime_v1 as rt
    import legacy_reference_sample_prepare_v1 as prep
    root,out=Path(root),Path(out); out.mkdir(parents=True,exist_ok=False)
    contract=c.read(root/'runtime_contract.json')
    if target:
        c.require(platform.system()=='Linux' and sys.version_info[:3]==(3,9,25),'TARGET_PYTHON')
        for name,expected in contract['target_versions'].items():
            c.require(version(name).split('+')[0]==expected,'TARGET_VERSION:'+name)
    tshark=contract['tshark'] if target else shutil.which('tshark') or 'C:/Program Files/Wireshark/tshark.exe'
    result=subprocess.run([tshark,'--version'],capture_output=True,text=True,timeout=30)
    c.require(result.returncode==0 and '4.6.6' in result.stdout.splitlines()[0],'TSHARK_VERSION')
    runtime=prep.old.legacy_runtime()
    expected=c.read(root/'fixtures/expected.json'); fixture=c.read(root/'fixtures/fixture_contract.json')
    import csv,io
    for spec in fixture['captures']:
        path=c.pin(root/spec['path'],spec['sha256'])
        names=rt.fields(runtime); command=[tshark,'-n','-r',str(path),'-T','fields','-E','header=y','-E','separator=/t','-E','quote=d','-E','occurrence=f']
        for name in names: command+=['-e',name]
        got=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60)
        c.require(got.returncode==0 and not got.stderr,'SYNTHETIC_DECODER')
        reader=csv.DictReader(io.StringIO(got.stdout),delimiter='\t',quotechar='"')
        c.require(reader.fieldnames==names==expected['fields'],'SYNTHETIC_FIELDS')
        c.require(list(reader)==expected['captures'][spec['capture_id']]['rows'],'SYNTHETIC_DECODE_PARITY')
    test=subprocess.run([sys.executable,'-m','unittest','-v','test_legacy_unsw_archival_v1'],
                        cwd=root/'repo/ood',capture_output=True,text=True,timeout=300)
    (out/'tests.log').write_text(test.stdout+test.stderr,encoding='utf-8')
    c.require(test.returncode==0,'SYNTHETIC_TESTS_FAILED')
    if target:
        # Original tokenizer/collator/mean-pooling path, generated input and stand-in model only.
        import numpy as np
        embed,translator,model,tokenizer,collator=rt.e3_runtime(root,synthetic=True)
        from test_legacy_unsw_archival_v1 import generated_flow
        flows=[generated_flow() for _ in range(17)]
        features=embed.embed_flows(translator,model,tokenizer,collator,flows,'cpu',16)
        c.require(features.shape==(17,768) and features.dtype==np.float32 and np.isfinite(features).all(),'SYNTHETIC_TOKENIZER_POOLING')
    c.write(out/'status.json',dict(status='PREFLIGHT_PASS',synthetic_only=True,
        target_environment_checked=target,real_model_forwards=0,real_raw_reads=0,optimizer_updates=0,
        python=sys.version,versions={n:version(n) for n in contract['target_versions'] if target or n in ('numpy','torch','dpkt')}))
    c.seal(out)


def save_flows(out,specs,query,refs,known,decoder,progress,workers):
    import legacy_unsw_archival_data_v1 as data
    import legacy_reference_sample_prepare_v1 as prep
    import issue27ckda_d0_resource_pilot_v1 as translator
    folder=out/'flows'; folder.mkdir(exist_ok=False)
    paths=[folder/('shard_%02d.jsonl.gz'%i) for i in range(workers)]
    files=[gzip.open(p,'xt',encoding='utf-8',newline='\n') for p in paths]
    counts=[0]*workers; uids=set(); runtime=prep.old.legacy_runtime()
    try:
        for spec in specs:
            progress.stage='CAUSAL_SNAPSHOTS_'+spec['capture_id']
            targets=[r for r in query+refs if r['capture_id']==spec['capture_id']]
            with decoder(spec) as decoded:
                for uid,flow in data.selected_snapshots(decoded,spec,targets,known,runtime,translator):
                    c.require(uid not in uids,'DUPLICATE_FLOW_UID')
                    shard=(len(uids)//16)%workers
                    files[shard].write(json.dumps(dict(uid=uid,flow=flow),separators=(',',':'),allow_nan=False)+'\n')
                    counts[shard]+=1; uids.add(uid)
                    if len(uids)%256==0: progress.tick(len(uids),len(query)+len(refs))
    finally:
        for f in files: f.close()
    c.require(uids=={r['uid'] for r in query+refs},'FLOW_UID_COVERAGE')
    c.write(folder/'index.json',dict(shards=[dict(file=p.name,count=n) for p,n in zip(paths,counts)],
        total=len(uids),manifest_seal_sha256=c.sha(out/'manifests/SHA256SUMS'),immutable_causal_snapshots=True))
    c.seal(folder)


def merge_features(out,query,refs,workers):
    import numpy as np
    folder=out/'features'; folder.mkdir(exist_ok=False)
    allrows=query+refs; index={r['uid']:i for i,r in enumerate(allrows)}; seen=set()
    cache=np.lib.format.open_memmap(folder/'features.npy',mode='w+',dtype=np.float32,shape=(len(allrows),768))
    for shard in range(workers):
        source=out/('worker_%02d'%shard); c.verify(source)
        c.require(c.read(source/'status.json')['status']=='COMPLETE','WORKER_STATUS')
        uids=c.read(source/'uids.json'); data=np.load(source/'features.npy',mmap_mode='r',allow_pickle=False)
        c.require(data.shape==(len(uids),768) and data.dtype==np.float32,'SHARD_SHAPE')
        for start in range(0,len(uids),1024):
            batch=uids[start:start+1024]; values=data[start:start+1024]
            c.require(not seen.intersection(batch) and len(set(batch))==len(batch) and
                      all(uid in index for uid in batch) and np.isfinite(values).all(),'SHARD_UID_OR_NONFINITE')
            cache[[index[uid] for uid in batch]]=values; seen.update(batch)
    c.require(seen==set(index),'FEATURE_UID_COVERAGE')
    cache.flush(); del cache
    c.write(folder/'uids.json',[r['uid'] for r in allrows])
    c.write(folder/'receipt.json',dict(rows=len(allrows),recipe_sha256=c.RECIPE_SHA,
        manifest_seal_sha256=c.sha(out/'manifests/SHA256SUMS'),flows_seal_sha256=c.sha(out/'flows/SHA256SUMS')))
    c.seal(folder); c.verify(folder)
    return np.load(folder/'features.npy',mmap_mode='r',allow_pickle=False)


def execute(root,out,explicit):
    root,out=authorize(root,out,explicit)
    import legacy_unsw_archival_runtime_v1 as rt
    import legacy_unsw_archival_data_v1 as data
    import legacy_reference_sample_prepare_v1 as prep
    recipe,roster,labels,controls=c.contracts(root)
    contract=c.read(root/'runtime_contract.json')
    progress=rt.Progress(out,contract['limits'])
    def interrupted(signum,frame):
        raise RuntimeError('SIGNAL_STOP:'+str(signum))
    previous_signal=signal.signal(signal.SIGTERM,interrupted)
    try:
        c.write(out/'launch.json',dict(scope='MATERIALIZE_FROZEN_SCORE_EXPORT',recipe_sha256=c.RECIPE_SHA,
            authority='Explicit --authorize-frozen-evaluation invocation',pid=os.getpid(),
            policy_declared_at='2026-09-26',archive_capture_year=2018,optimizer=False,calibration=False,retries=0))
        preflight(root,out/'preflight')
        progress.stage='VERIFY_REUSED_INPUTS'; progress.tick(force=True)
        checkpoint=root/'vendor/netFound-base/model.safetensors'
        c.pin(checkpoint,recipe['immutable_e3']['checkpoint_sha256'])
        specs=[]
        for i,source in enumerate(recipe['sources']):
            path=Path(contract['raw_root'])/Path(source['path']).name
            c.require(path.stat().st_size==source['bytes'],'RAW_SIZE')
            c.pin(path,source['sha256'])
            specs.append(dict(source,raw_path=str(path),kind='normal' if i==0 else 'mixed',
                packet_count=contract['packet_counts'][source['capture_id']],
                selection_salt=recipe['normal_queries']['selection_salt'],intervals=labels['intervals']))
        known=contract['known_device_macs']; runtime=prep.old.legacy_runtime(); decode_number=[0]
        def decoder(spec):
            decode_number[0]+=1
            return rt.decode(spec['raw_path'],spec,runtime,progress,out/('decode_%02d.stderr.log'%decode_number[0]),contract['tshark'])
        query,refs=data.materialize(root,out/'manifests',recipe,roster,labels,specs,known,decoder,progress)
        # A complete, sealed denominator is required BEFORE model loading or feature work.
        c.verify(out/'manifests')
        save_flows(out,specs,query,refs,known,decoder,progress,contract['workers'])
        progress.stage='E3_FEATURES'; progress.tick(0,recipe['counts']['total_feature_targets'],force=True)
        rt.launch_features(root,out,progress)
        progress.stage='MERGE_FEATURES'; progress.tick(force=True)
        features=merge_features(out,query,refs,contract['workers'])
        progress.stage='FROZEN_SCORING'; progress.tick(force=True)
        from legacy_unsw_archival_score_v1 import evaluate
        decision=evaluate(root,out/'evaluation',recipe,roster,controls,query,refs,features,progress)
        progress.stop('COMPLETE',scientific_gate=decision)
        c.seal(out)
    except BaseException as exc:
        progress.stop('STOPPED_NO_RETRY',repr(exc))
        raise
    finally:
        signal.signal(signal.SIGTERM,previous_signal)


def export(root):
    root=Path(root); target=root/'evaluation_pullback.tar.gz'
    c.require(not target.exists(),'EXPORT_EXISTS')
    paths=[]
    for folder in ('runs/real_evaluation','logs'):
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file())
    paths.extend(p for p in (root/'job.id',root/'exit_code.txt',root/'runtime_contract.json') if p.is_file())
    # Preserve remote full-run seals as provenance. The separately pinned export
    # index declares deliberately omitted intermediates so a partial archive can
    # never masquerade as a complete original directory seal.
    included={}; omitted={}
    for path in sorted(paths):
        rel=path.relative_to(root).as_posix()
        dest=omitted if '/flows/' in rel or rel.endswith('/features.npy') else included
        dest[rel]=dict(sha256=c.sha(path),bytes=path.stat().st_size)
    manifest=root/'export_manifest.json'
    c.write(manifest,dict(included=included,omitted=omitted,recipe_sha256=c.RECIPE_SHA,
        original_seals_are_provenance_not_complete_export_seals=True,
        raw_captures_included=False,source_checkpoint_included=False))
    with tarfile.open(target.with_suffix('.partial'),'x:gz',compresslevel=1) as tar:
        for path in sorted(paths):
            rel=path.relative_to(root).as_posix()
            if rel not in included: continue
            tar.add(path,arcname=rel,recursive=False)
        tar.add(manifest,arcname='export_manifest.json',recursive=False)
    target.with_suffix('.partial').replace(target)
    Path(str(target)+'.sha256').write_text(c.sha(target)+'  '+target.name+'\n',encoding='utf-8')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['run','worker','preflight','export'])
    p.add_argument('--root',type=Path,required=True); p.add_argument('--output',type=Path)
    p.add_argument('--shard',type=int); p.add_argument('--authorize-frozen-evaluation',action='store_true')
    p.add_argument('--local-synthetic',action='store_true')
    a=p.parse_args(argv)
    if a.command=='run': execute(a.root,a.output or a.root/'runs/real_evaluation',a.authorize_frozen_evaluation)
    elif a.command=='worker':
        from legacy_unsw_archival_runtime_v1 import feature_worker
        feature_worker(a.root,a.output,a.shard,a.authorize_frozen_evaluation)
    elif a.command=='preflight': preflight(a.root,a.output,not a.local_synthetic)
    else: export(a.root)


if __name__=='__main__': main()
