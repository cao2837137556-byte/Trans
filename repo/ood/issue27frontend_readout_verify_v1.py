"""Re-read final receipts and predictions without new model/teacher computation."""
import gzip
import json
import math
import issue27frontend_readout_support_v1 as s


def verify_stage(stage,out,r,budget):
    access = budget.access
    zero = ('teacher_passes','teacher_rows_read','guard_pairs_read','projection_loads','raw_decodes','network_requests','retries')
    s.require(all(access[k]==0 for k in zero),'FORBIDDEN_ACTION')
    if stage=='T':
        barrier = s.read_json(out/'candidates_sealed.json')
        s.require(barrier['status']=='FINAL_CANDIDATE_SEALED' and barrier['recipe_sha256']==s.RECIPE_SHA
                  and set(barrier['candidates'])=={'H_AB'},'T_BARRIER')
        rec = barrier['candidates']['H_AB']
        s.require(s.read_json(out/'H_AB.receipt.json')==rec and s.sha(out/'H_AB.pt',budget.check)==rec['file_sha256'],'T_CANDIDATE_FILE')
        s.require(rec['counts']==r['schedule']['expected_counts_per_arm'] and rec['epoch']==r['schedule']['epochs']
                  and rec['initial_state_sha256']==r['inputs']['initial_AB']['state_sha256'],'T_RECEIPT_COUNTS')
        expected_names = {'event_projection.weight','event_projection.bias','encoder.weight_ih_l0',
                          'encoder.weight_hh_l0','encoder.bias_ih_l0','encoder.bias_hh_l0'}
        frozen = rec['initial_frozen_tensor_hashes']
        s.require(set(frozen)==expected_names and frozen==rec['final_frozen_tensor_hashes']
                  and rec['frozen_grad_none'] and rec['frozen_optimizer_state_absent'],'T_FROZEN_IDENTITY')
        s.require(rec['trainable_parameters']==8321 and rec['frozen_parameters']==82944,'T_PARAMETER_COUNTS')
        entry = s.read_json(out/'entry_receipt.json')
        s.require(entry['status']=='INPUT_AND_ORDER_IDENTITY_VERIFIED' and entry['recipe_sha256']==s.RECIPE_SHA
                  and entry['initial_AB_state_sha256']==rec['initial_state_sha256']
                  and entry['reference_recipe_sha256']==r['base_contract']['sha256'],'ENTRY_RECEIPT')
        s.require(set(barrier['order_hashes'])=={'H_AB'}
                  and barrier['order_hashes']['H_AB']==entry['reference_order_hashes'],'T_ORDER_IDENTITY')
        epochs = [json.loads(line) for line in (out/'epoch_log.jsonl').read_text(encoding='utf-8').splitlines()]
        s.require(len(epochs)==r['schedule']['epochs'],'T_EPOCHS')
        for i,row in enumerate(epochs,1):
            s.require(row['epoch']==i and row['arm']=='H_AB' and row['frozen_tensor_hashes']==frozen
                      and row['frozen_grad_none'] and row['frozen_optimizer_state_absent'],'T_EPOCH_FROZEN_IDENTITY')
        count = 0
        with (out/'training_log.jsonl').open(encoding='utf-8') as f:
            for line in f:
                row = json.loads(line); epoch,step = divmod(count,r['schedule']['steps_per_epoch'])
                s.require(row['arm']=='H_AB' and row['epoch']==epoch+1 and row['step']==step+1
                          and all(math.isfinite(row[k]) for k in ('label','head_gradient_L2','clip_factor')),'T_TRAINING_LEDGER')
                count += 1; budget.check(phase='VERIFYING_TRAINING_LEDGER')
        s.require(count==access['optimizer_steps']==rec['counts']['updates'],'T_UPDATE_LEDGER')
        s.require(access['feature_bytes_decoded']==r['stages']['T']['expected_feature_bytes_decoded'],'T_FEATURE_BYTES')
        s.require(access['new_candidate_loads']==access['evaluated_targets']==0,'T_EVALUATION_FORBIDDEN')
    elif stage=='E':
        from issue27frontend_readout_evaluate_v1 import (
            read_baseline,read_predictions,historical_predictions,model_metrics,check_details,contrast,tail_composition,compare_ab_tail,flips)
        baseline = read_baseline(s.pin(r['inputs']['expanded_A_predictions'],budget.check))
        expected = [t['uid'] for t in baseline]; result = s.read_json(out/'comparison.json')
        q = read_predictions(out/'H_AB_expanded.csv.gz',expected)
        all_q = historical_predictions(r,baseline,budget); all_q['H_AB'] = q
        models = model_metrics(baseline,all_q,budget)
        s.require(models==result['models'],'E_METRIC_RECOMPUTATION')
        s.require({name:tail_composition(baseline,values,models[name]['ranking']) for name,values in all_q.items()}
                  == result['tail_composition'],'E_TAIL_RECOMPUTATION')
        s.require(compare_ab_tail(models['H_AB'],models['AB'])==result['AB_tail_comparison']['H_AB'],'E_AB_TAIL')
        s.require(set(result['contrasts'])==set(r['evaluation']['contrasts']),'E_CONTRAST_SET')
        for name,value in result['contrasts'].items():
            new,old = name.split('-')
            s.require(contrast(models[old],models[new])==value,'E_CONTRAST_RECOMPUTATION')
        plan = s.read_json(s.pin(r['inputs']['plan'],budget.check)); preds = {}
        for role in ('train','check'):
            ts = s.targets([c for c in plan['contexts'] if c['role']==role])
            preds[role] = read_predictions(out/('H_AB_'+role+'.csv.gz'),[t['uid'] for t in ts])
        reference = s.read_json(s.pin(r['inputs']['historical_check_scores'],budget.check))['A']
        ca = {t['uid']:t['hard'] for t in reference if t['owner']=='A'}
        s.require(check_details(r,plan['contexts'],preds,ca)==result['check_and_train']['H_AB'],'E_CHECK_TRAIN_RECOMPUTATION')
        hard = {k:int(v>=0) for k,v in q.items()}
        for name in list(all_q)+['old_P2']:
            if name=='H_AB':continue
            old = {t['uid']:t['old_hard'] for t in baseline} if name=='old_P2' else {k:int(v>=0) for k,v in all_q[name].items()}
            with gzip.open(out/('H_AB_vs_'+name+'_flips.json.gz'),'rt',encoding='utf-8') as f:
                s.require(json.load(f)==flips(baseline,old,hard),'E_FLIP_RECOMPUTATION')
        s.require(result['original_strict_verdict']=='HISTORICAL_FAIL_UNCHANGED'
                  and result['commissioning']=='NOT_EVALUATED','E_CLAIM_SCOPE')
        expected_boundary = 'MANUAL_RISK_REVIEW_NO_AUTOMATIC_PROMOTION' if result['contrasts']['H_AB-AB']['status']=='DEVELOPMENT_DIRECTIONAL_JOINT_GAIN' else 'END_ADJACENT_SAME_TRAIN_TUNING_REQUIRE_INPUT_OR_TRAINING_SUPPORT_EVIDENCE'
        s.require(result['next_boundary']==expected_boundary,'E_CONTINUATION_BOUNDARY')
        s.require(access['optimizer_steps']==access['historical_student_loads']==0,'E_TRAINING_FORBIDDEN')
    else:
        raise s.Stop('INVALID_STAGE')
    for key in ('student_forwards','optimizer_steps','historical_student_loads','new_candidate_loads','evaluated_targets'):
        if key in r['stages'][stage]:s.require(access[key]==r['stages'][stage][key],'EXACT_ACTION_COUNT:'+key)
    s.require(not any('teacher' in p.name or 'projection_training' in p.name for p in out.iterdir()),'FORBIDDEN_ARTIFACT')
    budget.check(True,phase='VERIFIED')
    s.atomic_json(out/'verification.json',dict(status='PASS',stage=stage,real_extra_forwards=0,recipe_sha256=s.RECIPE_SHA))
