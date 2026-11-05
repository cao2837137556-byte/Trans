"""Actual frozen encoder/head replay; sources read-only, score-independent slices."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
import argparse,gzip,hashlib,importlib.util,json,pickle,sys,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
PROJECT=Path('/public/home/jiangxinwei.zr/work/paper04')
ROOT=PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/checkout'
SOURCE=PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/outputs/gate_182089'
PINS={}
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def pin(p,expected=None):
    got=sha(p)
    if expected:assert got==expected,'SHA:'+str(p)
    PINS[str(p)]=got;return p
def write(name,d):
    p=HERE/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**extra):write(PHASE+'_PROGRESS.json',dict(stage=stage,done=done,total=total,**extra))
def independent_q(body,row):
    import math
    p=body['provenance'];proto=row['protocol'];matches=[]
    for b,d in zip(p['bursts'],body['flow']['directions']):
        matches += [(h,d) for f,h in zip(b['frames'],b['headers']) if f==row['frame']]
    assert len(matches)==1;h,d=matches[0];flags=h[5] if proto==6 else 0
    q=[float(proto==6)]+[float(bool(flags&(1<<i))) for i in range(9)]
    q += [math.log1p(h[2])/math.log(65536),math.log1p(h[6])/math.log(65536) if proto==6 else 0.,math.log1p(h[5])/math.log(65536) if proto==17 else 0.,float(d)]
    return np.asarray(q,np.float32)
def edge_samples():
    wanted={};selection=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=read(selection/'QUERY_SELECTION_SEAL.json')
    for role in ['NORMAL','UDP']:
        spec=seal['roles'][role]
        with gzip.open(pin(selection/spec['selected_file'],spec['selected_sha256']),'rt') as f:
            rr=[json.loads(line) for line in f]
        rr=[r for r in rr if r['protocol']==17]
        for r in sorted(rr,key=lambda x:hashlib.sha256(('context-v1|'+x['uid']).encode()).hexdigest())[:16]:wanted[r['uid']]=(role,'UDP')
    enc=read(pin(SOURCE/'encoded/COMPLETE.json','7b0ffe2288281e8b15d91d8955392710f747604d051ce248b053f7ab9266ca01'));found={}
    for b in enc['batches']:
        take=set(b['uids'])&set(wanted)
        if not take:continue
        base=SOURCE/'encoded/batches'/b['batch_id'];m=read(pin(base/'MANIFEST.json',b['manifest_sha256']))
        for name,v in m['files'].items():pin(base/name,v['sha256'])
        rr=read(base/'rows.json');z=np.load(base/'E3.npy');q=np.load(base/'q14.npy')
        for i,r in enumerate(rr):
            if r['uid'] in take:found[r['uid']]=dict(dataset='EDGE',group='/'.join(wanted[r['uid']]),uid=r['uid'],row=r,expected_e3=z[i],expected_q14=q[i],input_hash=r['_input_tensor_sha256'])
    imports=read(pin(SOURCE/'COMPLETE_IMPORT.json','2b169a24e39b250b58e6cd8ba227ec3b03b0215f5227ccf64dd8ec5c0e8416af'))
    for role in ['NORMAL','HTTP','UDP']:
        base=SOURCE/'spools'/role;comp=read(pin(base/'COMPLETE.json',imports['roles'][role]['complete_sha256']))
        for chunk in comp['chunks']:
            folder=base/comp['attempt']/chunk['name'];index=read(pin(folder/'INDEX.json',chunk['index']['sha256']))
            entries=[e for e in index if e['uid'] in found]
            if not entries:continue
            with (folder/'snapshots.bin').open('rb') as stream:
                for e in entries:
                    stream.seek(e['offset']);data=stream.read(e['bytes']);assert hashlib.sha256(data).hexdigest()==e['sha256']
                    value=pickle.loads(data);assert value['uid']==e['uid'];found[e['uid']]['body']=value['body']
    for path in sorted((SOURCE/'evaluation/chunks').glob('q*/MANIFEST.json')):
        m=read(path)
        if not set(m['uids'])&set(found):continue
        pin(path);payload=pin(path.parent/'RESULT.npz',m['sha256'])
        with np.load(payload) as z:
            for i,uid in enumerate(m['uids']):
                if uid in found:found[uid]['expected_scores']=z['raw_scores'][i].copy()
    assert len(found)==len(wanted) and all('body' in v and 'expected_scores' in v for v in found.values())
    return list(found.values())
def numpy_scores(z,q,normalizer,weights):
    x=np.concatenate((((np.asarray(z,dtype=np.float64)-normalizer[0])/normalizer[1]).astype(np.float32),np.asarray(q,np.float32)),axis=-1)
    return np.asarray([(np.maximum(0,x@w['0.weight'].T+w['0.bias'])@w['2.weight'].T+w['2.bias']).item() for w in weights])
