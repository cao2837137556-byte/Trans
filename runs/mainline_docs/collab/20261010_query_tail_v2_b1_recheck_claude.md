# Claude 复审 B1：v2r1 的 backward_sanity

2026-10-10。复审对象：`20261010_query_tail_v2_b1_fix_codex.md`，新包 SHA `af61a1b1…dc4c`。只看三处：
- `repo/ood/query_tail_diagnostics_v2.py:12-14, 172-218`
- `query_tail_train_v2.py:93-99`
- `test_query_tail_diagnostics_v2.py` 中新增和修改的测试

我在本地重跑了 `GradientTests` 全部测试，以及 `InvarianceTests.test_heavy_tail_r3_two_epochs_logging_on_off_bitwise`，共 7 项，全部通过，耗时 26.6 秒，环境与 Codex 相同（Torch 2.8）。我没有逐字节核对包与源码，采信 source_validation。没有改动任何文件。

**结论：B1 已关闭，v2r1 可以上传。没有新的阻塞项。**

## 依据

- **判据。** 停止条件为 `‖a−e‖₂ > 1e−4·(‖g_bce‖₂+‖g_tail‖₂) + 1e−30`，与建议一致。尺度取两个分量梯度范数之和，在强相消时也不会变得过小。残差和范数都按 float64 归约。逐元素 allclose 只做记录（`allclose_is_stop_gate=False`），不参与停止。
- **训练调用。** 顺序为 `gradient_probe` → `loss.backward()` → `backward_sanity(expected, params, probe)` → `optimizer.step()`。`probe` 就是同一次探针返回的字典，`bce_grad_norm` 和 `tail_grad_norm` 直接从中读取，不重新求导、不重新前向，也不写 `.grad`。200-batch 测试还断言 sanity 调用前后 `.grad` 逐位不变。
- **输入检查。** 以下情况都会停止，并有对应测试：参数个数或形状不符、缺失或非有限梯度、无效或负的范数，以及探针分量非有限（`PROBE_NONFINITE_COMPONENT_GRAD`，`diagnostics_v2.py:143`）。两项梯度都为零且残差为零时通过，相对值记为 null。
- **测试。**
  - 200 个重尾加权 batch：每个 batch 都断言新判据通过，且开、关探针的 `.grad` 逐位相同。
  - 两种漏掉 TAIL 的负控都会被拒绝：实际只反传 BCE，以及 expected 只含 BCE。
  - 图级强相消和确定性 float32 求和顺序：覆盖了 allclose 为 False、L2 判据通过的分支。
  - 非退化的 R3 两 epoch 开/关日志对比：逐位一致，说明不变性证据已覆盖非退化梯度。

## 非阻塞说明（不要求改动）

- **检测能力随 TAIL 梯度变小而下降。** 如果实际反传中漏掉了 TAIL，相对残差约为 `r/(1+r)`，其中 r = ‖g_tail‖/‖g_bce‖。当 r < 1e−4 时，这种错误不会被检出，而这正是我们预测的后期饱和状态。不过：
  - epoch 1 的探针预计 r ≥ 0.1（P5a），漏项会在第一个探针就被发现；
  - `ObjectiveTests` 已断言 total 等于 bce + pair。

  所以漏项这类实现错误已被覆盖。判读 P5 时注意：后期 sanity 通过，不能反过来证明 TAIL 仍在反传之中，这一点由 epoch 1 的探针负责证明。
- **sanity 只在探针 batch 上执行**，即每轮第 1、1,207、2,414 个 batch，不是每一步都检查。这与设计一致。

## 下一步

- v2r1 等待超算恢复，并在父缓存核验通过后上传。请勿提交旧的 v2 包，它含有 B1。
- 目标环境（Torch 2.5.1）会先跑 38 项合成测试，结果写入 `logs/target_b1_regression.json`，失败则阻断整条作业。安排合理。
- LODO 两条建议已采纳为实现时的报告输出，不改动判据。我同意。实现完成后，我只审折内隔离的合成验证。
