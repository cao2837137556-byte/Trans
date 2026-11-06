"""Isolated bounded finite-update guard experiment from the frozen stratified pilot."""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'runs/source_stratified_pilot_v1_20261106'
def write(n,s):(HERE/n).write_bytes(s.encode())
def once(s,a,b):assert s.count(a)==1,a;return s.replace(a,b)
def main():
    assert not (HERE/'START_INTENT.json').exists();(HERE/'.private').mkdir(exist_ok=True)
    pins0=json.loads((OLD/'DELIVERY.json').read_text())['pins']
    for n,h in pins0.items():assert hashlib.sha256((OLD/n).read_bytes()).hexdigest()==h,n
    for n in ['risk_core.py','sampling_core.py','test_risk.py','test_sampling.py','dependency_gate.py','test_dependencies.py']:(HERE/n).write_bytes((OLD/n).read_bytes())
    spec=json.loads((OLD/'SPEC.json').read_text());spec.update(version='SOURCE_GUARDED_PILOT_V1',
        control='Frozen source_stratified_pilot_v1 epoch5 endpoint; identical sampling identities/weights, teacher, loss, baseline optimizer; guarded LR replay adds compute and may retain fewer steps',
        updates_per_seed=320,updates_count_semantics='320 nominal proposal slots, up to1280 actual optimizer steps; retained optimizer steps<=320; runtime negative controls separately reported',
        primary_endpoint='retained state after fixed fifth source-guarded proposal round, never CAL-selected',
        guard=dict(rounds=5,batches_per_round=64,lr_factors=[1.,.5,.25,.125],
            check_scope=['all FIT','FIT not sampled for gradient'],
            acceptance='All original per-seed source scientific criteria plus full FIT normal tail risk nonincrease from previous retained state',
            rollback='restore complete model, Adam moments/step counters and torch RNG before every attempt; all fail restores previous retained state',
            full_FIT_feedback=True,CAL_feedback=False,normal_risk_atol=1e-14,normal_risk_rtol=1e-10,
            no_per_packet_or_intermediate_step_guarantee=True),
        forecast='2*(load_seconds + sum(preflight_head_seconds + 5*4*worst_measured_scaled_attempt_seconds)) +60 <=3600',
        preflight_actual_steps='8 nominal, up to32 on replay; plus4 forced one-step rejections to verify complete state restoration')
    spec['scientific_gates']['per_seed_roles']=['FIT','FIT_NOT_SAMPLED_FOR_GRADIENT','CAL']
    spec['limitations'] += ['All FIT now participates in optimization feedback; non-gradient FIT is not validation.',
        'Per-seed source guard does not guarantee CAL, external or ensemble quantile preservation.',
        'Original soft loss retained; finite guard prevents storing rejected round endpoints only.',
        'Backtracking may stall; report zero accepted progress rather than expanding time or relaxing guards.',
        'Guarded vs historical control has different compute; report actual attempted and retained updates.']
    write('SPEC.json',json.dumps(spec,indent=2)+'\n')
    pins=json.loads((OLD/'INPUT_PINS.json').read_text())
    for n,h in pins0.items():
        if n.endswith('.py'):pins[(OLD/n).relative_to(ROOT).as_posix()]=h
    for n in ['SPEC.json','PILOT_RESULT.json']:
        p=OLD/n;pins[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    write('INPUT_PINS.json',json.dumps(pins,indent=2)+'\n')
    src=(OLD/'worker.py').read_text();src=once(src,'import sampling_core as sampler','import sampling_core as sampler\nimport guard_core as guard_module\nimport guarded_training')
    begin=src.index('    rng=np.random.default_rng(seed); count=0; epochs=1 if small else spec[\'epochs\']')
    end=src.index("    c.save_arrays(folder/'head.npz'",begin)
    training='''    guard=guard_module.SourceGuard(rr,selected,saved['fit'],fullzero['fit'],cut,scale,upper,k.class_weights,criteria)
    def evaluate_guard():
        model.eval();p.stage='SOURCE_GUARD_SCORE_seed'+str(seed)
        s=k.scores(model,data['values'],data['q'],data['fit'],data['norm'],790,p)
        p.stage='SOURCE_GUARD_ZERO_seed'+str(seed)
        z=zero_scores(model,data,data['fit'],p)
        return guard.evaluate(s,z)
    training=guarded_training.run(model,optimizer,x,zx,teacher,teacher_zero,sy,sw,upper,scale,seed,small,spec,folder,p,c,guard,evaluate_guard)
    count=training['executed_updates'];epochs=training['epochs'];records=training['gradient_probes'];epoch_receipts=training['trajectory']
    train_seconds=training['train_seconds'];first_normal_norm=training['first_normal_gradient_norm']
    assert training['nominal_updates']==(8 if small else 320) and r.fingerprint(baseline)==before
    assert training['retained_optimizer_updates']<=training['nominal_updates'] and count<=4*training['nominal_updates']+(4 if small else 0)
'''
    src=src[:begin]+training+src[end:]
    src=src.replace('fit_not_used_in_pilot','fit_not_sampled_for_gradient')
    src=once(src,"gates={role:criteria(metric) for role,metric in metrics.items()}","gates={role:criteria(metric) for role,metric in metrics.items()}\n    for role in ['fit','fit_not_sampled_for_gradient']:\n        assert gates[role]=={key.split('/',1)[1]:value for key,value in training['final_source_guard']['checks'].items() if key.startswith(role+'/')}\n    assert abs(metrics['fit']['normal']['candidate_tail_risk']-training['final_source_guard']['normal_tail_risk'])<1e-12,'FINAL_GUARD_PARITY'")
    src=once(src,'signal_ready=identity[\'normal_active_rows\']>0 and first_normal_norm>1e-12 and before!=r.fingerprint(model)',"signal_ready=training['signal_ready'] and before!=r.fingerprint(model)")
    src=once(src,"train_seconds=train_seconds,seconds=time.monotonic()-started,metrics=metrics,gates=gates,","train_seconds=train_seconds,seconds=time.monotonic()-started,metrics=metrics,gates=gates,guarded_training=training,")
    src=once(src,"module('local_sampling_regression',HERE/'test_sampling.py').main(HERE/'LINUX_SAMPLING_REGRESSION.json')","module('local_sampling_regression',HERE/'test_sampling.py').main(HERE/'LINUX_SAMPLING_REGRESSION.json')\n        module('local_guard_regression',HERE/'test_guard.py').main(HERE/'LINUX_GUARD_REGRESSION.json')")
    src=src.replace('source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json','source_stratified_pilot_v1_20261106/PILOT_RESULT.json')
    src=once(src,"assert ens['cut']==control['ensemble']['cut']","assert ens['cut']==control['ensemble']['cut']\n        assert all(heads[str(s)]['identity']['uid_sha256']==control['heads'][str(s)]['identity']['uid_sha256'] and heads[str(s)]['identity']['sample_weight_sha256']==control['heads'][str(s)]['identity']['sample_weight_sha256'] for s in [27,127,227]),'SAMPLING_CONTROL_IDENTITY'")
    src=src.replace('sampling_only_method_revision=True','guarded_update_method_revision=True')
    src=once(src,"forecast=2*(data['load_seconds']+sum(h['seconds']+39*h['train_seconds'] for h in heads.values()))+60","assert all(h['guarded_training']['rollback_smoke']['status']=='PASS' for h in heads.values())\n            forecast=2*(data['load_seconds']+sum(h['seconds']+5*4*h['guarded_training']['worst_single_attempt_formal_epoch_seconds'] for h in heads.values()))+60")
    src=once(src,"external_candidate_scoring=False,threshold_refit=False,encoder_finetuned=False,automatic_full_training=False)","external_candidate_scoring=False,threshold_refit=False,encoder_finetuned=False,automatic_full_training=False,all_FIT_used_for_guard_feedback=True,CAL_used_for_update_acceptance=False)")
    write('worker.py',src)
    for n in ['receiver.py','chain_client.py','prepare_delivery.py']:
        src=(OLD/n).read_text().replace('18857','18858').replace('SOURCE_STRATIFIED','SOURCE_GUARDED').replace('source-stratified','source-guarded')
        if n=='prepare_delivery.py':
            src=once(src,"names=['worker.py'","assert json.loads((HERE/'GUARD_REGRESSION.json').read_text())['status']=='PASS'\n    names=['worker.py'")
            src=once(src,"'sampling_core.py','test_sampling.py'","'sampling_core.py','test_sampling.py','guard_core.py','guarded_training.py','test_guard.py'")
        write(n,src)
    html=(OLD/'progress.html').read_text().replace('SOURCE_STRATIFIED','SOURCE_GUARDED')
    html=html.replace('分层抽样与权重校正：源域小试','源域受限更新：正常风险与攻击保护').replace('改善抽样覆盖，检验误报与攻击保护','保护攻击尾部，检验正常风险能否继续下降')
    start=html.index('<div class="card"><strong>本轮改变什么</strong>');end=html.index('<div class="card"><strong>怎样判定值得继续</strong>',start)
    html=html[:start]+'''<div class="card"><strong>本轮改变什么</strong><p>保留分层抽样、原损失与模型起点。每轮64批后，用全部源FIT检查原保护门和正常尾部风险；不通过则恢复模型、Adam状态及随机状态，以1/2、1/4、1/8步长重算，最多4档，仍失败则回退。</p><p>三个种子固定5轮提案；每头名义320步，最多实际1280步，实际计算和保留更新分别报告。全部FIT参与更新判断，未抽中梯度训练的FIT也不是独立验证集。CAL不参与更新选择。</p></div>\n'''+html[end:]
    html=html.replace('共960次更新','名义共960步，重算另计').replace('三种子各8批真实源训练，核对分数复现、更新、回执与耗时','三种子各8批真实提案、全源验收、强制拒绝回退测试及最坏耗时预算')
    html=html.replace('本轮未使用FIT','未抽中梯度训练的FIT').replace('固定第5轮端点','固定第5轮保留端点')
    write('progress.html',html);write('.gitattributes','* -text\n')
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    print('GUARDED_PACKAGE_BUILT')
if __name__=='__main__':main()
