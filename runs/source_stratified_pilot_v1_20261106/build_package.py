"""Build a bounded sampling-only method revision from a pinned accepted pilot."""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'runs/source_risk_preservation_pilot_v2_20261106'
def write(n,s):(HERE/n).write_bytes(s.encode('utf-8'))
def replace_once(s,a,b):assert s.count(a)==1,a;return s.replace(a,b)
def main():
    assert not (HERE/'START_INTENT.json').exists();(HERE/'.private').mkdir(exist_ok=True)
    delivery=json.loads((OLD/'DELIVERY.json').read_text())['pins']
    for n in ['worker.py','risk_core.py','test_risk.py','dependency_gate.py','test_dependencies.py','SPEC.json']:
        assert hashlib.sha256((OLD/n).read_bytes()).hexdigest()==delivery[n],n
    for n in ['risk_core.py','test_risk.py','dependency_gate.py','test_dependencies.py']:(HERE/n).write_bytes((OLD/n).read_bytes())
    spec=json.loads((OLD/'SPEC.json').read_text());spec.update(version='SOURCE_STRATIFIED_PILOT_V1',
        sampling='Within label: semantic strata (device,activity,protocol); one draw minimum per stratum, largest remainder allocation of remaining draws proportional to full FIT class mass; conditional PPS with replacement',
        pilot_weights='For each draw in stratum g use Wg/ng, never multiply original row weight again; existing balanced minibatch n_class/batch_class scaling unchanged',
        intended_target='full FIT per-class hierarchical expectation; unbiased design expectation for fixed parameters before sampling, not an adaptive optimization unbiasedness claim',
        normal_risk='E_full_FIT_normal[relu((score-upper)/original_FIT_scale)^2] estimated by fixed stratified draw set',
        attack_preservation='E_full_FIT_attack[relu((baseline-score)/original_FIT_scale-0.01)^2] estimated by fixed stratified draw set',
        context_preservation='E_full_FIT_attack[1(lift0>0)*relu((0.9*lift0-lift)/original_FIT_scale)^2] estimated by fixed stratified draw set',
        control='Reuse sealed v2 epoch5 three-seed endpoint; same input, optimizer, loss algebra, steps, cuts; sampling plus estimator jointly changed, no factorial attribution',
        sample_count_semantics='8192 draws per class; duplicate source identities allowed; actual unique identities reported; fixed draw set reused over five epochs',
        sampling_independent_of_CAL_scores=True,expected_semantic_groups={'normal':94,'attack':11})
    spec['limitations'] += ['No new independent test; CAL has been inspected diagnostically.',
        'Three model seeds share a single sampling realization, not independent sampling replicates.',
        'Same step budget and full-source target; not the same realized empirical objective as old uniform subset.',
        'Strata coverage does not guarantee within-stratum tail coverage or better detection.',
        'With-replacement fixed sample optimization can overfit; estimator expectation does not guarantee adaptive gradient unbiasedness.']
    write('SPEC.json',json.dumps(spec,indent=2)+'\n')
    pins=json.loads((OLD/'INPUT_PINS.json').read_text())
    for n,h in delivery.items():
        if n.endswith('.py'):pins[(OLD/n).relative_to(ROOT).as_posix()]=h
    for n in ['SPEC.json','PILOT_RESULT.json']:
        p=OLD/n;pins[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    write('INPUT_PINS.json',json.dumps(pins,indent=2)+'\n')
    src=(OLD/'worker.py').read_text()
    src=replace_once(src,'import risk_core as r','import risk_core as r\nimport sampling_core as sampler')
    src=replace_once(src,"selected=r.sample(labels); sy=labels[selected]; sw=r.batch_weights(data['w'][selected],sy)","selected,sw,sampling_receipt=sampler.draw(rr,data['w'],each=8192,seed=spec['sample_seed']); sy=labels[selected]\n    assert len(sampling_receipt['strata'])==105 and all(sum(v['label']==y for v in sampling_receipt['strata'])==expected for y,expected in [(0,94),(1,11)]), 'SOURCE_SEMANTIC_IDENTITY'")
    src=replace_once(src,'assert len(set(selected))==16384 and not set(data[\'fit\'][selected])&set(data[\'cal\'])',"assert len(selected)==16384 and not set(data['fit'][selected])&set(data['cal'])")
    src=replace_once(src,"sampling='uniform without replacement within each FIT class; fixed seed 20261106; no score selection',","sampling=sampling_receipt,\n                  unique_normal_rows=len(set(selected[sy==0])),unique_attack_rows=len(set(selected[sy==1])),")
    src=replace_once(src,"import test_risk;test_risk.main(HERE/'LINUX_REGRESSION.json')","module('local_risk_regression',HERE/'test_risk.py').main(HERE/'LINUX_REGRESSION.json')\n        module('local_sampling_regression',HERE/'test_sampling.py').main(HERE/'LINUX_SAMPLING_REGRESSION.json')")
    src=replace_once(src,"ens=ensemble(data,heads,small)","ens=ensemble(data,heads,small)\n        control=c.read(ROOT/'runs/source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json')\n        assert all(heads[str(s)]['initial_fingerprint']==control['heads'][str(s)]['initial_fingerprint'] and heads[str(s)]['cut']==control['heads'][str(s)]['cut'] and heads[str(s)]['normal_upper']==control['heads'][str(s)]['normal_upper'] for s in [27,127,227]),'CONTROL_IDENTITY'\n        assert ens['cut']==control['ensemble']['cut']")
    src=replace_once(src,"result=dict(status='PASS',heads=heads,ensemble=ens,signal_ready=", "result=dict(status='PASS',historical_control_sha256=c.sha(ROOT/'runs/source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json'),sampling_only_method_revision=True,heads=heads,ensemble=ens,signal_ready=")
    write('worker.py',src)
    for n in ['receiver.py','chain_client.py']:
        src=(OLD/n).read_text().replace('18855','18857').replace('SOURCE_RISK_PILOT','SOURCE_STRATIFIED_PILOT').replace('SOURCE_RISK_NO_SIGNAL','SOURCE_STRATIFIED_NO_SIGNAL').replace('source-risk','source-stratified')
        write(n,src)
    src=(OLD/'prepare_delivery.py').read_text().replace('18855','18857').replace('SOURCE_RISK_PILOT_V2','SOURCE_STRATIFIED_PILOT_V1').replace('SOURCE_RISK_PRESERVATION_PILOT','SOURCE_STRATIFIED_PILOT')
    src=replace_once(src,"'test_risk.py','dependency_gate.py'","'test_risk.py','sampling_core.py','test_sampling.py','dependency_gate.py'")
    src=replace_once(src,"names=['worker.py'","assert json.loads((HERE/'SAMPLING_REGRESSION.json').read_text())['status']=='PASS'\n    names=['worker.py'")
    src=src.replace("runs/fusion_training_audit_v1_20261105/.private/connection.json","runs/source_coverage_audit_v1_20261106/.private/connection.json")
    write('prepare_delivery.py',src)
    html=(OLD/'progress.html').read_text().replace('SOURCE_RISK_PILOT','SOURCE_STRATIFIED_PILOT').replace('SOURCE_RISK_NO_SIGNAL','SOURCE_STRATIFIED_NO_SIGNAL')
    html=html.replace('正常误报与攻击保护：源域小试','分层抽样与权重校正：源域小试').replace('降低正常误报，同时保护攻击检测','改善抽样覆盖，检验误报与攻击保护')
    html=html.replace('<strong>训练目标</strong>','<strong>本轮改变什么</strong><p>按设备／活动／协议分层分配配额，组内按原权重有放回抽样，损失使用配套Wg/ng权重，避免重复加权。每类8192个样本位，实际独立样本数另报；每种子仍320次更新。</p><p>对照复用已封存原均匀抽样小试；起点、损失公式、优化器、阈值及验收门相同。仅源FIT决定抽样，不根据CAL或Edge成绩选样本。</p><strong>训练目标</strong>')
    write('progress.html',html);write('.gitattributes','* -text\n')
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    print('STRATIFIED_PACKAGE_BUILT')
if __name__=='__main__':main()
