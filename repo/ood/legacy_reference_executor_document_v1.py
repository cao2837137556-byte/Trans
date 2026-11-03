# -*- coding: utf-8 -*-
"""Write verified implementation evidence, never run a real experiment."""
import ast,shutil,subprocess,time
from pathlib import Path
import legacy_reference_executor_common_v1 as c
def main():
    out=c.PACKAGE;docs=c.ROOT/'runs/mainline_docs'
    suites={n:c.load(out/(n+'.json')) for n in ('unit_acceptance_v2','supervisor_acceptance_v2','e2e_acceptance_v3')}
    c.require(all(x['status']=='PASS' and x['failures']==x['errors']==0 for x in suites.values()),'ACCEPTANCE_FAILED')
    c.require(sum(x['tests'] for x in suites.values())==32,'ACCEPTANCE_COUNT');c.scope_metadata()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(c.ROOT),text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=str(c.ROOT),text=True).strip()
    c.require(head=='4b28747b09480471e2bac1beb3a9badf27280efb' and branch=='codex/exp-mainline','GIT_CHANGED')
    final_runs=[]
    for folder in sorted((out/'synthetic').glob('e2e_final_*')):
        for name in ('closed_run','open_run'):
            run=folder/name
            if not (run/'result.json').exists():continue
            c.verify_seal(run);result=c.load(run/'result.json')
            c.require(result['status']=='COMPLETE' and result['synthetic_only'],'SYNTHETIC_RESULT')
            audits=[c.load(p) for p in (run/'requests').glob('*.access.json')]
            c.require(len(audits)==len(result['stages']) and all(x['blocked_asset_attempts']==x['real_checkpoint_reads']==x['real_raw_reads']==0 for x in audits),'ASSET_ACCESS_DRIFT')
            final_runs.append(dict(path=str(run.relative_to(c.ROOT)),heldout_opened=result['heldout_opened'],
                stages=len(result['stages']),simulated_open=bool(result['gate'].get('synthetic_gate_override')),result_sha256=c.sha(run/'result.json')))
    c.require(len(final_runs)==2 and {x['heldout_opened'] for x in final_runs}=={True,False},'BOTH_BRANCHES_REQUIRED')
    pending=list((c.ROOT/'repo/ood').glob('*legacy_reference_executor*.py'))+[c.ROOT/'repo/ood/legacy_reference_feature_adapter_v1.py']
    source=set()
    while pending:
        p=pending.pop().resolve()
        if p in source:continue
        source.add(p);tree=ast.parse(p.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for name in names:
                child=c.ROOT/'repo/ood'/(name.split('.')[0]+'.py')
                if child.is_file() and child.resolve() not in source:pending.append(child)
    source.update(c.ROOT/'scripts'/n for n in ('start_legacy_reference_executor_v1.ps1','show_legacy_reference_executor_v1.ps1'))
    source.update([c.RECIPE,c.SAMPLE/'SHA256SUMS',c.SAMPLE/'finalized/SHA256SUMS',c.ROOT/'runs/legacy_cic2022_p2_enhancement_design_v1_20260915/vendor_source_pins.json'])
    c.atomic_json(out/'code_pins.json',{str(p.relative_to(c.ROOT)).replace(chr(92),'/'):c.sha(p) for p in sorted(source)})
    c.atomic_json(out/'authorization.json',dict(user_quote='动手下一步',scope='Implementation and synthetic acceptance only',
        real_features=False,real_training=False,real_scoring=False,new_downloads=False,hpc=False))
    c.atomic_json(out/'acceptance.json',dict(status='PASS',tests=32,suites=suites,real_model_forwards=0,real_optimizer_steps=0,real_raw_decodes=0,
        final_synthetic_chains=final_runs,recipe_sha256=c.RECIPE_SHA,code_pins_sha256=c.sha(out/'code_pins.json'),
        preservation=dict(original_recipe_and_source_pins=True,unrelated_files=8,branch=branch,head=head),
        engineering_fixes=['Report helper reference fixed after first synthetic attempt; failure retained.',
                           'Supervisor test directory collision fixed in fixture; original test log retained.'],
        scientific_result=False,completed_epoch=time.time()))
    c.atomic_json(out/'execution_scope.template.json',dict(execution_authorized=False,recipe_sha256=c.RECIPE_SHA,
        stages=['LEARN_DEV_FEATURES','NINE_TRAIN_ENDPOINTS','DEV','CONDITIONAL_HOLDOUT'],retries=0,local_only=True,
        output_run_name='legacy_reference_joint_development_v1_20260917',
        authorization_note='Review template only. Later explicit complete-chain authorization required. Frozen recipe remains unchanged.',
        limits=c.recipe()['runtime']))
    document="""# 正常参考机制执行器：实现与合成验收完成

日期：2026-09-17。**代码实现与工程验收完成，没有读取真实模型权重、提取真实特征、进行真实训练或生成科学检测结果。**

## 1. 已接通的执行链

学习/开发清单 → 一份共用 E3 缓存 → Q/M/C 各3 seed、共9个固定训练终点 → 学习集拟合诊断和 DEV 判断 → 门槛通过后一次保留设备特征/评估 → 完整报告与封存。

原配方 SHA256 为 85dc7138cd43cdef16ab15394b7712eb97b124311c06b4ea63aba853f781560a，字节未变。原 E3、标准化参数、R 和概率阈值 0.065159872174263 不变。Q/M/C 参数分别为14,385/38,961/27,201，末层零初始化；无参考时精确回退 R。M 使用实际参考总体标准差，C 的均值/最大值均屏蔽填充。

训练只使用 LEARN 查询和参考。相同 seed 的三臂采用相同独立随机排列、相同行曝光与权重；每 epoch 每个 UID 一次。冻结的 N/batch_actual_size 加权 BCE 不作批内重新归一化。40 epochs、3 seeds、末轮平均 logit 和原阈值保持冻结，不挑最佳 seed 或 epoch。

特征生成使用现有因果适配器，在每个输入包 append 前隔离设备/捕获/连接；保留未抽中但合法的过去上下文，检查源 SHA、UID、标签、时间和完整覆盖。缓存使用按捕获索引和磁盘数组供各臂共用，不改变样本分母，不静默删除失败行。方向/设备本地端口只进入报告旁路，以免 Philips 入站本地 TCP80 对照混入出站访问远端80；MAC、角色、标签和文件统计不进入模型向量。

## 2. 最终32项验收

- 25项行为/因果适配器检查：旧 R 数值一致、无参考精确回退、参考填充/顺序、总体标准差、尾批次权重梯度、相同行呈现、参考时间/用途、DEV 禁止进入优化器、逐设备/模式门槛、本地服务方向。
- 5项监督器检查：超时清理整棵子进程树、磁盘上限停止并保留产物、Windows Job 内存限制、明确停止请求、失败封存和禁止原地重复运行。
- 2条完整合成链：真实 tokenizer/collator 和旧数值转换器，配合替身编码器、合成 R 状态与流量，执行九个小训练终点、分项报告、预算16和错配参考干预、封存。

每条完整合成链每个终点6次更新。关闭路径由实际合成 DEV 门槛关闭；开启路径使用**仅限合成夹具的显式覆盖**，只验证流程，不代表科学门槛通过。子进程文件守卫禁止读取夹具目录外的模型权重、NPY/NPZ、PCAP，最终两条链无越界读取或被拦截尝试。

首个合成流程发现报告辅助函数引用错误；监督器测试发现测试目录重名。均已修复并在新测试目录验证，失败证据保留。没有科学规则变更，也没有真实实验重试。

## 3. 运行、报告与限制

本地一次一个模型进程、最多附带一个解码器；Windows Job 对工作进程树设置12GiB提交内存上限，关闭/终止时清理子进程。监督器检查16GiB新输出、整个链72小时上限；CPU4线程、E3 batch16、零自动重试。72小时是停止上限，不是预计用时，真实吞吐尚未测量。

状态与结果由本地程序落盘，无需 LLM 持续轮询。查看脚本识别监督进程消失及 PID 复用，避免将断电残留 RUNNING 当作仍运行。已有输出目录拒绝再次启动；真实异常保留现场，不自动重试。

报告含正常误报、攻击检出、逐设备/模式/捕获、活动覆盖和持续连接分层、R 正确攻击的新漏检与 R 漏检的新检出；全部 seed 与主平均结果均保存。干预不重训、不晋升为最佳模型。缺失比较、上游标签/协议排除明确记录。旧 ID 的0/2,378只作为已披露的原样回退锚点，不伪装新做独立 ID 测试。

C 的方向性干预实现采用保守判据：至少一台 DEV 设备，正确参考相比等预算错误参考降低正常误报，同时该设备总体攻击检出损失不超过1个百分点；仍完整报告每种攻击模式。还必须满足原冻结 C 对 R、C 对 M 联合比较。这只是有限开发证据，不代表显著性或部署保证。

服务/采集视角混淆、设备少、Ring仅1条及 Atomi/Globe各2条参考、E3预训练排重未证明等限制未消失。合成验收不能证明真实 E3 对全部目标前向成功，也不承诺模型能力改善。

## 4. 入口与下一步

实现/验收包：runs/legacy_reference_executor_implementation_v1_20260917/，含 acceptance、代码闭包 pins、测试日志、合成证据和 SHA256SUMS。

启动脚本：scripts/start_legacy_reference_executor_v1.ps1。
独立状态脚本：scripts/show_legacy_reference_executor_v1.ps1 -OutputDirectory <run> [-Watch]。
execution_scope.template.json 的 execution_authorized=false，只是完整链模板，没有自动启动任何真实工作。

下一步为另行明确授权后的一次完整真实链：学习/开发特征 → 九终点 → DEV → 若通过则一次保留设备确认。无需再逐文件授权或泛泛重开方案；异常停止，零自动重试。不下载新数据、不启动 HPC。

solved: 冻结配方的执行链与端到端合成验收完成。
changed_mainline: EXECUTOR_IMPLEMENTED_SYNTHETIC_ACCEPTANCE_PASS，无科学结果。
active_blocker: 真实完整链尚未授权、未启动；真实吞吐和收益未知。
frozen: 原样本/配方/旧 R/阈值/原有修改保留。
next_action: 明确授权后一次执行完整真实链，异常停止且不自动重试。
"""
    result=docs/'legacy_reference_executor_implementation_result_v1_20260917.md';c.require(not result.exists(),'RESULT_EXISTS')
    result.write_text(document,encoding='utf8');result.with_suffix('.sha256').write_text(c.sha(result)+'  '+result.name+'\n',encoding='utf8')
    prior=out/'living_docs_before';prior.mkdir(exist_ok=False)
    for name in ('mainline_handoff.md','mainline_experiment_map.md'):shutil.copy2(docs/name,prior/name)
    path=docs/'mainline_handoff.md';old=path.read_bytes().decode('utf8');nl='\r\n' if '\r\n' in old else '\n'
    anchor='### 2026-09-17 latest: real sample manifests and prospective recipe COMPLETE; no model execution'
    c.require(old.count(anchor)==1,'HANDOFF_ANCHOR')
    panel="""### 2026-09-17 latest: reference executor IMPLEMENTED; 32 synthetic acceptance checks PASS

Read legacy_reference_executor_implementation_result_v1_20260917.md / SHA and run
legacy_reference_executor_implementation_v1_20260917: acceptance, code_pins, logs,
two final synthetic chains, execution_scope.template and SHA256SUMS.
Frozen sample/recipe unchanged: LEARN766,727 / DEV179,886 / HOLDOUT341,222 queries;227refs.
Q/M/C fixed heads, frozen R/normalizer/E3, shared caches,9endpoints, original threshold,
DEV gate before single conditional HOLDOUT, matched reference interventions implemented.
25behavior/causal checks +5process/resource checks +2end-to-end synthetic chains PASS.
Real tokenizer/collator with stand-in model; real assets denied in synthetic workers.
Real features/model forwards/optimizer updates/raw decodes this stage: ZERO. No science PASS.

Local one-model worker, Job memory12GiB, disk16GiB, chain72h maximum, zero auto retries.
Persisted progress/results and standalone viewer; interrupted output cannot auto-restart.
8unrelated changes and historical frozen inputs preserved. Engineering test failures
retained and fixed; no real experiment retry. Sparse reference/service-view limits remain.
NEXT: separately authorized LEARN/DEV-feature +9train +DEV +conditional-HOLDOUT chain.
Template execution_authorized=false. Implementation authorization does not start real work.
No new downloads/HPC/undisclosed historical evaluations.

### Historical 2026-09-17: real sample manifests and prospective recipe COMPLETE; no model execution"""
    path.write_bytes(old.replace(anchor,panel.replace('\n',nl),1).encode('utf8'))
    path=docs/'mainline_experiment_map.md';lines=path.read_bytes().decode('utf8').splitlines(keepends=True)
    found=[i for i,x in enumerate(lines) if x.startswith('| Paper priority: original E3/P2 and joint capability 2026-09-17 |')]
    c.require(len(found)==1,'MAP_ANCHOR');i=found[0];nl='\r\n' if lines[i].endswith('\r\n') else '\n'
    lines[i]='| Paper priority: original E3/P2 and joint capability 2026-09-17 | Reference executor IMPLEMENTED;32 synthetic checks PASS;real features/training/scoring ZERO. Frozen sample/R/threshold preserved | legacy_reference_executor_implementation_result_v1_20260917.md / SHA; acceptance/code pins/seals and unauthorized complete-chain template. Next explicit shared features,9endpoints,DEV,conditional one-time HOLDOUT;zero auto retries/downloads/HPC |'+nl
    path.write_bytes(''.join(lines).encode('utf8'))
    c.atomic_json(out/'document_receipt.json',dict(result=str(result.relative_to(c.ROOT)),sha256=c.sha(result),handoff_updated=True,map_updated=True,real_execution_authorized=False))
    print(result)
if __name__=='__main__':main()

