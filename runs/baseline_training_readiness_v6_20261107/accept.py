"""Validate pinned receipts; distinguish engineering passes from training release."""
import hashlib,itertools,json,math
from collections import defaultdict
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
checks=0
def read(n):return json.loads((HERE/n).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(value,label):
    global checks
    assert value,label
    checks+=1
def write(n,v):(HERE/n).write_bytes((json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())

def main():
    for n,h in read('RETRIEVAL.json')['sha256'].items():check(sha(HERE/n)==h,'RETRIEVAL:'+n)
    delivery=read('DELIVERY.json')
    for n,h in delivery['pins'].items():check(sha(HERE/n)==h,'DELIVERY:'+n)
    check(sha(HERE/'receiver.py')==delivery['receiver_sha256'],'RECEIVER')
    check(sha(ROOT/'runs/paper_results_freeze_v1_20261107/METHOD_FREEZE.json')==read('LOCAL_REGRESSION.json')['main_freeze_sha256'],'MAIN_UNCHANGED')
    job=read('JOB.json');check(job==dict(job_id='182749',cpu=1,memory_gib=8,wall_seconds=7200),'JOB')
    scheduler=read('SCHEDULER.json');check(scheduler['returncode']==0,'SACCT')
    lines=[line.split('|') for line in scheduler['stdout'].splitlines()]
    jobrow=next(r for r in lines if r[0]=='182749');batch=next(r for r in lines if r[0]=='182749.batch')
    check(jobrow[1:4]==['COMPLETED','0:0','00:06:39'],'COMPLETED')
    check(batch[4].endswith('K'),'RSS_UNIT');scheduler_mib=float(batch[4][:-1])/1024
    result=read('RESULT.json');spec=read('SPEC.json');check(result['status']=='PASS_WITH_RESOURCE_GATES','RESULT')
    check(result['formal_training_started'] is False,'NO_FORMAL_TRAINING')
    check(set(result['results'])==set(spec['phases']),'ALL_PHASES')
    for phase in spec['phases']:
        r=read(phase+'_RESULT.json');check(r==result['results'][phase],phase+':CONSISTENCY')
        check(r['status']==('NEEDS_RESOURCES' if phase=='NCA_RESOURCE' else 'PASS'),phase+':STATUS')
        check(0<r['seconds']<spec['phase_caps_seconds'][phase],phase+':WALL')
        check(0<r['rss_peak_mib']<6656,phase+':RSS')
    pipe=read('PIPELINE_RESULT.json');enc=pipe['encoder']
    check(sum(v['frames'] for v in pipe['causal'].values())==322679,'REAL_FRAMES')
    check(enc['encoded_rows']==112 and enc['encoded_batches']==7,'FRESH_ENCODING')
    for n in ('e3_max_abs_error','cached_support_error','fresh_support_error'):check(enc[n]==0,n)
    f=read('FIDELITY_RESULT.json');check(all(v['status']=='PASS' for v in f['checks'].values()),'FIDELITY')
    check(not f['author_dataset_replication_required'],'SCOPE_ADJUSTMENT')
    for phase in ('DTE_PILOT','CAT_PILOT'):
        r=read(phase+'_RESULT.json');check(0<=r['source_cal_weighted_fpr']<=.01+1e-12,phase+':CAL')
        check(len(r['checkpoint_sha256'])==64 and not r['formal_training'],phase+':CHECKPOINT_SCOPE')
    check(read('CAT_PILOT_RESULT.json')['reload_exact'],'CAT_RELOAD')
    # DTE result omits a reload flag; the byte-pinned worker calls save_reload,
    # whose exact equality assertion must finish before this result is emitted.
    code=(HERE/'readiness.py').read_text();check("h=save_reload(model.model,folder/'checkpoint.npz',probe)" in code,'DTE_RELOAD_ASSERT_PATH')
    src=read('SOURCE_RESULT.json');check(src['full_fit_rows']==617908 and src['normal_fit_rows']==134493,'SOURCE_SIZE')
    groups=src['groups'];check(len({g['group'] for g in groups})==len(groups)==48,'GROUP_UNIQUE')
    counts=defaultdict(lambda:dict(train_normal=0,valid_normal=0,train_attack=0,valid_attack=0,normal_groups=0,attack_groups=0))
    by_stratum=defaultdict(list)
    captures=[]
    for g in groups:
        devs={c.split('|')[0] for c in g['captures']};check(len(devs)==1,'GROUP_DEVICE')
        device=next(iter(devs));captures.extend(g['captures']);prefix='valid' if g['validation'] else 'train'
        check((g['normal']>0)!=(g['attack']>0),'PURE_CLASS_GROUP_FOR_PROPOSAL')
        for cls in ('normal','attack'):
            counts[device][prefix+'_'+cls]+=g[cls]
            if g[cls]:counts[device][cls+'_groups']+=1;by_stratum[(device,cls)].append(g)
    check(len(captures)==len(set(captures)),'NO_REPEATED_CAPTURE')
    for view,prefix in [('train','train'),('validation','valid')]:
        for cls in ('normal','attack'):check(sum(d[prefix+'_'+cls] for d in counts.values())==src['split_counts'][view][cls],'SPLIT_COUNT')
    check(sum(sum(g[c] for c in ('normal','attack')) for g in groups)==617908,'GROUP_TOTAL')
    missing={cls:sorted(d for d,v in counts.items() if v['valid_'+cls]==0) for cls in ('normal','attack')}
    check(len(missing['normal'])==3 and len(missing['attack'])==4,'COVERAGE_DIAGNOSIS')
    audit=dict(status='NEEDS_STRATIFIED_GROUP_SPLIT',current_split_basic_gate=src['inner_split_gate'],devices=dict(counts),missing_validation=missing,validation_simcam_attack_fraction=counts['SimCam']['valid_attack']/src['split_counts']['validation']['attack'],validation_hue_normal_fraction=counts['Philips Hue Bridge']['valid_normal']/src['split_counts']['validation']['normal'],scores_used=False)
    write('SOURCE_SPLIT_AUDIT.json',audit)
    # Source-only design candidate: exhaustive subset selection within the small
    # device/class group strata. No target scores, no group splitting, no training.
    chosen=[];proposal=[]
    for (device,cls),gs in sorted(by_stratum.items()):
        total=sum(g[cls] for g in gs);options=[]
        for n in range(1,len(gs)):
            for subset in itertools.combinations(gs,n):
                ids=tuple(sorted(g['group'] for g in subset));count=sum(g[cls] for g in subset)
                tie=hashlib.sha256(('source-group-coverage-v1|'+device+'|'+cls+'|'+','.join(map(str,ids))).encode()).hexdigest()
                options.append((abs(5*count-total),tie,ids,count))
        check(bool(options),'SOURCE_STRATUM_SPLIT_FEASIBLE');best=min(options);chosen.extend(best[2])
        proposal.append(dict(device=device,label=cls,train_rows=total-best[3],validation_rows=best[3],validation_groups=list(best[2]),validation_fraction=best[3]/total))
    check(len(chosen)==len(set(chosen)),'PROPOSAL_UNIQUE_GROUPS')
    write('SOURCE_SPLIT_PROPOSAL.json',dict(status='DESIGN_ONLY_NOT_MATERIALIZED',rule='Per device/class choose nonempty proper whole-group subset minimizing abs(5*validation_rows-total_rows); tie by fixed SHA256',source_group_sha256=sha(HERE/'SOURCE_RESULT.json'),selected_validation_group_ids=sorted(chosen),strata=proposal,scores_used=False,cal_used=False,required_before_training=['Materialize new masks on HPC and seal train/validation UID hashes','Verify capture/session/component disjointness on original rows','Audit activity/protocol coverage and weighted metric definition'],old_arrays_unchanged=True))
    nca=read('NCA_RESOURCE_RESULT.json')
    check(not nca['full_pool_backward_executed'] and nca['formal_candidate_cap'] is None,'NCA_SCOPE')
    check(math.isclose(nca['single_expanded_activation_gib'],nca['default_sampled_candidates']*nca['embedded_dim']*4/2**30),'NCA_ALLOCATION')
    check(nca['single_expanded_activation_gib']>8,'NCA_BUDGET_FAIL')
    check(read('DTE_FULL_RESULT.json')['steps']==math.ceil(134493/64),'DTE_EPOCH')
    check(read('TABR_FULL_RESULT.json')['full_candidate_backward'],'TABR_CANDIDATES')
    plan=read('FORMAL_PLAN_SEALED.json');check(sha(HERE/'TRAINING_PROTOCOL.json')==plan['protocol_sha256'],'PLAN_PROTOCOL_SHA')
    check(plan['source_identity']==src['sha256'],'PLAN_SOURCE_SHA')
    check(sha(HERE/'FORMAL_PLAN_SEALED.json')==read('SEAL_RESULT.json')['plan_sha256'],'PLAN_SHA')
    check(not read('SEAL_RESULT.json')['formal_training_ready'],'PLAN_NOT_READY')
    peak=max(scheduler_mib,max(r['rss_peak_mib'] for r in result['results'].values()))
    out=dict(status='ENGINEERING_ACCEPTED_FORMAL_TRAINING_NOT_RELEASED',checks=checks,job_id='182749',scheduler_elapsed_seconds=399,worker_seconds=result['seconds'],conservative_peak_gib=peak/1024,scheduler_peak_mib=scheduler_mib,stage_status_counts={'PASS':13,'NEEDS_RESOURCES':1},new_adapters_passed=['DTE-C','CatBoost'],cumulative_engineering_methods=['TabM','ModernNCA','DisentAD','TabR','SLAD','DTE-C','CatBoost'],formal_training_ready=False,source_split_coverage_gate='NEEDS_REVISION',old_basic_split_gate_preserved=True,main_model_changed=False,large_artifacts='HPC_ONLY; remote file hashes are receipts, not locally rehashed large arrays',required_next=['Materialize and audit source-only coverage-balanced grouped split','Measure epoch plus validation and checkpoint/resume on actual formal resources; qualify full ModernNCA backward','Freeze enumerated trials, sampling distributions, weighting formula and resource limits; qualify all exposed architecture options'],receipt_sha256=read('RETRIEVAL.json')['sha256'])
    write('ACCEPTANCE.json',out);print(json.dumps({k:v for k,v in out.items() if k!='receipt_sha256'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
