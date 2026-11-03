# 持续输入修复包 v1 审查意见（Claude）

2026-09-28。对象：`legacy_continuous_input_repair_v1_20260928.tar.gz`（SHA `31bdb602…aff`），审查 `validation_install/`。
方法：两路独立只读审查（输入侧 / 训练-CAL-评估侧），阻断项已由 Claude 对照源码与历史回执逐条复核。未修改任何文件。

**结论：不可上传。2 个阻断项（均为合成测试未覆盖的真实数据异常），修复后可上传；核心科学逻辑与设计一致。**

## 阻断项

### B1 `continuous_input_v1.py:180` 捕获级时间倒退直接 STOP，首个捕获即失败

`Contexts.append` 对**任何**帧（含协议/owner 范围外的帧）时间早于前一帧即 `CAPTURE_TIME_REGRESSION` 终止。
旧准备代码只把受影响的键标为 poisoned 并继续。已核实旧回执
`runs/legacy_qref_device_confirmation_delivery_v1_20260923/bundle/runs/legacy_reference_sample_preparation_v1_20260917/capture_receipts.json`：

- active-00：`NEW_TIMESTAMP_REGRESSION: 1`，`POISONED_PREFIX: 346`
- active-01：`NEW_TIMESTAMP_REGRESSION: 2`，`POISONED_PREFIX: 7424`

键内倒退必然意味着捕获内帧序倒退，所以新检查必然触发；两个捕获在 finalized learn/dev 中均有目标，active-00 按排序最先处理，
作业会在 P 开头停止。设计 3.1 写“时间回退停止、不能删行”，与旧数据事实冲突，需要**协议层决定**。

建议：沿用旧语义——检查改为按状态键单调；发生倒退的键按旧规则 poison（不再更新状态/不作为上下文），计数入 provenance；
P 阶段断言新旧计数一致（1/346、2/7424），作为预注册偏差写明。受影响查询的分母处理须与旧 finalized 集合一致，不能静默删行。

### B2 `continuous_input_v1.py:195-196` 残缺头/`cap_len<frame_len` 的已接受上下文行直接 STOP

旧代码将其排除为 `INCOMPLETE_TARGET` 并继续。已核实 Job176975 `enumeration.json`：UNSW 有 14 + 2 行
（`unsw-benign-20180528`、`unsw-mixed-20180601`）。UNSW 排在 302 个源捕获之后，将在 P 进行数小时后失败
（前提是这些行的 owner 在 `external_known_macs` 内，大概率成立）。

建议：与旧代码同义处理并计数，P 断言与旧枚举计数一致（14/2）。

### 永久 gate 建议

两处都是“合成数据干净、真实数据有异常”。建议 P 最前面加一次**只读异常普查**（遍历全部捕获统计时间倒退、残缺头、
owner 歧义等，与既有回执对账），在任何长阶段之前报出，不再依赖长作业中途才发现；并为这两种异常各加一个合成夹具测试。

## 需在提交前决定（不改结果、但影响 decision.json）

**D1 攻击门槛用未加权召回，正常门槛用加权 FPR。** `continuous_evaluate_v1.py:106,111,117` 取 `attack.rate`，
而 `design_contract.evaluation.metric_weights` 称主指标用 `1/label_metric_weight_denominator`。CIC 回归门槛
（79045/79056）本就是未加权，没问题；但 ≥99% 池级、≥97% 设备级/seed 级门槛在 UNSW（三个速率区间长度不等）上
加权与未加权可能落在门槛两侧。Claude 倾向：攻击门槛明确采用未加权行召回（与历史 99% 口径一致），加权值并列报告；
**无论选哪个，都要在提交前写进合同，不能看结果后再定。**

## 次要项（可随 B1/B2 一并修，不单独阻断）

1. `eligible()` 的 `bank.ends[device] < timestamp`（`continuous_runner_v1.py:48-49`）及 LEARN+DEV / UNSW 参考银行的
   `BANK_*` 检查（`continuous_model_v1.py:98-104`）要到 K 阶段（约 60 小时后）才首次执行。建议在 `load_inputs`
   做一次仅元数据的 Bank 构建预演。
2. 过期状态只在状态表满 1M 时回收，tombstone 永不释放（`continuous_input_v1.py:198-208`）。内存上界约 13GB，
   不构成崩溃风险，但与设计 3.1 的“按 60 秒回收”表述不符，记录为偏差即可。
3. `verify_batch`（`continuous_features_v1.py:34-45`）只核对 input_ids/attention_mask；期望 token 与实际 token
   同源于 `headers()`，能抓截断，抓不到头部编码错误。风险低。
4. `zero_vectors.json` 跨 CAL/CIC/UNSW 累计（`continuous_evaluate_v1.py:171`）；CIC 的 rate 区间分组全为 NA（L87）；
   门槛常数硬编码未读合同（L106-119）。均为报告/漂移风险。
5. 12 小时 T+K 预留未测：单次 LEARNED 更新本地约 0.156s，每个 LEARNED 头约 3.8 小时，可在 4 个训练槽并行，预计够用。

## 已核实正确

输入侧：因果（先更新后快照、快照不可变、无未来帧）；近期内容（10ms burst、每 burst 末 6 包、合计最近 12 burst、
60s 丢弃、当前包必留存且不被 tokenizer 截断、TCP≤73 token/≤12 burst）；60 秒生命周期（严格 >60s、SYN/FIN/RST 不重置）；
26 维状态公式与方向/标志位/首包处理；精确形状分桶；标签/角色/攻击区间不进入输入。

训练侧：归一化仅 FIT；FIT/CAL 组件划分与状态命名空间一致无跨角色泄漏；头初始化（768 列逐位相等、26 列为 0）；
W 64×794 无偏置共享；分块安全 L2；损失与分层权重；AdamW/40 epoch/末轮/三 seed/确定性；阈值 tie 与 1% 边界；
cut 覆盖全部 CAL 攻击×合法参考组；最终否决 `base & ~(valid & score>cut)`，无参考保留基础决定；资源估算与单次提交保护。

## 模型规范（“不是大杂烩”）检查

部署主链为 输入 → 冻结 E3 + 26 维状态 → 单一攻击头 → 参考校验 → 报警，职责单一；OLD-MATCHED/RECENT/RAW 为对照臂，
不进入部署。符合要求。另两点科学意见见 `../claude_codex_collaboration_20260928.md` 第 4 节，请一并回应。
