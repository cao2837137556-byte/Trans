"""Audit signed compact outcomes and every source-guard decision; no HPC array download."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'source_stratified_pilot_v1_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(HERE/n).write_bytes((json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
checks=0
def check(v):
    global checks
    assert v;checks+=1
def near(a,b):check(math.isclose(a,b,rel_tol=1e-9,abs_tol=2e-12))
def gates(m):
    n,a=m['normal'],m['attack']
    return dict(normal_weighted_nonincrease=n['candidate_weighted_rate']<=n['baseline_weighted_rate']+1e-12,
        normal_unweighted_nonincrease=n['candidate_rate']<=n['baseline_rate']+1e-12,
        attack_weighted_drop_within_0_1pp=a['candidate_weighted_rate']>=a['baseline_weighted_rate']-.001,
        attack_unweighted_drop_within_0_1pp=a['candidate_rate']>=a['baseline_rate']-.001,
        attack_removed_fraction_within_0_1pp=a['removed']/a['rows']<=.001,
        attack_p01_margin_drop_within_slack=a['standardized_score_change']['p01']>=-.010001,
        positive_context_retention=a['positive_context_retention'] is None or a['positive_context_retention']>=.9,
        protocol_attack_drop_within_0_1pp=all(v['candidate_rate']>=v['baseline_rate']-.001 for v in a['cohorts']['protocol'].values()))
def source(e):
    check(e['CAL_used'] is False and e['guard_rows']==617908)
    flags={role+'/'+k:v for role,m in e['metrics'].items() for k,v in gates(m).items()}
    check(e['checks']==flags);near(e['normal_tail_risk'],e['metrics']['fit']['normal']['tail_risk']);return flags
def compact(m):
    n,a=m['normal'],m['attack']
    return dict(false_alarms=n['candidate_alarms'],FPR=n['candidate_rate'],weighted_FPR=n['candidate_weighted_rate'],
        weighted_relative_reduction_vs_original=1-n['candidate_weighted_rate']/n['baseline_weighted_rate'],
        normal_tail_risk=n['candidate_tail_risk'],attack_recall=a['candidate_rate'],attack_removed=a['removed'],
        attack_p01=a['standardized_score_change']['p01'],attack_worst_change=a['standardized_score_change']['min'],
        attack_over_slack_rows=round(a['attack_slack_violation_fraction']*a['rows']),
        positive_context_retention=a['positive_context_retention'],context_under90_rows=round(a['context_preservation_violation_fraction']*a['positive_context_rows']),
        attack_min_actual_margin=a['margin']['min'])
def main():
    done=read(HERE/'PILOT_COMPLETION.json');retrieval=read(HERE/'RETRIEVAL.json');check(done['receipt_sha256']==retrieval['sha256'])
    check(retrieval['state']['stage']=='SOURCE_GUARDED_PILOT_COMPLETE')
    for n,h in done['receipt_sha256'].items():check(sha(HERE/n)==h)
    for n,h in read(HERE/'DELIVERY.json')['pins'].items():check(sha(HERE/n)==h)
    d=read(HERE/'PILOT_RESULT.json');old=read(OLD/'PILOT_RESULT.json');pre=read(HERE/'TRAIN_PREFLIGHT_RESULT.json')
    check(d['historical_control_sha256']==sha(OLD/'PILOT_RESULT.json'));check(d['status']=='PASS' and list(d['heads'])==['27','127','227'])
    check(d['all_FIT_used_for_guard_feedback'] and d['CAL_used_for_update_acceptance'] is False)
    for k in ['external_candidate_scoring','threshold_refit','encoder_finetuned','automatic_full_training']:check(d[k] is False)
    check(pre['signal_ready'] and pre['forecast_seconds']<=3600)
    resources={};comparison={};failed={};accounting={};remote={};reject_reasons={}
    for phase in ['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']:
        job=read(HERE/(phase+'_JOB.json'));receipt=read(HERE/(phase+'_RESULT.json'));check(receipt['status']=='PASS')
        lines=[v.split('|') for v in read(HERE/(phase+'_SCHEDULER.json'))['stdout'].splitlines()]
        row=next(v for v in lines if v[0]==job['job_id']);check(row[1:3]==['COMPLETED','0:0'] and row[5]=='1')
        h,m,s=map(int,row[3].split(':'));resources[phase]=dict(job=job['job_id'],seconds=h*3600+m*60+s,
            slurm_maxrss_bytes=max(float(v[4][:-1])*1024 for v in lines if v[4].endswith('K')),process_peak_bytes=receipt['rss_peak_bytes'])
    for seed,h in d['heads'].items():
        previous_head=old['heads'][seed];t=h['guarded_training'];previous=t['initial_source_guard'];check(all(source(previous).values()))
        for key in ['initial_fingerprint','cut','scale','normal_upper']:check(h[key]==previous_head[key])
        for key in ['uid_sha256','sample_weight_sha256']:check(h['identity'][key]==previous_head['identity'][key])
        check(h['baseline_parity']=={'fit':0.,'cal':0.} and h['epochs']==5 and not h['runtime_gate_only'])
        check(h['trajectory']==t['trajectory'] and len(t['trajectory'])==5)
        executed=retained=rejected=accepted=0;rounds=[]
        for number,round_ in enumerate(t['trajectory'],1):
            check(round_['round']==number and round_['rollback_verified'])
            attempts=round_['attempts'];check([a['factor'] for a in attempts]==[1.,.5,.25,.125][:len(attempts)])
            check(1<=len(attempts)<=4)
            for i,a in enumerate(attempts):
                flags=source(a['evidence']);tol=max(1e-14,abs(previous['normal_tail_risk'])*1e-10)
                flags['normal_risk_nonincrease_from_retained']=a['evidence']['normal_tail_risk']<=previous['normal_tail_risk']+tol
                check(flags==a['checks'] and a['accepted']==all(flags.values()))
                check(not a['accepted'] or i==len(attempts)-1)
                check(a['training']['updates']==64);executed+=64
                x,y,z,total=a['training']['loss_means'];near(x+10*(y+z),total)
                if not a['accepted']:
                    rejected+=1
                    for k,v in flags.items():
                        if not v:reject_reasons[k]=reject_reasons.get(k,0)+1
            check(round_['accepted']==attempts[-1]['accepted'])
            if round_['accepted']:
                check(round_['factor']==attempts[-1]['factor'] and round_['evidence']==attempts[-1]['evidence']);previous=round_['evidence'];retained+=64;accepted+=1
            else:check(len(attempts)==4 and round_['factor']==0. and round_['evidence']==previous)
            check(round_['executed_updates']==executed and round_['retained_optimizer_updates']==retained and round_['nominal_updates']==64*number)
            check(all(source(previous).values()))
            rounds.append(dict(round=number,factor=round_['factor'],attempts=len(attempts),retained=retained,risk=previous['normal_tail_risk']))
        check(t['final_source_guard']==previous and h['updates']==t['executed_updates']==executed)
        check(t['nominal_updates']==320 and t['retained_optimizer_updates']==retained and t['rejected_attempts']==rejected and t['accepted_rounds']==accepted)
        near(t['normal_tail_risk_relative_reduction'],1-previous['normal_tail_risk']/t['initial_source_guard']['normal_tail_risk'])
        check(t['rollback_smoke'] is None)
        smoke=pre['heads'][seed]['guarded_training']['rollback_smoke'];check(smoke['status']=='PASS' and smoke['actual_optimizer_steps']==4 and smoke['complete_state_restored'])
        for role in ['fit','fit_not_sampled_for_gradient']:
            check(gates(h['metrics'][role])==gates(previous['metrics'][role]))
            near(h['metrics'][role]['normal']['candidate_tail_risk'],previous['metrics'][role]['normal']['tail_risk'])
        accounting[seed]=dict(nominal=320,executed=executed,retained=retained,rejected_attempts=rejected,accepted_rounds=accepted,rounds=rounds)
        remote[seed]={k:h[k] for k in ['arrays','head_sha256','sample_identity_sha256']}
    for seed,h in list(d['heads'].items())+[('ensemble',d['ensemble'])]:
        previous_head=old['ensemble'] if seed=='ensemble' else old['heads'][seed]
        for role,m in h['metrics'].items():
            oldrole='fit_not_used_in_pilot' if role=='fit_not_sampled_for_gradient' else role
            for label,v in m.items():
                check(v['rows']==previous_head['metrics'][oldrole][label]['rows'])
                for key in ['baseline_rate','baseline_weighted_rate','baseline_alarms']:near(v[key],previous_head['metrics'][oldrole][label][key])
                near(v['candidate_rate'],v['candidate_alarms']/v['rows']);check(v['candidate_alarms']==v['baseline_alarms']+v['added']-v['removed'])
                for cohorts in v['cohorts'].values():
                    check(sum(a['rows'] for a in cohorts.values())==v['rows']);near(sum(a['rows']*a['candidate_rate'] for a in cohorts.values()),v['candidate_alarms'])
                if label=='attack':check(v['candidate_rate']==1 and v['removed']==0)
            if seed!='ensemble':check(gates(m)==h['gates'][role]);failed[seed+'/'+role]=[k for k,v in gates(m).items() if not v]
        if seed!='ensemble':check(h['source_preservation_pass']==all(all(v.values()) for v in h['gates'].values()))
        comparison[seed]=dict(previous=compact(previous_head['metrics']['cal']),current=compact(h['metrics']['cal']))
    e=d['ensemble'];flags=gates(e['metrics']['cal']);n=e['metrics']['cal']['normal'];flags['cal_weighted_fpr_relative_reduction_10pct']=n['baseline_weighted_rate']>0 and n['candidate_weighted_rate']<=.9*n['baseline_weighted_rate']
    check(e['gates']==flags);go=all(flags.values()) and all(h['source_preservation_pass'] for h in d['heads'].values())
    check(e['source_pilot_go']==go and d['scientific_status']==('SOURCE_PILOT_GO' if go else 'SOURCE_PILOT_NO_GO'))
    failed['ensemble/cal']=[k for k,v in flags.items() if not v]
    neutral=dict(seed=227,all_full_steps=all(v['factor']==1 for v in accounting['227']['rounds']),head_sha_equal=d['heads']['227']['head_sha256']==old['heads']['227']['head_sha256'],fingerprint_equal=d['heads']['227']['final_fingerprint']==old['heads']['227']['final_fingerprint'])
    check(all(v for k,v in neutral.items() if k!='seed'))
    prior=read(OLD/'PILOT_ACCEPTANCE_SUMMARY.json');check(sha(OLD/'PILOT_ACCEPTANCE_SUMMARY.json')==read(OLD/'FINAL_PILOT_ACCEPTANCE.json')['audit_summary_sha256'])
    lan=n['cohorts']['activity']['LAN_RECORDING'];near(lan['rows']*lan['candidate_rate'],3);check(lan['removed']==0)
    unchanged=dict(count=3,share_of_remaining_weighted_FP=prior['unchanged_LAN_alarms']['mass']/n['candidate_weighted_rate'],inference='same signed baseline set and zero LAN alarm removals')
    write('PILOT_ACCEPTANCE_SUMMARY.json',dict(comparison=comparison,failed_gates=failed,accounting=accounting,
        total_executed=sum(v['executed'] for v in accounting.values()),total_retained=sum(v['retained'] for v in accounting.values()),
        reject_reasons=reject_reasons,neutral_control=neutral,unchanged_LAN=unchanged,resources=resources,
        successful_chain_seconds=sum(v['seconds'] for v in resources.values()),checks=checks,remote_large_artifacts=remote))
    write('FINAL_PILOT_ACCEPTANCE.json',dict(engineering='PASS',scientific=d['scientific_status'],checks=checks,
        audit_summary_sha256=sha(HERE/'PILOT_ACCEPTANCE_SUMMARY.json'),receipt_sha256=done['receipt_sha256'],
        no_new_jobs=True,all_FIT_used_in_optimization=True,remote_arrays_recomputed_locally=False,
        limitations=['Fixed signed summaries verified, large arrays not independently rescored locally.',
            'Guarded source criteria are optimization conditions, not independent validation.',
            'CAL used previously for calibration and diagnosis; no new external efficacy.',
            'Failure of four epoch-scale proposals is not proof that every feasible direction is exhausted.',
            'Historical comparator has less compute and different numbers of retained steps.']))
    print(json.dumps(dict(status='AUDITED',scientific=d['scientific_status'],checks=checks,cal=comparison['ensemble'],accounting={k:{a:v[a] for a in ['executed','retained','rejected_attempts']} for k,v in accounting.items()})))
if __name__=='__main__':main()
