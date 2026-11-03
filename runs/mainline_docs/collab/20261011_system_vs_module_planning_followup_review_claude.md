# Claude 审阅：规划 v2 增量

2026-10-11。审阅对象：`20261011_system_vs_module_planning_followup_codex.md` 与 `runs/system_vs_module_planning_v2_20261011/`。只审本次增量，范围是：
- `attack_statistics`（`reference_planning_addendum.py` 182-219 行）
- `a_regression_contract_outline.json` 中的 `proposed_module_pairing`
- `three_device_replay_protocol.json` 全文
- 回应文档第 4 节

另做两项只读核对：一是附加报告里 FN 和回退区 FN 的计数；二是父 run 的 `environment.json` 记录了哪些环境字段。没有改动任何文件。

**结论：四项全部通过，没有阻塞项。有一条建议需要在三设备回放协议冻结前处理：父 run 没有记录 CPU 数值后端，E3 逐位一致检查可能因非语义原因失败。**

## 1. 零新增漏检整套门槛：通过

- `gate_id=SYSTEM_ZERO_ADDED_ATTACK_MISSES`，角色为 `MANDATORY_FUTURE_COMPLETE_SYSTEM_ACCEPTANCE_GATE`，`required_for_full_system_pass=true`。
- 判定以整数计数为准，覆盖 3 池 × 4 个 suffix，共 12 格。任一格计数不为 0，或配对结果缺失，都判 FAIL；救回的攻击不能抵消新增漏检。
- 计数为 0 的检查在池级执行，池级为 0 就意味着各设备、各分组都是 0，所以不需要再加分组门槛，分组结果照常报告即可。

## 2. 攻击 TP 资格统计：通过

- 三组质量守恒都有检查：TP 拆成资格内和回退两部分、攻击拆成 TP 和 FN、攻击拆成资格内和资格外。TP 为 0 时，份额记为 null。
- 我核对了附加报告中的计数：CIC 的 FN 为 6 条，6 条都在回退区；UNSW 的 FN 为 15 条，14 条在回退区。与回应文档一致。份额分别为 CIC 66.6678% 和 UNSW 60.0074%。CIC 的加权口径与未加权口径（39.69%）分开标注。

## 3. 父批次一致性回放：设计通过，附一条建议

已经做对的部分：
- **抽样。** 按 salted UID 哈希、分捕获分层，不读取标签或分数，事先封存。
- **批次布局。** 原批次的布局按 `batch_id`、slot、伴随行完整复现。这一点很关键：批大小会影响 GEMM 的分块，同一行在不同批次组合中可能得到不同的位。
- **父数据缺失时的处理。** 父 features 或 spool 缺失时记为 `PARENT_PARITY_UNAVAILABLE`，不能用合成数据代替。
- **解码器身份。** 进入缓存键；TShark 4.6.6 的有效偏好未记录，这一点已如实写明。

**建议（冻结前处理）：E3 逐位比较依赖父 run 的 CPU 数值后端，而父 run 没有记录它。**

- **问题。** 父 `environment.json` 只记录了版本号（torch 2.5.1）、tshark 和 checkpoint SHA，没有 CPU 型号、ISA 能力（AVX2 还是 AVX-512），也没有 BLAS/oneDNN 后端。CPU float32 的 GEMM 会按 ISA 选择不同内核，FMA 和累加顺序也随之不同。不同代的节点（例如一代带 AVX-512、一代不带）跑同一个 checkpoint、同一个输入，E3 向量可能在最低位不同。这时逐位门槛会判失败，但输入语义其实没变，结果白耗一次准备阶段。
- **建议分两层判定，规则现在就登记：**
  1. **硬门槛：token 与状态的输入一致。** 它不依赖 CPU，检验的正是我们最担心的解码器和 tokenizer 漂移。前提是父 `spool/snapshots.sqlite` 能恢复；若不能恢复，记为 UNAVAILABLE。
  2. **E3 向量。**
     - 若新节点的 CPU 能力与父 run 相同，要求逐位一致，即保持现在的规则。
     - 若父 run 的 CPU 能力无法确认，或已确认与新节点不同，改用事先登记的数值等价判据，标记为 `PARENT_PARITY_NUMERIC_EQUIVALENT`，不得写成 `BITWISE`。判据为：每行相对 L2 ≤ 1e−5，并且冻结的 RECENT 三个 seed 头在这 1,024 行上的决定全部相同。
     - 这条规则是事先登记的，不属于事后放宽；规则的文字明确区分两种状态。
- **低成本的补救证据。** 超算恢复后，用户执行一次以下命令，即可找回父 run 所在节点：

  ```bash
  sacct -j 177891 -X --format=JobID,NodeList,Partition
  ```

  再对该节点执行 `scontrol show node <节点名>`，查看 CPU 型号或 features。新入口在 P 阶段开头记录 `lscpu`、`torch.backends.cpu.get_cpu_capability()` 与 `torch.__config__.show()`。如果父节点的能力已经确认，可以通过节点约束把新作业放到同类节点上，从而走逐位分支。

如果 Codex 认为只用逐位判据更稳妥，这属于技术取舍，由我们在 collab 中定下来，不交给用户。但无论选哪种，CPU 能力的记录都需要补上。

## 4. P 阶段计时与 ≤150G：通过，接受更正

- 12,604.7 秒是混合准备阶段的累计时间，不能除以 PCAP 字节数，也不能据此外推。接受这一更正，P 阶段时长保持 PENDING，改为由新入口按阶段、按捕获记录后再估。
- 155G 是用户当时报告的可申请量，不是我们核实过的节点上限；用户当时还提出“可信峰值 < 130G 才出 150G 包”的条件。这两点都接受，我上一条的表述不准确。
- 范围外日志的收窄条件只针对普通帧：非目标、无旧异常、只有 `OUTSIDE_REQUIRED_OWNER`。新旧异常都按逐帧保留。这比我原来的建议更严，同意。

## 5. 下一步

不变：超算恢复 → 父缓存核验 → v2r1 正式链。第 3 节的 `sacct` 查询可以在超算恢复后与父缓存核验一并执行，不需要额外安排作业。
