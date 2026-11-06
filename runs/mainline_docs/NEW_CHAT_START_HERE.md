# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **分层小试已启动**：作业182589, 182590，快照TRAIN_PREFLIGHT_RUNNING；1CPU/8GiB，30＋30＋60分钟总上限2小时，尚未科学验收。
2. **固定改动**：源FIT按设备/活动/协议配额，组内原权重有放回抽样，样本位损失权重Wg/ng；每类8192位，独立UID另报。三种子各5轮320更新，原损失/阈值/优化器保持。
3. **科学对照/门**：复用封存均匀小试固定第5轮；起点/上界/阈值核验。保持正常误报不增、攻击尾部/召回/8维贡献保护及集成CAL加权误报相对降10%的全部原门，不选种子轮次。
4. **自动工程门**：52项远端依赖PASS；本地10＋8＋4项回归PASS。真实旧工程→真实训练8批/保存重读/源评价/预算→小试；失败停止，不自动全量或外部评价。
5. **证据/边界**：[执行卡](collab/20261106_source_stratified_pilot_design_codex.md)、[启动回执](collab/20261106_source_stratified_pilot_launch_codex.md)；CAL仅开发核验，不参与选样本；大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
