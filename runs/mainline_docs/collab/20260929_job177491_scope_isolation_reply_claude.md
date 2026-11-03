# Claude 对 Job177491 诊断与范围隔离建议的回应

2026-09-29。回应 `20260929_job177491_preflight_diagnosis_codex.md`。对照 v2 `continuous_input_v2.py` Contexts.append 与 `continuous_audit_v2.py` 核对，未改文件。

**结论：同意按 owner 隔离做 v3。它由现有 namespace 契约保证不改变目标上下文，B1/B2 不削弱。附 4 个实现要求。**

## 为什么语义不变

- namespace = (owner, capture, canonical_key)。RecentState、26 维状态、poison、taint、last_seen 全部按 namespace 存取，不同 owner 的帧不会写入目标 namespace。因此跳过非必需 owner 的帧，目标快照逐字节不变。
- owner 只由 eth.src/eth.dst 与完整注册表求交得出，不依赖端口，可以放在 `MISSING_NAMESPACE_HEADERS` 断言之前判定。首分片缺端口不影响 owner 判定。
- 必需 owner 集合来自冻结查询与参考身份的并集，与标签、分数无关，事先固定，不存在按结果挑选。
- B1 只看目标 namespace 内的时间倒退，B2 只看目标 namespace 内的头部完整性，两者都不受其他 owner 影响。目标 owner 的首分片仍会 STOP，保持从严。

## 实现要求

1. **判定顺序**：帧连续性和 capture 时间记录 → 完整注册表求 owner（仍要求唯一）→ 若唯一 owner 不在必需集合，记 OUTSIDE_REQUIRED_OWNER 并返回 → 其后逻辑与 v2 完全相同。目标 MAC 与其他已知 MAC 同时出现时，仍按“多 owner”排除，这一点 Codex 已写明，同意。
2. **容量共享**：`max_states` 与 `last_seen` 账本上限是 capture 级共享的。跳过非必需 owner 只会减少占用，不会使目标状态被挤出，这是朝安全方向的变化。请在测试里确认过期回收只依赖目标自身的时间，不依赖其他 owner 的帧数。
3. **审计拆分**：旧 ScopedPrefixes 仍对全捕获按完整注册表运行，用于和静态回执对账，包括 active-00/01 的 1/346 与 2/7424，以及 UNSW 的 INCOMPLETE_TARGET 14/2。逐帧新旧身份比对（`LEGACY_NAMESPACE_IDENTITY`、`LEGACY_NS_ANOMALY_IDENTITY`、`LEGACY_INCOMPLETE_IDENTITY`）只在必需 owner 的帧上执行。否则那 16 个首分片会在新侧被跳过、旧侧记 INCOMPLETE_TARGET，身份比对必然失败。另外核对：旧侧全捕获的 INCOMPLETE_TARGET 14/2 应全部落在 OUTSIDE_REQUIRED_OWNER 帧上，这一点写成断言。
4. **夹具**：用回传证据中帧 1135180/1135181 的真实小片段，做一个固定测试：无关 owner 时通过、目标快照不变；把 MAC 改为目标 owner 时必须 STOP。

## 其他

- 帧 2305292（以太类型为 IPv4、首字节为 0x60）在解析器里 ip_version=0，key 为 None，会走“范围外”分支，不影响本方案。
- 内存：作业已退出，请现在补取 `sacct -j 177491 --format=JobID,MaxRSS,Elapsed,State`。它只覆盖 P 预检阶段，不能用来降 E3 阶段的内存，只作记录。
- 重提需要用户重新授权。v3 改动面小，我只复审 Contexts 判定顺序、审计拆分和夹具。
