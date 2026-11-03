"""Shared group indices and compressed counts; no models or test-set tuning."""
from collections import defaultdict
from pathlib import Path
import gzip,json,math
import numpy as np
import legacy_qref_common_v1 as c

FIELDS=[('device',),('device','activity'),('device','protocol'),('device','capture_id'),('device','session_id'),
        ('device','component_id'),('device','normal_activity_stratum'),('device','reference_dependency_stratum'),('eligible',),('device','eligible'),
        ('device','report_direction'),('device','report_local_port')]

def summarize(rows,pred,base,ix=None):
    if ix is None:ix=np.arange(len(rows))
    y=np.array([rows[i]['label'] for i in ix]);w=np.array([1/rows[i]['label_metric_weight_denominator'] for i in ix])
    pp=np.asarray(pred)[ix];bb=np.asarray(base)[ix];result={}
    for label,key in [(0,'normal'),(1,'attack')]:
        mask=y==label;n=int(mask.sum());den=math.fsum(w[mask])
        result[key]=dict(rows=n,positive=int(pp[mask].sum()),rate=float(pp[mask].mean()) if n else None,
                         weighted_positive=math.fsum(w[mask]*pp[mask]),weight=den,
                         weighted_rate=math.fsum(w[mask]*pp[mask])/den if den else None)
    result['paired']=dict(new_attack_misses=int(((y==1)&bb&~pp).sum()),normal_fixed=int(((y==0)&bb&~pp).sum()),
                          normal_new_FP=int(((y==0)&~bb&pp).sum()),recovered_attack=int(((y==1)&~bb&pp).sum()))
    return result

def group_tables(rows,predictions,bases,valid,out,progress):
    out=Path(out);out.mkdir(exist_ok=False)
    y=np.array([r['label'] for r in rows]);w=np.array([1/r['label_metric_weight_denominator'] for r in rows])
    sessions={};sid=np.array([sessions.setdefault((r['device'],r['session_id']),len(sessions)) for r in rows])
    result={name:dict(overall=summarize(rows,p,bases[name]),groups={}) for name,p in predictions.items()}
    progress.begin('GROUP_REPORTS',len(FIELDS))
    for fields in FIELDS:
        index={};keys=[];codes=[]
        for i,r in enumerate(rows):
            key=tuple(str(bool(valid[i])) if f=='eligible' else str(r.get(f,'NA')) for f in fields)
            if key not in index:index[key]=len(keys);keys.append(key)
            codes.append(index[key])
        codes=np.array(codes);ng=len(keys)
        arrays={};label_masks={}
        for label,cl in [(0,'normal'),(1,'attack')]:
            mask=y==label;label_masks[cl]=mask
            arrays[cl+'_rows']=np.bincount(codes[mask],minlength=ng)
            arrays[cl+'_weight']=np.bincount(codes[mask],weights=w[mask],minlength=ng)
        attack=y==1
        pairs=np.stack([codes[attack],sid[attack]],axis=1)
        unique,inv=np.unique(pairs,axis=0,return_inverse=True)
        for name,pred in predictions.items():
            base=bases[name]
            for cl,mask in label_masks.items():
                arrays[name+'__'+cl+'_positive']=np.bincount(codes[mask],weights=pred[mask].astype(np.int64),minlength=ng).astype(np.int64)
                arrays[name+'__'+cl+'_weighted_positive']=np.bincount(codes[mask],weights=w[mask]*pred[mask],minlength=ng)
            for title,mask in [('new_attack_misses',attack&base&~pred),('normal_fixed',(y==0)&base&~pred),
                                ('normal_new_FP',(y==0)&~base&pred),('recovered_attack',attack&~base&pred)]:
                arrays[name+'__'+title]=np.bincount(codes[mask],minlength=ng)
            seen_old=np.bincount(inv,weights=base[attack].astype(int),minlength=len(unique))>0
            seen_new=np.bincount(inv,weights=pred[attack].astype(int),minlength=len(unique))>0
            harmed=np.bincount(inv,weights=(base[attack]&~pred[attack]).astype(int),minlength=len(unique))>0
            for title,mask in [('affected_attack_sessions',harmed),('newly_wholly_missed_sessions',seen_old&~seen_new)]:
                arrays[name+'__'+title]=np.bincount(unique[mask,0],minlength=ng)
        groupname='/'.join(fields);filename='__'.join(fields)
        with (out/(filename+'.npz')).open('xb') as f:np.savez_compressed(f,**arrays)
        with gzip.open(out/(filename+'.keys.json.gz'),'wt',encoding='utf-8') as f:json.dump(dict(fields=fields,keys=keys),f)
        if fields not in [('device','capture_id'),('device','session_id'),('device','component_id')]:
            for name in predictions:
                entries=[]
                for g,key in enumerate(keys):
                    metrics={}
                    for cl in ('normal','attack'):
                        n=int(arrays[cl+'_rows'][g]);pos=int(arrays[name+'__'+cl+'_positive'][g]);den=float(arrays[cl+'_weight'][g])
                        metrics[cl]=dict(rows=n,positive=pos,rate=pos/n if n else None,
                            weighted_positive=float(arrays[name+'__'+cl+'_weighted_positive'][g]),weight=den,
                            weighted_rate=float(arrays[name+'__'+cl+'_weighted_positive'][g])/den if den else None)
                    metrics['paired']={t:int(arrays[name+'__'+t][g]) for t in ['new_attack_misses','normal_fixed','normal_new_FP','recovered_attack','affected_attack_sessions','newly_wholly_missed_sessions']}
                    entries.append(dict(group=dict(zip(fields,key)),metrics=metrics))
                result[name]['groups'][groupname]=entries
        progress.tick()
    c.write(out/'schema.json',dict(shared_denominators=True,keys='ordered keys JSON.gz indexes correspond to npz rows',
        metrics='Rates: positive/rows; weighted_rate: weighted_positive/weight; zero denominator=>NA',
        arms=list(predictions),all_fields=FIELDS,scope='Full original denominator; no dropped capture/session/component group'))
    c.seal(out);return result

