"""Identity-sealed E3 cache. The synthetic backend uses real tokenization only."""
from __future__ import annotations
import gzip,json,os,sqlite3,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import legacy_reference_executor_common_v1 as c
import legacy_reference_sample_prepare_v1 as prep
import legacy_reference_feature_adapter_v1 as adapter
COMPACT=('uid','device','partition','use','label','activity','capture_id','session_id','component_id','timestamp',
         'label_metric_weight_denominator','balanced_bce_weight_denominator','normal_activity_stratum','reference_dependency_stratum',
         'protocol','owner','canonical_key','frame')
def build_runtime(recipe,synthetic=False):
    import torch
    import legacy_cic2022_enhancement_prepare_v1 as old
    import issue27ckda_d0_resource_pilot_v1 as translator
    import issue27ckda_d1_e3_embed_v1 as embed
    old.runtime_dependencies()
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    model_spec=recipe['legacy']['model']
    old.verify_vendor({'model':model_spec},verify_checkpoint=False)
    config_path=Path(model_spec['checkpoint_dir'])/'config.json'; c.pin(config_path,model_spec['config_sha256'])
    if synthetic:
        config_type,collator_type,_,tokenizer_type=translator.import_netfound(Path(model_spec['source_root']))
        config=config_type.from_pretrained(str(config_path.parent),local_files_only=True); config.pretraining=False;config.compile=False
        tokenizer=tokenizer_type(config=config);tokenizer.pretraining=True;tokenizer.raw_labels=False
        collator=collator_type(pad_token_id=tokenizer.pad_token_id)
        class StandIn:
            def eval(self):return self
            def base_transformer(self,**batch):
                x=(batch['input_ids'].float()%101)/101
                h=x[:,:,None]*torch.linspace(.01,1.,768)[None,None,:]
                return SimpleNamespace(last_hidden_state=h)
        model=StandIn()
    else:
        model,tokenizer,collator=embed.build_e3_runtime(translator,Path(model_spec['source_root']),Path(model_spec['checkpoint_dir']),'cpu')
        model.requires_grad_(False)
    api,prefix,_=prep.old.legacy_runtime()
    return dict(model=model,tokenizer=tokenizer,collator=collator,embed=embed,translator=translator,event=api,prefix=prefix)
def feature_batch(runtime,flows):
    values=runtime['embed'].embed_flows(runtime['translator'],runtime['model'],runtime['tokenizer'],runtime['collator'],flows,'cpu',16)
    c.require(values.shape==(len(flows),768) and values.dtype==np.float32 and bool(np.isfinite(values).all()),'ENCODER_OUTPUT')
    return values
def require_holdout(gate,recipe_digest):
    c.require(gate is not None and gate.get('open') is True and gate.get('recipe_digest')==recipe_digest
              and gate.get('all_nine_endpoints_sealed') is True,'HOLDOUT_GATE_CLOSED')
