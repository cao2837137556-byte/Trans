# 当前状态

1. **本批范围**：最终3D的SYN保护开关、p=1/2/3/4，共五配置；固定主模型/库/尺度/λ/阈值/UID，不扩展其他消融。
2. **当前执行**：183530运行真实缓存核验，1CPU8GiB1小时；三池BASE全部通过后先保护、后指数。未提前宣称消融验收。
3. **工程记录**：独立v2快照解决四份来源JSON的缺失/格式差异，旧文件不覆盖；183529因缺/usr/bin/time于1秒失败，183530改用Python+Slurm记账，科学计算未改。
4. **已有基线**：本次在线核对六方法均COMPLETE；不重跑，本轮未开展其正式科学验收。
5. **接续**：paper_reading_ablations_v2_20261111计算；paper_reading_ablations_deploy_v1_20261111交付/received；客户端47644、18881接收、18806页面。见[提交回执](collab/20261111_paper_reading_ablations_submission_codex.md)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md)
