# 论文贡献段中文草稿

本文围绕 benign-OOD drift 下的低告警少样本入侵检测适配展开研究。第一，本文将开放部署中的 IDS 适配问题重新表述为一个受 OOD benign 告警预算约束的少样本攻击检测问题，强调 ordinary AUC 与低告警工作点性能之间的差异。第二，本文提出增强型低告警守卫适配（Enhanced LOW-GUARD+），通过 OOD 安全的 source-rich 特征选择、kcenter confirmed attack support coreset 和 guarded few-shot adapter，在少量攻击证据下学习攻击导向且 OOD 安全的评分函数。第三，本文给出系统性证据链：top64 表示修复 top32 的 OOD 超预算问题，在 primary 与 harder-shift settings 上保持低告警，并在 locked bins 上获得 moderate positive validation；同时，复杂 adapter、fusion、routing/promotion 的负结果被保留为方法边界，说明当前主收益来自 representation selection 与 low-alert guard，而非模型复杂度堆叠。
