"""Re-read persisted stage products without additional model or teacher forwards."""
import math
import issue27frontend_aligned_support_v1 as s


def verify_stage(stage,out,r,budget):
    a=budget.access
    s.require(all(a[k]==0 for k in ('raw_decodes','retries','network_requests','teacher_passes')),'FORBIDDEN_ACTION')
    if stage=='P':
        from issue27frontend_aligned_prepare_v1 import load_prepared
        contexts=s.train_metadata(s.read_json(s.pin(r['inputs']['plan'],budget.check)),r)
        cache=load_prepared(contexts,r,out,budget)
        s.require(len(cache)==a['derived_teacher_rows']==r['teacher_cache']['expected_targets'],'P_TARGETS')
        s.require(all(a[k]==0 for k in ('optimizer_steps','historical_student_loads','new_candidate_loads','student_forwards','feature_bytes_decoded','evaluated_targets')),'P_FORBIDDEN')
    elif stage=='T':
        barrier=s.read_json(out/'candidates_sealed.json')
        s.require(barrier['status']=='BOTH_FINAL_CANDIDATES_SEALED' and set(barrier['candidates'])=={'Q','R'} and barrier['recipe_sha256']==s.RECIPE_SHA,'T_BARRIER')
        for arm,rec in barrier['candidates'].items():
            s.require(s.sha(out/(arm+'.pt'),budget.check)==rec['file_sha256'],'T_CANDIDATE_FILE')
            s.require(rec['epoch']==r['schedule']['epochs'] and rec['counts']['updates']==r['schedule']['updates_per_arm']
                and rec['counts']['targets']==r['schedule']['target_presentations_per_arm']
                and rec['initial_state_sha256']==r['inputs']['initial_A']['state_sha256'],'T_CANDIDATE_COUNTS')
            s.require(rec['guard_pair_occurrences']==r['losses']['A_guard']['pair_occurrences'],'T_GUARD_COUNTS')
        s.require(s.sha(out/'R_projection_training_only.pt',budget.check)==barrier['candidates']['R']['projection_file_sha256'],'T_PROJECTION_FILE')
        s.require(barrier['candidates']['Q']['counts']==barrier['candidates']['R']['counts'] and
                  barrier['order_hashes']['Q']==barrier['order_hashes']['R'],'T_MATCHED_BUDGET')
        s.require(a['optimizer_steps']==r['schedule']['updates_all_arms'] and a['historical_student_loads']==1
                  and a['evaluated_targets']==a['new_candidate_loads']==0,'T_ACTIONS')
    elif stage=='E':
        from issue27frontend_aligned_evaluate_v1 import read_baseline,read_predictions,fixed,ranking,contrast
        baseline=read_baseline(s.pin(r['inputs']['expanded_A_predictions'],budget.check))
        expected=[t['uid'] for t in baseline];result=s.read_json(out/'comparison.json')
        recomputed={}
        for arm in ('Q','R'):
            q=read_predictions(out/(arm+'_expanded.csv.gz'),expected)
            recomputed[arm]=dict(fixed=fixed(baseline,{k:int(v>=0) for k,v in q.items()}),ranking=ranking(baseline,q))
            s.require(recomputed[arm]==result['models'][arm],'E_METRICS_RECOMPUTATION')
            plan=s.read_json(s.pin(r['inputs']['plan'],budget.check))
            for role in ('train','check'):
                rows=s.targets([c for c in plan['contexts'] if c['role']==role])
                values=read_predictions(out/(arm+'_'+role+'.csv.gz'),[t['uid'] for t in rows])
                s.require(fixed(rows,{k:int(v>=0) for k,v in values.items()})==result['check_and_train'][arm][role],'E_ROLE_RECOMPUTATION')
            fit=s.read_json(out/(arm+'_train_transfer_fit.json'))
            s.require(fit['targets']==r['teacher_cache']['expected_targets'] and fit['extra_student_forwards']==0
                      and all(math.isfinite(v) for v in fit.values() if isinstance(v,(float,int))),'E_TRAIN_FIT_RECORD')
            budget.check(phase='VERIFYING_METRICS',arm=arm)
        for name,value in result['contrasts'].items():
            new,old=name.split('-')
            s.require(contrast(result['models'][old],result['models'][new])==value,'E_CONTRAST_RECOMPUTATION')
        s.require(a['evaluated_targets']==r['evaluation']['targets_all_arms'] and a['new_candidate_loads']==2
                  and a.get('new_projection_loads')==1 and a['optimizer_steps']==a['historical_student_loads']==0,'E_ACTIONS')
    else:
        raise s.Stop('INVALID_STAGE')
    budget.check(True,phase='VERIFIED')
    s.atomic_json(out/'verification.json',dict(status='PASS',stage=stage,real_extra_forwards=0,recipe_sha256=s.RECIPE_SHA))
