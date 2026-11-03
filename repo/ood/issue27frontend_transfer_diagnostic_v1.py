"""One authorized TRAIN-only fixed-C2 diagnostic; no optimizer or new candidate."""
import argparse
import csv
import gzip
import hashlib
import html
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback
import issue27frontend_transfer_control_v2 as parent

s=parent.s
ROOT=s.ROOT
PARENT=ROOT/'runs/frontend_task_knowledge_transfer_implementation_v2_20260911'
PACKAGE=ROOT/'runs/frontend_transfer_diagnostic_implementation_v1_20260912'
OUT=ROOT/'runs/frontend_transfer_diagnostic_v1_20260912'
T=ROOT/'runs/frontend_task_knowledge_transfer_t_v2_20260911'
E=ROOT/'runs/frontend_task_knowledge_transfer_e_v2_20260911'
CONTRACT=ROOT/'runs/mainline_docs/frontend_transfer_diagnostic_scope_v1_20260912.json'
TOKEN='I_AUTHORIZE_ONE_FIXED_C2_TRAIN_ONLY_DIAGNOSTIC_V1'
LIMITS=dict(seconds=900,memory=8*1024**3,output=64*1024**2)
N_BUCKETS,N_TARGETS,N_TEACHER,N_CONTEXTS,MAX_BATCH=197,15073,9379,10583,32
PARENT_SEAL='5490d9de933ffebe2d398501f1b3d64c61c915f91beea19d7777c1fda92bd895'
T_SEAL='6d51dfa3967ac13352a4bd9f41c40299282fcaf2a20443c5a2b24f4ad4194dec'
E_SEAL='20baf0790e7e01d12699820e1ad849259197883295cae1db5efe2a9cd9e95adb'
TRAIN_PRED_SHA='78ed1b749b91cc9c5d53b5b2aa33bded5a4edd66d670a5691b5fccbe219eeda0'


def local_pins():
    files=list((ROOT/'repo/ood').glob('issue27frontend_transfer_diagnostic*_v1.py'))
    files+=list((ROOT/'scripts').glob('*frontend_transfer_diagnostic_v1.ps1'))
    return {p.relative_to(ROOT).as_posix():s.sha(p) for p in sorted(files)}


def activate():
    s.PACKAGE=PACKAGE
    s.OUTPUTS['D']=OUT
    parent.v1.present=present


def readiness(check=lambda:None,verify_git=True):
    r=parent.readiness(check,verify_git)
    cfg=s.read_json(PACKAGE/'config.json')
    s.require(s.sha(CONTRACT,check)==cfg['diagnostic_contract_sha256'],'DIAGNOSTIC_CONTRACT_DRIFT')
    s.require(s.read_json(CONTRACT)['limits']==LIMITS,'DIAGNOSTIC_CAP_DRIFT')
    counts=s.read_json(CONTRACT)['counts']
    s.require(counts==dict(buckets=N_BUCKETS,targets=N_TARGETS,teacher_targets=N_TEACHER,contexts=N_CONTEXTS,
                          max_batch=MAX_BATCH,student_forwards=2*N_BUCKETS,task_gradient_calls=4*N_BUCKETS,
                          hidden_gradient_calls=N_BUCKETS,optimizer_steps=0),'DIAGNOSTIC_COUNT_DRIFT')
    s.manifest(T,T_SEAL,check)
    s.require(s.read_json(T/'supervisor_terminal.json')['status']=='COMPLETE','T_NOT_COMPLETE')
    # Authenticate exactly the already-generated TRAIN file; no other E product is opened.
    s.require(s.sha(E/'SHA256SUMS',check)==E_SEAL,'E_MANIFEST_IDENTITY')
    entries=dict((rel,h) for h,rel in (line.split('  ',1) for line in (E/'SHA256SUMS').read_text().splitlines()))
    s.require(entries['C2_train.csv.gz']==TRAIN_PRED_SHA and s.sha(E/'C2_train.csv.gz',check)==TRAIN_PRED_SHA,'TRAIN_PREDICTION_PIN')
    return r


