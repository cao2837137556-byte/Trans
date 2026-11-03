"""Derive finite margins only from sealed TRAIN teacher records; no model forward."""
import math
import statistics
from collections import defaultdict
import numpy as np
import torch
import issue27frontend_aligned_support_v1 as s


def balanced_mean(values, rows):
    groups=defaultdict(list)
    for i,t in enumerate(rows):groups[(int(t['label']),t['context_key'])].append(i)
    means={y:[] for y in (0,1)}
    for (y,key),indices in sorted(groups.items()):
        indices=sorted(indices,key=lambda i:rows[i]['uid'])
        means[y].append(float(np.mean(np.asarray(values,dtype=np.float64)[indices],dtype=np.float64)))
    s.require(all(means.values()),'EMPTY_TEACHER_CLASS')
    return .5*sum(float(np.mean(means[y],dtype=np.float64)) for y in (0,1))


def derive(rows, values, targets, r):
    cfg=r['teacher_cache'];p=r['losses']['task_score']['p_T']
    s.require(len(rows)==len(targets)==cfg['expected_targets'],'TEACHER_ROW_COUNT')
    s.require(values.shape==(len(rows),128) and values.dtype==np.dtype('<f4') and np.isfinite(values).all(),'TEACHER_VALUES')
    tau=math.log(p)-math.log1p(-p);raw=[];hard=[]
    for i,(row,t) in enumerate(zip(rows,targets)):
        s.require(row['row']==i and all(row[k]==t[k] for k in ('uid','context_key','label')),'TEACHER_CACHE_JOIN')
        q,prob=float(row['canonical_logit']),float(row['canonical_probability'])
        s.require(math.isfinite(q) and math.isfinite(prob) and 0<=prob<=1,'TEACHER_NONFINITE')
        decision=prob>=p
        s.require(decision==bool(t['old_hard'])==bool(t['label']),'TEACHER_CANONICAL_HARD')
        raw.append(q-tau);hard.append(decision)
    margins=np.asarray(raw,dtype=np.float64);m32=margins.astype('<f4')
    s.require(np.isfinite(margins).all() and np.isfinite(m32).all(),'MARGIN_NONFINITE')
    bad=np.flatnonzero(((margins>=0)!=hard)|((m32>=0)!=hard))
    s.require(not len(bad),'MARGIN_HARD_BOUNDARY_MISMATCH:'+','.join(rows[i]['uid'] for i in bad))
    denoms={str(y):len({t['context_key'] for t in rows if t['label']==y}) for y in (0,1)}
    s.require(denoms=={str(y):cfg['expected_N_T'+str(y)] for y in (0,1)},'TEACHER_DENOMINATORS')
    scale=max(1.,math.sqrt(balanced_mean(np.square(margins),rows)));scale32=np.float32(scale)
    s.require(math.isfinite(scale) and bool(np.isfinite(scale32)) and scale32>=1,'TASK_SCALE_NONFINITE')
    v=values.astype(np.float64);res=v-v.mean(axis=1,keepdims=True)
    result=dict(tau_T=tau,s_q64=scale,s_q32=float(scale32),s_q32_hex=scale32.tobytes().hex(),
                denominator=denoms,minimum_signed_margin=float(np.min(np.where(hard,margins,-margins))),
                boundary_mismatches=0,original_energy=balanced_mean(np.mean(v*v,axis=1),rows),
                residual_energy=balanced_mean(np.sum(res*res,axis=1)/127,rows))
    derived=[dict(row,margin64=float(margins[i]),margin32=float(m32[i]),margin32_hex=m32[i].tobytes().hex()) for i,row in enumerate(rows)]
    return derived,m32,result


def load_guard(contexts,r,budget):
    value=s.read_json(s.pin(r['teacher_cache']['guard'],budget.check))
    groups=value['groups'];scale=value['scale'];cfg=r['losses']['A_guard']
    actual={t['uid']:t for t in s.targets(contexts) if t['owner']=='A'}
    seen=set();counts={0:0,1:0};enriched={}
    for key,rows in groups.items():
        s.require(rows and [t['uid'] for t in rows]==sorted(t['uid'] for t in rows),'GUARD_ORDER')
        enriched[key]=[]
        for row in rows:
            uid=row['uid'];s.require(uid in actual and uid not in seen,'GUARD_UID')
            t=actual[uid];seen.add(uid)
            s.require(all(row[k]==t[k] for k in ('uid','context_key','label','component_id','event')) and key==t['context_key'],'GUARD_JOIN')
            s.require(math.isfinite(row['logit']) and int(row['logit']>=0)==t['label'],'GUARD_HARD')
            counts[t['label']]+=1;enriched[key].append(dict(t,logit=row['logit']))
    s.require(len(groups)==cfg['eligible_contexts'] and len(seen)==cfg['eligible_targets'] and
              counts=={0:cfg['eligible_benign'],1:cfg['eligible_attack']},'GUARD_COUNTS')
    expected=max(1.,statistics.median(statistics.mean(abs(t['logit']) for t in vs) for vs in groups.values()))
    s.require(scale==expected==cfg['s_A'],'GUARD_SCALE')
    return enriched,scale


