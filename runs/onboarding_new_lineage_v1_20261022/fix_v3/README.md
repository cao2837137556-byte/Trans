# 2026-10-22 固定查询中的观察期重放：评价校验修复

v2 已完成两个正常捕获的完整解码、B0/B1/B2 六组真实参考 E3，以及评价前的头回放。其最后一步在 `REFERENCE_QUERY_UID_OVERLAP` 停止，尚未输出完整系统指标。前面的成果均可复用。

## 原因与边界

原协议要求：固定全量查询保留；在整库截止之前的查询仅使用基础头，不允许追溯修正。同时，参考生成器从固定正常捕获的完整候选中选窗内代表端点。由于固定报告还包含早期查询，同一物理端点可能既是观察期内的历史查询，又成为窗口关闭后供未来查询使用的参考。

旧 runner 和 ReferenceBank 在时间判断之前一概禁止 UID 重叠，与上述全量早期查询回退口径冲突。不是坏缓存或重复上传，也不能通过换 UID、删查询、降低分母、忽略校验来解决。

真实元数据盘点 `../overlap_audit_v3.json`：CIC B0/B1 各 63 个、B2 64 个重叠；UNSW B0/B1 为 0、B2 为 19。全部来自相同池、相同正常物理端点，source SHA/frame/owner/component/session/capture/device/partition/protocol/time 均一致，且时间与帧均处于该库截止前。该事实是审计，不是按标签或误报效果挑选参考。

## v3 修复

新增版本化 `constrained_onboarding_core_v3.py`、`constrained_onboarding_runner_v3.py` 和 `causal_reference_overlap_v1.py`；原封存 v2 包不动。共享源码同时保存在 repo/ood，后续现代头接入应使用这一修正版评价路径。

- 仅 B0/B1/B2 的目标正常观察期重放允许经完整身份检查进入报告；OLD_BANK、源 FIT/CAL 和源参考仍要求 UID 互斥。
- 同 UID 元数据不一致、跨池、源角色、晚于整库截止等情况继续报错。
- 时间/帧因果规则、参考库选择、半径/尺度/lambda、头权重与阈值均不变。重叠早期行仍在原查询位置和分母中，强制 support=0、eligible=false、无参考匹配、最终原判定不变。
- 不改 UID 或查询角色，不删早期样本，不按效果重选参考。新增 `prebank_history_audit.json` 公开每个历史重放 UID 和截止边界。

97 项测试通过。新增测试覆盖：旧实现对重叠的报错复现、早期重放原分数/决定精确保持、后续查询与旧计算一致、伪身份/跨池/源混用/未来重放拒绝、完整小型流水线原分母保持，以及无重叠时全部分数/决定和源校准文件逐字节不变。验证摘要绑定 package_v3 的代码清单。

## 接续与验收

对 v2 已完成的 raw 和六库共 92 个文件逐项封存、核验并复制到新的 v3 输出，输入清单 `../src/resume_inputs_v3.json` SHA `03f64b8c…5b437`。旧失败状态及完整旧输出保留。本次仅执行 `evaluate`，不再解码或生成参考 E3，也不重建查询前端。

unit：`paper04-onboarding-20261022-v3`；8核/16GiB、零自动重试、无自动停机。软件 `/srv/paper04/onboarding_new_lineage_20261022_v3`；run/state/export 分别位于各自父目录下的同名v3目录。18764 页面由 `track_onboarding_v3.py` 每60秒同步，结果备份独立写入 `pullback_v3/`、`final_state_v3/`、`RESULT_BACKUP_VERIFIED_v3.json`。

完整系统仍须检查每个 seed 与集成的新增漏检；三设备回归及独立确认未补齐，不将两池开发结果称为全部验收 PASS。

正式接续已越过原失败点：全量源校准完成，CIC/B0 的 scores、decisions、reports 已生成，仍保留179,886条固定查询；三个seed和集成的新增漏检均为0。其余策略/池继续执行，尚未作完整效果结论。真实历史重放审计及92文件复用回执已保存本目录。
