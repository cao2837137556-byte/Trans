# CKDA D1 实现 — Kimi 独立审查

- 日期：2026-08-12
- 对象：commit `a9d4d21`（14 文件，+4,680 行），报告 `ckda_d1_implementation_report_20260812.md`
- 冻结合同：`ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`

## 总结论：IMPLEMENTATION PASS —— 授权构建 D1 bundle

## 独立复验记录

| 项 | 实测 | 结果 |
|---|---|---|
| 合同测试 | 本地复跑 **46/46 PASS**（32.8s 真实执行） | PASS |
| FROZEN 哈希钉死 | 代码内 `CONTRACT_SHA256` = 冻结合同 | PASS |
| 良性语料上限 | **独立复算：2,182,190 < 10,000,000**（27 行清单、允许 20/排除 7，排除原因全部为 `FROZEN_EXCLUDED_ROLE`） | PASS，I1 前置门数学上必然失败 |
| 行动门九条合取 | 逐条对照 §10.2：69/69、244,050、−0.5pp、16 族 −2pp、131,391、0.8483、0.302722、单池 +2pp、90%、review=0、合同门——全部一致，且分母漂移直接 raise | PASS |
| 状态机优先级 | 工程失败/未完成 → ENGINEERING_FAILURE；P1/P2 actionable → ACTIONABLE（唯一 GO_D2），与 §12 一致 | PASS |
| I1→E3 推进 | Slurm 内：良性 census 仍真实执行并审计；若门"通过"（与冻结上限矛盾）立即 fail-closed `RuntimeError`；门失败则记 `I1_PRIMARY_PRECONDITION_FAILED` 转 E3 | PASS（保守方向 fail-closed，正确） |
| 因果前缀 | `MAX_PREFIX=256`、事件位置 tie-break、current-inclusive 切片（`order[start:start+256]`），46 项测试含 future-mutation 不变性 | PASS |
| report 隔离 | fit/select 计划审计在 report 计划前改名防覆盖；validator 强制双审计 + 三 frontier 表 | PASS |
| CKCZ 接口修复 | `load_manifest` → `validate_manifest(...)` 实际合同，有永久回归测试，本地发现未烧机时 | PASS |

## 科学判定

1. **I1 线在本轮数学上不会启动**（良性上限 218 万 token < 1000 万门）。这不违反 FROZEN——§4.2 的合取门是先冻结后测量，门失败转 E3 是协议内路径。执行结果将是 **E3 netFound 的三层探针判决**。
2. "上限矛盾即 fail-closed"的设计把不可能事件按工程失败处理而非悄悄训练，方向正确。
3. 报告的诚实性确认：明确不承诺零故障、明确 D1 未证明任何信号。

## 非阻塞备注

1. 若未来想救活 I1 线，合法路径是补充独立良性数据源后走新命名路线+新预注册，不能复用本次 D1 的 report。
2. E3 保持 `NO_KNOWN_OVERLAP` 限定语，即使 actionable 也不支持 KNOWN_DISJOINT 声明——写作时注意。

## 授权边界

- 本 PASS 授权 Codex **构建并验证 D1 bundle**。
- HPC 提交仍需用户明确授权。
