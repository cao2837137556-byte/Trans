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
    for role in ['NORMAL','HTTP','UDP']:
        spec=seal['roles'][role];groups={}
        with gzip.open(pin(selection/spec['selected_file'],spec['selected_sha256']),'rt') as f:
            for line in f:
                r=json.loads(line);group=str(r['protocol']) if role=='NORMAL' else r['stratum']
                groups.setdefault(group,[]).append(r)
        for group,rr in sorted(groups.items()):
            for r in sorted(rr,key=lambda x:x['uid'])[:(2 if role=='UDP' else 1)]:wanted[r['uid']]=(role,group)
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
def main():
    start=time.monotonic();os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    sys.path[:0]=[str(ROOT/'runs/edge_formal_execution_v4_20261104'),str(ROOT/'repo/ood'),str(ROOT/'runs/history_normal_reference_keyrepair_v1_20261031')]
    from streaming import FrozenBackend,module
    from evaluate import FrozenHeads
    from continuous_features_v3 import tokenize,verify_batch,tensor_hash
    from continuous_input_v3 import verify_tokenized
    from hnr.encoding import physical_batch
    engine=module('_forensic_engine',ROOT/'runs/edge_external_test1_engineering_v1_20261103/preflight/engine.py')
    progress('LOAD_FIXED_SAMPLES');receipt=read(HERE/'SAMPLE_RECEIPT.json')
    with gzip.open(pin(HERE/'AB_SAMPLES.json.gz',receipt['payload_sha256']),'rt') as f:ab=json.load(f)
    edge=edge_samples();samples=ab+edge
    if PHASE=='PREFLIGHT':samples=[next(x for x in ab if x['group']=='NORMAL_17'),next(x for x in edge if x['group']=='UDP/UDP')]
    progress('LOAD_ACTUAL_ENCODER',0,len(samples));backend=FrozenBackend()
    embed,_,model,tokenizer,collator=backend.encoder
    assert not model.training and not any(p.requires_grad for p in model.parameters())
    encoder_root=ROOT/'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime'
    checkpoint=pin(encoder_root/'vendor/netFound-base/model.safetensors',receipt['ab_encoder_checkpoint_sha256'])
    from safetensors import safe_open
    live=model.state_dict();matched=0;missing=[];different=[]
    with safe_open(str(checkpoint),framework='pt',device='cpu') as saved:
        keys=set(saved.keys())
        for key,value in live.items():
            if not key.startswith('base_transformer.'):continue
            if key not in keys:missing.append(key);continue
            import torch
            expected=saved.get_tensor(key).to(dtype=value.dtype)
            if not torch.equal(value.cpu(),expected):different.append(key)
            matched+=1
    assert matched>0 and not missing and not different,('ENCODER_LIVE_WEIGHTS',matched,missing,different)
    freeze,spec,norm,pins=engine.frozen_assets();PINS.update({str(ROOT/k):v for k,v in pins.items()});heads=FrozenHeads(spec,norm)
    weights=[]
    for seed in [27,127,227]:
        with np.load(ROOT/spec['heads']['endpoints'][str(seed)]['head.npz']['path']) as f:weights.append({k:f[k].copy() for k in f.files})
    result=dict(status='RUNNING',phase=PHASE,same_encoder_checkpoint_as_ab=True,checkpoint_sha256=sha(checkpoint),
                live_encoder_tensors_exact=matched,encoder_eval=True,encoder_frozen=True,heads_order=[27,127,227],
                same_heads_and_normalizer_pins=pins,ab_runtime_versions=receipt['ab_runtime_versions'],
                head_branch_nonzero_weights=[dict(e3=int(np.count_nonzero(w['0.weight'][:,:768])),q14=int(np.count_nonzero(w['0.weight'][:,768:]))) for w in weights],samples=[])
    for index,s in enumerate(samples):
        progress('FRESH_FORWARD',index,len(samples),dataset=s['dataset'],group=s['group'])
        q=independent_q(s['body'],s['row']);assert np.array_equal(q,np.asarray(s['expected_q14'],np.float32)),'Q14_RECONSTRUCTION'
        example=tokenize(tokenizer,s['body']['flow']);verify_tokenized(s['body']['flow'],s['body']['provenance'],example)
        batch=collator([example]);verify_batch([example],batch);actual,n=physical_batch(batch,1,tensor_hash)
        ih=tensor_hash(actual,0)
        if 'input_hash' in s:assert ih==s['input_hash'],'ENCODER_INPUT_HASH'
        before=time.monotonic();all_z=embed.core.e3_forward_batches(model,[actual],'cpu');assert all_z.shape==(16,768)
        assert all(np.array_equal(all_z[0],v) for v in all_z),'CLONE_ROWS'
        z=all_z[0];expected=np.asarray(s['expected_e3'],np.float32);ze=float(np.max(np.abs(z-expected)))
        pred=heads.scores(z[None,:],q[None,:])[0];saved_pred=np.asarray(s['expected_scores']);se=float(np.max(np.abs(pred-saved_pred)))
        independent=numpy_scores(z,q,norm,weights);ne=float(np.max(np.abs(pred-independent)))
        cuts=np.asarray(freeze['calibration']['cuts']['cuts']);same_decisions=bool(np.array_equal(pred>cuts,saved_pred>cuts))
        entry=dict(dataset=s['dataset'],group=s['group'],uid=s['uid'],packets=sum(s['body']['flow']['counts']),
                   input_sha256=ih,e3_max_abs_error=ze,head_max_abs_error=se,numpy_head_max_abs_error=ne,
                   same_seed_decisions=same_decisions,fresh_scores=pred.tolist(),saved_scores=saved_pred.tolist(),
                   fresh_e3_std=float(np.std(z)),e3_zero_branch_score_delta=(numpy_scores(np.zeros(768,np.float32),q,norm,weights)-independent).tolist(),
                   q14_zero_branch_score_delta=(numpy_scores(z,np.zeros(14,np.float32),norm,weights)-independent).tolist(),
                   seconds=time.monotonic()-before)
        result['samples'].append(entry);write(PHASE+'_RESULT.json',result)
        assert ze<=receipt['tolerances']['e3_abs'] and se<=receipt['tolerances']['head_abs'] and ne<=.002 and same_decisions,('REPLAY_MISMATCH',entry)
    result.update(status='PASS',seconds=time.monotonic()-start,source_writes=0,training=0,threshold_fit=0,
                  limitations=['Finite score-independent slices; no universal extraction-correctness claim','Zero-branch interventions test wiring/sensitivity, not a trained ablation or performance improvement'],
                  source_pins=PINS)
    write(PHASE+'_RESULT.json',result);progress('PASS',len(samples),len(samples))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['PREFLIGHT','FULL'],required=True);PHASE=parser.parse_args().phase
    try:main()
    except Exception as e:
        import traceback
        write(PHASE+'_STOP.json',dict(status='FAIL',error=repr(e),traceback=traceback.format_exc()));raise
