"""Two-pass bounded F4 preparation, then one fixed AB inference; no fitting."""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
import os
import struct
import time
import traceback
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
import issue27frontend_expanded_eval_support_v1 as s
import issue27frontend_f0_zero_training_semantics_v1 as engine
import issue27frontend_f0_zero_training_semantics_real_v1 as zt
import issue27frontend_f1_d1_train_v1 as f1
import issue27frontend_f3_conflict_field_sufficiency_v1 as f3
import issue27frontend_f3_full_fit_l1_identifiability_v1 as f3b
import issue27frontend_f4_fieldwise_input_v1 as f4
import issue27frontend_paired_train_model_v1 as m
from issue27frontend_inheritance_outer_runner_v1 import decoder_rows


def key_route(route):
    return route.tier,route.base_key


def route_digest(route):
    return hashlib.sha256(engine.canonical_json_bytes([route.tier,route.base_key,route.orientation])).hexdigest()


def discover(decoded, targets, maximum):
    """Target routes only; all packets still advance first-seen endpoint tokens."""
    tokens=engine.EndpointTokens();last={};target_routes={};count=0
    for position,(raw,event) in enumerate(decoded):
        s.require(position<=maximum and event.packet_ordinal==position,'DISCOVERY_ORDINAL')
        count+=1;route=engine.classify_route(event,tokens)
        if position in targets:
            uid=targets[position]['uid']
            s.require(event.target_uid==uid and not engine._event_missing_reason(event),'DISCOVERY_TARGET_SEMANTICS')
            last[key_route(route)]=position;target_routes[uid]=route_digest(route)
    s.require(count==maximum+1 and len(target_routes)==len(targets),'DISCOVERY_CONSERVATION')
    return last,target_routes


def replay(decoded,targets,maximum,last,target_routes,emit):
    """Same F0/F3 state transitions; retain feature prefixes only for target routes.

    Discovery affects storage only. Epochs and endpoint token order are derived
    from the beginning of each source/member, including all intervening packets.
    Labels and reference outcomes are never passed into this function.
    """
    tokens=engine.EndpointTokens();states={};contexts={};epochs={};h4_current=None
    seen=set();count=0;peak=0;closed=set();emitted=0
    def finish(context):
        nonlocal emitted
        if context is not None and context['targets']:
            length=max(t['event'] for t in context['targets'])+1
            emit({'key':context['key'],'signatures':context['signatures'][:length],
                  'targets':context['targets'],'tier':context['tier']})
            emitted+=1
    for position,(raw,event) in enumerate(decoded):
        s.require(position<=maximum and event.packet_ordinal==position,'REPLAY_ORDINAL')
        count+=1;route=engine.classify_route(event,tokens);identity=key_route(route)
        if route.tier=='H4':
            if h4_current is not None and h4_current!=identity:
                states.pop(h4_current,None);finish(contexts.pop(h4_current,None))
            h4_current=identity
        state=states.get(identity);context=contexts.get(identity)
        active=identity in last and position<=last[identity] and identity not in closed
        missing=engine._event_missing_reason(event)
        if active and not missing:
            previous=state;previous_last=None if previous is None else float(previous.last_surrogate)
            state,next_epoch=engine.SemanticPrototype._append_or_split(route,state,epochs.get(identity,0),float(event.timestamp))
            epochs[identity]=next_epoch;states[identity]=state
            if previous is None or state is not previous:
                finish(context)
                key='%s\x1f%s\x1f%d'%(event.member_id,engine._context_id(event.source_id,event.member_id,state),state.epoch)
                context={'key':key,'signatures':[],'targets':[],'tier':route.tier};contexts[identity]=context
                delta=0.;regression=False
            else:
                s.require(context is not None and previous_last is not None,'LIVE_CONTEXT_ABSENT')
                delta=max(previous_last,float(event.timestamp))-previous_last
                regression=float(event.timestamp)<previous_last
            base=f1.canonical_signature(raw,event,route,engine._direction(route,state),delta,regression)
            context['signatures'].append(f3b.l1_signature(f3,base,raw,event,delta))
            s.require(len(context['signatures'])==state.event_count<=256,'CONTEXT_LENGTH')
        if position in targets:
            uid=targets[position]['uid']
            s.require(uid not in seen and event.target_uid==uid and not missing and active and context is not None,'REPLAY_TARGET')
            s.require(route_digest(route)==target_routes[uid],'DISCOVERY_REPLAY_ROUTE_DRIFT')
            context['targets'].append({'uid':uid,'event':len(context['signatures'])-1});seen.add(uid)
        if identity in last and position==last[identity]:
            states.pop(identity,None);finish(contexts.pop(identity,None));closed.add(identity)
        peak=max(peak,len(states))
    for context in contexts.values():finish(context)
    s.require(count==maximum+1 and seen=={t['uid'] for t in targets.values()},'REPLAY_CONSERVATION')
    s.require(not states,'ACTIVE_CONTEXTS_AFTER_LAST_TARGET')
    return {'packets':count,'targets':len(seen),'contexts':emitted,'peak_live_target_routes':peak}


