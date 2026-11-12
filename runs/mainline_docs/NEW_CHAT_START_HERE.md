# 当前状态

1. **本轮提交**：TabM＋3D迁移作业183549，初始PENDING；RTX4090/8CPU/16GiB/2小时，20依赖通过，尚不宣称真实RAW门或结果通过。
2. **固定五行**：MLP RAW、MLP＋3D自身尺度、TabM RAW、TabM＋3D自身尺度、冻结完整系统。p=3、λ=.25、SYN保护开，不晋升、不调指数、不重训。
3. **源侧门**：TabM完整FIT补前向，原分层权重两类各半算Q90−Q10；独立源正常CAL阈值，原生RAW完整回算和指标复现后才参考修正。负分保留，不套MLP logit尺度。
4. **已完成材料**：上一批保护/指数消融已验收并回传论文，不重跑；六基线作业完成，统一科学验收另做。
5. **接续**：tabm_3d_transfer_v1_20261111，客户端44692/接收18882/页面18806。见[执行回执](collab/20261111_tabm_3d_transfer_launch_codex.md)，完成后取received结果验收回传，不持续轮询。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
