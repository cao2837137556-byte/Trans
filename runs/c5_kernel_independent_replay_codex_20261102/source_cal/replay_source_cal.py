"""Isolated frozen-179602 source CAL support reconstruction and C5 audit.

Reads saved encodings only. Writes exclusively beside this script. No model,
training, raw PCAP, network, or production entry point is invoked.
"""
import os
for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_k] = '2'
import sys
sys.dont_write_bytecode = True
import gc
import gzip
import hashlib
import json
import math
from pathlib import Path
import threading
import time
import traceback

import numpy as np
import psutil
from threadpoolctl import threadpool_limits, threadpool_info

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SCIENCE = ROOT / 'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027/evidence179602/science'
ASSETS = ROOT / 'runs/diagnostics_d1_d2_v1_20261022/assets'
PREP = ASSETS / 'heads/run/prepared'
CALIB = ASSETS / 'onboarding/run/evaluation/calibration'
DENSE = SCIENCE / 'encode/banks/SOURCE_REFS'
RSS_LIMIT = 2 * 2**30
STARTED = time.monotonic()
PEAK_RSS = 0
STOP = threading.Event()
STATE = dict(status='STARTING', no_training=True, no_new_encoding=True, no_network=True)
SUFFIXES = ('27', '127', '227', 'ensemble')


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write(p, value):
    p = Path(p)
    q = p.with_name(p.name + '.tmp')
    q.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(q, p)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 * 2**20), b''):
            h.update(b)
    return h.hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def progress(stage, **kwargs):
    STATE.update(stage=stage, elapsed_seconds=time.monotonic()-STARTED,
                 peak_rss_bytes=PEAK_RSS, rss_limit_bytes=RSS_LIMIT, **kwargs)
    write(OUT/'progress.json', STATE)


def watch_memory():
    global PEAK_RSS
    proc = psutil.Process()
    while not STOP.wait(.5):
        rss = proc.memory_info().rss
        PEAK_RSS = max(PEAK_RSS, rss)
        if rss > RSS_LIMIT:
            STATE.update(status='FAILED', error='RSS_LIMIT_EXCEEDED', rss_bytes=rss)
            write(OUT/'progress.json', STATE)
            os._exit(19)


def gzrows(p):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def risk(rows, base, missed, weights):
    """Same weights/union semantics, independently assembled group readout."""
    def one(ix):
        ix = np.asarray(ix, dtype=np.int64)
        mass = math.fsum(weights[ix])
        values = {}
        for k, name in enumerate(SUFFIXES):
            detected = math.fsum(weights[ix][base[ix, k]])
            lost = math.fsum(weights[ix][missed[ix, k]])
            remain = math.fsum(weights[ix][base[ix, k] & ~missed[ix, k]])
            values[name] = dict(rows=len(ix), baseline_tp=int(base[ix, k].sum()),
                added_fn_count=int(missed[ix, k].sum()), weight_mass=mass,
                baseline_detected_weight=detected, added_fn_weight=lost,
                remaining_detected_weight=remain,
                baseline_recall=None if mass == 0 else detected/mass,
                corrected_recall=None if mass == 0 else remain/mass,
                recall_loss_pp=None if mass == 0 else 100*lost/mass)
        return values
    answer = dict(overall=one(range(len(rows))), groups={})
    for field in ('device', 'activity'):
        answer['groups'][field] = {v:one([i for i,r in enumerate(rows) if r[field]==v])
            for v in sorted({r[field] for r in rows})}
    return answer


def audit_protection(summary, rows, base, missed):
    failures = []
    # Original source selector protects every detected UID in every head.
    strict = not bool(missed.any())
    for field, limit in (('device',1.0), ('activity',5.0)):
        for group, heads in summary['groups'][field].items():
            ix = np.array([r[field]==group for r in rows])
            for k,name in enumerate(SUFFIXES):
                item = heads[name]
                if item['recall_loss_pp'] is not None and item['recall_loss_pp'] > limit:
                    failures.append(field+':'+group+':'+name+':LOSS')
                if item['baseline_recall'] is not None and item['baseline_recall'] < .99 and missed[ix,k].any():
                    failures.append(field+':'+group+':'+name+':LOW_BASELINE_WITHDRAWAL')
    for name,item in summary['overall'].items():
        if item['corrected_recall'] is not None and item['corrected_recall'] < .99:
            failures.append('ABSOLUTE_RECALL:'+name)
    return dict(strict_source_zero_withdrawal_pass=strict, group_absolute_pass=not failures, failures=failures)