@lru_cache(maxsize=65536)
def event_bytes(signature):
    return f4.encode_event(f4.parse_l1(signature)).astype('<f4',copy=False).tobytes()


def feature_payload(signatures):
    s.require(1<=len(signatures)<=256,'FEATURE_CONTEXT_LENGTH')
    return b''.join(event_bytes(x) for x in signatures)


def prefix_hash(raw,event):
    return hashlib.sha256(b'F4_INPUT_V1\0'+struct.pack('<II',event+1,131)+raw[:(event+1)*524]).hexdigest()


class Progress:
    def __init__(self,out,start,config):
        self.out,self.start,self.config=out,start,config;self.last=0
        self.data={'status':'STARTING','targets_total':262050,'targets_complete':0,'members_total':40,
                   'members_complete':0,'decoder_packets':0,'decoder_packets_total':46297382,'retries':0}
    def check(self,force=False,**values):
        self.data.update(values);now=time.monotonic()
        s.require(now-self.start<self.config['caps']['wall_seconds']-5,'WORKER_WALL_CAP')
        if force or now-self.last>=2:
            self.last=now
            s.atomic_json(self.out/'progress.json',{**self.data,'elapsed_seconds':now-self.start,'updated_unix':time.time()})


def decoded_member(member,config,targets,progress,pass_name,base_count):
    st=Path(member['container']).stat()
    s.require(st.st_size==config['archive_bytes'] and st.st_mtime_ns==config['archive_mtime_ns'],'ARCHIVE_CHANGED_DURING_RUN')
    identity={'dataset_kind':'gotham_zip','container_path':member['container'],
              'raw_source_path':member['member'],'member_uncompressed_bytes_if_archive':member['member_bytes'],
              'member_crc32_if_archive':member['member_crc32']}
    fields=list(zt.TSHARK_FIELDS)+['tcp.flags','tcp.len','udp.length']
    source=decoder_rows(config['tshark']['executable_path'],identity,member['packets'],fields,progress.check)
    try:
        for position,raw in enumerate(source):
            target=targets.get(position)
            event=zt.raw_to_event(engine,raw,member['source_group'],member['member'],position,None if target is None else target['uid'])
            if position%4000==0:
                progress.check(status=pass_name,member=member['member'],member_packets=position,
                               member_packets_total=member['packets'],decoder_packets=base_count+position)
            yield raw,event
    finally:source.close()


