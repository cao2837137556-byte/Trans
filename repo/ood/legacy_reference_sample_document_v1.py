# -*- coding: utf-8 -*-
"""Document the verified sample preparation without inventing scientific scores."""
from pathlib import Path
import time
import legacy_reference_sample_prepare_v1 as p

ROOT=p.ROOT
RUN=ROOT/'runs/legacy_reference_sample_preparation_v1_20260917'
DOCS=ROOT/'runs/mainline_docs'


def sealed_write(path,content):
    if path.exists():raise RuntimeError('Refuse overwrite: '+str(path))
    path.write_text(content,encoding='utf8')
    path.with_suffix('.sha256').write_text(p.old.sha(path)+'  '+path.name+'\n',encoding='utf8')


def main():
    v=p.load(RUN/'independent_verification.json')
    if v['status']!='PASS':raise RuntimeError('Independent verification is required')
    f=RUN/'finalized';s=p.load(f/'denominators.json');recipe=p.load(f/'recipe.json');idx=p.load(f/'manifest_index.json')
    costs=p.load(f/'reference_costs.json');interventions=p.load(f/'reference_interventions.json')
    excluded=p.load(f/'excluded_capture_modes.json');captures=p.load(RUN/'capture_catalog.json')
    receipt=p.load(RUN/'capture_receipts.json');status=p.load(RUN/'status.json')
    role_lines=[]
    for role,label in [('LEARN','学习'),('DEV','开发判断'),('DEVICE_HOLDOUT','保留设备确认')]:
        rows=[x for x in s['devices'] if x['partition']==role]
        role_lines.append('| %s | %d | %s | %s | %s |' % (label,len(rows),format(sum(x['normal'] for x in rows),','),format(sum(x['attack'] for x in rows),','),format(idx[role]['rows'],',')))
    device_lines=['| %s | %s | %s | %s | %d | %d | %s |' %
        (d['device'],d['partition'],format(d['normal'],','),format(d['attack'],','),d['references'],d['normal_active_dates'],format(d['reference_shared_component_queries'],',')) for d in s['devices']]
    controls='；'.join('%s→%s：%d 条等数量/协议参考' % (x['device'],x['donor'],x['equal_count']) if x['status']=='DEFINED' else x['device']+'：无同协议覆盖的合法供体，本项记缺失' for x in interventions)
    source_packet_count=sum(c['expected_packets'] for c in captures if not c['skip_reason'])
    document='''# 正常参考机制：真实样本与完整开发配方准备结果

日期：2026-09-17。**本次准备完成，身份、标签、参考与查询 UID、权重、训练配方和执行边界已封存；没有生成真实 E3 特征、模型分数或训练结果。**

当前工作目录与分支为 kitnet-exp-mainline / codex/exp-mainline，HEAD 4b28747b09480471e2bac1beb3a9badf27280efb。原有 8 个无关修改哈希保持不变，旧 R、阈值和历史结果未改。

## 1. 真正可用的样本

本次从已核验的 302 个捕获条目建立新作用域清单：287 个进行此次 UID 物化，15 个没有当前 HTTP 请求证据的攻击目录捕获按预先标签规则排除。复用旧资格证据与源身份，新做所需的 UID/因果范围索引；没有重跑旧模型实验。实际新索引覆盖 {decoded_packets:,} 条原始记录。

| 用途 | 设备数 | 正常查询 | 攻击查询 | 合计 |
| --- | ---: | ---: | ---: | ---: |
{roles}

另外封存 **{refs:,} 条参考表示的目标位置**，供相同设备的 M/C 共用。未来最多需要生成 {features:,} 个 E3 向量，纯 float32 向量载荷约 {feature_gib:.3f} GiB；这不是全部运行内存。没有新阈值拟合集，校准行数为 0：沿用原概率阈值 0.065159872174263，DEV 只作固定终点的开发判断。

| 设备 | 用途 | 正常查询 | 攻击查询 | 实际参考数 | Active 日期数 | 与参考同规范连接的查询 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{devices}

表中查询是冻结抽样后的真实 UID 数，**不是全量包数，也不是独立观测次数**。每个捕获内、每个设备的旧规范双向连接最多取 32 个均匀候选序位，保留首尾；所有合格连接均参与。使用完整合格因果前缀，不因目标抽样丢掉未选中的合法历史包。冻结前按“相同捕获字节及同微秒”保守排除 {duplicates:,} 个重复查询观测，排除清单可追溯；不同时间的相同字节不自动视为泄漏。

真实 owner/DHCP 规则下，七天 Active 候选总量是 {active:,}，此前仅估计 DHCP 排除后的数量是 1,788,610；本次两者一致性为 {match}。这些候选仍未全部成为优化器或评估目标。

数量判断：本轮已从两摄像头短片段扩展到 11 设备和七日正常观察，可以启动有限开发检验；不声称覆盖全部正常模式或满足独立 1% 风险认证。长连接设备即使包数很多，独立变化仍有限；Ring 的实际参考只有 1 条，Atomi/Globe 各只有 2 条，不填充复制。设备、捕获、活动、长期连接的相关性必须随结果一起报告。

## 2. 标签、参考和防泄漏怎样执行

正常只取具有独立正常来源依据、属于目标物理设备且满足原输入条件的包。训练和检测查询均限定旧前端支持范围，范围外默认报警不能算作学到的攻击检出。LOIC 只取已核查攻击源 MAC/IP → 受害设备本地 80 端口的对应 UDP 数据、TCP 数据/SYN 或当前 HTTP 请求；Hydra 沿用当前入站 554/DESCRIBE 且具有认证请求行的规则。响应、背景、无语义证据的 HTTP 目录包和 Nmap 混合文件不补标正常或攻击。15 个排除捕获不是“没有攻击”的结论，而是当前 HTTP 正例标签依据不足。

上下文在每次 append 前执行 owner/capture/原规范连接隔离，双向共享 DHCP 排除。只看查询当前及以前捕获位置；同连接时间倒退持久失效，不能排序或悄悄跳过来恢复。MAC、角色、文件名、日期、标签与整文件统计不进入新模型。未来特征适配器与此次索引共享同一规则，目标快照深拷贝，已用旧数值转换器和合成流验证。

参考使用每台设备最早三个正常捕获，只在这些观测里按规范连接依赖组保留一个末端合法目标，再按固定 hash 顺序取最多 64 个。参考观察区间严格早于查询，held-out 参考不拟合模型、标准化或阈值。记录完整观察字节、时长、活动与实际参考数。

对旧提案作了一项明确的前瞻性澄清：**捕获结束不等于 TCP/UDP 真实连接已经结束。** 不伪造会话关闭；跨日期相同规范键按保守依赖组单列。因果合法的持续连接查询可以保留，但它与新连接查询分项报告，不声称独立会话。这不改变任何历史样本规则或分母。

## 3. 一次比较具体固定了什么

R 为原 E3/P2；Q 仅用查询学习修正；M 使用相同参考的均值与总体标准差作普通条件学习；C 学查询与每条参考的关系。新头参数分别为 14,385 / 38,961 / 27,201，不宣称等参数量。R/E3/原标准化全部冻结，各残差末层零初始化。

Q/M/C 使用完全相同的 LEARN UID、标签、批次次序与权重，M/C 参考预算相同。设备、正常/攻击各半，然后活动/攻击模式、捕获、规范连接和目标分层等权；不让一个洪泛长流的包数主导损失。固定 AdamW、lr=3e-4、weight_decay=1e-4、40 epochs、batch256、seeds27/127/227：每模型 {updates:,} 次更新，共 9 个预定模型，全部报告，不选最好 seed。主分数是各臂三 seed 末轮 logit 的均值，禁止中途按 DEV 选轮次。

当前冻结的是有限目标抽样比较，不再沿用旧未冻结提案里可能让数千万包全部评分的含混预算。主表同时列原始错误数/抽样分母和分层指标，不能将抽样率写成全部捕获的逐包率。

两个 DEV 设备上，只有 M 或 C 达到正常宏平均误报下降、各设备正常不恶化，且各设备/可用攻击模式检出率相对 R 的下降不超过 1 个百分点，才有条件打开三台保留设备一次。它只是开发进入条件，不是统计非劣证明或论文达标。若打开，R/Q/M/C、所有 seed 和事先规定的干预都报告，不根据保留结果重新调参。

C 还必须与同信息 M 比较，配合查询不变、参考等数量且 TCP/UDP 组成一致的错配干预；否则不能把更复杂网络称为机制创新。固定干预：{controls}。另报最多16条正确参考的减量诊断，实际不足16则注明不构成预算变化，不挑最好干预。

三类核心成绩仍是 ID 误报、攻击检出与 OOD/入网正常误报。旧 ID 的 0/2,378（248 会话）作为**已披露、原回退路径不变的历史锚点**清楚标记；本阶段没有新做 ID 评分，不能把该值写成新实验独立测试。无合法设备参考的旧 hydraulic/predictive 等问题不会由此次方法自动解决，也不能用旧攻击大池掩盖新设备内漏检。

## 4. 工程验收、资源与边界

18 项合成检查通过；参考对照按协议数量匹配的补充审查及对应 7 项套件通过。真实独立回读核对了 UID、来源、设备角色、标签、时间、权重、参考成本/干预和清单 SHA。实际 E3 前向尚未运行，因此这些是准备阶段的工程验收，不是模型能力提升。

后续完整执行范围为：执行器接入与端到端合成验收 → 一份 LEARN/DEV 特征缓存供各臂复用 → 固定九模型训练 → DEV 决策 → 若满足条件，保留设备一次性特征/评估 → 全部封存。训练执行器、真实 tokenizer/collator 链和监督器还需按 recipe 的 acceptance 项接入验收，不能把本阶段可复用的输入适配器叫成整条训练链已完成。

未来 recipe 预算：本地 CPU 4 线程、模型进程 1 个、E3 batch16、进程树内存上限12GiB、新输出16GiB、完整链72小时上限；这是资源上限，不是预计用时。无需重复资源试验，获授权后可从真实准备进度估计剩余时间。任何身份/标签/因果/数值/进程/资源异常停止，零自动重试，禁止静默删行。当前没有真实特征、训练、评分、下载或 HPC 授权。

当前权限来自用户“可以，动手下一步”，覆盖这次具体样本/配方准备。旧阶段的真实训练授权不自动扩展到本次新机制。

## 5. 入口与可追溯产物

- `runs/legacy_reference_sample_preparation_v1_20260917/finalized/`：四份 UID 清单、精确分母、参考成本/对照、排除表、recipe、verification 和 SHA256SUMS。
- 同 run 的 `independent_verification.json`、`synthetic_acceptance.json`、`control_refinement_acceptance.json`：独立验收。
- 同 run 的 `captures/`：每捕获身份、候选统计、目标序位、规范连接和上下文拒绝原因。
- `scripts/show_legacy_reference_sample_preparation_v1.ps1`，可加 `-Watch`；有限本地收尾脚本不依赖 LLM 轮询，且不启动模型。
- `legacy_reference_development_recipe_v1_20260917.json` / SHA 是 mainline_docs 中相同字节的配方副本。

服务/采集视角缺口继续限制结论：Philips 局部本地 HTTP 对照不代表所有设备已排除服务捷径；正常网关与攻击机器视角不等价证明仍缺失。LOIC 多个协议选项不等于多个全新攻击机制，也不声称已实现任意攻击/OOD 泛化或在线同网同时攻击的因果验证。三台保留设备是相对本轮条件学习的保留；已做原始元数据资格审查，且 E3 外部预训练的完整排重尚未证明，不能称为整个项目从未接触的 FINAL。

solved: 合法参考/查询 UID、三种设备用途、精确权重分母与有限开发配方已物化并封存。
changed_mainline: SAMPLE_AND_RECIPE_PREPARATION_COMPLETE；没有科学成绩。
active_blocker: 完整训练执行器与端到端合成验收尚未接入，真实特征/训练/一次性评估尚未授权。
frozen: 本次新清单/配方已冻结；旧 R/阈值/历史结果及原有修改保留。
next_action: 按这份完整 recipe 接入执行链及验收，随后在明确整体执行授权下一次运行；不再泛泛补数据或重开方案。
'''.format(decoded_packets=source_packet_count,roles='\n'.join(role_lines),refs=s['reference_rows'],features=s['feature_rows'],
        feature_gib=recipe['runtime']['float32_embedding_payload_bytes']/2**30,devices='\n'.join(device_lines),duplicates=s['removed_duplicate_observations'],
        active=v['guarded_active_candidates'],match=str(v['estimate_matches_actual']),updates=recipe['optimization']['updates_per_model'],controls=controls)
    recovery_path=RUN/'recovery_powerloss_v1/recovery_record.json'
    if recovery_path.exists():
        recovery=p.load(recovery_path)
        if recovery['status']!='VERIFIED_RESUME_FINALIZATION_ONLY':
            raise RuntimeError('Unverified power-loss recovery')
        document+='''
## 6. 本次断电恢复

用户明确要求断电后继续。恢复时 302 份捕获回执与逐文件回执一致，287 个已索引捕获的压缩 CRC/JSON 完整回读通过，汇总前 1,288,330 条目标完整，原始输入/代码 pins 一致。根状态文件为 304 字节全零，原汇总目录为空；两者已保存到 `recovery_powerloss_v1/`，没有把损坏状态当作成功证据。

本次仅恢复状态并完成汇总、独立核验和文档封存，没有重扫捕获、重做模型实验或自动重试。`recovery_powerloss_v1/PRE_RECOVERY_SHA256SUMS` 固定恢复前产物；根目录 `closeout_verification.json` 与 `SHA256SUMS` 记录最终保全核对与封存范围。
'''
    result=DOCS/'legacy_reference_sample_preparation_result_v1_20260917.md'
    sealed_write(result,document)
    copy=DOCS/'legacy_reference_development_recipe_v1_20260917.json'
    if copy.exists():raise RuntimeError('Refuse overwrite frozen recipe')
    copy.write_bytes((f/'recipe.json').read_bytes());copy.with_suffix('.sha256').write_text(p.old.sha(copy)+'  '+copy.name+'\n',encoding='utf8')
    prior=RUN/'living_docs_before';prior.mkdir(exist_ok=False)
    for name in ('mainline_handoff.md','mainline_experiment_map.md'):
        (prior/name).write_bytes((DOCS/name).read_bytes())
    handoff=DOCS/'mainline_handoff.md';text=handoff.read_bytes().decode('utf8');nl='\r\n' if '\r\n' in text else '\n'
    anchor='### 2026-09-17 latest: seven-day normal supplement COMPLETE; prospective scope implemented'
    if text.count(anchor)!=1:raise RuntimeError('Handoff anchor changed; preserve and review')
    new='''### 2026-09-17 latest: real sample manifests and prospective recipe COMPLETE; no model execution

Read `legacy_reference_sample_preparation_result_v1_20260917.md` / SHA and
`legacy_reference_development_recipe_v1_20260917.json` / SHA; run sample_preparation_v1 has
finalized UID manifests/denominators/reference controls/seals and independent_verification.
LEARN={learn:,}, DEV={dev:,}, DEVICE_HOLDOUT={hold:,} query rows; references={ref:,}.
All legal canonical capture sessions retained with max32 systematic targets; exact duplicate
observations removed prospectively. Not full-packet rates or independent sample counts.
Guard applied before every append. Old encoder/R/threshold untouched; zero features/scores/training.
18 synthetic cases PASS plus strengthened protocol-matched reference-control suite7 PASS;
independent UID/time/label/weight/resource readback PASS. 8unrelated files unchanged.

Reference observations strictly earlier; do NOT claim capture end proves connection closure.
Same-canonical ongoing-connection queries tagged separately. Ring1actual reference, Atomi/Globe2each,
not padded. Reference interventions equal counts AND TCP/UDP composition, unavailable controls NA.
Freeze Q/M/C40epochs,3seeds each, original threshold, matched queries/weights; DEV gate precedes
one conditional heldout check. R/old ID0/2378 is disclosed unchanged fallback anchor, not a new test.
Service/view limits remain; no science PASS, no automatic downloads/HPC or undisclosed evaluation.
NEXT: integrate full executor and end-to-end synthetic acceptance from this exact recipe, then
one explicitly authorized feature/train/DEV/conditional-HOLDOUT chain. Current authorization
completed sample/recipe preparation ONLY; no further generic data expansion or automatic training.

### Historical 2026-09-17: seven-day normal supplement COMPLETE; prospective scope implemented'''.format(
        learn=idx['LEARN']['rows'],dev=idx['DEV']['rows'],hold=idx['DEVICE_HOLDOUT']['rows'],ref=s['reference_rows'])
    handoff.write_bytes(text.replace(anchor,new.replace('\n',nl),1).encode('utf8'))
    map_path=DOCS/'mainline_experiment_map.md';text=map_path.read_bytes().decode('utf8')
    old_lines=text.splitlines(keepends=True);matches=[i for i,line in enumerate(old_lines) if line.startswith('| Paper priority: original E3/P2 and joint capability 2026-09-17 |')]
    if len(matches)!=1:raise RuntimeError('Map anchor changed; preserve and review')
    i=matches[0];ending='\r\n' if old_lines[i].endswith('\r\n') else '\n'
    old_lines[i]='| Paper priority: original E3/P2 and joint capability 2026-09-17 | Real sample/recipe preparation COMPLETE: LEARN{:,}/DEV{:,}/HOLDOUT{:,}queries,{}reference targets; owner/capture/causal isolation, labels and UID seals independently verified. No real features/scores/training | `legacy_reference_sample_preparation_result_v1_20260917.md` / SHA and `legacy_reference_development_recipe_v1_20260917.json` / SHA. Fixed R/Q/M/C, original threshold,40epochs/3seeds, conditional heldout gate. Next executor integration/end-to-end synthetic acceptance, then explicit complete execution authority. No generic data expansion/HPC; old R/rules and8unrelated edits preserved |'.format(idx['LEARN']['rows'],idx['DEV']['rows'],idx['DEVICE_HOLDOUT']['rows'],s['reference_rows'])+ending
    map_path.write_bytes(''.join(old_lines).encode('utf8'))
    p.dump(RUN/'document_receipt.json',dict(result=str(result.relative_to(ROOT)),result_sha256=p.old.sha(result),recipe=str(copy.relative_to(ROOT)),recipe_sha256=p.old.sha(copy),
        handoff_updated=True,map_updated=True,training=False,completed_epoch=time.time()))
    print(result)


if __name__=='__main__':main()