def main():
    require(not (OUT/'RESULT.json').exists(), 'FRESH_RESULT_REQUIRED')
    sys.path.insert(0, str(ROOT/'repo/ood'))
    import constrained_onboarding_core_v3 as core
    from indexed_features_v1 import IndexedMatrix
    prior_seal = read(SCIENCE/'source_cal/INPUT_SEAL.json')
    paths = [PREP/n for n in ('LEARN.jsonl.gz','LEARN_q.npy','CAL.npz','normalizer.npz')]
    paths += [CALIB/(n+'.json') for n in ('cuts','geometry','scales','protection')]
    paths += [ROOT/'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy',
        ROOT/'runs/diagnostics_d1_d2_v1_20261022/output/d1/r2/source_actual_trace.npz',
        DENSE/'bank.npz', DENSE/'references.jsonl.gz', DENSE/'receipt.json',
        SCIENCE/'source_cal/R-DENSE/PREPARATION.json', SCIENCE/'source_cal/R-DENSE/EPS0_PARITY.json',
        SCIENCE/'source_cal/RESULT.json', SCIENCE/'source_cal/INPUT_SEAL.json',
        ROOT/'repo/ood/constrained_onboarding_core_v3.py', ROOT/'repo/ood/indexed_features_v1.py',
        ROOT/'repo/ood/legacy_qref_data_v1.py', Path(__file__)]
    entries = []
    for i,p in enumerate(paths):
        progress('LOCKING_INPUT_SHA256', input_index=i, input_count=len(paths), path=str(p))
        checksum = sha(p)
        suffix = str(p.relative_to(ROOT)).replace('\\','/')
        prior = [v for k,v in prior_seal.items() if k.replace('\\','/').endswith('/'+suffix)]
        if p.is_relative_to(SCIENCE):
            marker = 'science/'+str(p.relative_to(SCIENCE)).replace('\\','/')
            prior = [v for k,v in prior_seal.items() if k.endswith('/'+marker)]
        require(not prior or len(set(prior))==1 and checksum==prior[0], '179602_INPUT_SHA:'+suffix)
        entries.append(dict(path=suffix, bytes=p.stat().st_size, sha256=checksum,
                            verified_against_179602=bool(prior)))
    require(sha(ROOT/'repo/ood/constrained_onboarding_core_v3.py') ==
            sha(ROOT/'runs/onboarding_new_lineage_v1_20261022/package_v3/constrained_onboarding_core_v3.py'),
            'FROZEN_V3_CORE')
    write(OUT/'INPUT_SEAL.json', dict(status='LOCKED_BEFORE_DISTANCE', inputs=entries,
        threads=2, rss_limit_bytes=RSS_LIMIT, source_job='179602'))
    with np.load(PREP/'CAL.npz', allow_pickle=False) as z:
        cal_indices=z['indices'].copy()
    require(len(cal_indices)==148819 and np.array_equal(cal_indices,np.unique(cal_indices)), 'CAL_INDEX_CONTRACT')
    cal_set=set(cal_indices.tolist()); cal=[]
    # Retain only fields needed by frozen geometry/causality, source weights,
    # group protection, and per-UID identification.
    keep=('uid','partition','device','owner','protocol','component_id','capture_id','timestamp','frame',
          'use','label','fit_role','activity','session_id','annotation_id','canonical_key','reference_end')
    with gzip.open(PREP/'LEARN.jsonl.gz','rt',encoding='utf-8') as f:
        for index,line in enumerate(f):
            r=json.loads(line)
            require((r.get('fit_role')=='CAL') == (index in cal_set), 'CAL_ROLE_INDEX')
            if index in cal_set:
                cal.append({k:r[k] for k in keep if k in r})
    del cal_set
    require(len(cal)==148819, 'CAL_ROW_COUNT')
    with gzip.open(OUT/'CAL_QUERIES.jsonl.gz','wt',encoding='utf-8') as f:
        for r in cal: f.write(json.dumps(r,separators=(',',':'))+'\n')
    with np.load(paths[9],allow_pickle=False) as z:
        require(z['uid'].tolist()==[r['uid'] for r in cal], 'CAL_LOGIT_UID_JOIN')
        logits=z['original_logits'].copy(); saved_dec=z['original_decisions'].copy()
    cuts=read(CALIB/'cuts.json'); geometry=read(CALIB/'geometry.json'); scales=read(CALIB/'scales.json')['scales']
    cut=np.asarray(cuts['cuts']); scale=np.asarray(scales)
    decide=lambda x: np.column_stack((x>cut,core.ordered_ensemble(x)>cuts['ensemble_cut']))
    require(np.array_equal(decide(logits),saved_dec),'RAW_DECISION_PARITY')
    normals_ix=np.flatnonzero([r['label']==0 for r in cal]); attacks_ix=np.flatnonzero([r['label']==1 for r in cal])
    normals=[cal[i] for i in normals_ix]; attacks=[cal[i] for i in attacks_ix]
    require((len(normals),len(attacks))==(33147,115672),'CAL_CLASS_COUNTS')
    # Read <=2048 selected rows from one transient source mapping at a time;
    # closing it prevents unrelated 2.44GB source pages accumulating in RSS.
    feature_path=ROOT/'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy'
    compact=np.lib.format.open_memmap(OUT/'CAL_E3.npy',mode='w+',dtype=np.float32,shape=(len(cal),768))
    for start in range(0,len(cal),2048):
        source=np.load(feature_path,mmap_mode='r',allow_pickle=False)
        compact[start:start+2048]=source[cal_indices[start:start+2048],:768]
        source._mmap.close();del source
        progress('EXTRACT_CAL_SAVED_FEATURES', rows_done=min(start+2048,len(cal)), rows_total=len(cal))
    compact.flush()
    qbase=np.load(PREP/'LEARN_q.npy',mmap_mode='r',allow_pickle=False)
    q14=np.array(qbase[cal_indices],dtype=np.float32);qbase._mmap.close();del qbase
    with np.load(PREP/'normalizer.npz',allow_pickle=False) as z: normalizer=(z['mean'].copy(),z['scale'].copy())
    refs=gzrows(DENSE/'references.jsonl.gz')
    with np.load(DENSE/'bank.npz',allow_pickle=False) as z:
        require(z['uid'].tolist()==[r['uid'] for r in refs] and len(refs)==4728,'DENSE_BANK_UID')
        bank=core.ReferenceBank(refs,z['e3'],z['q14'],normalizer,
            feature_uids=z['uid'].tolist(),q_uids=z['uid'].tolist(),allowed_partitions={'LEARN'})
    require(not {r['component_id'] for r in refs}.intersection(r['component_id'] for r in cal),'CAL_COMPONENT_LEAKAGE')
    roster=bank.roster();write(OUT/'DONOR_ROSTER.json',roster)
    n,k=len(attacks),len(roster)
    support=np.lib.format.open_memmap(OUT/'ATTACK_SUPPORT.npy',mode='w+',dtype=np.float64,shape=(n,k))
    eligible=np.lib.format.open_memmap(OUT/'ATTACK_ELIGIBLE.npy',mode='w+',dtype=np.bool_,shape=(n,k))
    same=np.lib.format.open_memmap(OUT/'ATTACK_SAME_COMPONENT.npy',mode='w+',dtype=np.bool_,shape=(n,k))
    joint=np.lib.format.open_memmap(OUT/'ATTACK_SECOND_JOINT.npy',mode='w+',dtype=np.float64,shape=(n,k))
    support[:]=0;eligible[:]=False;same[:]=False;joint[:]=np.inf
    ae=IndexedMatrix(compact,attacks_ix); aq=IndexedMatrix(q14,attacks_ix)
    auid=[r['uid'] for r in attacks]
    bank._queries(attacks,ae,aq,auid,auid)
    for j,key in enumerate(bank.keys):
        progress('ALL_LEGAL_DONOR_DISTANCE_REBUILD',donor_index=j,donor_count=k,donor=list(key))
        ix=[i for i,r in enumerate(attacks) if r['protocol']==key[2]]
        ans=bank._empty(n)
        bank._evaluate_group(ans,attacks,ae,aq,ix,bank.groups[key],geometry)
        support[:,j]=ans['support'];eligible[:,j]=ans['eligible'];same[:,j]=ans['same_component'];joint[:,j]=ans['second_joint']
        for arr in (support,eligible,same,joint):arr.flush()
        del ans;gc.collect()
    progress('NORMAL_OWN_DISTANCE_REBUILD')
    nuid=[r['uid'] for r in normals]
    own=bank.own(normals,IndexedMatrix(compact,normals_ix),IndexedMatrix(q14,normals_ix),geometry,
                 feature_uids=nuid,q_uids=nuid)
    np.savez_compressed(OUT/'NORMAL_OWN_SUPPORT.npz',uid=np.asarray(nuid),support=own['support'],
        eligible=own['eligible'],second_joint=own['second_joint'])
    np.savez_compressed(OUT/'CAL_FIXED_INPUTS.npz',uid=np.asarray([r['uid'] for r in cal]),
        learn_indices=cal_indices,attack_indices=attacks_ix,normal_indices=normals_ix,
        raw_logits=logits,raw_decisions=saved_dec,q14=q14)
    saved_preparation=read(SCIENCE/'source_cal/R-DENSE/PREPARATION.json')
    legacy=saved_preparation['legacy_protection']
    w=core.class_weights(attacks);nw=core.class_weights(normals)
    for name,rr,ww in (('attack',attacks,w),('normal',normals,nw)):
        old=saved_preparation['weight_identity'][name]
        require(old['uid_sha256']==core._uid_hash([r['uid'] for r in rr]) and
                old['float64_sha256']==hashlib.sha256(ww.tobytes()).hexdigest(),'SOURCE_WEIGHT_IDENTITY:'+name)
    coverage=dict(eligible_pairs=int(eligible.sum()),positive_support_pairs=int((support>0).sum()),
        attack_rows_with_support=int(np.any(support>0,axis=1).sum()),
        validity_matrix_sha256=hashlib.sha256(eligible.tobytes(order='C')).hexdigest())
    require(all(coverage[f]==legacy[f] for f in coverage),'179602_SUPPORT_COVERAGE_IDENTITY')
    require(roster==legacy['roster'],'179602_DONOR_ROSTER_IDENTITY')
    a_raw=logits[attacks_ix];a_base=saved_dec[attacks_ix];n_raw=logits[normals_ix];n_base=saved_dec[normals_ix]
    # First reproduce the original p=1, unguarded source summary and CAL own
    # decision hash; C2 was not part of that historical 179602 computation.
    p1_pair=np.zeros(4,dtype=np.int64);p1_miss=np.zeros((n,4),bool)
    for j in range(k):
        changed=decide(core.apply_correction(a_raw,support[:,j],scales,.25))
        m=a_base & ~changed & eligible[:,j,None]
        p1_pair+=m.sum(axis=0);p1_miss|=m
    expected=legacy['candidates'][-1]
    require({s:int(p1_miss[:,i].sum()) for i,s in enumerate(SUFFIXES)}==expected['new_miss_count'],'179602_P1_MISS_COUNT')
    require({s:int(p1_pair[i]) for i,s in enumerate(SUFFIXES)}==expected['new_miss_pair_count'],'179602_P1_PAIR_COUNT')
    p1_normal_dec=decide(core.apply_correction(n_raw,own['support'],scales,.25))
    nq={s:math.fsum(nw[n_base[:,i]&~p1_normal_dec[:,i]]) for i,s in enumerate(SUFFIXES)}
    require(nq==saved_preparation['candidates'][-1]['normal_fp_reduction'],'179602_NORMAL_REDUCTION_PARITY')
    own_full=np.zeros(len(cal));own_full[normals_ix]=own['support']
    lookup={(r['partition'],r['device'],r['protocol']):j for j,r in enumerate(roster)}
    for i,r in enumerate(attacks):
        j=lookup.get((r['partition'],r['device'],r['protocol']))
        if j is not None:own_full[attacks_ix[i]]=support[i,j]
    p1_full=core.apply_correction(logits,own_full,scales,.25)
    parity=read(SCIENCE/'source_cal/R-DENSE/EPS0_PARITY.json')
    decision_hash=hashlib.sha256(decide(p1_full).tobytes()).hexdigest()
    require(decision_hash==parity['corrected_decisions_sha256'],'179602_FULL_CAL_DECISION_HASH')
    p1_identity=dict(status='PASS',coverage=coverage,roster_exact=True,
        full_CAL_decisions_sha256=decision_hash,
        historical_logits_byte_hash_equal=hashlib.sha256(p1_full.tobytes()).hexdigest()==parity['corrected_logits_sha256'],
        normal_fp_reduction=nq,zero_withdrawals_all_heads=True)
    write(OUT/'P1_179602_IDENTITY.json',p1_identity)
    progress('P1_179602_IDENTITY_PASS')
    guard=(q14[:,0]==1)&(q14[:,2]==1)&(q14[:,5]==0)
    ag=guard[attacks_ix];ng=guard[normals_ix]
    results={};case_ids=set();all_case_details={}
    # All cap-reachable detected attacks with any legal positive donor. Keep
    # exact UID-level cases including the seed127/227 singleton.
    positive=np.any((support>0)&eligible,axis=1)
    sat=decide(core.apply_correction(a_raw,positive.astype(float),scales,.25))
    reach=a_base & ~sat
    case_ix=np.flatnonzero(reach.any(axis=1))
    for mode in ('p1','p2','p3','p4','positive_saturation'):
        progress('C2_KERNEL_GRID_REPLAY',candidate=mode)
        p=None if mode=='positive_saturation' else int(mode[1:])
        def transform(s):
            if p is None:return (s>0).astype(np.float64)
            if p==1:return np.asarray(s,dtype=np.float64).copy()
            return np.where(s>0,1-(1-s)**p,0.)
        missed=np.zeros((n,4),bool);pairs=np.zeros(4,dtype=np.int64)
        for j in range(k):
            s=transform(support[:,j]);s[ag]=0
            changed=decide(core.apply_correction(a_raw,s,scales,.25))
            m=a_base & ~changed & eligible[:,j,None]
            missed|=m;pairs+=m.sum(axis=0)
        ns=transform(own['support']);ns[ng]=0
        ndec=decide(core.apply_correction(n_raw,ns,scales,.25))
        summary=risk(attacks,a_base,missed,w)
        summary.update(new_miss_pair_count={s:int(pairs[i]) for i,s in enumerate(SUFFIXES)},
            protection=audit_protection(summary,attacks,a_base,missed),
            normal={},guard_split={},newly_missed_uids={s:[attacks[i]['uid'] for i in np.flatnonzero(missed[:,h])]
                                                   for h,s in enumerate(SUFFIXES)})
        for h,s in enumerate(SUFFIXES):
            summary['normal'][s]=dict(rows=len(normals),raw_fp=int(n_base[:,h].sum()),
                corrected_fp=int(ndec[:,h].sum()),weighted_raw_fpr=math.fsum(nw[n_base[:,h]]),
                weighted_corrected_fpr=math.fsum(nw[ndec[:,h]]),
                normal_new_fp=int((~n_base[:,h]&ndec[:,h]).sum()))
        for name,mask in (('SYN_NO_ACK',ag),('NON_SYN_GUARD',~ag)):
            summary['guard_split'][name]=dict(rows=int(mask.sum()),raw_tp={s:int(a_base[mask,h].sum()) for h,s in enumerate(SUFFIXES)},
                newly_missed={s:int(missed[mask,h].sum()) for h,s in enumerate(SUFFIXES)})
        for i in case_ix:
            uid=attacks[i]['uid'];case_ids.add(uid)
            item=all_case_details.setdefault(uid,dict(query=attacks[i],q14=q14[attacks_ix[i]].tolist(),
                guard=bool(ag[i]),raw_logits=a_raw[i].tolist(),raw_decisions=a_base[i].tolist(),
                margin_over_cap=[float(v) for v in (a_raw[i]-cut)/(.25*scale)],
                support_by_donor=support[i].tolist(),eligible_by_donor=eligible[i].tolist(),
                second_joint_by_donor=[None if not np.isfinite(v) else float(v) for v in joint[i]],
                candidates={}))
            item['candidates'][mode]=dict(withdrawn_by_head={s:bool(missed[i,h]) for h,s in enumerate(SUFFIXES)},
                mapped_support_by_donor=transform(support[i]).tolist())
        results[mode]=summary
        np.savez_compressed(OUT/(mode+'_DECISIONS.npz'),normal_corrected=ndec,attack_union_added_fn=missed)
    write(OUT/'CAP_REACHABLE_ATTACK_CASES.json',all_case_details)
    output_files={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ('RESULT.json','progress.json')}
    final=dict(status='PASS',source_job='179602',p1_identity=p1_identity,
        candidates=results,cap_reachable_attack_case_count=len(case_ids),
        cap_reachable_attack_uids=sorted(case_ids),
        guard=dict(attack_rows=int(ag.sum()),normal_rows=int(ng.sum())),
        source_CAN_distinguish_p_safety=len({tuple(v['overall'][s]['added_fn_count'] for s in SUFFIXES) for v in results.values()})>1,
        no_new_encoding=True,no_training=True,no_AB_inputs_loaded=True,
        support_function='s>0: 1-(1-s)^p; s=0:0; positive saturation I(s>0)',
        donor_semantics='union of newly missed UIDs across all legal same-protocol source donors, per head',
        peak_rss_bytes=PEAK_RSS,rss_limit_bytes=RSS_LIMIT,threadpool_info=threadpool_info(),
        elapsed_seconds=time.monotonic()-STARTED,output_sha256=output_files)
    write(OUT/'RESULT.json',final)
    STATE['status']='COMPLETE';progress('COMPLETE')
    print('C5_SOURCE_CAL_REPLAY_COMPLETE',json.dumps({m:{s:v['overall'][s]['added_fn_count'] for s in SUFFIXES} for m,v in results.items()}),flush=True)


if __name__=='__main__':
    threading.Thread(target=watch_memory,daemon=True).start()
    try:
        with threadpool_limits(limits=2):main()
    except BaseException:
        STATE.update(status='FAILED',error=traceback.format_exc())
        progress('FAILED');raise
    finally:
        STOP.set()
