"""D2-NEIGHBOR-TRACE-V1. Reproduce frozen decisions on preregistered subsets.

No new model forward, classifier fit, rule modification, threshold selection or
full A/B evaluation. Run with guarded_run.py, once, after hash-verified retrieval.
"""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='4'
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gc
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
INPUT=HERE/'retrieved'
OUT=HERE/'output'
sys.path.insert(0,str(ROOT/'runs/history_normal_reference_keyrepair_v1_20261031'))
from hnr.assets import load_assets, joined, helpers
from hnr.common import TARGETS, HEIM, rows as read_rows, sha, write
from hnr import evaluation as ev
import constrained_onboarding_core_v3 as core
MAX_PAIRS=80_000_000
SALT='D2_TRACE_20261031|'


def need(value,message):
    if not value:raise ValueError(message)


def serial(v):
    if isinstance(v,np.ndarray):return serial(v.tolist())
    if isinstance(v,np.generic):return serial(v.item())
    if isinstance(v,float) and not math.isfinite(v):return 'INF' if v>0 else '-INF' if v<0 else 'NAN'
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [serial(x) for x in v]
    return v


def hash_sort(indices,rows):
    return sorted(indices,key=lambda i:(hashlib.sha256((SALT+rows[i]['uid']).encode()).hexdigest(),rows[i]['uid']))


def choose(rows,new,old,primary,frozen):
    normal=np.asarray([r['label']==0 for r in rows])
    target=np.asarray([r['device']==HEIM['device'] or r['device'] in {t['device'] for t in TARGETS.values()} for r in rows])
    base=new['base'];now=new['corrected']
    prior=np.asarray(primary,dtype=bool)&target
    withdrew=np.any(base & ~now,axis=1)
    safe=np.any(base,axis=1)&np.all(now==base,axis=1)
    margin=core.ordered_ensemble(new['raw_logits'])-float(frozen['cuts']['ensemble_cut'])
    chosen={};used=set()
    def add(name,ix):
        ix=list(map(int,ix));need(not (set(ix)&used),'COHORT_OVERLAP:'+name)
        need(len(ix)==len(set(ix)),'DUPLICATE_COHORT_INDEX')
        chosen[name]=sorted(ix,key=lambda i:rows[i]['uid']);used.update(ix)
    add('P1_WITHDRAWN',np.flatnonzero(prior & ~normal & withdrew))
    samsung=TARGETS['SAMSUNG']['device']
    a4=np.asarray([r['device']==samsung and r.get('annotation_id')=='annotations/00166cab6b88.csv:4' for r in rows])
    add('P2A_SAMSUNG_4_CONTROL',np.flatnonzero(prior & ~normal & safe & a4))
    for key in ('SAMSUNG','TP_LINK','WEMO_POWER'):
        device=TARGETS[key]['device']
        population=[i for i,r in enumerate(rows) if prior[i] and not normal[i] and safe[i]
                    and r['device']==device and i not in used
                    and (key!='SAMSUNG' or r.get('annotation_id') in
                         ('annotations/00166cab6b88.csv:5','annotations/00166cab6b88.csv:6'))]
        near=sorted([i for i in population if margin[i]>0],key=lambda i:(margin[i],rows[i]['uid']))[:256]
        hashed=hash_sort([i for i in population if i not in set(near)],rows)[:256]
        add('P2B_'+key+'_CONTROL',near+hashed)
    heim=np.asarray([r['device']==HEIM['device'] for r in rows])
    tcp=np.asarray([r['protocol']==6 for r in rows]);udp=np.asarray([r['protocol']==17 for r in rows])
    add('P3_HEIM_NORMAL',np.flatnonzero(prior & normal & heim & (tcp | (udp & now[:,3]))))
    for key in ('WEMO_POWER','SAMSUNG','TP_LINK'):
        dev=np.asarray([r['device']==TARGETS[key]['device'] for r in rows])
        add('P4_'+key+'_RESIDUAL',hash_sort(np.flatnonzero(prior&normal&dev&now[:,3]),rows)[:1024])
        add('P4_'+key+'_RESCUED',hash_sort(np.flatnonzero(prior&normal&dev&old['corrected'][:,3]&~now[:,3]),rows)[:1024])
    need(all(prior[i] for i in used),'NON_PRIMARY_SELECTED')
    return chosen


