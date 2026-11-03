# 阶段条件校准 v1：代码实现与验收回执

2026-10-28。用户授权“按照方案，完成代码实现”并要求继续。本回执是最新实现状态；[原规格](20261028_phase_conditioned_calibration_plan_v1_codex.md)及原 PLAN/REVIEW 保留方案快照，不改写历史状态。

## 1. 已交付

独立目录：[实现说明](../../phase_conditioned_calibration_v1_20261028/README.md)、[执行卡](../../phase_conditioned_calibration_v1_20261028/EXECUTION_CARD.md)、[机器回执](../../phase_conditioned_calibration_v1_20261028/IMPLEMENTATION_RECEIPT.json)。

- 精确候选与严格 `>` 的 Q0/QG/QP；按元数据定支持等级；无证据阶段冻结、LOW_SUPPORT 仅 CAL 零原 TP 撤回；分组与临界预算使用整数层级分母的有理数核验。
- 源侧 P1：BASE 两折保存分数绑定、独立原 cut 和集成算术、48 报告、预登记推进门。科学 FAIL 仍完成对照，不能自动转向另一算法。
- 密源 P2：own 全 CAL 分数与 12 donor/raw fallback 安全场景分开，原 104/分数/判定/eligible SHA 与历史并集/正常质量复现门；密源与 RAW 各自源 CAL，错误留证不放宽、不重试。
- 目标 P3：D0/DG/DP/RAW-P/WRONG-P 五臂，80 报告，WRONG 严格复用 DP cut；原 BASE TP 撤回不被旧 FN 恢复抵扣。观察期后重建原层级，全量并列。D0 逐视图先验旧结果身份、样本、权重和指标。
- 单阶段 CLI 默认只读 check；P2 必须前序 P1 PASS，P3 必须 P2 PASS，代码和产物 SHA 同时封存；没有自动串阶段/远端提交。普通进度页能区分技术完成、科研 FAIL、异常、进程消失、状态停更及损坏，无 AI 轮询。

## 2. 验收证据

1. **63/63 合成与回归测试通过**，包括独立穷举阈值 oracle、float32/float64 前驱、完整 ties、双向四类变化、预算临界点、稀疏支持 CAL/HELD 区别、annotation_id 保护、重复 donor/无 eligible fallback 风险、原 104 字节反例、48/80 报告端到端合成流程、失败留证与进度终态。测试日志：[unit_tests_20261028.log](../../phase_conditioned_calibration_v1_20261028/validation/unit_tests_20261028.log)。沙箱临时目录原子重命名受 Windows 限制，最终完整测试使用已批准的本地测试命令复验。
2. **真实源 Q0 身份预检 PASS**：2 折×4 suffix×CAL/HELD 共 16 份旧报告复现，原 cut 和计数精确；旧 BLAS 与 fsum 的固定 1e-12 历史数值累加审计仅用于复现，不用于科学护栏。最终 check 21.469 秒，进程树峰值 840,876,032 字节，输出约18.6KB。见[最终预检回执](../../phase_conditioned_calibration_v1_20261028/outputs/final_preflight_20261028/STAGE_RECEIPT.json)。
3. **P2 26 项输入与 6 个冻结算术依赖通过只读预检**；包括原输入 seal、所有读取依赖及历史 lazy overlap 模块。见[P2 输入预检](../../phase_conditioned_calibration_v1_20261028/validation/P2_INPUT_PREFLIGHT.json)。未计算真实距离，因此不能声称三个重建 SHA 已在本包重新通过。
4. **179700 旧 D0 精确复现 PASS**：两池×双视图×4 suffix 共16指标报告，UID/权重 SHA、计数、加权 FPR/召回逐项一致，39秒。见[D0 身份审计](../../phase_conditioned_calibration_v1_20261028/validation/D0_IDENTITY_AUDIT.json)。只复核旧冻结点，没有新目标候选或阈值选择。

独立审阅发现并修复了 annotation_id 分组遗漏、输入清单信任链、src 导入、Windows STATUS/status 大小写冲突、P1→P2 规格字段绑定、进度损坏/失联显示及终态资源检查。14 个 Python 文件语法检查通过。

## 3. 当前边界与下一步

本轮真实数据新阈值选择/校准、距离计算、前向、编码、训练、云端作业均为0。P1/P2/P3 正式新实验尚未运行，**没有新的 A/B 误报率和召回结果**；旧179700结论不变。P2 的旧数值 SHA 门必须在真实重建时精确通过，当前 NumPy2.2.6 与历史2.0.1环境差异不能靠容差跳过。

下一步是单独执行 P1，获得“阶段 QP 是否比同回退共享 QG 有可迁移增益”的源侧结果。P1若 FAIL，按具体原因收尾，不启动 P2；通过后才单独进入密源重建与组合 CAL，再准备冻结目标评价。此前 A 的参考特异性失败、无 B2-P、第三池缺失及开发评价不能替代独立确认等限制保留。