def original_cache(contexts,r,budget):
    # Pin existing inputs only. No original P2 weights, mixed NPZ or feature bodies.
    spec=r['teacher_cache'];manifest=s.pin(spec['manifest'],budget.check)
    entries={rel:h for h,rel in (line.split('  ',1) for line in manifest.read_text(encoding='utf-8').splitlines())}
    terminal=manifest.parent/'supervisor_terminal.json'
    s.require(s.sha(terminal,budget.check)==entries[terminal.name],'ORIGINAL_P_TERMINAL_PIN')
    s.require(s.read_json(terminal)['status']=='COMPLETE','ORIGINAL_P_NOT_COMPLETE')
    for k in ('index','values','guard'):
        path=s.pin(spec[k],budget.check)
        s.require(path.parent==manifest.parent and entries[path.name]==spec[k]['sha256'],'P_CACHE_MANIFEST_JOIN')
    rows=s.read_json(s.ROOT/spec['index']['path'])
    values=np.fromfile(s.ROOT/spec['values']['path'],dtype='<f4')
    s.require(values.size==spec['expected_targets']*128,'TEACHER_FILE_SIZE')
    values=values.reshape(-1,128)
    return rows,values,s.teacher_targets(contexts,r)


def prepare(r,out,budget):
    contexts=s.train_metadata(s.read_json(s.pin(r['inputs']['plan'],budget.check)),r)
    s.pin(r['inputs']['membership'],budget.check)
    load_guard(contexts,r,budget)
    rows,values,targets=original_cache(contexts,r,budget)
    budget.check(True,phase='DERIVING_TRAIN_TARGETS',targets_total=len(rows))
    derived,margins,metadata=derive(rows,values,targets,r)
    with (out/'margins.f32le').open('xb') as f:f.write(margins.tobytes())
    s.atomic_json(out/'teacher_index.json',derived)
    result=dict(metadata,status='TASK_TARGETS_DERIVED',targets=len(rows),recipe_sha256=s.RECIPE_SHA,
        s_T=r['teacher_cache']['s_T'],source_manifest_sha256=r['teacher_cache']['manifest']['sha256'],
        index_sha256=s.sha(out/'teacher_index.json',budget.check),margins_sha256=s.sha(out/'margins.f32le',budget.check))
    s.atomic_json(out/'preparation_receipt.json',result)
    budget.access['derived_teacher_rows']=len(rows)
    budget.check(True,phase='TARGETS_DERIVED',targets_complete=len(rows))
    return result


def load_prepared(contexts,r,folder,budget):
    receipt=s.read_json(folder/'preparation_receipt.json')
    s.require(receipt['status']=='TASK_TARGETS_DERIVED' and receipt['recipe_sha256']==s.RECIPE_SHA,'DERIVED_PREPARATION_IDENTITY')
    rows,values,targets=original_cache(contexts,r,budget)
    expected,m32,metadata=derive(rows,values,targets,r)
    actual=s.read_json(folder/'teacher_index.json')
    s.require(actual==expected and all(receipt[k]==v for k,v in metadata.items()),'DERIVED_TARGET_DRIFT')
    for name,key in [('teacher_index.json','index_sha256'),('margins.f32le','margins_sha256')]:
        s.require(s.sha(folder/name,budget.check)==receipt[key],'DERIVED_FILE_HASH')
    s.require((folder/'margins.f32le').read_bytes()==m32.tobytes(),'MARGIN_BIT_DRIFT')
    s.require(receipt['targets']==len(rows) and receipt['s_T']==r['teacher_cache']['s_T'] and
              receipt['source_manifest_sha256']==r['teacher_cache']['manifest']['sha256'],'SOURCE_PREPARATION_IDENTITY')
    scale=torch.tensor(metadata['s_q32'],dtype=torch.float32)
    tensors=torch.from_numpy(values)
    return {t['uid']:dict(margin=torch.tensor(m32[i],dtype=torch.float32),target=tensors[i],scale=scale) for i,t in enumerate(targets)}
