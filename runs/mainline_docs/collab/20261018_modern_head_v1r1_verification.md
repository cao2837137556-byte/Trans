# 现代检测头 v1r1 复核确认

日期：2026-10-18
复核对象：`runs/modern_head_comparison_v1r1_20261018`
原复核：[20261018_modern_head_v1_code_review.md](20261018_modern_head_v1_code_review.md)
Codex 回应：[20261018_modern_head_v1_code_review_response_codex.md](20261018_modern_head_v1_code_review_response_codex.md)

复核方式：只读核对归档、安装包、源码、验证日志与关键测试；未改代码、未重跑全量测试、未连接远端。

## 结论

v1r1 是真实修订，不是只改文档：归档 SHA、包内源码、安装包和验证日志一致；P1–P7 均已落实；没有发现阻塞提交的问题。真实实验仍为 `NOT_STARTED`。

- 归档：`modern_head_comparison_v1r1_20261018.tar.gz`
- 实测 SHA256：`ad2454fa3766d3862d98e90370fb9dc1fa8b5d67afd20123863182123f71d4d3`（与 `validation.json` 一致）
- 包内 `SHA256SUMS` 的 SHA256：`c9f526e6e0ac6a991b0070a374bd56b6cc03e8ebb7897ec9674ed94df88fbe13`（实测一致）
- 安装包 163 个文件；Windows/WSL 均完成全新安装校验。
- 57 项受影响 Python 测试 + 37 项 Linux 模拟调度 + 3 项分阶段导出用例通过；导出在 Windows/Linux 各跑一次，共 100 次执行、97 个不同用例。原完整 65 项未整套重跑，回执已标 `rerun:false`。
- 安装包内 6 个关键源码与当前 `repo/ood` 逐字节一致；旧 v1 归档 SHA 仍为 `635d6176…c0dfc4`，未被覆盖。

## P1–P7 核对

| 项 | 状态 | 核对要点 |
|---|---|---|
| P1 LightGBM 自然停止 | 已修 | `modern_head_train_v1.py:165` 改为允许 `0 < callback <= requested` 且 `0 < effective <= callback`；endpoint 与 training_log 同时记录 requested/callback/effective/native_stop；无早停、无按目标选轮数。 |
| P2 P/T/K 与入网解耦 | 已修 | `inputs_head` 只依赖 QUERY_TAIL；`inputs_module` 才查六库；`--heads-only`/`--modules-only` 预检、状态、claim、回传归档分离；模块只读封存头，不重训。 |
| P3 复用证据 | 已修 | adapter 返回每池每 seed/ensemble 的 score/decision 逐位比较、UID 顺序、dtype/shape 与数组 SHA；runner 落盘 `reuse_adapter_replay.json` 并从比较结果生成 proof，不再硬编码 True；共享前置检查后才登记 `REUSE_VERIFIED`，仅捕获 `ReuseIneligible` 后重训，封存/哈希/非有限权重仍硬停。 |
| P4 CAL_used | 已修 | `modern_head_onboarding_v1.py:35-36` 与 reference/DEV 一起要求 `CAL_used is False`。 |
| P5 合同范围文字 | 已修 | `modern_gates()` 只改 `applies_to` 说明为“每个 family 的每 seed 与 ensemble”；数字门槛逐项不变，旧 QUERY_TAIL 合同字节未动。 |
| P6 M 零更新 | 已修 | `modern_head_runner_v1.py:279` 断言 `optimizer_updates == 0`，缺字段或非零均拒绝。 |
| P7 离线依赖 | 已修 | `submit_once.sh` 与 `run.slurm` 在模型 Python 启动前检查 `extra_deps/` 与 `dependency_install_receipt.json`，缺失明确退出，不自动安装。 |

## 对原 P1 判断的更正

原复核担心“LightGBM 天然无法分裂时回调次数会少于 500，原 `counter == rounds` 会失败”。Codex 用 LightGBM 4.6.0 常数特征 fixture 实测为：请求 500、回调 500、实际保留 1 棵树。因此**原回调相等断言在该 fixture 上不会失败**，我原来的表述过强；Codex 的更正正确。

新版仍值得保留：它把“请求轮数 / Python 回调次数 / 实际保留树轮数”分开记录，`native_stop` 定义为实际树少于请求预算；这比只看回调次数更准确，也覆盖未来版本若出现回调不足的情况。测试 `NativeStopTests` 同时覆盖常数特征保存/回放和 500 请求计数。

## 剩余注意（不阻塞）

1. **modules-only 的最终退出检查只在提交脚本里**：`submit_once.sh` 要求 `status/heads/exit_code.txt == 0`；但 `preflight --modules-only`/`run.slurm` 本身未再读该文件。正常走 `submit_logged.sh` 是安全的；若有人绕过提交入口直接 `sbatch`，模块可能在头导出失败后启动。建议后续把该检查补进 `preflight`/`run.slurm` 作为纵深防御。
2. **full 模式仍是全有或全无**：full 作业若在 M 阶段失败，`submit_claim.full` 和 `MODULES_STARTED.json` 会保留，之后不能直接转 `--modules-only`（提交脚本会拒绝）。这不是 bug，是 no-retry 设计；实际使用建议直接采用 heads + modules 两次作业，便于失败隔离和回传。
3. **目标环境仍未验证**：Python3.9/NumPy2.0.1/Torch2.5.1、glibc≥2.28、真实内存峰值和耗时都待超算恢复后核验；本地通过不等于目标兼容。
4. **证据边界**：v1r1 只重跑受影响测试和选定原回归；原 21 项 Python 测试、原 7 项导出 fixture、QUERY_TAIL/入网旧套件均未重跑，回执已逐项标注，不能概括为“全部旧测试重新通过”。

## 建议

v1r1 可以作为超算恢复后的待运行版本。使用顺序仍为：QUERY_TAIL v2r3 完整产物 → 现代头 `--heads-only`（P/T/K）→ 入网 v1r1 六库完成 → 同包 `--modules-only`；默认 full 仅在全部依赖一次备齐时使用。三设备回归未接入，完整系统仍不得 PASS。
