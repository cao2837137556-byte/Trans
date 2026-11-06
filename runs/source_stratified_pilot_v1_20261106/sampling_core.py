"""Fixed semantic quotas; conditional PPS draws with unbiased stratum weights."""
import numpy as np
FIELDS=('device','activity','protocol')

def draw(rows,weights,each=8192,seed=20261106):
    labels=np.asarray([r['label'] for r in rows]);weights=np.asarray(weights,np.float64)
    assert len(weights)==len(rows) and np.isfinite(weights).all() and (weights>0).all()
    rng=np.random.default_rng(seed);indices=[];coefficients=[];receipt=[];expected=np.zeros(len(rows));target=np.zeros(len(rows))
    for y in (0,1):
        members={}
        for i in np.flatnonzero(labels==y):
            key=tuple(str(rows[i][f]) for f in FIELDS);members.setdefault(key,[]).append(int(i))
        keys=sorted(members);assert 0<len(keys)<=each
        total=weights[labels==y].sum()
        masses=np.array([weights[members[key]].sum()/total for key in keys])
        raw=(each-len(keys))*masses;quotas=1+np.floor(raw).astype(int)
        remainder=each-int(quotas.sum())
        order=sorted(range(len(keys)),key=lambda j:(-(raw[j]-np.floor(raw[j])),keys[j]))
        quotas[order[:remainder]]+=1;assert quotas.sum()==each and (quotas>0).all()
        for key,mass,count in zip(keys,masses,quotas):
            ix=np.asarray(members[key]);prob=weights[ix]/weights[ix].sum()
            selected=rng.choice(ix,size=int(count),replace=True,p=prob)
            coefficient=float(mass/count)
            indices.extend(selected.tolist());coefficients.extend([coefficient]*int(count))
            expected[ix]=count*coefficient*prob
            receipt.append(dict(label=y,key=list(key),source_rows=len(ix),draws=int(count),
                                unique_rows=len(np.unique(selected)),class_mass=float(mass),per_draw_weight=coefficient))
        target[labels==y]=weights[labels==y]/total
        assert np.allclose(expected[labels==y],target[labels==y],rtol=1e-12,atol=1e-15),'TARGET_EXPECTATION'
    ix=np.asarray(indices,np.int64);w=np.asarray(coefficients,np.float64)
    for y in (0,1):assert (labels[ix]==y).sum()==each and abs(w[labels[ix]==y].sum()-1)<1e-12
    return ix,w,dict(method='fixed semantic quotas; within-stratum PPS with replacement; weight Wg/ng per draw',
        fields=list(FIELDS),seed=seed,draws=len(ix),unique_rows=len(np.unique(ix)),strata=receipt,
        expected_row_weight_max_error=float(np.max(np.abs(expected-target))),
        expectation_verified=True,selection_uses_scores=False,selection_uses_CAL=False,
        unbiased_for_fixed_parameters_before_draw=True,adaptive_training_unbiasedness_claim=False)