def gate(reports,rows,valid):
    q=reports['Q']['overall'];full=reports['FULL']['overall'];fpr=full['normal']['weighted_rate'];base=q['normal']['weighted_rate']
    reasons=[];opportunities=[];improved=[]
    for entry in reports['FULL']['groups']['device']:
        device=entry['group']['device'];ix=np.array([i for i,r in enumerate(rows) if r['device']==device and valid[i]])
        if not len(ix):continue
        # Total per-device errors can only be repaired in eligible strata.
        qr=next(g['metrics'] for g in reports['Q']['groups']['device/eligible'] if g['group']=={'device':device,'eligible':'True'})
        fr=next(g['metrics'] for g in reports['FULL']['groups']['device/eligible'] if g['group']=={'device':device,'eligible':'True'})
        labels={rows[i]['label'] for i in ix}
        if labels=={0,1} and qr['normal']['positive']>0:
            opportunities.append(device)
            if fr['normal']['positive']<qr['normal']['positive'] and entry['metrics']['paired']['new_attack_misses']==0:improved.append(device)
    if full['paired']['new_attack_misses']:reasons.append('NEW_ATTACK_MISSES')
    if full['paired']['normal_new_FP']:reasons.append('NEW_NORMAL_FP')
    seed_ok=sum(reports['FULL_'+str(s)]['overall']['paired']['new_attack_misses']==0 and reports['FULL_'+str(s)]['overall']['paired']['normal_fixed']>0 for s in c.SEEDS)
    informative=base is not None and base>0 and bool(opportunities)
    if informative:
        if fpr>base*.7:reasons.append('WEIGHTED_NORMAL_GAIN_BELOW30PCT')
        if not improved:reasons.append('NO_DEVICE_GAIN')
        if seed_ok<2:reasons.append('SEED_SUPPORT')
    status='FAIL' if reasons else 'PASS' if informative else 'INCONCLUSIVE'
    raw=reports['RAW']['overall'];no=reports['NO_CF']['overall']
    learned=status=='PASS' and fpr<raw['normal']['weighted_rate']
    cf=status=='PASS' and fpr<=no['normal']['weighted_rate'] and full['paired']['new_attack_misses']<=no['paired']['new_attack_misses'] and (fpr<no['normal']['weighted_rate'] or full['paired']['new_attack_misses']<no['paired']['new_attack_misses'])
    personalization=[]
    for device in sorted({r['device'] for r in rows}):
        def direction(suffix):
            correct=next(g['metrics'] for g in reports['FULL_matched_correct'+suffix]['groups']['device'] if g['group']['device']==device)
            wrong=next(g['metrics'] for g in reports['FULL_matched_wrong'+suffix]['groups']['device'] if g['group']['device']==device)
            a=correct['normal']['weighted_rate'];b=wrong['normal']['weighted_rate']
            return a is not None and b is not None and a<b and correct['paired']['new_attack_misses']<=wrong['paired']['new_attack_misses']
        personalization.append(dict(device=device,support=direction('') and sum(direction('_'+str(s)) for s in c.SEEDS)>=2))
    return dict(status=status,reasons=reasons,informative_devices=opportunities,improved_devices=improved,individual_seeds_passing=seed_ok,
        two_device_replication={'Borun Camera','Netatmo Camera'}<=set(improved),learned_over_raw=learned,
        worst_reference_constraint_supported=cf,personalization=personalization,
        evidence='DEVICE_HELD_OUT_SAME_COLLECTION_NOT_POPULATION_RISK_CERTIFICATE',no_threshold_or_model_selection=True)
