"""Five preregistered arms; pure numpy, no fitting or target selection."""
import numpy as np
HEADS=('27','127','227','ensemble')
ARMS={'BASE':(3,True),'GUARD_OFF':(3,False),'P1':(1,True),'P2':(2,True),'P4':(4,True)}
PAIRS={'guard':[('BASE','GUARD_OFF')],
       'exponent':[('P1','P2'),('P2','BASE'),('BASE','P4'),('BASE','P1'),('BASE','P2'),('P1','BASE'),('P1','P4')]}

def guard(q):return (q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)

def scores(raw,s,q,scales,arm):
    raw=np.asarray(raw);s=np.asarray(s)
    assert raw.dtype==np.float64 and raw.ndim==2 and raw.shape[1]==4
    assert s.shape==(len(raw),) and q.shape==(len(raw),14)
    assert np.isfinite(raw).all() and np.isfinite(s).all() and ((s>=0)&(s<=1)).all()
    power,on=ARMS[arm];g=s.copy() if power==1 else np.where(s>0,1.-np.power(1.-s,power),0.)
    # Identical indexing and arithmetic order to frozen common.correction.
    x=raw[:,:3].copy()
    for j,b in enumerate(scales):x[g>0,j]=raw[g>0,j]-(.25*b)*g[g>0]
    if on:x[guard(q)]=raw[guard(q),:3]
    return np.column_stack((x,np.stack([x[:,j] for j in range(3)]).mean(0,dtype=np.float64)))

def groups(rows):
    label=np.array([int(r['label']) for r in rows]);out={'NORMAL':label==0,'ATTACK':label==1}
    for dev in sorted({r['device'] for r in rows}):
        same=np.array([r['device']==dev for r in rows])
        for v,n in [(0,'NORMAL'),(1,'ATTACK')]:out['device:'+dev+' / '+n]=same&(label==v)
    for field in ['source_role','activity','stratum']:
        for value in sorted({str(r.get(field,'')) for r in rows}-{'','None'}):
            same=np.array([str(r.get(field,''))==value for r in rows])
            if field=='source_role' and value in ['HTTP','UDP']:out[value]=same
            for v,n in [(0,'NORMAL'),(1,'ATTACK')]:out[field+':'+value+' / '+n]=same&(label==v)
    return {k:v for k,v in out.items() if v.any()}

def metrics(pool,rows,pred,views,q,expansion=None,population=None,*,group_masks=None):
    out=[];gg=groups(rows) if group_masks is None else group_masks;g=guard(q)
    for view,(ix,weight) in views.items():
        selected=np.zeros(len(rows),bool);selected[ix]=True;weight=np.asarray(weight);assert weight.shape==(len(rows),) and np.isfinite(weight).all() and (weight>=0).all()
        for name,mask in gg.items():
            for condition,gm in [('ALL',np.ones(len(rows),bool)),('GUARD_ON',g),('GUARD_OFF',~g)]:
                ii=np.flatnonzero(selected&mask&gm)
                if not len(ii):continue
                den=float(weight[ii].sum());assert den>0
                for head,j in zip(HEADS,range(4)):
                    positive=pred[ii,j];num=float(weight[ii][positive].sum())
                    r=dict(pool=pool,view=view,head=head,group=name,guard_stratum=condition,rows=len(ii),alarm_count=int(positive.sum()),sample_rate=float(positive.mean()),weighted_numerator=num,weighted_denominator=den,hierarchical_rate=num/den)
                    if expansion is not None:
                        r['ht_alarm_total']=float(expansion[ii][positive].sum());r['ht_selected_expansion_total']=float(expansion[ii].sum())
                        # Only the original role has a sealed population denominator.
                        # Subgroup HT totals are contributions, never fabricated rates.
                        if name in population and condition=='ALL':r.update(HT_denominator=population[name],HT_rate=r['ht_alarm_total']/population[name])
                    out.append(r)
    return out

def paired(pool,rows,a,b,views,q,expansion=None,*,group_masks=None):
    gg=groups(rows) if group_masks is None else group_masks;g=guard(q);out=[]
    for view,(ix,weight) in views.items():
        selected=np.zeros(len(rows),bool);selected[ix]=True
        for name,mask in gg.items():
            for condition,gm in [('ALL',np.ones(len(rows),bool)),('GUARD_ON',g),('GUARD_OFF',~g)]:
                ii=np.flatnonzero(selected&mask&gm)
                if not len(ii):continue
                for j,head in enumerate(HEADS):
                    r=dict(pool=pool,view=view,head=head,group=name,guard_stratum=condition,rows=len(ii),weighted_denominator=float(weight[ii].sum()))
                    for av,bv in [(0,0),(0,1),(1,0),(1,1)]:
                        take=(a[ii,j]==bool(av))&(b[ii,j]==bool(bv));key=f'n{av}{bv}';r[key]=int(take.sum());r['weighted_'+key]=float(weight[ii][take].sum())
                        if expansion is not None:r['ht_'+key]=float(expansion[ii][take].sum())
                    assert sum(r['n'+k] for k in ['00','01','10','11'])==len(ii);out.append(r)
    return out

def invariant(values,s,q,cuts,stage):
    pred={k:v>cuts for k,v in values.items()};g=guard(q);stable=g|(s==0)|(s==1)
    checks=0
    if stage=='guard':
        assert np.all(values['BASE']>=values['GUARD_OFF']);assert not np.any(pred['GUARD_OFF']&~pred['BASE'])
        assert np.array_equal(values['BASE'][~g],values['GUARD_OFF'][~g]);assert not np.any((pred['BASE']!=pred['GUARD_OFF'])[~g]);checks+=4
    else:
        for a,b in [('P1','P2'),('P2','BASE'),('BASE','P4')]:
            assert np.all(values[a]>=values[b]),'SCORE_MONOTONICITY'
            assert not np.any(pred[b]&~pred[a]),'ALARM_SET_MONOTONICITY'
            assert np.array_equal(pred[a][stable],pred[b][stable]),'BOUNDARY_GUARD_DECISION_PARITY';checks+=3
    return dict(status='PASS',checks=checks,strict_decision=True)