def prepare(config,metadata,out,progress):
    members_dir=out/'members';members_dir.mkdir();by_member=defaultdict(list)
    for t in metadata:by_member[t['member_id']].append(t)
    receipts=[];packets=0;total_targets=0;total_contexts=0;total_bytes=0
    for i,member in enumerate(config['members']):
        rows=by_member[member['id']]
        targets={r['position']:{'uid':r['uid']} for r in rows}
        s.require(len(targets)==member['targets'],'MEMBER_TARGETS')
        maximum=member['packets']-1
        progress.check(True,status='DISCOVERING_TARGET_ROUTES',members_complete=i,member=member['member'])
        first=decoded_member(member,config,targets,progress,'DISCOVERING_TARGET_ROUTES',packets)
        try:last,route_by_uid=discover(first,targets,maximum)
        finally:first.close()
        packets+=member['packets']
        folder=members_dir/member['id'];folder.mkdir();offset=0;feature_sha=hashlib.sha256();index_count=0
        with (folder/'features.f32le').open('xb') as features,gzip.open(folder/'contexts.jsonl.gz','wt',encoding='utf-8',newline='\n') as index:
            def emit(c):
                nonlocal offset,index_count,total_bytes
                raw=feature_payload(c['signatures']);s.require(features.tell()==offset,'FEATURE_OFFSET')
                features.write(raw);feature_sha.update(raw)
                ts=[{**t,'feature_prefix_sha256':prefix_hash(raw,t['event'])} for t in c['targets']]
                entry={'key':c['key'],'tier':c['tier'],'length':len(c['signatures']),'offset':offset,'targets':ts}
                index.write(json.dumps(entry,ensure_ascii=False,separators=(',',':'))+'\n')
                offset+=len(raw);total_bytes+=len(raw);index_count+=1
                s.require(total_bytes<config['caps']['output_bytes']-1024**3,'FEATURE_OUTPUT_CAP')
            second=decoded_member(member,config,targets,progress,'MATERIALIZING_F4_PREFIXES',packets)
            try:counts=replay(second,targets,maximum,last,route_by_uid,emit)
            finally:second.close()
        packets+=member['packets'];total_targets+=counts['targets'];total_contexts+=counts['contexts']
        s.require(index_count==counts['contexts'],'CONTEXT_OUTPUT_COUNT')
        event_bytes.cache_clear()
        receipt={**counts,'member_id':member['id'],'member':member['member'],'feature_bytes':offset,
                 'features_sha256':feature_sha.hexdigest(),'contexts_sha256':s.sha_file(folder/'contexts.jsonl.gz'),
                 'target_route_count':len(last),'passes':2}
        s.atomic_json(folder/'receipt.json',receipt);receipts.append(receipt)
        progress.check(True,status='MATERIALIZING_F4_PREFIXES',members_complete=i+1,decoder_packets=packets,
                       prepared_targets=total_targets,prepared_contexts=total_contexts,feature_bytes=total_bytes)
        del last,route_by_uid
    s.require(total_targets==262050 and packets==46297382,'PREPARATION_COUNTS')
    result={'status':'ALL_F4_INPUTS_PREPARED','targets':total_targets,'contexts':total_contexts,
            'feature_bytes':total_bytes,'decoder_packets':packets,'decoder_calls':80,'members':receipts,
            'model_forwards':0,'optimizer_steps':0}
    s.atomic_json(out/'preparation_receipt.json',result)
    return result


def load_target_metadata():
    rows=[]
    for r in s.read_csv(s.PACKAGE/'targets.csv.gz'):
        for k in ('label','position','old_hard','old_missing'):r[k]=int(r[k])
        for k in ('uid_in_ab_train','uid_in_ab_check','member_in_ab_train','member_in_ab_check'):r[k]=bool(s.boolean(r[k]))
        rows.append(r)
    s.validate_targets(rows);return rows


