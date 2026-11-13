# 当前状态

1. **正常参考补证首轮**：用户已授权 D／M／C0／C1。本地运行包和输入清单封存，M 的 13,247 条参考 UID 已用真实参考资料独立复算。
2. **运行状态**：未见可复用的超算 SSH 通道，未核实本批远端作业或资产存在性，未取得新提交回执。真实计算节点小切片、D 及 M/C0/C1 评价尚未执行。
3. **接续入口**：[本地接续](../reference_evidence_round1_v1_20261112/LOCAL_HANDOFF.md) · [进度](http://127.0.0.1:18807/)。接通后先查目录、squeue/sacct 和资产 SHA，已有作业优先续接；通过真实门后生成 D，后继按实测资源自动提交。
4. **论文主结果**：完整库 MLP p4 仍是主结果；[p4 与 TabM 已验收回传](paper_writing_v1/experiment_results_p4_and_tabm_codex_20261112.md) 可用。C0/C1 待验证，不能写作压缩已完成。
5. **工作边界**：用户手动连接；正常提交且进度页可用就结束当轮。结果取回后以本批 received/RESULTS_FOR_PAPER.md 和 FINAL_ACCEPTANCE.json 供论文对话读取。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