def prepare(recipe,out,stage,gate=None,fixture=None):
    synthetic=fixture is not None
    c.require(stage in ('LEARN_DEV','HOLDOUT'),'PREPARE_STAGE')
    if stage=='HOLDOUT':require_holdout(gate,c.digest(recipe))
    allowed={'LEARN','DEV'} if stage=='LEARN_DEV' else {'DEVICE_HOLDOUT'}
    out=Path(out);out.mkdir(exist_ok=False);runtime=None
    catalog={s['capture_id']:s for s in (fixture['catalog'] if synthetic else c.load(c.SAMPLE/'capture_catalog.json'))}
    devices=fixture['devices'] if synthetic else c.load(c.SAMPLE/'devices.json')
    db=sqlite3.connect(str(out/'targets.sqlite'));db.execute('create table targets(role text, idx integer, capture text, frame integer, uid text unique, body text, primary key(role,idx))')
    manifests=recipe['data']['manifests'];counts={};paths={}
    for role in ['REFERENCE']+sorted(allowed):
        meta=manifests[role]; source=Path(meta['path']) if synthetic else c.confined(c.ROOT,meta['path'])
        c.pin(source,meta['sha256']);n=0;uids=[]
        path=out/(role+'.rows.jsonl.gz')
        with gzip.open(path,'wt',encoding='utf8') as dest:
            for r in c.rows(source):
                if role=='REFERENCE' and r['partition'] not in allowed:continue
                c.require((role=='REFERENCE' and r['use']=='REFERENCE' and r['label']==0) or (r['partition']==role and r['use']!='REFERENCE'),'MANIFEST_ROLE')
                body=json.dumps(r,separators=(',',':'))
                dest.write(body+'\n');db.execute('insert into targets values (?,?,?,?,?,?)',(role,n,r['capture_id'],r['frame'],r['uid'],body));n+=1;uids.append(r['uid'])
        c.require(n>0,'EMPTY_FEATURE_ROLE')
        if role!='REFERENCE':c.require(n==meta['rows'] and c.uid_sha(uids)==meta['sorted_uid_lines_sha256'],'MANIFEST_COUNT_UID')
        counts[role]=n;paths[role]=dict(rows=n,uid_sha256=c.uid_sha(uids),metadata=path.name,metadata_sha256=c.sha(path))
    db.execute('create index captures on targets(capture,frame)');db.commit()
    arrays={role:np.lib.format.open_memmap(out/(role+'.npy'),mode='w+',dtype=np.float32,shape=(n,768)) for role,n in counts.items()}
    written={role:np.zeros(n,dtype=bool) for role,n in counts.items()};done=0;total=sum(counts.values())
    annotations=gzip.open(out/'report_annotations.jsonl.gz','wt',encoding='utf8')
    c.emit(out,'BUILD_RUNTIME',0,total,status='RUNNING',synthetic_only=synthetic)
    runtime=build_runtime(recipe,synthetic)
    for (cid,) in db.execute('select distinct capture from targets order by capture').fetchall():
        spec=catalog[cid]; raw_before=None
        if not synthetic:
            source=Path(spec['path']);c.require(source.stat().st_size==spec['bytes'],'RAW_BYTES');c.pin(source,spec['sha256'])
            raw_before=(source.stat().st_size,source.stat().st_mtime_ns)
        entries=db.execute('select role,idx,uid,body from targets where capture=? order by frame',(cid,)).fetchall()
        targets=[json.loads(e[3]) for e in entries];slots={e[2]:(e[0],e[1]) for e in entries};del entries
        target_by_frame={t['frame']:t for t in targets}
        packet_counter=[0];last_progress=[time.monotonic()]
        def source_rows():
            iterator=iter(fixture['rows'][cid]) if synthetic else prep.decoded_rows(spec,out/(cid+'.stderr.log'))
            for row in iterator:
                packet_counter[0]+=1
                target=target_by_frame.get(packet_counter[0])
                if target is not None:
                    owner=target['owner'];inbound=row.get('eth.dst','').lower()==owner;outbound=row.get('eth.src','').lower()==owner
                    direction='inbound' if inbound and not outbound else 'outbound' if outbound and not inbound else 'ambiguous'
                    prefix='tcp.' if target['protocol']==6 else 'udp.'
                    port=prep.old.number(row.get(prefix+('dstport' if inbound else 'srcport')))
                    role,ix=slots[target['uid']]
                    annotations.write(json.dumps(dict(role=role,index=ix,uid=target['uid'],report_direction=direction,report_local_port=port))+'\n')
                if time.monotonic()-last_progress[0]>10:
                    c.emit(out,'FEATURES',done,total,status='RUNNING',capture=cid,packets=packet_counter[0],capture_packets=spec['expected_packets'])
                    last_progress[0]=time.monotonic()
                yield row
        queue=[];uids=[]
        def flush():
            nonlocal done
            if not queue:return
            values=feature_batch(runtime,queue)
            for uid,value in zip(uids,values):
                role,ix=slots[uid];c.require(not written[role][ix],'FEATURE_DUPLICATE')
                arrays[role][ix]=value;written[role][ix]=True;done+=1
            queue.clear();uids.clear()
        for uid,flow in adapter.selected_flows(source_rows(),targets,spec,[d['mac'] for d in devices],runtime['event'],runtime['prefix'],runtime['translator']):
            queue.append(flow);uids.append(uid)
            if len(queue)==16:flush()
        flush();c.require(packet_counter[0]==spec['expected_packets'],'PACKET_COUNT_DRIFT')
        if not synthetic:c.require(raw_before==(source.stat().st_size,source.stat().st_mtime_ns),'RAW_CHANGED_DURING_DECODE')
        c.emit(out,'FEATURES',done,total,status='RUNNING',capture=cid,synthetic_only=synthetic)
    annotations.close();db.close();del runtime
    for role,array in arrays.items():
        c.require(bool(written[role].all()),'FEATURE_COVERAGE');array.flush()
        paths[role].update(features=role+'.npy',features_sha256=c.sha(out/(role+'.npy')))
    arrays.clear()
    descriptor=dict(status='COMPLETE',stage=stage,recipe_digest=c.digest(recipe),roles=paths,rows=total,annotations_sha256=c.sha(out/'report_annotations.jsonl.gz'),synthetic_only=synthetic,models='stand-in' if synthetic else 'frozen E3')
    c.atomic_json(out/'cache.json',descriptor);c.emit(out,'FEATURES_COMPLETE',done,total,status='COMPLETE',synthetic_only=synthetic);c.seal(out)
    return descriptor
