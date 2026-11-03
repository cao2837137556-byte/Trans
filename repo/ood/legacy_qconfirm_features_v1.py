"""Whole-capture feature shards with unchanged causal input adapter."""
from pathlib import Path
from collections import defaultdict
import numpy as np
import legacy_qref_common_v1 as c
from legacy_qconfirm_common_v1 import dump_rows

def partition(rows,refs,catalog,workers):
    by=defaultdict(list)
    for r in refs+rows:by[r['capture_id']].append(r)
    c.require(1<=workers<=8 and set(by)<=set(catalog),'CAPTURE_PLAN')
    loads=[0]*workers;groups=[[] for _ in loads]
    for cid in sorted(by,key=lambda k:(-len(by[k]),k)):
        ix=min(range(workers),key=lambda j:(loads[j],j));groups[ix].append(cid);loads[ix]+=len(by[cid])
    return [dict(captures=ids,targets=[r for cid in ids for r in by[cid]]) for ids in groups if ids]

def materialize(task,catalog,known_macs,runtime,out,progress,decoder=None):
    import legacy_reference_sample_prepare_v1 as prep
    import legacy_reference_feature_adapter_v1 as adapter
    import legacy_reference_executor_features_v1 as features
    out=Path(out);targets=task['targets'];c.require(bool(targets),'EMPTY_SHARD')
    index={r['uid']:i for i,r in enumerate(targets)};c.require(len(index)==len(targets),'DUPLICATE_SHARD_UID')
    arr=np.lib.format.open_memmap(out/'features.npy',mode='w+',dtype=np.float32,shape=(len(targets),768))
    seen=np.zeros(len(targets),bool);annotations=[]
    progress.begin('E3_FEATURES',len(targets))
    for cid in task['captures']:
        spec=catalog[cid];rr=[r for r in targets if r['capture_id']==cid]
        if decoder is None:
            p=Path(spec['path']);c.require(p.stat().st_size==spec['bytes'],'RAW_BYTES');c.pin(p,spec['sha256'])
            before=(p.stat().st_size,p.stat().st_mtime_ns)
        slots={r['frame']:r for r in rr};count=[0]
        def records():
            source=decoder(spec) if decoder else prep.decoded_rows(spec,out/(cid+'.stderr.log'))
            for row in source:
                count[0]+=1
                target=slots.get(count[0])
                if target:
                    owner=target['owner'];inside=row.get('eth.dst','').lower()==owner;outside=row.get('eth.src','').lower()==owner
                    direction='inbound' if inside and not outside else 'outbound' if outside and not inside else 'ambiguous'
                    prefix='tcp.' if target['protocol']==6 else 'udp.'
                    port=prep.old.number(row.get(prefix+('dstport' if inside else 'srcport')))
                    annotations.append(dict(uid=target['uid'],report_direction=direction,report_local_port=port))
                if count[0]%4096==0:
                    progress.guard();progress.emit(capture=cid,packets=count[0],capture_packets=spec['expected_packets'],feature_rows_done=int(seen.sum()))
                yield row
        queue=[];uids=[]
        def flush():
            if not queue:return
            batch=features.feature_batch(runtime,queue);ix=np.array([index[u] for u in uids])
            c.require(not bool(seen[ix].any()),'DUPLICATE_FEATURE')
            arr[ix]=batch;seen[ix]=True;queue.clear();uids.clear()
            progress.work_done=int(seen.sum())-1;progress.tick(capture=cid)
        for uid,flow in adapter.selected_flows(records(),rr,spec,known_macs,runtime['event'],runtime['prefix'],runtime['translator']):
            queue.append(flow);uids.append(uid)
            if len(queue)==16:flush()
        flush();c.require(count[0]==spec['expected_packets'],'PACKET_COUNT')
        if decoder is None:c.require(before==(p.stat().st_size,p.stat().st_mtime_ns),'RAW_CHANGED')
    c.require(bool(seen.all()) and len(annotations)==len(targets),'FEATURE_COVERAGE')
    arr.flush();del arr;dump_rows(out/'rows.jsonl.gz',targets);dump_rows(out/'annotations.jsonl.gz',annotations)
    c.write(out/'cache.json',dict(status='COMPLETE',rows=len(targets),uid_sha256=c.uid_sha(index),features_sha256=c.sha(out/'features.npy')))
    progress.finish('COMPLETE',synthetic_only=decoder is not None);c.seal(out)

def merge(shards,rows,refs,out,progress):
    out=Path(out);out.mkdir(exist_ok=False);allrows=refs+rows
    idx={r['uid']:i for i,r in enumerate(allrows)};c.require(len(idx)==len(allrows),'MERGE_UIDS')
    arrays=np.lib.format.open_memmap(out/'features.npy',mode='w+',dtype=np.float32,shape=(len(allrows),768));seen=np.zeros(len(allrows),bool)
    annotations=[];progress.begin('MERGE',len(shards))
    for shard in shards:
        shard=Path(shard);c.verify(shard);rr=c.rows(shard/'rows.jsonl.gz');meta=c.read(shard/'cache.json')
        c.require(meta['status']=='COMPLETE' and len(rr)==meta['rows'] and c.uid_sha(r['uid'] for r in rr)==meta['uid_sha256'],'SHARD_IDENTITY')
        arr=np.load(c.pin(shard/'features.npy',meta['features_sha256']),allow_pickle=False,mmap_mode='r')
        c.require(arr.shape==(len(rr),768) and arr.dtype==np.float32,'FEATURE_SCHEMA')
        ix=np.array([idx.get(r['uid'],-1) for r in rr]);c.require(bool((ix>=0).all()),'UNEXPECTED_UID')
        c.require(not bool(seen[ix].any()) and len(set(ix))==len(ix),'DUPLICATE_MERGE')
        c.require(all(r==allrows[int(i)] for r,i in zip(rr,ix)) and bool(np.isfinite(arr).all()),'MERGE_METADATA_OR_FINITE')
        arrays[ix]=arr;seen[ix]=True;annotations.extend(c.rows(shard/'annotations.jsonl.gz'));progress.tick()
    c.require(bool(seen.all()),'MERGE_MISSING_UID')
    c.require(len(annotations)==len(allrows) and {a['uid'] for a in annotations}==set(idx),'ANNOTATION_COVERAGE')
    arrays.flush();del arrays;dump_rows(out/'rows.jsonl.gz',allrows);dump_rows(out/'annotations.jsonl.gz',annotations)
    c.write(out/'cache.json',dict(rows=len(allrows),reference_rows=len(refs),features_sha256=c.sha(out/'features.npy'),status='COMPLETE'))
    c.seal(out);return np.load(out/'features.npy',mmap_mode='r',allow_pickle=False)