def summarize_support(ix,new):
    ix=np.asarray(ix,dtype=np.int64);s=new['support'][ix];eligible=new['eligible'][ix]
    return dict(rows=len(ix),eligible=int(eligible.sum()),zero_support=int((s==0).sum()),
                positive_support=int((s>0).sum()),one_support=int((s==1).sum()),
                support_min=float(s.min()) if len(s) else None,
                support_max=float(s.max()) if len(s) else None,
                support_quantiles=np.quantile(s,[0,.25,.5,.75,1]).tolist() if len(s) else [],
                newly_withdrawn_by_head={suffix:int((new['base'][ix,j]&~new['corrected'][ix,j]).sum())
                                       for j,suffix in enumerate(ev.SUFFIXES)})


def read_only_audit(data,new,primary,cohorts):
    rows=data['rows'];groups={}
    for label,device,protocol in (('HEIM_TCP_RESIDUAL_42',HEIM['device'],6),
                                 ('POWER_TCP_RESIDUAL_1865',TARGETS['WEMO_POWER']['device'],6)):
        ix=[i for i,r in enumerate(rows) if primary[i] and r['label']==0 and r['device']==device
            and r['protocol']==protocol and new['corrected'][i,3]]
        groups[label]=summarize_support(ix,new)
    for name in ('P1_WITHDRAWN','P2A_SAMSUNG_4_CONTROL'):
        ix=[i for i in cohorts[name] if rows[i].get('annotation_id')=='annotations/00166cab6b88.csv:4']
        groups['SAMSUNG_4_'+name]=summarize_support(ix,new)
    return groups


def history_inputs():
    datasets=[]
    for key in TARGETS:
        directory=INPUT/'history'/key/'encoded'
        rows=list(read_rows(directory/'references.jsonl.gz'))
        need(all(r['history_role']=='HIST_REF' and r['use']=='REFERENCE' and r['label']==0 for r in rows),'HISTORY_REF_ROLE')
        with np.load(directory/'references.npz',allow_pickle=False) as f:
            need(f['uid'].tolist()==[r['uid'] for r in rows],'HISTORY_UID_JOIN')
            datasets.append(joined(rows,f['e3'].copy(),f['q14'].copy()))
    need(sum(len(x['rows']) for x in datasets)==24163,'HIST_REF_TOTAL')
    return joined([r for d in datasets for r in d['rows']],np.concatenate([d['e3'] for d in datasets]),
                  np.concatenate([d['q14'] for d in datasets]))


def load_saved(pool,data):
    with np.load(INPUT/'ab'/pool/'DECISIONS.npz',allow_pickle=False) as f:
        need(f['uid'].tolist()==data['feature_uids'],'SAVED_DECISION_UID_JOIN')
        need(float(f['selected_lambda'])==.25,'SAVED_LAMBDA')
        result={k:f[k].copy() for k in ('support','eligible','base','corrected','raw_logits','corrected_logits')}
    need(np.array_equal(result['raw_logits'],data['logits']),'SAVED_LOGITS_EXACT')
    return result


