"""Vectorized source-stratum coverage; score derivatives are not parameter gradients."""
import numpy as np

def groups(rows,fields):
    mapping={};keys=[];ids=np.empty(len(rows),np.int64)
    for i,row in enumerate(rows):
        key=tuple(str(row[f]) for f in fields)
        if key not in mapping:mapping[key]=len(keys);keys.append(key)
        ids[i]=mapping[key]
    return keys,ids

def summarize(keys,ids,labels,weights,selected,base,score,zero_base,zero,cut,scale,upper):
    assert scale>0 and len(ids)==len(labels)==len(weights)==len(selected)==len(base)
    assert np.isfinite(score).all() and np.isfinite(base).all()
    out={};g=len(keys);selected=np.asarray(selected,bool)
    for label,name in [(0,'normal'),(1,'attack')]:
        mask=labels==label;take=selected&mask
        w=weights*mask;assert w.sum()>0;w=w/w.sum()
        sw=w*take;sw=sw/sw.sum() if sw.sum()>0 else sw
        positive=np.maximum(base-zero_base,0)
        violation=np.maximum((base-score)/scale-.01,0)
        residual=(score>cut)&mask
        active=(base>upper)&mask if label==0 else (violation>0)&mask
        risk=np.maximum((score-upper)/scale,0)**2 if label==0 else violation**2
        derivative=2*np.maximum((score-upper)/scale,0)/scale if label==0 else 2*violation/scale
        values=dict(rows=mask.astype(float),pilot_rows=take.astype(float),class_mass=w,pilot_class_mass=sw,
            baseline_alarm_mass=w*(base>cut),residual_alarm_mass=w*residual,
            baseline_alarms=mask*(base>cut),residual_alarms=residual.astype(float),
            active_rows=active.astype(float),pilot_active_rows=(active&selected).astype(float),
            score_violation_rows=(mask&(violation>0)).astype(float),pilot_score_violation_rows=(take&(violation>0)).astype(float),
            score_violation_mass=w*(violation>0),objective_risk_mass=w*risk,
            objective_abs_score_derivative_mass=w*derivative,
            original_weighted_risk_on_selected=w*risk*selected,
            original_weighted_score_derivative_on_selected=w*derivative*selected,
            positive_context_mass=w*positive,context_shortfall_mass=w*np.maximum(.9*positive-(score-zero),0)*(positive>0))
        sums={k:np.bincount(ids,weights=v,minlength=g) for k,v in values.items()}
        records=[]
        countfields={'rows','pilot_rows','baseline_alarms','residual_alarms','active_rows','pilot_active_rows','score_violation_rows','pilot_score_violation_rows'}
        for i,key in enumerate(keys):
            if sums['rows'][i]==0:continue
            rec=dict(key=list(key),**{k:int(a[i]) if k in countfields else float(a[i]) for k,a in sums.items()})
            rec['sample_mass_to_population_mass']=rec['pilot_class_mass']/rec['class_mass']
            records.append(rec)
        missing=(sums['rows']>0)&(sums['pilot_rows']==0)
        missed_active=(sums['active_rows']>0)&(sums['pilot_active_rows']==0)
        total_risk=float(np.dot(w,risk));total_derivative=float(np.dot(w,derivative))
        info=dict(rows=int(mask.sum()),pilot_rows=int(take.sum()),strata=len(records),missing_strata=int(missing.sum()),
            missing_stratum_class_mass=float(sums['class_mass'][missing].sum()),
            class_mass_TV_distance=float(np.abs(sums['class_mass']-sums['pilot_class_mass']).sum()/2),
            residual_alarm_mass_in_missing_strata=float(sums['residual_alarm_mass'][missing].sum()),
            objective_risk_mass_in_missing_strata=float(sums['objective_risk_mass'][missing].sum()),
            active_strata_without_sampled_active=int(missed_active.sum()),
            objective_risk_mass_without_sampled_active=float(sums['objective_risk_mass'][missed_active].sum()),
            objective_risk_mass=total_risk,objective_abs_score_derivative_mass=total_derivative,
            selected_share_of_original_risk=float(np.dot(w*risk,selected)/total_risk) if total_risk>0 else None,
            selected_share_of_original_score_derivative=float(np.dot(w*derivative,selected)/total_derivative) if total_derivative>0 else None,
            top_risk_strata=sorted(records,key=lambda a:(-a['objective_risk_mass'],a['key']))[:20],
            top_residual_alarm_strata=sorted(records,key=lambda a:(-a['residual_alarm_mass'],a['key']))[:20])
        out[name]=dict(summary=info,records=records)
    return out

def proposed_samples(labels,weights,actual):
    n=len(labels);actual=np.asarray(actual,bool);out={'ACTUAL_8192_EACH':actual}
    for mode,count in [('UNIFORM_16384_EACH',16384),('WEIGHTED_8192_EACH',8192)]:
        rng=np.random.default_rng(20261106);mask=np.zeros(n,bool)
        for y in (0,1):
            ix=np.flatnonzero(labels==y);assert len(ix)>=count
            if mode.startswith('UNIFORM'):chosen=rng.permutation(ix)[:count]
            else:chosen=rng.choice(ix,count,replace=False,p=weights[ix]/weights[ix].sum())
            mask[chosen]=True
        out[mode]=mask
    return out