def present(out,value):
    status=value.get('status',value.get('phase','STARTING'))
    value=dict(value)
    if status=='COMPLETE':
        value.update(bucket=N_BUCKETS,targets=N_TARGETS,teacher_targets=N_TEACHER)
    elif status=='STOP' and (out/'progress.json').exists():
        progress=s.read_json(out/'progress.json')
        for key in ('bucket','targets','teacher_targets'):value[key]=progress.get(key,0)
    text='# 固定模型的训练侧机制诊断\n\n状态：'+status+'\n\n'
    text+='训练桶：%s/%s；目标：%s/%s；教师目标：%s/%s。\n\n'%(value.get('bucket',0),N_BUCKETS,value.get('targets',0),N_TARGETS,value.get('teacher_targets',0),N_TEACHER)
    text+='耗时：%.1f 分钟。参数更新为 0；异常停止，不重试。\n'%(value.get('elapsed_seconds',0)/60)
    text+=(value.get('reason') or '')+'\n终态以 supervisor_terminal.json 和 SHA256SUMS 为准。\n'
    (out/'status.md').write_text(text,encoding='utf-8')
    (out/'status.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="5"><pre style="font:20px system-ui;white-space:pre-wrap;margin:32px">'+html.escape(text)+'</pre>',encoding='utf-8')


def build(test_path):
    s.PACKAGE=PARENT
    parent.readiness()
    s.manifest(PARENT,PARENT_SEAL)
    result=s.read_json(test_path)
    s.require(result['status']=='PASS' and result['tests_run']==result['tests_passed'],'SYNTHETIC_FAILURE')
    tested=result['tested_code_pins'];local=local_pins()
    s.require(set(local)<=set(tested),'SYNTHETIC_CODE_COVERAGE')
    s.require(all((ROOT/path).resolve().is_relative_to(ROOT.resolve()) and s.sha(ROOT/path)==h for path,h in tested.items()),'CODE_CHANGED_AFTER_TESTS')
    cfg=s.read_json(PARENT/'config.json')
    cfg['code_pins'].update(local_pins())
    cfg.update(scope='One fixed C2 TRAIN-only diagnostic; no optimizer, no evaluation candidates.',
               diagnostic_contract_sha256=s.sha(CONTRACT),test_result_sha256=s.sha(test_path))
    PACKAGE.mkdir(exist_ok=False)
    s.atomic_json(PACKAGE/'config.json',cfg)
    s.atomic_json(PACKAGE/'acceptance.json',dict(result,config_sha256=s.sha(PACKAGE/'config.json')))
    s.seal(PACKAGE);activate();readiness()
    print(s.canonical(dict(status='IMPLEMENTATION_SEALED',tests=result['tests_run'],sha256=s.sha(PACKAGE/'SHA256SUMS'))).decode())


def describe_gradients(tasks,dm):
    import torch
    tasks=dict(tasks)
    zero=next(iter(tasks.values()))
    for name in ('label_A','label_B','guard','teacher'):
        if name not in tasks:tasks[name]={k:torch.zeros_like(v) for k,v in zero.items()}
    tasks['label']={k:tasks['label_A'][k]+tasks['label_B'][k] for k in zero}
    result={}
    for group in list(zero)+['shared']:
        vectors={name:(torch.cat([v['event_projection'],v['encoder']]) if group=='shared' else v[group]) for name,v in tasks.items()}
        result[group]=dict(norms={name:float(v.norm()) for name,v in vectors.items()},pairs={})
        for a,b in [('teacher','label'),('teacher','guard'),('guard','label'),('label_A','label_B')]:
            result[group]['pairs'][a+'__'+b]=dm.vector_metrics(vectors[a],vectors[b])
    return result


def statistics(values):
    import numpy as np
    x=np.asarray(values,dtype=np.float64)
    s.require(x.size>0 and np.isfinite(x).all(),'STATISTICS_INPUT')
    return dict(n=int(x.size),mean=float(x.mean()),rms=float(np.sqrt(np.mean(x*x))),
                min=float(x.min()),p50=float(np.quantile(x,.5)),p90=float(np.quantile(x,.9)),
                p99=float(np.quantile(x,.99)),max=float(x.max()))


def row_summary(rows):
    import numpy as np
    from collections import defaultdict
    groups=defaultdict(list)
    for r in rows:
        for k in ('ALL','label:'+str(r['label']),'source:'+r['source_group'],'family:'+r['attack_family']):groups[k].append(r)
    result={}
    for k,rs in groups.items():
        v={field:statistics([r[field] for r in rs]) for field in ('coordinate_huber','coordinate_rmse','task_residual')}
        v['absolute_task_residual']=statistics([abs(r['task_residual']) for r in rs])
        x=np.array([r['teacher_logit']+r['task_residual'] for r in rs]);y=np.array([r['student_logit'] for r in rs])
        v['anchored_readout_deploy_pearson']=float(np.corrcoef(x,y)[0,1]) if len(rs)>1 and x.std()>0 and y.std()>0 else None
        cos=[r['local_head_teacher_cosine'] for r in rs if r['local_head_teacher_cosine'] is not None]
        v['local_head_teacher_cosine']=statistics(cos) if cos else None
        result[k]=v
    return result