def prepare(assets,frozen):
    hist=history_inputs();a=assets.a_history()
    packs={};audit={};budget=[];cohort_manifest=[]
    for pool in ev.POOLS:
        data=assets.queries(pool);new=load_saved(pool,data)
        old,_=assets.baseline(pool,data['feature_uids'])
        need(np.array_equal(new['base'],old['base']) and np.array_equal(new['base'],ev.decisions(data['logits'],frozen)),'BASE_REPLAY')
        need(np.array_equal(ev.decisions(core.apply_correction(data['logits'],new['support'],frozen['scales'],.25),frozen),new['corrected']),'SAVED_CORRECTION_REPLAY')
        primary=helpers().metrics.post_window_mask(data['rows'],assets.spec['pools'][pool]['windows'])
        primary=np.asarray(primary,dtype=bool)
        cohorts=choose(data['rows'],new,old,primary,frozen)
        audit[pool]=read_only_audit(data,new,primary,cohorts)
        dense=assets.dense(pool);history=a if pool=='CIC_DEV' else hist
        merged=ev.union_bank(dense,history)
        bank=ev._bank(merged,frozen['normalizer'],history_replay=True)
        sources={r['uid']:'B2_DENSE' for r in dense['rows']}
        sources.update({r['uid']:'A_OLD_11' if pool=='CIC_DEV' else 'B_HIST_REF' for r in history['rows']})
        indices=sorted({i for group in cohorts.values() for i in group})
        mapping={old:new for new,old in enumerate(indices)}
        selected=ev._subset(data,indices)
        selected_new={k:v[indices] for k,v in new.items()}
        mapped={name:[mapping[i] for i in ix] for name,ix in cohorts.items()}
        packs[pool]=dict(data=selected,saved=selected_new,cohorts=mapped,bank=bank,sources=sources)
        for name,ix in mapped.items():
            rr=[selected['rows'][i] for i in ix]
            own_pairs=ev._actual_pairs(bank,rr)
            # Every saved eligible row with source geometry has two matched refs.
            matched_rows=sum(bool(selected_new['eligible'][i]) and core._radius(frozen['geometry'],selected['rows'][i]['protocol']) is not None for i in ix)
            extra_pairs=2*matched_rows
            budget.append(dict(pool=pool,cohort=name,priority=name[:2],rows=len(ix),
                               own_pairs=own_pairs,matched_pair_checks=extra_pairs,total_pairs=own_pairs+extra_pairs))
            cohort_manifest += [dict(pool=pool,cohort=name,uid=r['uid'],device=r['device'],
                                     label=r['label'],protocol=r['protocol'],annotation_id=r.get('annotation_id')) for r in rr]
        print('D2_PREPARED '+pool+' '+str(len(indices))+' queries',flush=True)
        del data,new,old,dense,merged,selected,selected_new,bank;gc.collect()
    need(audit['CIC_DEV']['HEIM_TCP_RESIDUAL_42']['rows']==42,'HEIM_RESIDUAL_COUNT')
    need(audit['UNSW_DEV']['POWER_TCP_RESIDUAL_1865']['rows']==1865,'POWER_RESIDUAL_COUNT')
    need(len(packs['CIC_DEV']['cohorts']['P3_HEIM_NORMAL'])==194,'HEIM_PRIMARY_COUNT')
    write(OUT/'SAVED_SUPPORT_AUDIT.json',audit)
    write(OUT/'COHORTS.json',cohort_manifest)
    write(OUT/'PAIR_PLAN.json',dict(limit=MAX_PAIRS,groups=budget,total_requested_pairs=sum(x['total_pairs'] for x in budget)))
    return packs,budget


def neighbors(bank,data,trace,k,sources,frozen):
    row=data['rows'][k]
    uids=trace['matched_reference_uids'][k]
    if uids[0] is None:
        need(uids[1] is None,'ONE_MATCH_ONLY')
        return [],0
    radii=core._radius(frozen['geometry'],row['protocol'])
    z=core._unit(data['e3'][k:k+1],bank.normalizer)[0]
    query_q=np.asarray(data['q14'][k],dtype=np.float64)
    found=[];joints=[]
    for uid in uids:
        ix=bank.by_uid[uid];ref=bank.rows[ix]
        dz=float(np.clip(1.-z @ bank.z[ix],0.,2.))
        dq=float(np.sqrt(np.mean((query_q-bank.q14[ix])**2)))
        ratios=[float(core._ratio(np.asarray([d]),rad)[0]) for d,rad in zip((dz,dq),radii)]
        joint=max(ratios);joints.append(joint)
        found.append(dict(source=sources[uid],reference=ref,q14=bank.q14[ix].tolist(),
                          dz=dz,dq=dq,dz_over_rho=ratios[0],dq_over_rho=ratios[1],joint=joint,
                          query_minus_reference_seconds=row['timestamp']-ref['timestamp']))
    need(found[0]['reference']['component_id']!=found[1]['reference']['component_id'],'MATCHED_COMPONENTS_DISTINCT')
    need(np.isclose(max(joints),trace['second_joint'][k],rtol=0,atol=1e-12),'ACTUAL_PAIR_JOINT_REPLAY')
    return found,2


