# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **本轮结束**：182554/182555/182556全部COMPLETED/0:0；真实预检及A/B/Edge工程PASS，科学FAIL；累计5:01，峰值1.691GiB，无新作业。
2. **关键结果**：新ANCHOR790集成Edge C5正常误报5.79%→0.58%，但UDP98.66%→0%，HTTP94.995%→46.51%；127误报5047→116，收益未保住。
3. **定位边界**：UDP在RAW已全低于阈值、C5扣分0；HTTP裕量缩小并撤警6467条。旧四组全量判定复现，新头身份通过；支持锚定牺牲收益的假设，尚未证明8维贡献机制。
4. **保留与下一步**：不采用ANCHOR790替代；保留原FUSION790/OLD782。建议现有头8维贡献干预＋源FIT梯度冲突诊断，再定新目标，不直接调λ或挑种子/轮次。原A/B门和Edge安全门FAIL保留。
5. **证据与存储**：[验收报告](collab/20261105_fusion_anchor_evaluation_acceptance_codex.md)，`runs/fusion_anchor_evaluation_v1_20261105/FINAL_EVALUATION_ACCEPTANCE.json`；全五组/全部种子有据，大数组留超算，[进度/验收页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