def infer_prepared(config,metadata,prepared,out,progress):
    # All member inputs are complete before the first real candidate load/forward.
    progress.check(True,status='VERIFYING_PREPARED_INPUTS')
    contexts=[]
    for receipt in prepared['members']:
        folder=out/'members'/receipt['member_id']
        s.require(s.sha_file(folder/'features.f32le',progress.check)==receipt['features_sha256'],'PREPARED_FEATURE_SHA')
        s.require(s.sha_file(folder/'contexts.jsonl.gz')==receipt['contexts_sha256'],'PREPARED_INDEX_SHA')
        offset=0
        with gzip.open(folder/'contexts.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                c=json.loads(line);s.require(c['offset']==offset,'PREPARED_LAYOUT')
                offset+=c['length']*524;c['member_id']=receipt['member_id'];contexts.append(c)
        s.require(offset==receipt['feature_bytes'],'PREPARED_BYTE_COUNT')
    contexts.sort(key=lambda c:c['key'])
    s.require(len(contexts)==prepared['contexts']==len({c['key'] for c in contexts}),'PREPARED_CONTEXT_KEYS')
    wanted={r['uid']:r for r in metadata};seen_targets=set()
    for c in contexts:
        for t in c['targets']:
            s.require(t['uid'] in wanted and t['uid'] not in seen_targets and wanted[t['uid']]['member_id']==c['member_id'],'PREPARED_TARGET_JOIN')
            s.require(0<=t['event']<c['length']<=256,'PREPARED_TARGET_EVENT');seen_targets.add(t['uid'])
    s.require(seen_targets==set(wanted),'PREPARED_UID_CONSERVATION')
    candidate=s.ROOT/config['candidate_path']
    s.require(s.sha_file(candidate)==config['candidate_file_sha256'],'AB_CHECKPOINT_SHA')
    model=m.Student();model.load_state_dict(torch.load(candidate,map_location='cpu',weights_only=True),strict=True)
    model.eval();before=m.state_hash(model)
    s.require(before==config['candidate_state_sha256'],'AB_TENSOR_STATE')
    s.atomic_json(out/'candidate_before.json',{'file_sha256':config['candidate_file_sha256'],'state_sha256':before})
    check_keys=set(config['check_context_keys']);train_prefix=set(config.get('train_feature_prefix_sha256',[]))
    handles={};rows=[];seen=set();batches=0;events=0
    try:
        with torch.inference_mode():
            for start in range(0,len(contexts),32):
                batch=contexts[start:start+32];sequences=[]
                for c in batch:
                    if c['member_id'] not in handles:handles[c['member_id']]=(out/'members'/c['member_id']/'features.f32le').open('rb')
                    f=handles[c['member_id']];f.seek(c['offset']);raw=f.read(c['length']*524)
                    s.require(len(raw)==c['length']*524,'INFERENCE_INPUT_SHORT')
                    for t in c['targets']:s.require(prefix_hash(raw,t['event'])==t['feature_prefix_sha256'],'INFERENCE_PREFIX_SHA')
                    sequences.append(torch.from_numpy(np.frombuffer(raw,dtype='<f4').copy().reshape(c['length'],131)))
                qs=model(sequences,[c['key'] for c in batch]);batches+=1
                for c,q in zip(batch,qs):
                    events+=c['length']
                    for t in c['targets']:
                        uid=t['uid'];s.require(uid not in seen,'DUPLICATE_INFERENCE');seen.add(uid)
                        logit=float(q[t['event']]);s.require(math_finite(logit),'NONFINITE_PREDICTION')
                        trained_to=config['train_context_events'].get(c['key'],-1)
                        rows.append({**wanted[uid],'owner':'B' if wanted[uid]['old_missing'] else 'A',
                                     'context_key':c['key'],'event_index':t['event'],'context_tier':c['tier'],
                                     'feature_prefix_sha256':t['feature_prefix_sha256'],
                                     'context_in_ab_train':trained_to>=0,'target_within_trained_prefix':t['event']<=trained_to,
                                     'context_in_ab_check':c['key'] in check_keys,
                                     'feature_prefix_seen_in_ab_train':t['feature_prefix_sha256'] in train_prefix,
                                     'ab_logit':logit,'ab_hard':int(logit>=0)})
                progress.check(status='EVALUATING_FIXED_AB',targets_complete=len(rows),contexts_complete=min(start+32,len(contexts)),
                               contexts_total=len(contexts),batches_complete=batches,batches_total=(len(contexts)+31)//32)
    finally:
        for f in handles.values():f.close()
    s.require(seen==set(wanted),'INFERENCE_CONSERVATION')
    after=m.state_hash(model);s.require(after==before,'MODEL_CHANGED')
    s.atomic_json(out/'candidate_after.json',{'state_sha256':after})
    rows.sort(key=lambda r:r['uid'])
    with gzip.open(out/'predictions.csv.gz','wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    result=s.metrics(rows)
    result.update(status='FIXED_AB_EXPANDED_DEVELOPMENT_EVALUATION_COMPLETE',targets=262050,
                  contexts=len(contexts),batches=batches,events=events,optimizer_steps=0,teacher_forwards=0,
                  independent_confirmation=False,new_device_evaluated=False,true_FINAL_opened=False)
    s.atomic_json(out/'comparison.json',result)
    s.atomic_json(out/'inference_receipt.json',{'targets':len(rows),'contexts':len(contexts),'batches':batches,
                  'events':events,'model_loads':1,'optimizer_steps':0,'teacher_forwards':0,'retries':0,
                  'predictions_sha256':s.sha_file(out/'predictions.csv.gz')})
    return result


def math_finite(value):
    return bool(np.isfinite(value))


def write_report(out,result):
    rate=lambda x:'—' if x is None else '%.4f%%'%(100*x)
    a=result['attack'];future=result['future_query']
    lines=['# 固定AB模型扩大评估结果','',
           '**模型推理完成；终态核验尚未完成。以下为历史暴露数据上的开发复评。模型和阈值未调整。**','',
           '| 检查项 | 分母 | 旧P2 | 新AB |','|---|---:|---:|---:|',
           '| 攻击召回 | 244,050 | %s | %s |'%(rate(a['old_recall']),rate(a['ab_recall'])),
           '| future-query攻击召回 | 131,391 | %s | %s |'%(rate(future['old_recall']),rate(future['ab_recall']))]
    for g in result['groups']:
        if g['dimensions']==['pool'] and g['benign']:
            lines.append('| %s正常误报 | %s | %s | %s |'%(g['values'][0],format(g['targets'],','),rate(g['old_fpr']),rate(g['ab_fpr'])))
    lines+=['','旧P2检出而新AB漏检：%d条；旧P2漏检而新AB检出：%d条。'%(a['old_correct_new_wrong'],a['old_wrong_new_correct']),
            'ID沿用既有结果：检查151条、误报0；另外658条为训练内结果，误报0。未增加ID推理。','',
            '| 攻击族 | 分母 | 旧P2召回 | 新AB召回 |','|---|---:|---:|---:|']
    for g in result['groups']:
        if g['dimensions']==['attack_family'] and g['attacks']:
            lines.append('| %s | %s | %s | %s |'%(g['values'][0],format(g['targets'],','),rate(g['old_recall']),rate(g['ab_recall'])))
    lines+=['','这些结果不构成新的独立确认、未见攻击族泛化证明或新设备入网实验。',
            'A/B表示旧输入是否可用，不等于ID/OOD。逐来源、输入可用性和训练暴露分层见comparison.json。',
            '旧实验的严格继承FAIL保持，不根据这次复评事后改门槛。','']
    (out/'result_pending.md').write_text('\n'.join(lines),encoding='utf-8')


def worker(config,out,start):
    progress=Progress(out,start,config)
    try:
        m.configure()
        progress.check(True,status='LOADING_QUALIFIED_TARGETS')
        metadata=load_target_metadata()
        prepared=prepare(config,metadata,out,progress)
        result=infer_prepared(config,metadata,prepared,out,progress)
        write_report(out,result)
        progress.check(True,status='WORKER_COMPLETE_PENDING_VERIFICATION',targets_complete=262050)
        s.atomic_json(out/'worker_terminal.json',{'status':result['status'],'targets':262050,'contexts':result['contexts'],
                      'decoder_packets':prepared['decoder_packets'],'decoder_calls':80,'optimizer_steps':0,
                      'teacher_forwards':0,'retries':0,'elapsed_seconds':time.monotonic()-start})
        return 0
    except Exception as exc:
        (out/'failure_traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        s.atomic_json(out/'worker_terminal.json',{'status':'INPUT_OR_EXECUTION_STOP','reason':type(exc).__name__+': '+str(exc),
                      'scientific_result':None,'last_progress':progress.data,'retries':0,'elapsed_seconds':time.monotonic()-start})
        return 1