def diagnose(r,out,budget):
    import torch
    from collections import defaultdict
    import issue27frontend_transfer_model_v1 as m
    import issue27frontend_transfer_train_v1 as train
    import issue27frontend_transfer_diagnostic_math_v1 as dm
    m.configure()
    plan=s.read_json(s.pin(r['inputs']['plan'],budget.check));contexts=s.train_metadata(plan,r)
    saved=s.read_json(s.pin(r['inputs']['saved_train_scores'],budget.check))['A']
    guard=s.guard_metadata(contexts,saved,r)
    pdir=s.OUTPUTS['P']; cache=train.load_teacher(contexts,r,pdir,budget)
    index={t['uid']:t for t in s.read_json(pdir/'teacher_index.json')}
    scale=s.read_json(pdir/'preparation_receipt.json')['s_T']
    contexts=train.load_contexts(contexts,s.pin(r['inputs']['train_check_features'],budget.check),budget)
    with gzip.open(E/'C2_train.csv.gz','rt',encoding='utf-8',newline='') as f:
        raw=list(csv.DictReader(f))
    baseline={v['uid']:float(v['logit']) for v in raw}
    s.require(len(raw)==len(baseline)==N_TARGETS and set(baseline)=={t['uid'] for t in s.targets(contexts)},'BASELINE_TRAIN_UIDS')
    s.require(all(math.isfinite(float(v['logit'])) and int(v['hard'])==int(float(v['logit'])>=0) for v in raw),'BASELINE_FINITE_HARD')
    model=m.Student(); projection=m.Projection()
    model.load_state_dict(torch.load(T/'C2.pt',map_location='cpu',weights_only=True),strict=True)
    projection.load_state_dict(torch.load(T/'C2_projection_training_only.pt',map_location='cpu',weights_only=True),strict=True)
    budget.access.update(new_candidate_loads=1,projection_loads=1,teacher_cache_rows=len(cache))
    model.eval();projection.eval();before=[m.state_hash(model),m.state_hash(projection)]
    s.require(before[0]==s.read_json(T/'C2.receipt.json')['state_sha256'],'C2_STATE_IDENTITY')
    groups=dm.parameter_groups(model,projection);params=[p for ps in groups.values() for p in ps]
    s.require({id(p) for p in params}=={id(p) for p in list(model.parameters())+list(projection.parameters())},'PARAMETER_COVERAGE')
    totals={task:{k:torch.zeros(sum(p.numel() for p in ps),dtype=torch.float64) for k,ps in groups.items()} for task in ('label_A','label_B','guard','teacher')}
    owner={g:{c['key']:c for c in contexts if c['targets'][0]['owner']==g} for g in 'AB'}
    keys={g:s.order(owner[g],20,g) for g in 'AB'}
    for g in 'AB':s.require(hashlib.sha256(s.canonical(keys[g])).hexdigest()==plan['accounting']['epoch_order_hashes'][19][g+'_order_sha256'],'EPOCH20_ORDER')
    buckets={g:list(s.buckets(keys[g],N_BUCKETS)) for g in 'AB'}
    rows=[];seen=set();loss_sums=defaultdict(float);bucket_records=[];max_delta=0.;pair_count=0
    vD=scale*projection.weight.detach().to(torch.float64).sum(dim=0)
    for step in range(N_BUCKETS):
        bucket_grad={task:{k:torch.zeros_like(v) for k,v in values.items()} for task,values in totals.items()}
        losses_record={}
        for g in 'AB':
            batch=[owner[g][k] for k in buckets[g][step]]
            s.require(0<len(batch)<=MAX_BATCH and all(c['role']=='train' for c in batch),'BATCH_TRAIN_ONLY')
            qs,hs=model([c['x'] for c in batch],[c['key'] for c in batch],with_hidden=True)
            budget.access['student_forwards']+=1
            losses={'label_'+g:m.label_loss(batch,qs)*(N_BUCKETS/r['data'][g]['contexts'])}
            if g=='A':
                losses['guard'],n=m.guard_loss(batch,qs,guard[0],20,guard[1]);pair_count+=n
                cfg=r['losses']['P2_feature']
                losses['teacher']=m.teacher_loss(batch,hs,projection,cache,{y:cfg['expected_N_T'+str(y)] for y in (0,1)},N_BUCKETS)
                readout=dm.row_diagnostics(batch,qs,hs,projection,cache,index,scale)
                selected=[q[t['event']] for c,q in zip(batch,qs) for t in c['targets'] if t['uid'] in cache]
                sensitivities=torch.autograd.grad(torch.stack(selected).sum(),hs,retain_graph=True,allow_unused=True)
                budget.access['hidden_gradient_calls']+=1
                cosine={t['uid']:dm.vector_metrics(hg[t['event']].detach(),vD)['cosine'] for c,hg in zip(batch,sensitivities) for t in c['targets'] if t['uid'] in cache}
                for v in readout:v['local_head_teacher_cosine']=cosine[v['uid']]
                rows+=readout
            grads=dm.task_gradients(losses,groups);budget.access['task_gradient_calls']+=len(losses)
            for task,values in grads.items():
                for k,v in values.items():bucket_grad[task][k]+=v
                losses_record[task]=float(losses[task].detach());loss_sums[task]+=losses_record[task]/N_BUCKETS
            for c,q in zip(batch,qs):
                for t in c['targets']:
                    uid=t['uid'];s.require(uid not in seen,'REPEATED_TARGET');seen.add(uid)
                    value=float(q[t['event']].detach());old=baseline[uid];delta=abs(value-old);max_delta=max(max_delta,delta)
                    s.require(math.isfinite(value) and delta<=5e-5+2e-5*abs(old) and (value>=0)==(old>=0),'FIXED_DEPLOY_PREDICTION_DRIFT')
            budget.access['contexts_processed']+=len(batch)
            del qs,hs,losses,grads
        for task,values in bucket_grad.items():
            for k,v in values.items():totals[task][k]+=v/N_BUCKETS
        record=dict(bucket=step+1,losses=losses_record,gradients=describe_gradients(bucket_grad,dm))
        bucket_records.append(record)
        with (out/'bucket_diagnostics.jsonl').open('ab') as f:f.write(s.canonical(record)+b'\n')
        budget.check(phase='FIXED_ENDPOINT_DIAGNOSIS',bucket=step+1,targets=len(seen),teacher_targets=len(rows))
    s.require(len(seen)==N_TARGETS and len(rows)==len({v['uid'] for v in rows})==N_TEACHER,'DIAGNOSTIC_DENOMINATORS')
    s.require(budget.access['contexts_processed']==N_CONTEXTS and budget.access['student_forwards']==2*N_BUCKETS,'FORWARD_COUNTS')
    s.require(budget.access['task_gradient_calls']==4*N_BUCKETS and budget.access['hidden_gradient_calls']==N_BUCKETS,'GRADIENT_COUNTS')
    s.require(all(p.grad is None for p in params) and before==[m.state_hash(model),m.state_hash(projection)],'PARAMETERS_CHANGED')
    with (out/'teacher_readout.jsonl').open('xb') as f:
        for row in rows:f.write(s.canonical(row)+b'\n')
    cosine_summary={}
    for group in ('event_projection','encoder','shared','head','projection'):
        for pair in ('teacher__label','teacher__guard','guard__label','label_A__label_B'):
            vs=[b['gradients'][group]['pairs'][pair]['cosine'] for b in bucket_records]
            valid=[v for v in vs if v is not None]
            cosine_summary[group+'/'+pair]=dict(defined=len(valid),zero_norm=len(vs)-len(valid),negative=sum(v<0 for v in valid),statistics=statistics(valid) if valid else None)
    result=dict(status='DIAGNOSTIC_COMPLETE',losses_fixed_epoch20=dict(loss_sums),
                gradient_of_mean_objective=describe_gradients(totals,dm),bucket_cosines=cosine_summary,
                readout=row_summary(rows),guard_pairs_epoch20=pair_count,
                baseline_max_abs_delta=max_delta,parameters_unchanged=True,parameter_grad_none=True,
                targets=N_TARGETS,teacher_targets=N_TEACHER,diagnostic_epoch_order=20,
                limitations=['TRAIN-only fixed-endpoint local geometry, not historical AdamW update directions.',
                             'Readout and local alignment do not establish causal use or out-of-domain benefit.',
                             'Anchored reconstructed teacher logits require teacher rows and are not a deployable head.',
                             'Teacher-to-head and label/guard-to-projection are structurally disconnected; inactive guard also yields zero gradients.',
                             'Row errors are float64 diagnostic summaries; frozen float32 losses retain original context/class denominators.',
                             'No parameter updates, new candidate, ROC, threshold choice or check/expanded access.'])
    s.atomic_json(out/'diagnostic.json',result)
    text='# 训练侧机制诊断完成\n\n参数更新 0；模型状态核对不变。只描述固定端点训练侧机制，不是新检测效果。\n\n'
    text+='固定端点损失：'+json.dumps(result['losses_fixed_epoch20'])+'\n\n'
    text+='共享表示梯度：'+json.dumps(result['gradient_of_mean_objective']['shared'])+'\n\n'
    text+='任务方向残差：'+json.dumps(result['readout']['ALL']['absolute_task_residual'])+'\n\n'
    text+='完整结果见 diagnostic.json；逐桶与逐训练教师目标证据已保存。\n'
    (out/'result.md').write_text(text,encoding='utf-8')
    return result


