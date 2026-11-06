# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **已知结果**：四组评价工程通过，融合C5 Edge样本UDP98.66%、HTTP94.995%、正常FPR5.79%；A/B RAW误报退化和Edge C5安全门失败，不能宣称修复完成。
2. **当前任务**：用户要求检查768维隐式特征是否真正使用，同时排查误报与种子127失稳。representation_usage_diagnosis_v2 预检 182478，当前 PREFLIGHT_RUNNING，通过后自动完整诊断。
3. **方法**：冻结四组/三种子/集成；输入拼接、分块零参考消融/Shapley、同协议UID置换、分数×阈值×尺度对照、正常误报分组。无训练、无阈值拟合、无择优。
4. **工程证据**：v1作业182469因远端缺少本地生成验收回执4秒失败，有效计算0秒；v2随包交付回执修复。见 [执行回执](collab/20261105_representation_usage_diagnosis_launch_codex.md)。1CPU/8GiB，预检30分钟、完整诊断2小时上限。
5. **接续/存储**：先确认真实预检与完整诊断，再区分“正确输入”“有功能依赖”“帮助分类”；零化/置换可能离分布。大数组/模型留超算，小摘要自动回本地；[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