def load_cache(folder,role,recipe_digest):
    folder=Path(folder);c.verify_seal(folder);meta=c.load(folder/'cache.json')
    c.require(meta['status']=='COMPLETE' and meta['recipe_digest']==recipe_digest,'CACHE_RECIPE')
    c.require(role in meta['roles'],'CACHE_ROLE_UNAVAILABLE');part=meta['roles'][role]
    source=c.confined(folder,part['metadata']);c.pin(source,part['metadata_sha256'])
    metadata=[{k:v for k,v in row.items() if k in COMPACT} for row in c.rows(source)]
    c.require(len(metadata)==part['rows'] and c.uid_sha(r['uid'] for r in metadata)==part['uid_sha256'],'CACHE_UIDS')
    path=c.confined(folder,part['features']);c.pin(path,part['features_sha256']);features=np.load(path,mmap_mode='r',allow_pickle=False)
    c.require(features.shape==(len(metadata),768) and features.dtype==np.float32,'CACHE_FEATURE_SCHEMA')
    annotation=folder/'report_annotations.jsonl.gz';c.pin(annotation,meta['annotations_sha256'])
    count=0
    for a in c.rows(annotation):
        if a['role']!=role:continue
        row=metadata[a['index']];c.require(row['uid']==a['uid'],'REPORT_ANNOTATION_UID')
        c.require('report_direction' not in row,'REPORT_ANNOTATION_DUPLICATE')
        row.update(report_direction=a['report_direction'],report_local_port=a['report_local_port']);count+=1
    c.require(count==len(metadata),'REPORT_ANNOTATION_COVERAGE')
    return features,metadata
def load_state(recipe,fixture=None):
    path=Path(fixture['state']) if fixture else c.confined(c.ROOT,recipe['legacy']['probe_state_path'])
    c.pin(path,fixture['state_sha256'] if fixture else recipe['legacy']['probe_state_sha256'])
    with np.load(path,allow_pickle=False) as source:
        c.require(set(c.STATE_KEYS)<=set(source.files),'STATE_MISSING_KEYS')
        return {k:source[k].copy() for k in c.STATE_KEYS}

