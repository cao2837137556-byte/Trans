"""Bounded replay of existing Netatmo neighbors, not a candidate evaluation."""
import audit as a
from collections import Counter, defaultdict
import gzip
import json
import time
import numpy as np
from hnr.assets import load_assets
from hnr import evaluation as ev

DEVICE = 'unsw-attack-traces-2018:70:ee:50:18:34:43'
MAX_PAIRS = 5_000_000
MAX_SECONDS = 180

def main():
    started=time.monotonic()
    evidence=a.read(a.HERE/'EVIDENCE.json')
    assets=load_assets();frozen=assets.calibration(); data=assets.queries('UNSW_DEV')
    rr=data['rows'];ids=data['feature_uids']
    saved_path=a.pin(a.ROOT/'runs/history_normal_reference_c3_progress_repair_v1_20261101/output/ab/UNSW_DEV/DECISIONS.npz')
    with np.load(saved_path,allow_pickle=False) as f:
        assert f['uid'].tolist()==ids
        saved={k:f[k].copy() for k in ('base','corrected','support','eligible','guard')}
    primary=ev.helpers().metrics.post_window_mask(rr,assets.spec['pools']['UNSW_DEV']['windows'])
    fp=[i for i,r in enumerate(rr) if primary[i] and r['device']==DEVICE and r['label']==0 and saved['corrected'][i,3]]
    dense=assets.dense('UNSW_DEV')
    refs=ev._subset(dense,[i for i,r in enumerate(dense['rows']) if r['device']==DEVICE])
    bank=ev._bank(refs,frozen['normalizer'],history_replay=True)
    assert len(fp)==4309
    # Assert no historical additions were made to this device in C1.
    for key in ('SAMSUNG','TP_LINK','WEMO_POWER'):
        hr=a.rows(a.ROOT/f'runs/history_normal_reference_d2_trace_v1_20261031/retrieved/history/{key}/encoded/references.jsonl.gz')
        assert all(r['device']!=DEVICE for r in hr)
    cohorts={};used=set()
    def choose(name,candidates,n):
        chosen=sorted(candidates,key=lambda i: a.hashlib.sha256(('B_SAMPLE_TRACE_V1|'+ids[i]).encode()).digest())[:n]
        assert not used.intersection(chosen);used.update(chosen);cohorts[name]=chosen
    top=[r for r in evidence['components'] if r['device']==DEVICE][:3]
    for rank,item in enumerate(top,1):
        choose(f'FP_COMPONENT_{rank}',[i for i in fp if rr[i]['component_id']==item['component_id']],64)
    choose('OTHER_FP',[i for i in fp if i not in used],64)
    choose('RESCUED_CONTROL',[i for i,r in enumerate(rr) if primary[i] and r['device']==DEVICE and r['label']==0
                             and saved['base'][i,3] and not saved['corrected'][i,3]],64)
    costs={name:ev._actual_pairs(bank,[rr[i] for i in ix])+2*len(ix) for name,ix in cohorts.items()}
    assert sum(costs.values())<=MAX_PAIRS
    a.write('TRACE_CARD.json',dict(operation='FROZEN_NEIGHBOR_REPLAY_ONLY',max_pairs=MAX_PAIRS,max_seconds=MAX_SECONDS,
        cohort_rule='64 UID-hash-selected rows in each of top 3 Netatmo FP components, other residuals and rescued control; descriptive sample only',
        requested_pairs=sum(costs.values()),costs=costs,uids={k:[ids[i] for i in v] for k,v in cohorts.items()},script_sha256=a.sha(__file__)))
    summary={};consumed=0
    with gzip.open(a.HERE/'NETATMO_NEIGHBORS.jsonl.gz','xt',encoding='utf-8') as out:
        for name,ix in cohorts.items():
            counts=Counter();values=defaultdict(list)
            for start in range(0,len(ix),16):
                assert time.monotonic()-started<MAX_SECONDS,'TIME_LIMIT'
                indices=ix[start:start+16]; sub=ev._subset(data,indices)
                cost=ev._actual_pairs(bank,sub['rows'])+2*len(indices)
                assert consumed+cost<=MAX_PAIRS
                trace=bank.own(sub['rows'],sub['e3'],sub['q14'],frozen['geometry'],feature_uids=sub['feature_uids'],q_uids=sub['q_uids'])
                assert np.array_equal(trace['eligible'],saved['eligible'][indices])
                assert np.allclose(trace['support'],saved['support'][indices],rtol=0,atol=1e-12)
                corrected=a.core.apply_correction(sub['logits'],trace['support'],frozen['scales'],.25)
                corrected[saved['guard'][indices]]=sub['logits'][saved['guard'][indices]]
                assert np.array_equal(ev.decisions(corrected,frozen),saved['corrected'][indices])
                z=a.core._unit(sub['e3'],bank.normalizer)
                for j,i in enumerate(indices):
                    radii=a.core._radius(frozen['geometry'],rr[i]['protocol']);neighbors=[]
                    for uid in trace['matched_reference_uids'][j]:
                        k=bank.by_uid[uid]
                        dz=float(np.clip(1.-z[j]@bank.z[k],0.,2.))
                        delta=sub['q14'][j].astype(float)-bank.q14[k]
                        dq=float(np.sqrt(np.mean(delta**2)))
                        neighbors.append(dict(reference=bank.rows[k],q14=bank.q14[k].tolist(),z_ratio=dz/radii[0],
                            q_ratio=dq/radii[1],q_squared_delta=(delta**2).tolist()))
                    zr=max(n['z_ratio'] for n in neighbors);qr=max(n['q_ratio'] for n in neighbors)
                    assert abs(max(zr,qr)-trace['second_joint'][j])<1e-12
                    counts['rows']+=1;counts['z_limiter']+=int(zr>=qr);counts['q_limiter']+=int(qr>zr)
                    counts['z_radius_blocked']+=int(zr>=1);counts['q_radius_blocked']+=int(qr>=1)
                    counts['query_component_in_bank']+=int(trace['same_component'][j])
                    counts['zero_support']+=int(trace['support'][j]==0)
                    values['z_ratio'].append(zr);values['q_ratio'].append(qr);values['support'].append(float(trace['support'][j]))
                    values['query_q14'].append(sub['q14'][j].tolist())
                    for n in neighbors:values['neighbor_q14'].append(n['q14'])
                    out.write(json.dumps(dict(cohort=name,query=rr[i],query_q14=sub['q14'][j].tolist(),
                        support=float(trace['support'][j]),neighbors=neighbors),ensure_ascii=False)+'\n')
                consumed+=cost
            summary[name]=dict(counts=dict(counts),quantiles={k:a.quant(v) for k,v in values.items() if 'q14' not in k},
                query_q14_min=np.min(values['query_q14'],axis=0).tolist(),query_q14_max=np.max(values['query_q14'],axis=0).tolist(),
                neighbor_q14_min=np.min(values['neighbor_q14'],axis=0).tolist(),neighbor_q14_max=np.max(values['neighbor_q14'],axis=0).tolist())
            print(name,json.dumps(summary[name]['counts']),flush=True)
    assets.immutable()
    for path,digest in a.PINS.items():assert a.sha(path)==digest,path
    a.write('TRACE_SUMMARY.json',dict(status='FROZEN_SUPPORT_AND_ALL_HEAD_DECISIONS_REPRODUCED',
        evidence='CONSUMED_DEVELOPMENT_DIAGNOSTIC_SAMPLE_ONLY',cohorts=summary,consumed_pairs=consumed,
        elapsed_seconds=time.monotonic()-started,model_forwards=0,reference_additions=0,
        input_sha256=a.PINS,asset_input_sha256={str(p):digest for p,digest in assets.inputs.pins.items()},
        trace_sha256=a.sha(a.HERE/'NETATMO_NEIGHBORS.jsonl.gz')))

if __name__=='__main__':main()
