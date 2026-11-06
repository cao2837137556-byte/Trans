"""Build a separately versioned pilot using the proven bounded transport."""
import ast, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
OLD=ROOT/'runs/context_anchor_diagnosis_v1_20261105'
def write(name,text): (HERE/name).write_bytes(text.encode('utf-8'))
def main():
    assert not (HERE/'START_INTENT.json').exists()
    (HERE/'.private').mkdir(exist_ok=True)
    spec=dict(version='SOURCE_RISK_PRESERVATION_PILOT_V1',seeds=[27,127,227],sample_seed=20261106,
              sample_per_class=8192,batch_per_class=128,epochs=5,updates_per_seed=320,
              learning_rate=1e-5,optimizer='AdamW',betas=[.9,.999],eps=1e-8,weight_decay=0,
              initial_model='matched original FUSION790 epoch40; new optimizer; encoder and normalizers frozen',
              normal_upper='weighted 90th percentile of original model full FIT normal scores',
              normal_risk='E_pilot_normal[relu((score-upper)/original_FIT_scale)^2]',
              attack_preservation='E_pilot_attack[relu((baseline-score)/original_FIT_scale-0.01)^2]',
              context_preservation='E_pilot_attack[1(lift0>0)*relu((0.9*lift0-lift)/original_FIT_scale)^2]',
              total_loss='normal_risk + 10*attack_preservation + 10*context_preservation',
              coefficients_preregistered=True,hyperparameter_search=False,
              attack_tolerance='0.01 original FIT scale; soft penalty, not a guaranteed hard constraint',
              context_intervention='zero normalized 8 columns; off-manifold diagnostic regularizer only',
              pilot_weights='preserve original FIT weights ratios, renormalize within each sampled class; equal-sized balanced batches',
              threshold_policy='original FUSION790 per-seed and ensemble CAL thresholds fixed; no recalibration',
              primary_endpoint='fixed fifth epoch; all seeds and ordered float64 ensemble reported; no selection',
              scientific_gates=dict(per_seed_roles=['FIT','FIT_NOT_IN_PILOT','CAL'],normal_weighted_and_unweighted_nonincrease=True,
                                    attack_recall_max_drop=.001,attack_removed_fraction_max=.001,
                                    attack_standardized_p01_change_min=-.01,positive_context_mean_retention_min=.9,
                                    per_protocol_attack_recall_max_drop=.001,ensemble_CAL_weighted_FPR_relative_reduction_min=.10),
              phases=dict(DECODE_PREFLIGHT=1800,TRAIN_PREFLIGHT=1800,PILOT=3600),cpu=1,memory_gib=8,
              preflight_updates_per_seed=8,automatic_full_training=False,automatic_external_evaluation=False,
              external_use='unchanged old engineering encoder/distance/metric replay only; candidate never scored externally',
              limitations=['Source CAL previously used to set original cuts and is not a fresh test.',
                           'FIT outside pilot was used by original model; holdout only for this fine-tuning.',
                           'Source protection does not guarantee Edge attack preservation.',
                           'Upper-tail compression may transfer poorly; report NO_GO rather than tune to Edge.'])
    write('SPEC.json',json.dumps(spec,indent=2)+'\n')
    pins={}
    for dirname in ['device_context_head_training_v2_20261105','fusion_score_anchor_v2_20261105','device_context_evaluation_v1_20261105']:
        deployed=json.loads((ROOT/'runs'/dirname/'DELIVERY.json').read_text())['pins']
        for name,expected in deployed.items():
            if not name.endswith('.py'):continue
            p=ROOT/'runs'/dirname/name
            assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,'LOCAL_DEPLOYED_SOURCE_DRIFT:'+name
            pins[p.relative_to(ROOT).as_posix()]=expected
    for n in ['CALIBRATION_RESULT.json','NORMALIZER.json','TRAINING_SPEC_FROZEN.json']+[f'TRAIN_FUSION790_{s}_RESULT.json' for s in [27,127,227]]:
        p=ROOT/'runs/device_context_head_training_v2_20261105'/n;pins[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    write('INPUT_PINS.json',json.dumps(pins,indent=2)+'\n')
    oldspec=ROOT/'runs/source_risk_preservation_pilot_v1_20261106/SPEC.json'
    assert oldspec.read_bytes()==(HERE/'SPEC.json').read_bytes(),'METHOD_MUST_NOT_CHANGE'
    phases="['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']"
    src=(OLD/'receiver.py').read_text().replace("['PREFLIGHT','CONTRIBUTION','GRADIENT']",phases).replace('18853','18855').replace('context-diag','source-risk')
    src=src.replace("def run(phase,minutes):", "def run(phase,minutes):\n    import dependency_gate\n    gate=dependency_gate.verify(PROJECT,read('INPUT_PINS.json'))\n    write('DEPENDENCY_GATE.json',gate)")
    src=src.replace("d['runtime_forecast']=read('RUNTIME_FORECAST.json')", "d['runtime_forecast']=read('RUNTIME_FORECAST.json')\n    d['dependency_gate']=read('DEPENDENCY_GATE.json')")
    src=src.replace("for phase in PHASES:run(phase,60 if phase=='GRADIENT' else 30)","for phase in PHASES:\n            if phase=='PILOT' and not read('TRAIN_PREFLIGHT_RESULT.json')['signal_ready']:\n                write('STATE.json',dict(stage='SOURCE_RISK_NO_SIGNAL',phase='TRAIN_PREFLIGHT'));return\n            run(phase,60 if phase=='PILOT' else 30)")
    src=src.replace('CONTEXT_ANCHOR_DIAGNOSIS_COMPLETE','SOURCE_RISK_PILOT_COMPLETE').replace("phase='GRADIENT'","phase='PILOT'")
    write('receiver.py',src)
    src=(OLD/'chain_client.py').read_text().replace("['PREFLIGHT','CONTRIBUTION','GRADIENT']",phases).replace('18853','18855')
    src=src.replace("state.get('phase','PREFLIGHT')","state.get('phase','DECODE_PREFLIGHT')").replace('DIAG_CONTEXT_ANCHOR_V1','SOURCE_RISK_PILOT_V2')
    src=src.replace('CONTEXT_ANCHOR_DIAGNOSIS_COMPLETE','SOURCE_RISK_PILOT_COMPLETE')
    src=src.replace("['STOP','SOURCE_RISK_PILOT_COMPLETE']","['STOP','SOURCE_RISK_PILOT_COMPLETE','SOURCE_RISK_NO_SIGNAL']")
    src=src.replace("['SOURCE_RISK_PILOT_COMPLETE','STOP']","['SOURCE_RISK_PILOT_COMPLETE','STOP','SOURCE_RISK_NO_SIGNAL']")
    src=src.replace('DIAGNOSIS_COMPLETION.json','PILOT_COMPLETION.json').replace('ENGINEERING_COMPLETION_INTERPRETATION_PENDING','SOURCE_PILOT_ENGINEERING_COMPLETE_SCIENTIFIC_REVIEW_PENDING')
    write('chain_client.py',src)
    src=(OLD/'prepare_delivery.py').read_text().replace("['worker.py','analysis_core.py','test_diagnosis.py','INPUT_PINS.json','SPEC.json']","['worker.py','risk_core.py','test_risk.py','dependency_gate.py','test_dependencies.py','INPUT_PINS.json','SPEC.json']")
    src=src.replace("names=['worker.py'", "assert json.loads((HERE/'DEPENDENCY_REGRESSION.json').read_text())['status']=='PASS'\n    names=['worker.py'")
    src=src.replace('18853','18855').replace('CONTEXT_DIAGNOSIS','SOURCE_RISK_PILOT_V2').replace('CONTEXT_CONTRIBUTION_SOURCE_GRADIENT_DIAGNOSIS','SOURCE_RISK_PRESERVATION_PILOT')
    src=src.replace('new_heads=0','new_heads=3').replace('accept_existing_ab_regression_only=True','external_evaluation_authorized=False,full_training_authorized=False')
    write('prepare_delivery.py',src)
    write('.gitattributes','* -text\n')
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    print('PILOT_PACKAGE_BUILT')
if __name__=='__main__':main()
