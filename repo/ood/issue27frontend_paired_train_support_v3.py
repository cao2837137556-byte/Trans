"""Frozen paired experiment metadata and accounting; no numeric imports/I/O."""
import math
from collections import defaultdict
from pathlib import Path
import issue27frontend_paired_metadata_v1 as meta
from issue27frontend_paired_metadata_io_fix_v3 import atomic_json

ROOT = meta.ROOT
PACKAGE = 'runs/frontend_paired_train_implementation_v3_20260910'
PREP = 'runs/frontend_paired_train_preparation_v3_20260910'
REAL = 'runs/frontend_paired_train_v3_20260910'
MEMBERSHIP = 'runs/frontend_paired_metadata_v3_20260909'
MEMBERSHIP_SHA = 'd9be8cfc181d25cd5ad64e8a66fd4a7491f2af31af4ae60d21c2a8e7a8e8d152'
PLAN_SHA = '2d17743edeab5d51751e9d95c308a414c3763934921e917fc2ab97c495e2e5ef'
PREP_AUTH = 'I_AUTHORIZE_ONE_PAIRED_FEATURE_PREPARATION'
TRAIN_AUTH = 'I_AUTHORIZE_ONE_PAIRED_A_AB_TRAINING_AND_TERMINAL_CHECK'
CAPS = dict(wall_seconds=14400, memory_bytes=8*1024**3, output_bytes=512*1024**2,
            reserve_bytes=1024**2, controller_reserve_bytes=512*1024**2)
PREP_CAPS = dict(CAPS, wall_seconds=1800, output_bytes=256*1024**2)
require, Stop = meta.require, meta.Stop
canonical, digest, sha_file = meta.canonical, meta.digest, meta.sha_file
read_json, read_csv, seal, verify_manifest = meta.read_json, meta.read_csv, meta.seal, meta.verify_manifest


def order(keys, epoch, owner):
    return sorted(keys, key=lambda k: (digest(canonical(['paired-order-v1',2705,epoch,owner,k])), k))


def buckets(keys, steps):
    q, r = divmod(len(keys), steps)
    start = 0
    for i in range(steps):
        n = q + (i < r)
        yield keys[start:start+n]
        start += n
    require(start == len(keys), 'BUCKET_CONSERVATION')


def views(contexts, role, owners):
    result = []
    for c in contexts:
        if c['role'] != role: continue
        ts = [t for t in c['targets'] if t['owner'] in owners]
        if ts:
            result.append({**c, 'targets': ts, 'length': max(t['event'] for t in ts)+1})
    return sorted(result, key=lambda c: c['key'])


def charges(batch):
    return {'events': sum(c['length'] for c in batch),
            'padded_slots': len(batch)*max((c['length'] for c in batch), default=0),
            'targets': sum(len(c['targets']) for c in batch), 'contexts':len(batch)}


def exact_accounting(contexts):
    groups = {g:views(contexts,'train',g) for g in ('A','B')}
    n = {g:len(v) for g,v in groups.items()}
    require(all(n.values()), 'EMPTY_TRAIN_OWNER')
    steps = (n['A']+31)//32
    totals = dict(events=0,padded_slots=0,targets=0,contexts=0)
    hashes=[]
    for epoch in range(1,41):
        entry={'epoch':epoch}
        for g,cs in groups.items():
            mapping={c['key']:c for c in cs}; keys=order(mapping,epoch,g)
            entry[g+'_order_sha256']=digest(canonical(keys))
            for bucket in buckets(keys,steps):
                for j in range(0,len(bucket),32):
                    ch=charges([mapping[k] for k in bucket[j:j+32]])
                    for k,v in ch.items():totals[k]+=v*(2 if g=='A' else 1)
        hashes.append(entry)
    post=dict(events=0,padded_slots=0,targets=0,contexts=0)
    for arm in ('A','AB'):
        for role in ('train','check'):
            cs=views(contexts,role,arm if role=='train' else 'AB')
            for j in range(0,len(cs),32):
                for k,v in charges(cs[j:j+32]).items():post[k]+=v
    return {'N_A':n['A'],'N_B':n['B'],'steps_per_epoch':steps,'updates_per_arm':40*steps,
            'epoch_order_hashes':hashes,'training':totals,'postfit_check':post,
            'total':{k:totals[k]+post[k] for k in totals}}


