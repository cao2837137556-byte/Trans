"""Fixed synthetic numerical compatibility test; never evaluates real traffic."""
from __future__ import annotations
import copy,json
from pathlib import Path
import numpy as np
import legacy_reference_executor_common_v1 as c

def create_inputs(folder):
    import legacy_reference_executor_fixture_v1 as fixture
    import legacy_reference_executor_features_v1 as features
    import legacy_reference_feature_adapter_v1 as adapter
    import legacy_reference_sample_prepare_v1 as prep
    import issue27ckda_d0_resource_pilot_v1 as translator
    folder=Path(folder);folder.mkdir(exist_ok=False)
    original_package=c.PACKAGE;c.PACKAGE=folder
    try:fx=c.load(fixture.create(folder/'synthetic/input'))
    finally:c.PACKAGE=original_package
    r=fx['recipe'];rows=list(c.rows(r['data']['manifests']['LEARN']['path']))
    refs=[x for x in c.rows(r['data']['manifests']['REFERENCE']['path']) if x['partition']=='LEARN']
    event,prefix,_=prep.old.legacy_runtime();flows=[]
    for spec in fx['catalog']:
        targets=[x for x in rows if x['capture_id']==spec['capture_id']]
        if not targets:continue
        flows.extend(flow for uid,flow in adapter.selected_flows(fx['rows'][spec['capture_id']],targets,spec,[d['mac'] for d in fx['devices']],event,prefix,translator))
    c.atomic_json(folder/'flows.json',flows)
    c.atomic_json(folder/'toy.json',dict(recipe=r,rows=rows,references=refs))
    rng=np.random.default_rng(912)
    state=features.load_state(r,fx)
    with (folder/'toy.npz').open('xb') as f:np.savez(f,features=rng.normal(size=(len(rows),768)).astype(np.float32),references=rng.normal(size=(len(refs),768)).astype(np.float32),**state)

def compute(recipe,inputs,out):
    import legacy_reference_executor_features_v1 as f
    import legacy_reference_executor_train_v1 as t
    inputs=Path(inputs);out=Path(out);out.mkdir(exist_ok=False)
    flows=c.load(inputs/'flows.json');c.require(len(flows)==12,'SYNTHETIC_FLOW_COUNT')
    runtime=f.build_runtime(recipe,synthetic=False)
    values=f.feature_batch(runtime,flows);del runtime
    np.save(out/'encoder.npy',values,allow_pickle=False)
    toy=c.load(inputs/'toy.json')
    with np.load(inputs/'toy.npz',allow_pickle=False) as data:
        state={k:data[k].copy() for k in c.STATE_KEYS};x=data['features'].copy();refs=data['references'].copy()
    for arm in ('Q','M','C'):
        t.train_endpoint(toy['recipe'],state,x,toy['rows'],refs,toy['references'],arm,27,out/arm,synthetic=True)
    c.atomic_json(out/'receipt.json',dict(synthetic_packet_forwards=len(flows),real_traffic_rows=0,real_optimizer_steps=0,synthetic_endpoint_count=3,threshold_selection=False))
    c.seal(out)

def compare(expected,actual):
    expected=Path(expected);actual=Path(actual);c.verify_seal(expected);c.verify_seal(actual)
    evidence={}
    def compare_array(name,a,b):
        c.require(a.shape==b.shape and a.dtype==b.dtype and bool(np.isfinite(b).all()),'COMPAT_SCHEMA:'+name)
        c.require(np.allclose(a,b,rtol=1e-4,atol=1e-5),'NUMERIC_COMPATIBILITY:'+name)
        evidence[name]=float(np.max(np.abs(a-b)))
    compare_array('encoder',np.load(expected/'encoder.npy'),np.load(actual/'encoder.npy'))
    for arm in ('Q','M','C'):
        ar=c.load(actual/arm/'endpoint.json');er=c.load(expected/arm/'endpoint.json')
        for key in ('updates','epochs','row_exposures','permutation_sha256','uid_sha256','weight_sha256','R_identity'):
            c.require(ar[key]==er[key],'COMPAT_TRAIN_EXPOSURE:'+arm+':'+key)
        with np.load(expected/arm/'head.npz') as a,np.load(actual/arm/'head.npz') as b:
            c.require(set(a.files)==set(b.files),'COMPAT_HEAD_KEYS')
            for key in a.files:compare_array(arm+'/'+key,a[key],b[key])
    return dict(status='PASS',rtol=1e-4,atol=1e-5,max_absolute_differences=evidence,scope='Fixed synthetic inputs only; not proof of bitwise full-dataset equivalence or scientific improvement.')
