"""Local acceptance of signed compact results; no remote arrays or new scoring."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(HERE/n).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
checks=0
def check(ok):
    global checks
    assert ok;checks+=1
def near(a,b):check(math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-12))
def main():
    receipt=read(HERE/'COVERAGE_COMPLETION.json')
    for n,h in receipt['receipt_sha256'].items():check(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h)
    pre=read(HERE/'PREFLIGHT_RESULT.json');full=read(HERE/'COVERAGE_RESULT.json')
    pilot=read(ROOT/'runs/source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json')
    for result in [pre,full]:
        check(result['status']=='PASS');check(result['optimizer_updates']==result['new_models']==0)
        for k in ['external_candidate_scoring','CAL_used_for_sampling','threshold_refit','parameter_gradients_measured']:check(result[k] is False)
    check(pre['engineering']['real_encoder_distance']['encoded_rows']==112)
    check(pre['engineering']['real_encoder_distance']['encoded_batches']==7)
    check(pre['forecast_seconds']<=3600)
    heads=full['coverage']['heads'];check(set(heads)=={'27','127','227','ensemble'})
    check(pre['source_preflight']['heads']['27']['fit']['ACTUAL_8192_EACH']==heads['27']['fit']['ACTUAL_8192_EACH'])
    compact={}
    for seed,h in heads.items():
        metrics=(pilot['ensemble'] if seed=='ensemble' else pilot['heads'][seed])['metrics'];compact[seed]={}
        for mode,levels in h['fit'].items():
            compact[seed][mode]={}
            for label in ['normal','attack']:
                baseline=levels['device'][label];records=baseline['top_risk_strata']
                check(len(records)==baseline['strata']==6)
                check(sum(x['rows'] for x in records)==metrics['fit'][label]['rows'])
                check(sum(x['residual_alarms'] for x in records)==metrics['fit'][label]['candidate_alarms'])
                near(sum(x['residual_alarm_mass'] for x in records),metrics['fit'][label]['candidate_weighted_rate'])
                near(sum(x['class_mass'] for x in records),1)
                for lev,labels in levels.items():
                    s=labels[label];check(s['rows']==baseline['rows']);check(s['pilot_rows']==(16384 if mode.startswith('UNIFORM') else 8192))
                    for key in ['objective_risk_mass','objective_abs_score_derivative_mass','selected_share_of_original_risk','selected_share_of_original_score_derivative']:near(s[key],baseline[key])
                    for key in ['missing_stratum_class_mass','class_mass_TV_distance','selected_share_of_original_risk','selected_share_of_original_score_derivative']:check(-1e-12<=s[key]<=1+1e-12)
                    for row in s['top_risk_strata']+s['top_residual_alarm_strata']:
                        check(0<=row['pilot_rows']<=row['rows']);check(0<=row['pilot_active_rows']<=row['active_rows'])
                s=levels['semantic'][label]
                compact[seed][mode][label]={k:s[k] for k in ['rows','pilot_rows','strata','missing_strata','missing_stratum_class_mass','class_mass_TV_distance','selected_share_of_original_risk','selected_share_of_original_score_derivative']}
                for key in ['objective_risk_mass','objective_abs_score_derivative_mass']:near(s[key],h['fit']['ACTUAL_8192_EACH']['semantic'][label][key])
        for label,cal in h['cal_descriptive'].items():
            if label=='attack':
                check(len(cal['top20'])==11)
                check(sum(x['cal']['rows'] for x in cal['top20'])==metrics['cal'][label]['rows'])
                check(sum(x['cal']['residual_alarms'] for x in cal['top20'])==metrics['cal'][label]['candidate_alarms'])
            check(cal['risk_mass_no_FIT_semantic_support']==0)
            if label=='normal':check(cal['risk_mass_FIT_present_but_not_sampled']==0)
    h=heads['ensemble'];cal=h['cal_descriptive']['normal']['top20'][0];check(cal['cal']['key']==['SimCam','LAN_RECORDING','6'])
    share=cal['cal']['residual_alarm_mass']/pilot['ensemble']['metrics']['cal']['normal']['candidate_weighted_rate']
    result=dict(status='PASS',scope='COMPACT_RECEIPT_AND_SUMMARY_AUDIT',checks=checks,engineering_complete=True,diagnostic_acceptance=True,
        training_go=False,decision='SOURCE_ONLY_SAMPLING_AND_WEIGHT_ESTIMATOR_REDESIGN_BEFORE_NEXT_PILOT',
        heads=compact,simcam_recording_cal=dict(rows=9,alarms=3,weighted_remaining_FP_share=share,fit_rows=66,pilot_rows=3),
        remote_artifacts={k:full['coverage'][k] for k in ['large_details','memberships']},
        receipt_sha256=receipt['receipt_sha256'],
        limitations=['Original pilot trained on ACTUAL rows; residual-risk comparisons are descriptive and training-conditioned, not causal efficacy tests.',
          'Weighted without-replacement membership improves coverage but is not an unbiased training estimator; blindly retaining old row weights double emphasizes high-weight rows.',
          'CAL semantic support is not feature-distribution equivalence; no CAL-driven membership selection.',
          'All heads share memberships, so seeds are not independent sampling replications.',
          'No local re-download or independent re-score of HPC arrays; hashes and compact receipt consistency checked.',
          'Attack residual_alarm fields count correctly detected attacks, not errors. Normal score_violation fields are score decreases, not protection failures.',
          'Ensemble objective is descriptive; actual training objectives operated separately per seed.'])
    write('COVERAGE_ACCEPTANCE_SUMMARY.json',result)
    write('FINAL_COVERAGE_ACCEPTANCE.json',dict(status='PASS',diagnosis_accepted=True,new_training_started=False,
        checks=checks,summary_sha256=hashlib.sha256((HERE/'COVERAGE_ACCEPTANCE_SUMMARY.json').read_bytes()).hexdigest()))
    print(json.dumps(dict(status='PASS',checks=checks,simcam_remaining_FP_share=share)))
if __name__=='__main__':main()