def main():
    need(not OUT.exists(),'OUTPUT_EXISTS_NO_AUTOMATIC_RETRY')
    OUT.mkdir()
    inventory=json.loads((INPUT/'REMOTE_TRACE_INVENTORY.json').read_text())
    for item in inventory['files']:
        if item['transfer']:
            path=INPUT/item['path']
            need(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'REMOTE_INPUT_PIN:'+item['path'])
    local_result=json.loads((ROOT/'runs/history_normal_reference_keyrepair_deployment_20261031/completion/RESULT.json').read_text())
    need(json.loads((INPUT/'RESULT.json').read_text())==local_result,'REMOTE_RESULT_MATCHES_PRESERVED_180435')
    assets=load_assets();frozen=assets.calibration()
    packs,plan=prepare(assets,frozen)
    state=dict(status='RUNNING',started_utc=datetime.now(timezone.utc).isoformat(),
               max_distance_pairs=MAX_PAIRS,max_wall_seconds=900,consumed_pairs=0,
               completed_cohorts=[],completed_priorities=[],model_forwards=0,threshold_changes=0,
               no_full_AB_replay=True,consistency_atol=1e-12,consistency_rtol=0)
    write(OUT/'STATUS.json',state)
    trace_path=OUT/'NEIGHBORS.jsonl.gz'
    with gzip.open(trace_path,'xt',encoding='utf-8') as output:
        for priority in ('P1','P2','P3','P4'):
            group=[g for g in plan if g['priority']==priority]
            cost=sum(g['total_pairs'] for g in group)
            if state['consumed_pairs']+cost>MAX_PAIRS:
                state.update(status='PARTIAL_BUDGET_STOP',stopped_before_priority=priority)
                break
            for g in group:
                pool=g['pool'];pack=packs[pool];bank=pack['bank'];ix=pack['cohorts'][g['cohort']]
                actual=0
                for start in range(0,len(ix),128):
                    indices=np.asarray(ix[start:start+128],dtype=np.int64)
                    data=ev._subset(pack['data'],indices)
                    count=ev._actual_pairs(bank,data['rows'])
                    trace=bank.own(data['rows'],data['e3'],data['q14'],frozen['geometry'],
                                   feature_uids=data['feature_uids'],q_uids=data['q_uids'])
                    saved=pack['saved']
                    need(np.array_equal(trace['eligible'],saved['eligible'][indices]),'ELIGIBLE_REPLAY')
                    need(np.allclose(trace['support'],saved['support'][indices],rtol=0,atol=1e-12),'SUPPORT_REPLAY')
                    changed=core.apply_correction(data['logits'],trace['support'],frozen['scales'],.25)
                    need(np.array_equal(ev.decisions(changed,frozen),saved['corrected'][indices]),'FOUR_HEAD_DECISIONS_REPLAY')
                    actual+=count;state['consumed_pairs']+=count
                    for k,index in enumerate(indices):
                        refs,extra=neighbors(bank,data,trace,k,pack['sources'],frozen)
                        actual+=extra;state['consumed_pairs']+=extra
                        item=dict(pool=pool,cohort=g['cohort'],query=data['rows'][k],query_q14=data['q14'][k],
                                  raw_logits=data['logits'][k],base=saved['base'][index],corrected=saved['corrected'][index],
                                  trace={key:value[k] for key,value in trace.items()},neighbors=refs)
                        output.write(json.dumps(serial(item),ensure_ascii=False,allow_nan=False)+'\n')
                    need(state['consumed_pairs']<=MAX_PAIRS,'PAIR_BUDGET_EXCEEDED')
                    state.update(current_cohort=g['cohort'],current_pool=pool,
                                 current_completed=min(start+128,len(ix)),current_total=len(ix))
                    write(OUT/'STATUS.json',state)
                need(actual==g['total_pairs'],'EXACT_PAIR_PLAN_MISMATCH')
                state['completed_cohorts'].append(dict(g,actual_pairs=actual))
                print('D2_COMPLETE '+pool+' '+g['cohort']+' rows='+str(len(ix))+' pairs='+str(actual),flush=True)
            state['completed_priorities'].append(priority)
        else:state['status']='COMPLETE_ALL_REPLAY_CHECKS_PASSED'
    assets.immutable()
    state.update(finished_utc=datetime.now(timezone.utc).isoformat(),trace_sha256=sha(trace_path),
                 saved_support_audit_sha256=sha(OUT/'SAVED_SUPPORT_AUDIT.json'),
                 cohorts_sha256=sha(OUT/'COHORTS.json'),pair_plan_sha256=sha(OUT/'PAIR_PLAN.json'))
    write(OUT/'STATUS.json',state)
    print(state['status'],state['consumed_pairs'],flush=True)


if __name__=='__main__':main()
