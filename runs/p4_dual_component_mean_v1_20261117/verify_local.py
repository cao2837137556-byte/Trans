"""Exercise the packaged paths against the archived geometry, weights, and boundary cases."""
import gzip
import json
from pathlib import Path
import sys
import tarfile
import tempfile

import numpy as np

from pack import ACCEPT, HERE, PREV, PRIVATE, RUNS, digest, read
from reports import A, B, headline, paper_text, require


def original_batch(root):
    proof = [json.loads(x) for x in gzip.decompress((root/'tensor/HEIM.jsonl.gz').read_bytes()).splitlines()]
    selected = [r for r in proof if r['shape'] == [6,13,1]]
    base = RUNS/'history_normal_reference_c3_progress_repair_v1_20261101/retrieved/encoded'
    with gzip.open(base/'references.jsonl.gz','rt',encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    uids = [r['uid'] for r in rows]
    with np.load(base/'references.npz',allow_pickle=False) as arr:
        require(arr['uid'].tolist() == uids, 'ORIGINAL_LOCAL_HEIM_UID')
        vectors = arr['e3']
        for pin in selected:
            require(digest(vectors[uids.index(pin['uid'])].tobytes()) == pin['feature_sha256'],
                    'ORIGINAL_LOCAL_E3_SHA')
    return dict(input_tensors=len(selected),captures=sorted({rows[uids.index(r['uid'])]['capture_id'] for r in selected}))


def paired_fixture():
    from common_round1 import artifact
    from geometry import top_two
    from vendor import constrained_onboarding_core_v3 as core, p4_worker
    from worker import formal_outputs, score_arms, witness
    from reports import matched
    geom = dict(geometry={'protocols':{'6':dict(status='READY',rho_z=1.,rho_q=1.)}},
                context_radii={'6':dict(status='READY',rho_c=1.)})
    def row(i,ref=False):
        return dict(uid=('r' if ref else 'q')+str(i),device='fixture',partition='DEV',
             component_id='c'+str(i),capture_id='cap',protocol=6,frame=i+1 if ref else i+5,
             timestamp=1. if ref else 5.,reference_end=2.,bank_end_frame=3,use='REFERENCE' if ref else 'QUERY',
             label=0 if ref or i%2==0 else 1,source_role='NORMAL' if ref or i%2==0 else 'HTTP')
    refs=[row(i,True) for i in range(3)]
    rr=[row(i) for i in range(8)]
    ids=[r['uid'] for r in rr]
    z=np.ones((8,768))
    q=np.zeros((8,14))
    q[-1,[0,2]]=1
    physical=np.zeros((8,8))
    bank=core.ReferenceBank(refs,z[:3],np.tile(np.array([.1,.75,.9])[:,None],(1,14)),
         (np.zeros(768),np.ones(768)),feature_uids=[r['uid'] for r in refs],q_uids=[r['uid'] for r in refs])
    rc=np.zeros((3,8))
    g=top_two(rr,z,q,physical,bank,rc,geom,lambda *args,**kwargs:None)
    raw=p4_worker.four(np.full((8,3),.8))
    method=dict(scales=[4.,4.,4.],cuts=[0.]*4)
    d=dict(rows=rr,ids=ids,z=z,q=q,x=physical,bank=bank,rc=rc,raw=raw,active=np.ones(8,bool),
           views={'full':(np.arange(8), np.linspace(1.,2.,8))},expansion=np.arange(1.,9.),
           population={'NORMAL':16,'HTTP':20},saved=g['weak'])
    d['p4']=p4_worker.correct(raw,d['saved'],q,method['scales'],True,power=4)
    values=score_arms(d,g,method)
    with tempfile.TemporaryDirectory() as dest:
        out=Path(dest)
        (out/'artifacts').mkdir()
        p=witness(out,'EDGE',d,np.arange(8),g,values,method,geom)
        metrics,pairs,r=formal_outputs(out,'EDGE',d,g,values,p)
        _,_,table=matched(metrics,pairs)
        normal=table['EDGE','full','ensemble','NORMAL','ALL']['n10']
        attack=table['EDGE','full','ensemble','HTTP','ALL']['n10']
        require((normal,attack) == (4,3) and r['changed']['rows'] == 7, 'KNOWN_TWO_WITHDRAWALS_AND_BYPASS')
        require(artifact(out/'artifacts/EDGE_changed.jsonl.gz')['sha256'] == r['changed']['sha256'],'CHANGED_UID_SHA')
    return dict(known_normal=normal,known_attack=attack,protected_retained=1)


def table_identity():
    accepted=[r for r in read(ACCEPT/'METRICS.json') if r['config']==A]
    other=[dict(r,config=B) for r in accepted]
    pairs=[]
    for r in accepted:
        p={k:r[k] for k in ('pool','view','head','group','guard_stratum','rows','weighted_denominator')}
        p.update(left=A,right=B,n00=r['rows']-r['alarm_count'],n11=r['alarm_count'],n01=0,n10=0,
                 weighted_n10=0.,weighted_n11=r['weighted_numerator'])
        if 'HT_denominator' in r:
            p.update(ht_n10=0.,ht_n11=r['ht_alarm_total'])
        pairs.append(p)
    rows=headline(accepted+other,pairs)
    require(len(rows)==44 and all(r['withdrawn']==r['added']==0 for r in rows),'ALL_VIEW_HEAD_GROUP_CELLS')
    require('额外撤回 0 条正常误报' in paper_text(rows,'fixture','fixture'),'GENERATED_PAPER_TEXT')
    return len(accepted)


def main():
    archive=PRIVATE/'package.tar.gz'
    previous=PREV/'.private/package_early_183987.tar.gz'
    require(digest(previous.read_bytes())=='7e86ae2700c8620105c99d995815fb7a88ab8369b06a7a56d963d47e51e7956f',
            'ARCHIVED_RUNTIME_PACKAGE')
    with tempfile.TemporaryDirectory(prefix='p04-dual-') as tmp:
        root=Path(tmp)
        with tarfile.open(archive,'r:gz') as tar:
            m=read(HERE/'PACKAGE_MANIFEST.json')
            require(set(tar.getnames())==set(m['files'])|{'PACKAGE_MANIFEST.json'},'ARCHIVE_CLOSURE')
            for name,pin in m['files'].items():
                require(digest(tar.extractfile(name).read())==pin,'PACKAGED_SOURCE_SHA')
        with tarfile.open(previous,'r:gz') as tar:
            for name in tar.getnames():
                if name.endswith('.py') or name=='tensor/HEIM.jsonl.gz':
                    path=root/name
                    require(path.resolve().is_relative_to(root),'TEST_EXTRACT_SCOPE')
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(tar.extractfile(name).read())
        sys.path.insert(1,str(root))
        from boundary_checks import run
        result=dict(status='PASS',environment='LOCAL',boundaries=run(),paired_fixture=paired_fixture(),
                    frozen_baseline_metric_rows=table_identity(), original_encoder_batch=original_batch(root),
                    package_sha256=digest(archive.read_bytes()), scientific_compute_preflight='PENDING_HPC',
                    formal_job=None)
    (HERE/'LOCAL_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()
