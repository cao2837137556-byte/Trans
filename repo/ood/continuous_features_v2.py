"""Full causal reconstruction, provenance and exact-shape frozen E3 batches."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from collections import Counter, defaultdict
import numpy as np
import torch
import continuous_common_v2 as c
import continuous_audit_v2 as audit_api
from continuous_input_v2 import Contexts, verify_tokenized, digest
import legacy_reference_sample_prepare_v1 as prep
from legacy_unsw_archival_runtime_v1 import decode, e3_runtime


def tokenize(tokenizer, flow):
    encoded = tokenizer({k:[v] for k,v in flow.items()})
    return {k:v[0] for k,v in encoded.items()}


def tensor_hash(batch, i):
    value = hashlib.sha256()
    names = ('input_ids', 'attention_mask', 'direction', 'iats', 'bytes', 'pkt_count', 'protocol', 'dataset_burst_sizes')
    for key in names:
        arr = batch[key][i].contiguous().cpu().numpy()
        value.update(key.encode()+str(arr.dtype).encode()+str(arr.shape).encode()+arr.tobytes())
    seq = np.arange(batch['input_ids'].shape[1], dtype=np.int64)
    value.update(b'position_ids'+seq.tobytes())
    return value.hexdigest()


def verify_batch(examples,batch):
    """Prove exact padded model tokens/mask retain the already verified current header."""
    widths={max(e['dataset_burst_sizes'])+1 for e in examples}
    counts={len(e['dataset_burst_sizes']) for e in examples}
    c.require(len(widths)==len(counts)==1,'MIXED_SHAPE_REJECTED')
    width=next(iter(widths));count=next(iter(counts))
    c.require(tuple(batch['input_ids'].shape)==(len(examples),width*count),'PACKING_SHAPE')
    for i,example in enumerate(examples):
        for j,(tokens,mask) in enumerate(zip(example['input_ids'],example['attention_mask'])):
            start=j*width;length=len(tokens)
            c.require(batch['input_ids'][i,start:start+length].tolist()==tokens and
                      batch['attention_mask'][i,start:start+length].tolist()==mask,'PACKED_CURRENT_TOKEN')


def spool(root, out, metadata, specs, runtime, progress):
    out = Path(out); out.mkdir(exist_ok=False)
    _, _, _, tokenizer, _ = e3_runtime(root, synthetic=True)
    api = prep.old.legacy_runtime()
    db = sqlite3.connect(str(out/'snapshots.sqlite'))
    db.execute('CREATE TABLE snapshots(uid TEXT PRIMARY KEY,role TEXT,slot INTEGER,protocol INTEGER,width INTEGER,bursts INTEGER,batch_id INTEGER,body TEXT)')
    by_capture = defaultdict(dict)
    for role, rows in metadata.items():
        for i, row in enumerate(rows):
            c.require(row['frame'] not in by_capture[row['capture_id']], 'DUPLICATE_CAPTURE_TARGET')
            by_capture[row['capture_id']][row['frame']] = (role, i, row)
    support = Counter(); support_groups = defaultdict(set); completed = 0; capture_audits = []
    if runtime.get('synthetic_only', False):
        early, expected = {}, {}
        early_uids = set()
    else:
        preflight = out.parent/'anomaly_preflight'
        c.verify(preflight)
        early = c.read(preflight/'receipt.json')['summaries']
        expected = c.read(Path(root)/'frozen/anomaly_receipts.json')
        early_uids = set(audit_api.early_target_uids(metadata,c.read(Path(root)/'design_contract.json')))
    early_proofs = {}
    with gzip.open(out/'target_provenance.jsonl.gz', 'wt', encoding='utf-8') as prov:
        for spec in sorted(specs, key=lambda s:s['capture_id']):
            targets = by_capture[spec['capture_id']]; seen = set()
            known = runtime.get('external_known_macs' if spec.get('external') else 'source_known_macs',runtime['known_macs'])
            auditor = audit_api.CaptureAudit(spec, known, api, targets, out, expected.get(spec['capture_id']))
            contexts = auditor.contexts
            before = (Path(spec['path']).stat().st_size, Path(spec['path']).stat().st_mtime_ns)
            progress.stage = 'P_DECODE_'+spec['capture_id']
            count = 0
            from contextlib import closing
            with closing(auditor), decode(spec['path'], spec, api, progress, out/(spec['capture_id']+'.stderr.log'), runtime['tshark']) as source:
                for count, row in enumerate(source, 1):
                    owner, ns, event = auditor.append(row)
                    if count % 8192 == 0:
                        progress.tick(count, spec['expected_packets']); db.commit()
                    if count not in targets: continue
                    role, slot, t = targets[count]
                    c.require(ns is not None and owner == t['owner'] and prep.digest(ns) == t['session_id'], 'TARGET_SCOPE')
                    c.require(t['source_sha256'] == spec['sha256'] and t['capture_id'] == spec['capture_id'] and
                        t['uid'] == prep.digest([spec['sha256'], count, owner]) and t['timestamp'] == event.timestamp and t['protocol'] == event.ip_proto, 'TARGET_IDENTITY')
                    c.require((t['timestamp'] <= t['reference_end']) if t['use'] == 'REFERENCE' else (t['timestamp'] > t['reference_end']), 'REFERENCE_QUERY_TIME')
                    flow, state, provenance = contexts.states[ns].snapshot()
                    example = tokenize(tokenizer, flow)
                    location = verify_tokenized(flow, provenance, example)
                    width = max(example['dataset_burst_sizes']) + 1
                    body = dict(flow=flow, state=state, provenance=provenance)
                    if t['uid'] in early_uids:
                        early_proofs[t['uid']] = dict(body, current_token_location=location,
                            role=role, source_sha256=spec['sha256'])
                    db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,NULL,?)',
                               (t['uid'],role,slot,t['protocol'],width,len(flow['counts']),json.dumps(body,separators=(',',':'))))
                    prov.write(json.dumps(dict(uid=t['uid'],role=role,source_sha256=spec['sha256'],
                        input_version=provenance['version'], query_frame=count, query_time_ns=provenance['query_time_ns'],
                        namespace_sha256=provenance['namespace_sha256'],current_token_location=location,
                        retained_frames=[b['frames'] for b in provenance['bursts']],
                        episode_first_frame=provenance['episode_first_frame'],reset_reason=provenance['reset_reason'],
                        source_semantic_sha256=digest(dict(flow=flow,state=state))),separators=(',',':'))+'\n')
                    if role == 'LEARN' and t['fit_role'] == 'FIT':
                        if event.ip_proto == 6 and t['label'] == 0: support['normal_TCP'] += 1
                        if event.ip_proto == 6 and event.tcp_syn and not event.tcp_ack:
                            support['TCP_SYN_without_ACK'] += 1
                            for name,value in [('devices',t['device']),('components',t['component_id']),('captures',t['capture_id'])]:
                                support_groups['TCP_SYN_'+name].add(value)
                        if event.ip_proto == 6 and prep.old.number(row.get('tcp.len')) > 0: support['TCP_payload'] += 1
                        support['protocol_%d_label_%d' % (event.ip_proto,t['label'])] += 1
                        rate = np.expm1(state[12 if row.get('eth.dst','').lower()==owner else 0])
                        support['rate_'+('lt1' if rate < 1 else '1to10' if rate < 10 else 'ge10')] += 1
                    seen.add(t['uid']); completed += 1
            c.require(count == spec['expected_packets'] and len(seen) == len(targets), 'CAPTURE_COVERAGE')
            c.require(before == (Path(spec['path']).stat().st_size, Path(spec['path']).stat().st_mtime_ns), 'RAW_CHANGED_DURING_READ')
            summary = auditor.finish()
            if spec['capture_id'] in early: audit_api.reconcile(early[spec['capture_id']], summary)
            capture_audits.append(summary)
    c.require(completed == sum(map(len,metadata.values())), 'NEW_INPUT_DENOMINATOR')
    c.require(support['TCP_SYN_without_ACK'] and support['normal_TCP'], 'SOURCE_FIT_SUPPORT_MISSING')
    db.commit()
    db.execute('CREATE INDEX shape_uid ON snapshots(protocol,width,bursts,uid)')
    batch_id = 0; previous = None; offset = 0; updates = []
    for uid, proto, width, bursts in db.execute('SELECT uid,protocol,width,bursts FROM snapshots ORDER BY protocol,width,bursts,uid').fetchall():
        key = (proto,width,bursts)
        if key != previous or offset == 16:
            batch_id += 1; offset = 0; previous = key
        updates.append((batch_id-1,uid)); offset += 1
        if len(updates) == 4096:
            db.executemany('UPDATE snapshots SET batch_id=? WHERE uid=?',updates);updates=[]
    if updates: db.executemany('UPDATE snapshots SET batch_id=? WHERE uid=?',updates)
    db.execute('CREATE INDEX batch_uid ON snapshots(batch_id,uid)');db.commit();db.close()
    c.write(out/'support.json',dict(counts=dict(support),groups={k:sorted(v) for k,v in support_groups.items()}, sufficient_generalization_proven=False))
    c.write(out/'captures.json',capture_audits)
    c.require(set(early_proofs)==early_uids,'EARLY_TARGET_PROOF_COVERAGE')
    c.write(out/'early_target_proofs.json',early_proofs)
    c.write(out/'receipt.json',dict(status='COMPLETE',rows=completed,batches=batch_id,query_frame_to_token_verified=completed,real_E3_forwards=0))
    c.seal(out);c.verify(out)


def feature_worker(root, run, shard, explicit):
    design, runtime = c.authorize(root, explicit)
    root, run = Path(root), Path(run)
    c.require(c.read(run/'launch.json')['design_sha256'] == c.DESIGN_SHA, 'WORKER_LAUNCH')
    c.pin(run/'spool/snapshots.sqlite', c.read(run/'spool_pin.json')['sha256'])
    output = run/('features_worker_%02d' % shard)
    progress = c.Progress(output, runtime['limits']); progress.stage='P_E3_FEATURES'
    try:
        if not runtime.get('synthetic_only',False): c.pin(runtime['checkpoint'], runtime['checkpoint_sha256'])
        embed, translator, model, tokenizer, collator = e3_runtime(root)
        db = sqlite3.connect('file:'+str(run/'spool/snapshots.sqlite').replace('\\','/')+'?mode=ro', uri=True)
        batch_ids = [x[0] for x in db.execute('SELECT DISTINCT batch_id FROM snapshots WHERE batch_id % ? = ? ORDER BY batch_id',(runtime['feature_workers'],shard))]
        total = db.execute('SELECT COUNT(*) FROM snapshots WHERE batch_id % ? = ?',(runtime['feature_workers'],shard)).fetchone()[0]
        arrays=[]; slots=[]; roles=[]; uids=[]; block=0; done=0
        with gzip.open(output/'tensor_receipts.jsonl.gz','wt',encoding='utf-8') as receipts:
            def commit():
                nonlocal block
                if not arrays: return
                folder=output/('block_%06d'%block);folder.mkdir()
                c.save_arrays(folder/'values.npz',values=np.concatenate(arrays),slots=np.asarray(slots,dtype=np.int64),roles=np.asarray(roles),uids=np.asarray(uids))
                c.write(folder/'receipt.json',dict(rows=len(uids),uid_sha256=c.uid_sha(uids),design_sha256=c.DESIGN_SHA))
                c.seal(folder);c.verify(folder);arrays.clear();slots.clear();roles.clear();uids.clear();block+=1
            for bid in batch_ids:
                entries=db.execute('SELECT uid,role,slot,body FROM snapshots WHERE batch_id=? ORDER BY uid',(bid,)).fetchall()
                bodies=[json.loads(e[3]) for e in entries]
                examples=[tokenize(tokenizer,b['flow']) for b in bodies]
                for b,e in zip(bodies,examples):verify_tokenized(b['flow'],b['provenance'],e)
                shapes={(e['protocol'],max(e['dataset_burst_sizes'])+1,len(e['dataset_burst_sizes'])) for e in examples}
                c.require(len(shapes)==1 and len(entries)<=16,'EXACT_SHAPE_BATCH')
                batch=collator(examples)
                verify_batch(examples,batch)
                values=embed.core.e3_forward_batches(model,[batch],'cpu')
                c.require(values.shape==(len(entries),768) and values.dtype==np.float32 and np.isfinite(values).all(),'E3_SCHEMA')
                states=np.asarray([b['state'] for b in bodies],dtype=np.float32)
                arrays.append(np.concatenate((values,states),axis=1))
                for i,(uid,role,slot,_) in enumerate(entries):
                    slots.append(slot);roles.append(role);uids.append(uid)
                    receipts.write(json.dumps(dict(uid=uid,role=role,slot=slot,batch_id=bid,
                        actual_tensor_sha256=tensor_hash(batch,i),feature_sha256=hashlib.sha256(values[i].tobytes()).hexdigest(),
                        checkpoint_sha256=design['input']['checkpoint_sha256'],design_sha256=c.DESIGN_SHA),separators=(',',':'))+'\n')
                done+=len(entries)
                if len(uids)>=1024:commit()
                progress.tick(done,total)
            commit()
        db.close();c.require(done==total,'WORKER_COVERAGE')
        c.write(output/'receipt.json',dict(status='COMPLETE',rows=done,blocks=block,design_sha256=c.DESIGN_SHA,
            tensor_receipts_sha256=c.sha(output/'tensor_receipts.jsonl.gz'),
            package_sha256=c.sha(root/'SHA256SUMS') if (root/'SHA256SUMS').is_file() else 'SYNTHETIC',
            checkpoint_sha256=design['input']['checkpoint_sha256']))
        progress.stop('COMPLETE');c.seal(output)
    except BaseException as exc:
        progress.record_failure(exc,'feature_worker');progress.stop('STOPPED_NO_RETRY',error=repr(exc));raise


def merge_features(run, metadata, runtime):
    run=Path(run);out=run/'features';out.mkdir(exist_ok=False)
    arrays={role:np.lib.format.open_memmap(out/(role+'.npy'),mode='w+',dtype=np.float32,shape=(len(rr),794)) for role,rr in metadata.items()}
    seen={role:np.zeros(len(rr),dtype=bool) for role,rr in metadata.items()}
    for shard in range(runtime['feature_workers']):
        worker=run/('features_worker_%02d'%shard);c.verify(worker)
        receipt=c.read(worker/'receipt.json');c.require(receipt['status']=='COMPLETE','WORKER_NOT_COMPLETE')
        for block in range(receipt['blocks']):
            with np.load(worker/('block_%06d'%block)/'values.npz',allow_pickle=False) as values:
                for uid,role,slot,value in zip(values['uids'],values['roles'],values['slots'],values['values']):
                    slot=int(slot);role=str(role)
                    c.require(metadata[role][slot]['uid']==str(uid) and not seen[role][slot],'MERGE_UID_OR_DUPLICATE')
                    c.require(np.isfinite(value).all(),'MERGE_NONFINITE')
                    arrays[role][slot]=value;seen[role][slot]=True
    for role,array in arrays.items():
        c.require(seen[role].all(),'MERGE_MISSING_UID');array.flush()
        with (out/(role+'.npy')).open('r+b') as stream:os.fsync(stream.fileno())
    c.write(out/'receipt.json',dict(status='COMPLETE',rows=sum(map(len,metadata.values())),dimension=794,design_sha256=c.DESIGN_SHA))
    arrays.clear();c.seal(out);c.verify(out)
