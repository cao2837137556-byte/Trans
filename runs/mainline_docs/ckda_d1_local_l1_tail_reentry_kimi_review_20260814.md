# CKDA D1 本地 L1 tail-reentry 修复 — Kimi 审查

- 日期：2026-08-14
- 对象：修复 `dbf8532`，HEAD `e396e1c`，报告 `ckda_d1_local_l1_tail_reentry_repair_20260814.md`

## 总结论：PASS —— 授权从零 member checkpoint 重跑 L1

## 裁定依据

**根因分析正确。** 旧条件 `session in wanted` 是静态集合成员判定：session 在其最后目标后被释放，若之后又作为非目标包出现（同 member 内其他 session 的目标使解码继续），`setdefault` 会重新创建空状态且永无释放事件，末尾的 fail-closed 断言正确触发。断言设计本身立功了——失败被拦在 checkpoint=0、无科学判决处。

**修复语义精确。** 新条件 `s in last_target AND p <= last_target[s]`：session s 的冻结目标前缀只需要位置 ≤ 其最后选中目标 L(s) 的包；L(s) 之后的包不可能影响任何被请求的 embedding。改的只是内存生命周期，不碰前缀内容、目标序、batch 序、checkpoint schema、模型、tokenizer、分数。与 FROZEN 因果语义一致。

**回归与验证充分。**
- 本地复跑 **47/47 PASS**，含新回归 `test_36g`（覆盖 current-inclusive 保留、cutoff 后排除、异 session 并行、None、未请求 session 五种情形）；
- 32 真实目标正式 vs 本地逐字节一致、最大差 0.0、checkpoint SHA 双侧一致；
- 新增 `local_embedding_attempt.txt` 标记，防止 L1 尝试与 L0 `embeddings_started=0` 混淆。

**失败分类正确：** 本地两遍适配器工程失败，null verdict，report/FINAL 未打开。真实 canary 未覆盖该拓扑（单保留 session、止于其最后目标）的局限性被诚实记录。

## 非阻塞备注

修复后的实现将首次在 ToN `normal_1.pcap` 这类"多 session 交错、200 万包"拓扑上实跑；byte-identical canary 未覆盖该拓扑。残余风险由 fail-closed 断言兜底，若再失败仍按工程失败分类。

## 授权边界

- 授权重跑 L1（25,467 E3 fit/select embedding + G0/P1/P2 + 阈值冻结），从零 member checkpoint 开始，止于 report 封存。
- L2 与论文声明仍分别单独授权；HPC 重放确认要求不变。
