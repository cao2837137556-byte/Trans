"""C4: immutable-old-bank top-up; encode on HPC, one local gated evaluation."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='4'
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['CUDA_VISIBLE_DEVICES']=''
import argparse
import gc
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
import numpy as np
from hnr.common import PACKAGE,ROOT,TARGETS,read,rows,write,sha,require,digest
from hnr.assets import joined,load_assets,helpers,score_dev
from hnr.encoding import concatenate
from hnr import evaluation as ev
from hnr.runtime import Runtime
from gates import dev_gate,final_gate,NET,GROUP
import constrained_onboarding_core_v3 as core

def semantic(value):
    if isinstance(value,dict):return {k:semantic(v) for k,v in value.items() if k not in ('root','path','runtime_root','tshark','normalizer','assets_manifest')}
    if isinstance(value,list):return [semantic(v) for v in value]
    return value

def verify(stage):
    card=read(PACKAGE/'EXECUTION_CARD.json');require(card['candidate']=='C4_HISTORY_SAMPLE_COVERAGE_TOPUP','CANDIDATE')
    for name,expected in card['code_sha256'].items():require(sha(PACKAGE/name)==expected,'CODE_PIN:'+name)
    require(digest(semantic(read(PACKAGE/'config/EXECUTION.json')))==card['config_semantic_sha256'],'CONFIG_SEMANTICS')
    if stage=='encode':
        for rel,expected in read(PACKAGE/'INPUT_MANIFEST.json')['local_inputs'].items():
            if rel.startswith('repo/ood/') or rel.startswith('runs/dense_reference_ab_stage_candidate_v1_20261028/src/'):
                require(sha(ROOT/rel)==expected,'SHARED_CODE_PIN:'+rel)
    if stage=='evaluate':
        for rel,expected in read(PACKAGE/'INPUT_MANIFEST.json')['local_inputs'].items():require(sha(ROOT/rel)==expected,'INPUT_PIN:'+rel)
    return card

def latch(stage):
    with (PACKAGE/(stage.upper()+'_ATTEMPT.json')).open('x',encoding='utf-8') as f:
        json.dump(dict(stage=stage,execution_card_sha256=sha(PACKAGE/'EXECUTION_CARD.json'),no_retry=True),f)

def guard(q):return (q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)

def corrected(raw,q,support,frozen):
    g=guard(q);value=core.apply_correction(raw,support,frozen['scales'],.25);value[g]=raw[g]
    return value,ev.decisions(value,frozen),g

def old_references(arrays=True):
    packs=[]
    for key in ('TP_LINK','WEMO_POWER','SAMSUNG'):
        rr=list(rows(PACKAGE/f'inputs/{key}_references.jsonl.gz'))
        require(all(r['use']=='REFERENCE' and r['history_role']=='HIST_REF' and r['label']==0 for r in rr),'OLD_REF_ROLE')
        if arrays:
            item=read(PACKAGE/'INPUT_MANIFEST.json')['history_arrays'][key]
            with np.load(ROOT/item,allow_pickle=False) as z:
                require(z['uid'].tolist()==[r['uid'] for r in rr],'OLD_REF_UID')
                packs.append(joined(rr,z['e3'].copy(),z['q14'].copy()))
        else:packs+=rr
    return joined(**concatenate(packs)) if arrays else packs

def join_packs(packs):return joined(**concatenate(packs))

def dataset(directory,name):
    rr=list(rows(Path(directory)/(name+'.jsonl.gz')))
    with np.load(Path(directory)/(name+'.npz'),allow_pickle=False) as z:
        require(z['uid'].tolist()==[r['uid'] for r in rr],'ENCODED_UID_JOIN')
        return joined(rr,z['e3'].copy(),z['q14'].copy())

def cleanup(member):
    member=Path(member).resolve();require(member.is_relative_to(PACKAGE/'outputs/encoding'),'CLEANUP_SCOPE')
    removed=[]
    for name in ('chronological.pcapng','candidates.sqlite','contexts_1.sqlite','contexts_2.sqlite'):
        p=member/name
        if p.is_file():
            require(not p.is_symlink() and p.resolve().parent==member,'CLEANUP_PATH')
            removed.append(dict(name=name,bytes=p.stat().st_size,sha256=sha(p)));p.unlink()
    write(member/'INTERMEDIATE_CLEANUP.json',dict(files=removed,selected_evidence_retained=True))

def encode():
    card=verify('encode');cfg=read(PACKAGE/'config/EXECUTION.json')
    import torch
    environment=dict(system=platform.system(),python=platform.python_version(),numpy=np.__version__,torch=str(torch.__version__).split('+')[0])
    require(environment==dict(system='Linux',python='3.11.11',numpy='2.0.1',torch='2.5.1'),'HPC_ENVIRONMENT:'+str(environment))
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    from hnr.history import prepare_member
    from hnr.encoding import new_encoder,encode_member
    latch('encode');old=old_references(arrays=False)
    with Runtime(PACKAGE/'outputs/encoding') as runtime:
        write(runtime.output/'ENVIRONMENT.json',environment)
        encoder=identity=None;members={}
        for spec in cfg['devices']:
            # Refuse avoidable disk exhaustion before a complete member traversal.
            require(shutil.disk_usage(runtime.output).free>spec['raw']['bytes']*3+2*2**30,'MEMBER_SCRATCH_HEADROOM')
            output=runtime.output/'history'/spec['key']
            prepared=prepare_member(spec,output,old,runtime,cfg['tshark'])
            require(prepared['status']=='PREPARED','PREPARE_STATUS')
            if encoder is None:encoder,identity=new_encoder(cfg['encoder'])
            encoded=encode_member(output,output/'encoded',dict(cfg['encoder'],old_rows=old),runtime,encoder=encoder,encoder_identity=identity)
            if spec['key']!='NETATMO':require(not encoded['HIST_DEV']['rows'],'OLD_DEV_MUST_BE_REUSED')
            else:
                assets=load_assets();frozen=assets.calibration()
                net_scored=score_dev(joined(**encoded['HIST_DEV']),assets,frozen,runtime)
                with (output/'encoded/DEV_LOGITS.npz').open('xb') as stream:
                    np.savez(stream,uid=np.asarray(net_scored['feature_uids']),raw_logits=net_scored['logits'])
                assets.immutable();del assets,frozen,net_scored
            members[spec['key']]=dict(new_references=len(encoded['HIST_REF']['rows']),new_dev=len(encoded['HIST_DEV']['rows']),
                selection_sha256=sha(output/'selection/SELECTION.json'),encode_sha256=sha(output/'encoded/ENCODE_RESULT.json'))
            cleanup(output);del encoded;gc.collect()
        del encoder;gc.collect()
        result=dict(status='C4_ENCODING_COMPLETE',members=members,execution_card_sha256=sha(PACKAGE/'EXECUTION_CARD.json'),
            model_training=0,AB_evaluations=0,old_DEV_encodings_reused=True)
        runtime.finish(result)

def saved_dev(inputs):
    rr=list(rows(ROOT/inputs['dev_rows']))
    with np.load(ROOT/inputs['dev_decisions'],allow_pickle=False) as z:saved={k:z[k].copy() for k in z.files}
    require(saved['uid'].tolist()==[r['uid'] for r in rr],'DEV_BASE_UID')
    features={}
    for key,path in inputs['dev_arrays'].items():
        with np.load(ROOT/path,allow_pickle=False) as z:
            ids=z['uid'].copy();e3=z['e3'].copy();q14=z['q14'].copy()
        for i,uid in enumerate(ids):
            require(str(uid) not in features,'DEV_DUPLICATE_UID');features[str(uid)]=(e3[i].copy(),q14[i].copy())
    require(set(features)==set(saved['uid']),'DEV_FULL_UID_ALIGNMENT')
    e3=np.stack([features[r['uid']][0] for r in rr]);q=np.stack([features[r['uid']][1] for r in rr])
    require(np.array_equal(q,saved['q14']),'DEV_Q14_BASELINE')
    return joined(rr,e3,q,logits=saved['raw_logits']),saved

def report(pool,data,saved,after,support,eligible,spec):
    metrics=helpers().metrics;rr=data['rows'];metrics.validate_full_weights(rr,pool)
    keep=np.flatnonzero(metrics.post_window_mask(rr,spec['windows']));views={}
    for name,ix in (('full',np.arange(len(rr))),(ev.PRIMARY,keep)):
        subset=[rr[int(i)] for i in ix];weights=metrics.original_weights(rr) if name=='full' else metrics.hierarchical_weights(subset,pool)
        reports={}
        for j,suffix in enumerate(ev.SUFFIXES):
            r=metrics.report(subset,saved['base'][ix,j],after[ix,j],weights,eligible[ix],support[ix]);r['protection']=ev.protection_gate(r);reports[suffix]=r
        views[name]=dict(rows=len(ix),retained_uid_sha256=core._uid_hash([r['uid'] for r in subset]),weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest(),reports=reports)
    return dict(pool=pool,query_rows=len(rr),original_devices=sorted({r['device'] for r in rr if r['label']==0}),views=views)

def evaluate(encoded_dir):
    card=verify('evaluate');inputs=read(PACKAGE/'INPUT_MANIFEST.json');encoded_dir=Path(encoded_dir).resolve()
    receipt=read(encoded_dir/'RESULT.json');require(receipt['status']=='C4_ENCODING_COMPLETE' and receipt['execution_card_sha256']==sha(PACKAGE/'EXECUTION_CARD.json'),'ENCODE_COMPLETION')
    stage_receipt=read(encoded_dir/'STAGE_RECEIPT.json')
    for rel,expected in stage_receipt['outputs'].items():require(sha(encoded_dir/rel)==expected,'ENCODE_OUTPUT_PIN:'+rel)
    assets=load_assets();frozen=assets.calibration();prior=old_references();newpacks=[];netdev=None
    for key in TARGETS:
        directory=encoded_dir/'history'/key/'encoded';new=dataset(directory,'references');newpacks.append(new)
        if key=='NETATMO':netdev=dataset(directory,'queries')
    additions=join_packs(newpacks);history=join_packs([prior,additions])
    physical=lambda r:(r['origin_raw_sha256'],r['origin_packet_ordinal'],r['owner'])
    require(len({physical(r) for r in history['rows']})==len(history['rows']),'HIST_PHYSICAL_UNIQUE')
    latch('evaluate')
    evaluation_runtime=Runtime(PACKAGE/'outputs/evaluation')
    remaining=card['limits']['total_wall_seconds']-float(stage_receipt['elapsed_seconds'])
    require(remaining>0,'ENCODING_EXHAUSTED_TOTAL_WALL_BUDGET')
    evaluation_runtime.limits['wall_seconds']=remaining
    with evaluation_runtime as runtime:
        previous_dev,saved=saved_dev(inputs)
        with np.load(encoded_dir/'history/NETATMO/encoded/DEV_LOGITS.npz',allow_pickle=False) as z:
            require(z['uid'].tolist()==netdev['feature_uids'],'NET_DEV_LOGIT_UID')
            netdev['logits']=z['raw_logits'].copy()
        dev=join_packs([previous_dev,netdev]);dev['logits']=np.concatenate([previous_dev['logits'],netdev['logits']])
        require(not {r['uid'] for r in dev['rows']}&{r['uid'] for r in history['rows']},'HIST_REF_DEV_OVERLAP')
        baseline=np.concatenate([saved['corrected'],ev.decisions(netdev['logits'],frozen)])
        old_support=np.concatenate([saved['original_support'],np.zeros(len(netdev['rows']))])
        bank=ev._bank(history,frozen['normalizer']);pairs=ev._actual_pairs(bank,dev['rows'])
        require(pairs<=card['dev_pair_upper_bound'],'DEV_PAIR_PLAN')
        trace=ev.support_once(bank,dev,frozen['geometry'],runtime,'HIST_DEV_SUPPORT')
        require(np.all(trace['support']>=old_support-1e-12),'DEV_SUPPORT_MONOTONE')
        logits,after,g=corrected(dev['logits'],dev['q14'],trace['support'],frozen)
        gate=dev_gate(dev['rows'],baseline,after)
        out=runtime.output/'dev';out.mkdir()
        from hnr.common import write_rows
        write_rows(out/'QUERIES.jsonl.gz',dev['rows'])
        np.savez_compressed(out/'DECISIONS.npz',uid=np.array(dev['feature_uids']),raw_logits=dev['logits'],q14=dev['q14'],
            before=baseline,corrected=after,corrected_logits=logits,support=trace['support'],eligible=trace['eligible'],guard=g)
        write(out/'GATE.json',gate)
        if gate['status']!='PASS_DEV':runtime.finish(dict(status='STOP_DEV_FAIL',dev=gate,AB_evaluated=False,method_frozen='C3'));return
        # No AB metadata or logits loaded before the historical DEV gate passes.
        previous=read(ROOT/inputs['c3_result'])['pools'];pools={};new_normals=new_attacks=0;untouched=True
        write(runtime.output/'AB_ATTEMPT.json',dict(candidate=card['candidate'],dev_gate_sha256=sha(out/'GATE.json'),retries=0))
        for pool in ('CIC_DEV','UNSW_DEV'):
            spec=assets.spec['pools'][pool];rr=assets.inputs.rows(spec['query']['rows'])
            with np.load(ROOT/inputs['c3_decisions'][pool],allow_pickle=False) as z:old={k:z[k].copy() for k in z.files}
            require(old['uid'].tolist()==[r['uid'] for r in rr],'AB_BASELINE_UID')
            destination=runtime.output/'ab'/pool;destination.mkdir(parents=True)
            if pool=='CIC_DEV':
                shutil.copyfile(ROOT/inputs['c3_decisions'][pool],destination/'DECISIONS.npz')
                require(sha(destination/'DECISIONS.npz')==sha(ROOT/inputs['c3_decisions'][pool]),'A_BYTE_EXACT')
                pools[pool]=previous[pool];write(destination/'RESULT.json',pools[pool]);continue
            data=assets.queries(pool);require(np.array_equal(data['logits'],old['raw_logits']),'B_RAW_LOGITS')
            require(not {r['uid'] for r in data['rows']}&{r['uid'] for r in additions['rows']},'AB_REF_QUERY_OVERLAP')
            dense=assets.dense(pool);merged=ev.union_bank(dense,history);bank=ev._bank(merged,frozen['normalizer'],history_replay=True)
            ix=np.array([i for i,r in enumerate(rr) if r['device'] in GROUP],dtype=np.int64)
            subset=ev._subset(data,ix);exact=ev._actual_pairs(bank,subset['rows'])
            require(runtime._pairs+exact<=card['pair_limit'],'TOTAL_EXACT_PAIR_PLAN')
            write(runtime.output/'EXACT_PAIR_PLAN.json',dict(dev=pairs,AB=exact,total=pairs+exact,limit=card['pair_limit']))
            new=ev.support_once(bank,subset,frozen['geometry'],runtime,'B_SUPPORT')
            support=old['support'].copy();eligible=old['eligible'].copy();support[ix]=new['support'];eligible[ix]=new['eligible']
            require(np.all(support>=old['support']-1e-12),'B_SUPPORT_MONOTONE')
            logits,after,g=corrected(data['logits'],data['q14'],support,frozen)
            normal=np.array([r['label']==0 for r in rr]);rest=np.array([r['device'] not in GROUP for r in rr])
            require(np.array_equal(g,old['guard']),'GUARD_UNCHANGED')
            untouched=np.array_equal(after[rest],old['corrected'][rest]) and np.array_equal(logits[rest],old['corrected_logits'][rest])
            new_normals=int((normal[:,None]&~old['corrected']&after).sum());new_attacks=int((~normal[:,None]&old['corrected']&~after).sum())
            pools[pool]=report(pool,data,old,after,support,eligible,spec)
            np.savez_compressed(destination/'DECISIONS.npz',uid=old['uid'],raw_logits=data['logits'],corrected_logits=logits,
                base=old['base'],corrected=after,support=support,eligible=eligible,guard=g)
            write(destination/'RESULT.json',pools[pool])
            write(runtime.output/'ATTACK_COVERAGE.json',dict(attack_rows=int((~normal).sum()),guarded_attacks=int((~normal&g).sum()),
                limitation='All B attack rows are SYN-no-ACK guarded; zero withdrawal does not test ACK/UDP over-endorsement.'))
        result=final_gate(previous,pools,new_normals,new_attacks,untouched)
        result.update(candidate=card['candidate'],dev=gate,pools=pools,AB_evaluated=True,evidence='CONSUMED_DEVELOPMENT_ONLY',
            distance_pairs=runtime._pairs,new_reference_rows=len(additions['rows']),new_base_head_training=0,
            normal_regressions=new_normals,attack_withdrawals=new_attacks,untouched_exact=untouched)
        assets.immutable();verify('evaluate');runtime.finish(result)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','encode','evaluate']);parser.add_argument('--execute-real-data',action='store_true');parser.add_argument('--encoded-dir',type=Path)
    args=parser.parse_args()
    if args.stage=='check':print(json.dumps(verify('evaluate')['candidate']))
    else:
        require(args.execute_real_data,'EXPLICIT_EXECUTE_FLAG')
        if args.stage=='encode':encode()
        else:require(args.encoded_dir is not None,'ENCODED_DIRECTORY_REQUIRED');evaluate(args.encoded_dir)
