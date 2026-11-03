"""Capture-aligned parallel preparation; immutable scientific workers are reused."""
from __future__ import annotations
import copy,gzip,json,shutil
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import legacy_reference_executor_common_v1 as c

def source_rows(recipe,role):
    c.require(role in ('LEARN','DEV','REFERENCE'),'DEV_ONLY_ROLE_BEFORE_OPEN')
    meta=recipe['data']['manifests'][role]
    path=c.confined(c.ROOT,meta['path']);c.pin(path,meta['sha256'])
    values=list(c.rows(path))
    c.require(len(values)==meta['rows'] and c.uid_sha(x['uid'] for x in values)==meta['sorted_uid_lines_sha256'],'SOURCE_MANIFEST_IDENTITY')
    if role=='REFERENCE':values=[x for x in values if x['partition'] in ('LEARN','DEV')]
    else:c.require(role in ('LEARN','DEV') and all(x['partition']==role and x['use']!='REFERENCE' for x in values),'DEV_ONLY')
    c.require(len({x['uid'] for x in values})==len(values),'DUPLICATE_SOURCE_UID')
    return values

def plan(recipe,out,workers):
    c.require(1<=workers<=8,'WORKER_LIMIT');out=Path(out);out.mkdir(exist_ok=False)
    rows={role:source_rows(recipe,role) for role in ('REFERENCE','LEARN','DEV')}
    counts=defaultdict(Counter)
    for role in ('LEARN','DEV'):
        for row in rows[role]:counts[row['capture_id']][role]+=1
    c.require(not {x['capture_id'] for x in rows['REFERENCE']}&set(counts),'REFERENCE_QUERY_SHARED_CAPTURE_UNSUPPORTED')
    assigned={};loads=[Counter() for _ in range(workers)]
    # DEV-first makes every shard evaluable; complete capture files are indivisible.
    for has_dev in (True,False):
        ids=sorted((cid for cid,v in counts.items() if bool(v['DEV'])==has_dev),key=lambda cid:(-sum(counts[cid].values()),cid))
        for cid in ids:
            role='DEV' if has_dev else 'LEARN'
            ix=min(range(workers),key=lambda i:(loads[i][role],sum(loads[i].values()),i))
            assigned[cid]=ix;loads[ix].update(counts[cid])
    c.require(all(v['LEARN']>0 and v['DEV']>0 for v in loads),'EMPTY_SHARD_ROLE')
    shard_recipes=[]
    for ix in range(workers):
        folder=out/('shard_'+str(ix));folder.mkdir();r=copy.deepcopy(recipe)
        for role in ('LEARN','DEV'):
            values=[x for x in rows[role] if assigned[x['capture_id']]==ix]
            path=folder/(role+'.jsonl.gz')
            with gzip.open(path,'wt',encoding='utf8') as f:
                for row in values:f.write(json.dumps(row,separators=(',',':'))+'\n')
            r['data']['manifests'][role]=dict(path=str(path.resolve()),sha256=c.sha(path),rows=len(values),sorted_uid_lines_sha256=c.uid_sha(x['uid'] for x in values))
        c.atomic_json(folder/'recipe.json',r);shard_recipes.append(str((folder/'recipe.json').resolve()))
    result=dict(status='COMPLETE',workers=workers,full_recipe_digest=c.digest(recipe),capture_assignment=assigned,loads=[dict(v) for v in loads],shard_recipes=shard_recipes,
                reference_query_captures_disjoint=True,reference_repeated_identically=True,holdout_materialized=False)
    c.atomic_json(out/'plan.json',result);c.seal(out);return result

