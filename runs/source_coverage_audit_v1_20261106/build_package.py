"""Use explicit already-deployed dependency inventories, never local glob pins."""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'runs/source_risk_preservation_pilot_v2_20261106'
def write(n,t):(HERE/n).write_bytes(t.encode())
def main():
    assert not (HERE/'START_INTENT.json').exists();(HERE/'.private').mkdir(exist_ok=True)
    for n in ['dependency_gate.py','test_dependencies.py']:(HERE/n).write_bytes((OLD/n).read_bytes())
    pins=json.loads((OLD/'INPUT_PINS.json').read_text())
    for n,h in json.loads((OLD/'DELIVERY.json').read_text())['pins'].items():
        if n.endswith('.py'):pins[(OLD/n).relative_to(ROOT).as_posix()]=h
    for n in ['PILOT_RESULT.json','SPEC.json']:
        p=OLD/n;pins[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    for n,h in pins.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
    write('INPUT_PINS.json',json.dumps(pins,indent=2)+'\n')
    spec=dict(version='SOURCE_COVERAGE_AUDIT_V1',seeds=[27,127,227],source='same frozen FIT/CAL rows, pilot memberships and epoch5 arrays',
        primary='full FIT normal risk coverage and attack score-decline tail coverage',
        levels=['device','device+activity','device+activity+protocol','device+activity+capture+session+protocol'],
        membership_plans=['ACTUAL_8192_EACH','UNIFORM_16384_EACH','WEIGHTED_8192_EACH'],seed=20261106,
        weighted_plan='class conditional original FIT hierarchy weights; without replacement; coverage only, no training or inclusion-corrected objective claim',
        cal='descriptive semantic stratum join only; never used to construct any selection',
        score_derivative='analytical absolute derivative of normal/attack squared hinge w.r.t score; not neural parameter gradient',
        prediction_claim=False,optimizer_updates=0,new_heads=0,threshold_refit=False,external_candidate_scoring=False,
        cpu=1,memory_gib=8,phases=dict(PREFLIGHT=1800,COVERAGE=3600),automatic_retries=0,
        forecast='2*12*measured one-head actual-membership source audit seconds +120; <=3600',
        limitations=['same semantic stratum does not guarantee same feature distribution','coverage simulations do not predict trained efficacy',
        'no causal parameter-gradient diagnosis; no CAL-selected training identities','preflight old engineering replay does not score new external candidates'])
    write('SPEC.json',json.dumps(spec,indent=2)+'\n')
    src=(OLD/'receiver.py').read_text().replace("['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']","['PREFLIGHT','COVERAGE']").replace('18855','18856').replace('source-risk','source-coverage')
    src=src.replace("            if phase=='PILOT' and not read('TRAIN_PREFLIGHT_RESULT.json')['signal_ready']:\n                write('STATE.json',dict(stage='SOURCE_RISK_NO_SIGNAL',phase='TRAIN_PREFLIGHT'));return\n",'')
    src=src.replace("60 if phase=='PILOT' else 30","60 if phase=='COVERAGE' else 30").replace("phase='PILOT'","phase='COVERAGE'").replace('SOURCE_RISK_PILOT_COMPLETE','SOURCE_COVERAGE_COMPLETE').replace("d['total_phases']=3","d['total_phases']=2")
    write('receiver.py',src)
    src=(OLD/'chain_client.py').read_text().replace("['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']","['PREFLIGHT','COVERAGE']").replace('18855','18856').replace("'DECODE_PREFLIGHT'","'PREFLIGHT'").replace('SOURCE_RISK_PILOT_V2','SOURCE_COVERAGE_V1').replace('SOURCE_RISK_PILOT_COMPLETE','SOURCE_COVERAGE_COMPLETE').replace(",'SOURCE_RISK_NO_SIGNAL'",'').replace('total_phases=3','total_phases=2').replace('PILOT_COMPLETION.json','COVERAGE_COMPLETION.json').replace('SOURCE_PILOT_ENGINEERING_COMPLETE_SCIENTIFIC_REVIEW_PENDING','SOURCE_COVERAGE_ENGINEERING_COMPLETE_INTERPRETATION_PENDING')
    write('chain_client.py',src)
    src=(OLD/'prepare_delivery.py').read_text().replace("['worker.py','risk_core.py','test_risk.py','dependency_gate.py','test_dependencies.py','INPUT_PINS.json','SPEC.json']","['worker.py','coverage_core.py','test_coverage.py','dependency_gate.py','test_dependencies.py','INPUT_PINS.json','SPEC.json']")
    src=src.replace('18855','18856').replace('SOURCE_RISK_PILOT_V2','SOURCE_COVERAGE').replace('SOURCE_RISK_PRESERVATION_PILOT','SOURCE_COVERAGE_AND_TAIL_AUDIT').replace('new_heads=3','new_heads=0')
    write('prepare_delivery.py',src);write('.gitattributes','* -text\n')
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    print('COVERAGE_PACKAGE_PREPARED')
if __name__=='__main__':main()