def qualify_plan(membership, lawful, index, audits, outer, outer_receipts):
    """Join only already-lawful metadata; no old model scores are opened."""
    law={r['uid']:r for r in lawful}; au={r['uid']:r for r in audits}
    require(len(law)==len(lawful) and len(au)==len(audits), 'DUPLICATE_INPUT_UID')
    sources={}; offset=0
    for c in index:
        key=c['context_key'];require(key not in sources,'DUPLICATE_CONTEXT')
        sources[key]=dict(source='parent',offset=int(c['event_offset'])*524,length=int(c['event_count']))
    ot={t['uid']:(c,t) for c in outer for t in c['targets']}
    receipts={r['uid']:r for r in outer_receipts}
    require(set(ot)==set(receipts) and len(receipts)==len(outer_receipts),'OUTER_RECEIPTS')
    for c in outer:
        require(c['key'] not in sources,'SOURCE_CONTEXT_OVERLAP')
        sources[c['key']]=dict(source='outer',offset=offset,length=c['length'])
        offset+=c['length']*524
    grouped=defaultdict(list);seen=set()
    for row in membership:
        t=dict(row)
        require(t['uid'] in law and t['uid'] not in seen,'MEMBERSHIP_UID')
        seen.add(t['uid']); old=law[t['uid']]
        for key in ('context_key','source_group','member','owner','label','attack_family','device_family','event_index','context_events','history'):
            require(str(t[key])==str(old[key]),'LAWFUL_JOIN_'+key)
        kind=old['teacher_kind'];owner=t['owner'];label=int(t['label'])
        require((owner=='A' and ((label==1 and kind=='attack_hard') or
                (label==0 and kind in ('benign_normal','benign_hard')))) or
                (owner=='B' and kind=='none'), 'OLD_VERDICT_LINEAGE')
        if t['uid'] in au:
            a=au[t['uid']]
            for key in ('context_key','event_index','source_group','owner','label','teacher_kind'):
                require(str(a[key])==str(old[key]),'F4_UID_JOIN_'+key)
            require(a['roundtrip_exact'].lower()=='true' and a['finite'].lower()=='true' and int(a['feature_width'])==131,'F4_RECEIPT')
            prefix=a['feature_prefix_sha256']
        else:
            require(t['uid'] in ot,'MISSING_SOURCE_TARGET');oc,a=ot[t['uid']]
            require(oc['key']==t['context_key'] and a['event']==int(t['event_index']),'OUTER_EVENT_JOIN')
            for key in ('source_group','owner','label','teacher_kind'):
                require(str(a[key])==str(old[key]),'OUTER_UID_JOIN_'+key)
            rr=receipts[t['uid']]
            require(rr['context']==t['context_key'] and rr['event']==a['event'],'OUTER_PREFIX_JOIN')
            prefix=rr['feature_prefix_sha256']
        require(t['new_role'] in ('train','check'),'ROLE')
        t.update(label=label,event=int(t['event_index']),old_hard=(kind!='benign_normal') if owner=='A' else None,
                 teacher_kind=kind,feature_prefix_sha256=prefix)
        grouped[t['context_key']].append(t)
    require(seen==set(law)==set(au)|set(ot),'FULL_LAWFUL_CONSERVATION')
    contexts=[];cursor=0;component_roles={}
    for key,ts in sorted(grouped.items()):
        src=sources[key];roles={t['new_role'] for t in ts};components={t['component_id'] for t in ts}
        require(len(roles)==len(components)==1,'CONTEXT_SPLIT')
        role=next(iter(roles));component=next(iter(components))
        require(component_roles.setdefault(component,role)==role,'DEPENDENCY_SPLIT')
        require(len({t['event'] for t in ts})==len(ts),'DUPLICATE_EVENT')
        require(all(0<=t['event']<src['length']<=256 for t in ts),'PREFIX_BOUNDS')
        require(all(int(t['context_events'])==src['length'] for t in ts),'SOURCE_LENGTH')
        length=max(t['event'] for t in ts)+1
        contexts.append(dict(key=key,role=role,component=component,length=length,
                             source=src['source'],source_offset=src['offset'],offset=cursor,
                             targets=sorted(ts,key=lambda t:t['event'])))
        cursor+=length*524
    return {'contexts':contexts,'feature_bytes':cursor,'targets':len(seen),'accounting':exact_accounting(contexts)}
