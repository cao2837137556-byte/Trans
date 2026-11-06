"""Audit compact frozen receipts. Does not download or rescore HPC arrays."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(HERE/n).write_bytes((json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
def close(a,b):assert math.isclose(a,b,rel_tol=1e-9,abs_tol=2e-12),(a,b)
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
def main():
    completion=read(HERE/'PILOT_COMPLETION.json');retrieval=read(HERE/'RETRIEVAL.json')
    assert completion['status']=='PASS' and retrieval['state']['stage']=='SOURCE_RISK_PILOT_COMPLETE'
    assert completion['receipt_sha256']==retrieval['sha256']
    for name,digest in completion['receipt_sha256'].items():assert sha(HERE/name)==digest,name
    for name,digest in read(HERE/'DELIVERY.json')['pins'].items():assert sha(HERE/name)==digest,name
    result=read(HERE/'PILOT_RESULT.json');spec=read(HERE/'SPEC.json')
    assert result['status']=='PASS' and result['scientific_status']=='SOURCE_PILOT_NO_GO'
    assert all(result[k] is False for k in ['external_candidate_scoring','threshold_refit','encoder_finetuned','automatic_full_training'])
    assert list(result['heads'])==['27','127','227'] and spec['epochs']==5 and spec['updates_per_seed']==320
    resources={};checks=0;remote={};summary={};identities=set();failed={}
    for phase in ['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']:
        job=read(HERE/(phase+'_JOB.json'));scheduler=read(HERE/(phase+'_SCHEDULER.json'))
        rows=[line.split('|') for line in scheduler['stdout'].splitlines()]
        row=next(row for row in rows if row[0]==job['job_id']);assert row[1:3]==['COMPLETED','0:0'] and row[5]=='1'
        parts=list(map(int,row[3].split(':')));seconds=parts[0]*3600+parts[1]*60+parts[2]
        rss=[float(v[4][:-1])*1024 for v in rows if v[4].endswith('K')]
        resources[phase]=dict(job=job['job_id'],elapsed_seconds=seconds,slurm_maxrss_bytes=max(rss),process_sampled_peak_bytes=read(HERE/(phase+'_RESULT.json'))['rss_peak_bytes'])
    for seed,h in list(result['heads'].items())+[('ensemble',result['ensemble'])]:
        if seed!='ensemble':
            assert h['epochs']==5 and h['updates']==320 and not h['runtime_gate_only'] and h['model_changed']
            assert h['initial_fingerprint']!=h['final_fingerprint'] and h['baseline_parity']=={'fit':0.,'cal':0.}
            assert [v['updates'] for v in h['trajectory']]==[64,128,192,256,320]
            for ep in h['trajectory']:
                a,b,c,total=ep['loss_means'];close(a+10*(b+c),total)
            identities.add((h['identity']['uid_sha256'],h['identity']['sample_weight_sha256']))
            remote[seed]=dict(arrays=h['arrays'],head_sha256=h['head_sha256'],sample_identity_sha256=h['sample_identity_sha256'])
        for role,m in h['metrics'].items():
            assert sum(v['rows'] for v in m.values())=={'fit':617908,'cal':148819,'fit_not_used_in_pilot':601524}[role]
            for label,v in m.items():
                n=v['rows'];close(v['baseline_rate'],v['baseline_alarms']/n);close(v['candidate_rate'],v['candidate_alarms']/n)
                assert v['candidate_alarms']==v['baseline_alarms']+v['added']-v['removed']
                for key in ['baseline_weighted_rate','candidate_weighted_rate']:assert -1e-12<=v[key]<=1+1e-12
                q=v['standardized_score_change'];assert list(q.values())==sorted(q.values())
                for group,cohorts in v['cohorts'].items():
                    assert sum(c['rows'] for c in cohorts.values())==n
                    for k in ['baseline','candidate']:
                        close(sum(c['rows']*c[k+'_rate'] for c in cohorts.values()),v[k+'_alarms'])
                    assert sum(c['removed'] for c in cohorts.values())==v['removed']
                    checks+=1
                if label=='attack':assert v['removed']==0 and v['baseline_alarms']==n and v['candidate_alarms']==n
                checks+=1
            expected=gates(m)
            if seed!='ensemble':assert expected==h['gates'][role];failed[seed+'_'+role]=[k for k,v in expected.items() if not v]
        cal=h['metrics']['cal'];n,a=cal['normal'],cal['attack']
        summary[seed]=dict(normal_rows=n['rows'],baseline_false_alarms=n['baseline_alarms'],candidate_false_alarms=n['candidate_alarms'],
            sample_FPR_before=n['baseline_rate'],sample_FPR_after=n['candidate_rate'],sample_FPR_relative_reduction=1-n['candidate_rate']/n['baseline_rate'],
            weighted_FPR_before=n['baseline_weighted_rate'],weighted_FPR_after=n['candidate_weighted_rate'],weighted_FPR_relative_reduction=1-n['candidate_weighted_rate']/n['baseline_weighted_rate'],
            attack_rows=a['rows'],attack_recall=a['candidate_rate'],attack_removed=a['removed'],
            attack_p01_standardized_score_change=a['standardized_score_change']['p01'],
            attack_slack_violation_fraction=a['attack_slack_violation_fraction'],attack_slack_violation_rows=round(a['attack_slack_violation_fraction']*a['rows']),
            attack_min_actual_margin=a['margin']['min'],positive_context_rows=a['positive_context_rows'],
            positive_context_retention=a['positive_context_retention'],context_below_90pct_rows=round(a['context_preservation_violation_fraction']*a['positive_context_rows']),
            context_lift_median_before=a['baseline_context_lift']['p50'],context_lift_median_after=a['candidate_context_lift']['p50'])
    assert len(identities)==1
    ens=result['ensemble'];expected=gates(ens['metrics']['cal']);n=ens['metrics']['cal']['normal']
    expected['cal_weighted_fpr_relative_reduction_10pct']=n['baseline_weighted_rate']>0 and n['candidate_weighted_rate']<=.9*n['baseline_weighted_rate']
    assert expected==ens['gates'] and ens['source_pilot_go'] is False
    failed['ensemble_cal']=[k for k,v in expected.items() if not v]
    # Normal class weights explicitly allocate equal mass to each nonempty device.
    devices=n['cohorts']['device'];close(sum(v['candidate_weighted_rate'] for v in devices.values())/len(devices),n['candidate_weighted_rate'])
    simcam=devices['SimCam']['candidate_weighted_rate']/len(devices)/n['candidate_weighted_rate']
    write('PILOT_ACCEPTANCE_SUMMARY.json',dict(cal=summary,failed_gates=failed,resources=resources,
        successful_chain_seconds=sum(v['elapsed_seconds'] for v in resources.values()),
        residual_CAL_weighted_FP_SimCam_share=simcam,cohort_count_checks=checks,
        context_regularizer_causality='not established: near-zero LC and no removal ablation',
        remote_large_artifacts=remote))
    write('FINAL_PILOT_ACCEPTANCE.json',dict(engineering='PASS',scientific='SOURCE_PILOT_NO_GO',
        scope='SOURCE_ONLY_FIXED_ENDPOINT_RAW_FIXED_THRESHOLDS',epochs_per_seed=5,total_updates=960,
        receipt_sha256=completion['receipt_sha256'],audit_summary_sha256=sha(HERE/'PILOT_ACCEPTANCE_SUMMARY.json'),
        no_new_jobs=True,external_efficacy_unknown=True,remote_arrays_recomputed_locally=False,
        limitations=['CAL reused from original calibration; not independent test',
                    'Source attacks remain far above threshold; recall alone is weak evidence of external safety',
                    'Positive context preservation is aggregate, not every row',
                    'Near-zero LC does not establish that LC caused preservation']))
    print(json.dumps(dict(status='AUDITED',scientific='NO_GO',cal=summary['ensemble'],simcam_share=simcam,checks=checks),ensure_ascii=False))
if __name__=='__main__':main()
