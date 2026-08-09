# CKBY DROCC seed-27 结果：Codex 回归审查

- 日期：2026-08-09
- 审查对象：`ckby_drocc_seed27_result_20260809.md`
- 背景交叉核对：`ckbw_next_iteration_briefing_20260807.md`、
  `ckbw_tail_margin_dual_control_preregistered_20260803.md`
- 审查边界：本轮只做三份文档间的一致性与科学声称边界审查；未重新读取原始
  CSV/JSON、训练轨迹或逐行预测工件，因此不把本结论表述为独立工件复算。

## 裁决

**PASS（科学裁决与后续路由成立；有两条非阻塞措辞保留意见）。**

## 1. 数据边界：PASS

- 结果文档钉住 FROZEN 预注册 SHA-256、勘误、特征快照与模型权重哈希；briefing
  round 9--11 对冻结、勘误、快照合同和执行链给出一致记录。
- checkpoint 与阈值在 report 池打开前冻结，report 只评估一次；`support_val 69`
  仅报告，不进入训练、阈值或 checkpoint 选择。
- `cooler-motor` 与 seed 37/47 未触碰，符合当前 FINAL 边界。
- 文档中未发现 held/report 反馈选择、事后晋升、family/source 专用阈值或 family
  补丁。

## 2. 同分母对照：PASS

- 表内攻击指标统一为 `future_query = 131,391` 行；OOD 指标统一为四池
  `18,000` 行的 family macro。
- C1 `86.83/93.09`、FrozenCKBQ `74.20/35.27`、CKBW M7
  `63.19/0.15` 与 briefing 已纠正后的 future-only 口径一致；没有把 CKBW 的
  all-role `attack_overall` 与 future-only 召回混用。
- CKBY OP-1 `9.04/55.57` 和 OP-0.1 `5.52/47.63` 在这两个轴上均被
  FrozenCKBQ 严格支配，因此“不存在同表 trade-off 优势点”成立。
- 结果文档第 3 节的 `future+same_file+sealed_final` 16-family GLOBAL 统计已明确标为
  分族诊断，没有冒充第 2 节的 future-only 同分母指标。

## 3. 封口结论：PASS（有界成立）

Gate A 的两个预注册条件同时大幅失败：OOD macro `55.57% > 30.27%`，future
召回 `9.04% < 84.83%`；副压力点也失败。按 briefing round 8--11 已冻结的路由，
这足以封死“现有冻结 51D 表示上只是模型容量不够”这一剩余替代解释，并停止继续
更换记录级学习器。

该封口没有越界：结果文档明确不声称“所有记录级表示均不可能”，并保留预训练流量
表征等储备路线。因此下一步进入 Episode Design Review 合理；当前不冻结方案、不写
代码、不触碰 FINAL、不提交 HPC。

## 4. 两条非阻塞措辞保留意见

1. 结果文档第 4 节“对抗阶段在原则上不可能被选中”应只按本次冻结配置解释：在本次
   训练轨迹和“最低 benign 验证 CE”规则下，所有对抗阶段 checkpoint 均输给 epoch 49。
   这不是对所有 DROCC 配置或所有 benign-only checkpoint 准则的一般数学不可能性。
2. “DROCC 是迄今所有记录级方法中最差”在后续引用时宜收紧为“在本轮列出的冻结、
   同分母记录级对照中最差”。本次表内支配关系充分成立，但不应扩成未列出方法的
   普遍排序。

以上两点不改变 Gate A FAIL、容量替代解释封口或 Episode Design Review 路由。
