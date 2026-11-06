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
    assert completion['status']=='PASS' and retrieval['state']['stage']=='SOURCE_STRATIFIED_PILOT_COMPLETE'
    assert completion['receipt_sha256']==retrieval['sha256']
    for name,digest in completion['receipt_sha256'].items():assert sha(HERE/name)==digest,name
    for name,digest in read(HERE/'DELIVERY.json')['pins'].items():assert sha(HERE/name)==digest,name
    result=read(HERE/'PILOT_RESULT.json');spec=read(HERE/'SPEC.json')
    assert result['status']=='PASS'
    control=read(HERE.parent/'source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json')
    assert result['historical_control_sha256']==sha(HERE.parent/'source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json')
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
            expected_rows=617908-h['identity']['unique_normal_rows']-h['identity']['unique_attack_rows'] if role=='fit_not_used_in_pilot' else {'fit':617908,'cal':148819}[role]
            assert sum(v['rows'] for v in m.values())==expected_rows
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
    sampling={}
    for seed,h in result['heads'].items():
        oldh=control['heads'][seed]
        assert h['initial_fingerprint']==oldh['initial_fingerprint'] and h['cut']==oldh['cut'] and h['normal_upper']==oldh['normal_upper']
        identity=h['identity'];design=identity['sampling'];assert design['expectation_verified'] and design['expected_row_weight_max_error']<1e-12
        assert not design['selection_uses_scores'] and not design['selection_uses_CAL']
        for y,count,source,unique in [(0,94,134493,identity['unique_normal_rows']),(1,11,483415,identity['unique_attack_rows'])]:
            groups=[g for g in design['strata'] if g['label']==y]
            assert len(groups)==count and sum(g['draws'] for g in groups)==8192
            assert sum(g['source_rows'] for g in groups)==source and sum(g['unique_rows'] for g in groups)==unique
            close(sum(g['class_mass'] for g in groups),1)
            for g in groups:
                assert 0<g['unique_rows']<=min(g['source_rows'],g['draws'])
                close(g['draws']*g['per_draw_weight'],g['class_mass'])
                checks+=1
        assert h['metrics']['fit_not_used_in_pilot']['normal']['rows']==134493-identity['unique_normal_rows']
        assert h['metrics']['fit_not_used_in_pilot']['attack']['rows']==483415-identity['unique_attack_rows']
        sampling[seed]=identity
        for role in ['fit','cal']:
            for label in ['normal','attack']:
                for key in ['rows','baseline_alarms','baseline_rate','baseline_weighted_rate']:
                    close(h['metrics'][role][label][key],oldh['metrics'][role][label][key])
        assert h['source_preservation_pass']==all(all(g.values()) for g in h['gates'].values())
    # Preserve old and new CAL summaries side by side, without recomputing large arrays.
    previous=read(HERE.parent/'source_risk_preservation_pilot_v2_20261106/PILOT_ACCEPTANCE_SUMMARY.json')['cal']
    comparison={seed:dict(previous=previous[seed],current=summary[seed]) for seed in summary}
    probes={seed:dict(defined=sum(v['relation']['cosine'] is not None for v in h['gradient_probes']),
        negative=sum(v['relation']['cosine'] is not None and v['relation']['cosine']<0 for v in h['gradient_probes'])) for seed,h in result['heads'].items()}
    # Previous signed joint-group diagnosis identified all three baseline LAN alarms.
    prior=read(HERE.parent/'source_coverage_audit_v1_20261106/COVERAGE_RESULT.json')
    prior_completion=read(HERE.parent/'source_coverage_audit_v1_20261106/COVERAGE_COMPLETION.json')
    assert sha(HERE.parent/'source_coverage_audit_v1_20261106/COVERAGE_RESULT.json')==prior_completion['receipt_sha256']['COVERAGE_RESULT.json']
    joint=prior['coverage']['heads']['ensemble']['cal_descriptive']['normal']['top20'][0]['cal']
    assert joint['key']==['SimCam','LAN_RECORDING','6'] and joint['baseline_alarms']==joint['residual_alarms']==3
    for seed,h in list(result['heads'].items())+[('ensemble',result['ensemble'])]:
        lan=h['metrics']['cal']['normal']['cohorts']['activity']['LAN_RECORDING']
        close(lan['baseline_rate']*lan['rows'],3);close(lan['candidate_rate']*lan['rows'],3);assert lan['removed']==0
    unchanged_lan=dict(alarms=3,identities_inferred_by_baseline_set_and_zero_removals=True,
        mass=joint['residual_alarm_mass'],share_of_new_weighted_FP=joint['residual_alarm_mass']/result['ensemble']['metrics']['cal']['normal']['candidate_weighted_rate'])
    ens=result['ensemble'];expected=gates(ens['metrics']['cal']);n=ens['metrics']['cal']['normal']
    for role in ['fit','cal']:
        for label in ['normal','attack']:
            for key in ['rows','baseline_alarms','baseline_rate','baseline_weighted_rate']:
                close(ens['metrics'][role][label][key],control['ensemble']['metrics'][role][label][key])
    expected['cal_weighted_fpr_relative_reduction_10pct']=n['baseline_weighted_rate']>0 and n['candidate_weighted_rate']<=.9*n['baseline_weighted_rate']
    assert expected==ens['gates']
    computed_go=all(expected.values()) and all(all(all(g.values()) for g in h['gates'].values()) for h in result['heads'].values())
    assert ens['source_pilot_go']==computed_go
    assert result['scientific_status']==('SOURCE_PILOT_GO' if computed_go else 'SOURCE_PILOT_NO_GO')
    failed['ensemble_cal']=[k for k,v in expected.items() if not v]
    # Normal class weights explicitly allocate equal mass to each nonempty device.
    devices=n['cohorts']['device'];close(sum(v['candidate_weighted_rate'] for v in devices.values())/len(devices),n['candidate_weighted_rate'])
    simcam=devices['SimCam']['candidate_weighted_rate']/len(devices)/n['candidate_weighted_rate']
    write('PILOT_ACCEPTANCE_SUMMARY.json',dict(cal=summary,failed_gates=failed,resources=resources,
        comparison= comparison,sampling=sampling,gradient_probe_signs=probes,unchanged_LAN_alarms=unchanged_lan,
        successful_chain_seconds=sum(v['elapsed_seconds'] for v in resources.values()),
        residual_CAL_weighted_FP_SimCam_share=simcam,cohort_count_checks=checks,
        context_regularizer_causality='not established: near-zero LC and no removal ablation',
        remote_large_artifacts=remote))
    write('FINAL_PILOT_ACCEPTANCE.json',dict(engineering='PASS',scientific=result['scientific_status'],
        scope='SOURCE_ONLY_FIXED_ENDPOINT_RAW_FIXED_THRESHOLDS',epochs_per_seed=5,total_updates=960,
        receipt_sha256=completion['receipt_sha256'],audit_summary_sha256=sha(HERE/'PILOT_ACCEPTANCE_SUMMARY.json'),
        no_new_jobs=True,external_efficacy_unknown=True,remote_arrays_recomputed_locally=False,
        limitations=['CAL reused from original calibration; not independent test',
                    'Source attacks remain far above threshold; recall alone is weak evidence of external safety',
                    'Positive context preservation is aggregate, not every row',
                    'Near-zero LC does not establish that LC caused preservation',
                    'Sampling plus estimator changed jointly; single draw realization reused for all model seeds',
                    'Unused FIT membership differs between pilots, compare common full FIT and CAL for effects']))
    print(json.dumps(dict(status='AUDITED',scientific=result['scientific_status'],cal=summary['ensemble'],simcam_share=simcam,checks=checks),ensure_ascii=False))
if __name__=='__main__':main()