def merge(recipe,plan_dir,shards,out):
    c.verify_seal(plan_dir);p=c.load(Path(plan_dir)/'plan.json')
    c.require(p['full_recipe_digest']==c.digest(recipe) and len(shards)==p['workers'],'MERGE_PLAN')
    expected={role:source_rows(recipe,role) for role in ('REFERENCE','LEARN','DEV')}
    out=Path(out);out.mkdir(exist_ok=False)
    maps={role:{x['uid']:i for i,x in enumerate(rows)} for role,rows in expected.items()}
    arrays={role:np.lib.format.open_memmap(out/(role+'.npy'),mode='w+',dtype=np.float32,shape=(len(rows),768)) for role,rows in expected.items()}
    written={role:np.zeros(len(rows),dtype=bool) for role,rows in expected.items()};ann_seen={};parts={}
    with gzip.open(out/'report_annotations.jsonl.gz','wt',encoding='utf8') as annotations:
        for shard_ix,shard in enumerate(shards):
            shard=Path(shard);c.verify_seal(shard);meta=c.load(shard/'cache.json');sr=c.load(p['shard_recipes'][shard_ix])
            c.require(meta['status']=='COMPLETE' and meta['stage']=='LEARN_DEV' and meta['recipe_digest']==c.digest(sr),'SHARD_IDENTITY')
            # Only manifest partitioning is permitted in a shard recipe.
            a=copy.deepcopy(sr);b=copy.deepcopy(recipe)
            a['data']['manifests']=b['data']['manifests'];c.require(a==b,'SHARD_SCIENCE_DRIFT')
            local={}
            for role in ('REFERENCE','LEARN','DEV'):
                part=meta['roles'][role];rows=list(c.rows(shard/part['metadata']));local[role]=rows
                c.require(len(rows)==part['rows'] and c.uid_sha(x['uid'] for x in rows)==part['uid_sha256'],'SHARD_UIDS')
                values=np.load(shard/part['features'],mmap_mode='r',allow_pickle=False)
                c.require(values.shape==(len(rows),768) and values.dtype==np.float32,'SHARD_SHAPE')
                for start in range(0,len(rows),4096):
                    block=rows[start:start+4096];ix=np.array([maps[role].get(x['uid'],-1) for x in block])
                    c.require(bool((ix>=0).all()),'UNEXPECTED_SHARD_UID')
                    c.require(all(x==expected[role][int(i)] for x,i in zip(block,ix)),'SHARD_METADATA_CHANGED')
                    batch=np.asarray(values[start:start+len(block)]);c.require(bool(np.isfinite(batch).all()),'SHARD_NONFINITE')
                    if role=='REFERENCE' and shard_ix:
                        c.require(np.array_equal(arrays[role][ix],batch),'REFERENCE_RECOMPUTATION_DRIFT')
                    else:
                        c.require(not bool(written[role][ix].any()),'DUPLICATE_SHARD_UID')
                        if role!='REFERENCE':c.require(all(p['capture_assignment'][x['capture_id']]==shard_ix for x in block),'WRONG_CAPTURE_SHARD')
                        arrays[role][ix]=batch;written[role][ix]=True
            for record in c.rows(shard/'report_annotations.jsonl.gz'):
                role=record['role'];row=local[role][record['index']]
                c.require(row['uid']==record['uid'],'SHARD_ANNOTATION_IDENTITY')
                fixed=dict(record,index=maps[role][record['uid']]);key=(role,record['uid'])
                if key in ann_seen:c.require(role=='REFERENCE' and ann_seen[key]==fixed,'DUPLICATE_ANNOTATION')
                else:ann_seen[key]=fixed;annotations.write(json.dumps(fixed)+'\n')
    for role,rows in expected.items():
        c.require(bool(written[role].all()),'MERGE_MISSING_UID');arrays[role].flush()
        path=out/(role+'.rows.jsonl.gz')
        with gzip.open(path,'wt',encoding='utf8') as f:
            for row in rows:f.write(json.dumps(row,separators=(',',':'))+'\n')
        parts[role]=dict(rows=len(rows),uid_sha256=c.uid_sha(x['uid'] for x in rows),metadata=path.name,metadata_sha256=c.sha(path),features=role+'.npy',features_sha256=c.sha(out/(role+'.npy')))
    total=sum(len(v) for v in expected.values());c.require(len(ann_seen)==total,'MERGE_ANNOTATION_COVERAGE')
    result=dict(status='COMPLETE',stage='LEARN_DEV',recipe_digest=c.digest(recipe),roles=parts,rows=total,annotations_sha256=c.sha(out/'report_annotations.jsonl.gz'),synthetic_only=bool(recipe.get('synthetic_only')),models='frozen E3; full capture shards',parallel_workers=len(shards))
    c.atomic_json(out/'cache.json',result);c.emit(out,'FEATURES_COMPLETE',total,total,status='COMPLETE');c.seal(out);return result