def worker():
    deadline=time.monotonic()+30
    while not (OUT/'worker_gate.json').exists():
        s.require(time.monotonic()<deadline,'GATE_TIMEOUT');time.sleep(.05)
    gate=s.read_json(OUT/'worker_gate.json')
    s.require(gate['pid']==os.getpid() and gate['parent_pid']==os.getppid() and gate['caps']==LIMITS and gate['workspace_verified'],'DIAGNOSTIC_GATE')
    budget=parent.v1.Budget(OUT,gate['started'],LIMITS)
    budget.access.update(contexts_processed=0,task_gradient_calls=0,hidden_gradient_calls=0,projection_loads=0,teacher_cache_rows=0)
    try:
        r=readiness(budget.check,verify_git=False)
        result=diagnose(r,OUT,budget)
        s.require(budget.access['optimizer_steps']==budget.access['teacher_passes']==budget.access['retries']==budget.access['raw_decodes']==0,'FORBIDDEN_ACTION')
        cfg=s.read_json(PACKAGE/'config.json')
        for path,h in cfg['unrelated_tracked_sha256'].items():s.require(s.sha(ROOT/path,budget.check)==h,'UNRELATED_CHANGED')
        budget.check(True,phase='VERIFIED',bucket=197,targets=15073,teacher_targets=9379)
        s.atomic_json(OUT/'verification.json',dict(status='PASS',parameters_unchanged=True,optimizer_steps=0,targets=15073,teacher_targets=9379))
        terminal=dict(status='WORK_COMPLETE_VERIFIED',stage='D',recipe_sha256=s.RECIPE_SHA,result='diagnostic.json')
    except Exception as exc:
        (OUT/'failure_traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        terminal=dict(status='STOP',stage='D',recipe_sha256=s.RECIPE_SHA,reason=type(exc).__name__+': '+str(exc))
    s.atomic_json(OUT/'access.json',budget.access)
    excluded={'progress.json','progress.jsonl','status.md','status.html','stdout.log','stderr.log','worker_terminal.json'}
    terminal['output_hashes']={p.name:s.sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in excluded}
    s.atomic_json(OUT/'worker_terminal.json',terminal)
    return 0 if terminal['status']=='WORK_COMPLETE_VERIFIED' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('build','check','status','run','worker'))
    parser.add_argument('--test-result',type=Path)
    parser.add_argument('--authorization')
    args=parser.parse_args()
    if args.mode=='build':build(args.test_result);return
    activate()
    if args.mode=='check':readiness();print('FIXED_TRAIN_DIAGNOSTIC_READY');return
    if args.mode=='status':print(s.canonical(parent.v1.status('D')).decode('utf-8'));return
    s.require(args.authorization==TOKEN,'EXPLICIT_FIXED_TRAIN_DIAGNOSTIC_AUTHORIZATION_REQUIRED')
    if args.mode=='worker':raise SystemExit(worker())
    s.require(not OUT.exists(),'DIAGNOSTIC_ATTEMPT_ALREADY_EXISTS')
    command=[str(s.PYTHON),'-B',str(Path(__file__).resolve()),'worker','--authorization',TOKEN]
    result=parent.v1.supervise('D',OUT,LIMITS,command)
    print(s.canonical(result).decode('utf-8'),flush=True)
    raise SystemExit(0 if result['status']=='COMPLETE' else 1)


if __name__=='__main__':
    main()
