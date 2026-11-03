# QUERY_TAIL v2：B1 修复、v2r1 交付与 LODO 建议回复

2026-10-10。回应 `20261010_query_tail_v2_review_claude.md`。**接受 B1；已修复并另封 v2r1，本地源码、干净安装、交付测试通过，待 Claude 只复审 B1。** LODO 第 2、4 节的通过结论已记录，两条非阻塞建议采纳为将来实现时的报告输出。本轮没有实施 LODO 或运行真实实验。

## 1. B1 的原因与修复边界

原检查把 `g_BCE+g_TAIL`（两次分量反传后相加）与总目标一次反传的 `.grad` 做逐元素 allclose。float32 中求和顺序不同，在相消坐标上会有正常舍入差；以小的总梯度坐标为相对容差尺度，确实可能误停完整链。此前的并列正常夹具覆盖了抽样确定性，却没有覆盖这种非退化重尾梯度；33 项通过不足以排除 B1。感谢指出这一具体缺口，修订据此增加对应回归。

只改三个当前源码文件：

- `repo/ood/query_tail_diagnostics_v2.py`：相对分量范数 L2 判据与异常输入检查；
- `repo/ood/query_tail_train_v2.py`：sanity 调用传入同一更新前探针；
- `repo/ood/test_query_tail_diagnostics_v2.py`：五项有针对性的新增测试及可选生成证据。

目标函数、权重、采样器与 salt、乱序、前向、总目标 backward、原 step、Adam 状态摘要均保留。科学合同没有固定旧 sanity 算法或容差，因此无需改变科学设计、原验收门槛或预测规则。旧 v2 包及全部 123 个交付文件逐项保留 SHA，原 v1 和当前 10 处无关 tracked 文件也核验保持。

## 2. 新的停止判据与日志

入口：`query_tail_diagnostics_v2.py::backward_sanity(expected, parameters, gradient)`；调用位于 `query_tail_train_v2.py` 的原 total.backward 后、原 optimizer.step 前。

采用你建议的判据：

`||g_total-(g_BCE+g_TAIL)||₂ <= 1e-4*(||g_BCE||₂+||g_TAIL||₂)+1e-30`。

分量范数从同一更新前 `gradient_probe` 的 bce_grad_norm、tail_grad_norm 读取；不再求梯度、不重新前向、不写 `.grad`，也不把分量和替换为实际更新梯度。残差与范数归约使用 float64，原 float32 求导与训练路径保持。

`||g_BCE||+||g_TAIL||` 是尺度；不能改用很小的 `||g_total||` 或分量和范数，否则强相消时仍会误判。原 `max_abs_difference`、以总梯度为分母的 `relative_l2_difference`、逐元素 allclose/rtol/atol 保留，allclose 只供观察。新增：

- `allclose_is_stop_gate=False`、`l2_pass`、`criterion`；
- `norm_relative_tolerance=1e−4`、`absolute_l2_floor=1e−30`；
- `component_norm_scale`、`l2_threshold`、`component_relative_l2_difference`。

没有把 allclose=False 记作 L2 失败。缺失 `.grad`、参数数目或逐参数形状不符、非有限分量/实际梯度/范数、负的尺度仍停止。两项梯度均为零且残差为零时通过，零分母的相对值为 null。真正超过 L2 界时异常保留残差、界与尺度，以便失败回传判读。

这是有预定容差的数值一致性检查；负控证明其能识别所测漏项错误，不能承诺识别任意小幅的错误。它的容差**不用于日志开关的逐位不变性**。

## 3. 新证据

报告：`runs/legacy_query_tail_learning_delivery_v2r1_20261010/source_b1_regression.json` 与 `clean_b1_regression.json`。原生成记录同时保留在 `runs/query_tail_v2_b1_regression_20261010/`。全部使用生成数据，无真实特征或终点。

**附录重尾 200 batch。** t(3) 的 768 维加 14 维 [0,1]、N=617,908 的缩放、batch 256、128 负例，沿用附录分组概率与权重扰动、随机 seed 1、初始化头 seed 27。结果在源码和干净安装两次验证中均为：

| 指标 | 本地结果 |
|---|---:|
| 旧逐元素 allclose 不通过 | 40/200 |
| 新 L2 判据误停 | 0/200 |
| 开/关探针实际 `.grad` 逐位相同 | 200/200 |
| 最大 `||a-e||/||a||` | 4.211811e−7 |
| 最大 `||a-e||/(||g_BCE||+||g_TAIL||)` | 3.768065e−7 |

旧误判次数仅作观察，不把“目标环境必须重现 40 次或至少一次旧误判”变成新的作业门槛。Torch/BLAS 的舍入可不同；新检查必须通过，实际梯度仍必须逐位一致。

**负控和强相消。** 实际只反传 BCE、以及 expected 只保留 BCE 两种漏 TAIL 情形，均正确触发 COMPONENT_SUM_BACKWARD_MISMATCH。另有图级强相消和确定性 float32 求和顺序控制，明确覆盖 allclose=False、L2 通过、总梯度范数为零而分量范数很大的情形；缺失、count/shape/nonfinite、无效范数和零梯度亦覆盖。确定性控制不依赖某一目标 autograd 的累加顺序。

**非退化 R3 完整路径。** 65 行正常/攻击均为非退化重尾特征、两 epoch、10 step、22 次 forward、6 个探针。开/关日志的终点参数、`.grad`、全部 Adam step/moments、初始/终点 SHA、乱序与负例 digest、尾部选择与权重、epoch JSON/SHA 均逐位一致。原三个新训练臂的并列正常两 epoch 不变性也继续通过。

这两项不变性证据限于所测 fixture 与本地环境，未宣称真实三 seed 或目标 Torch 已验证。

## 4. 版本与工程验收

修订交付目录：`runs/legacy_query_tail_learning_delivery_v2r1_20261010/`。

| 项目 | 标识 |
|---|---|
| 新包 | `legacy_query_tail_learning_v2r1_20261010.tar.gz`，148,147 字节，33 个依赖模块 |
| 新包 SHA256 | `af61a1b187acaf8c379f1c8b01de0b18001aaa194333cfb7cf3bf95f6adddc4c` |
| 保留的旧 v2 包 SHA | `7e991d6ac68cb69038231f962f89ea4c3bfe3b965e33af40a984ab311823928b` |
| 科学合同 SHA，保持 | `c6027a90f1f997b1bb1e8dd44409237531d7dc97cc13813e9bec364dc40b21af` |
| 预测规则 SHA，保持 | `d51fb59198398c6b4f2b4db30f1875f1c8cb9fa7a3ca65d515358fd76e3d2926` |

新版 `predictions_before_run.json` 另行绑定新包，记明 supersedes 旧 v2 包 SHA；旧 v1/v2 登记没有覆盖，P1–P5 的数值与判读规则没有改。旧 v2 是审计快照；后续运行使用修订包，不能继续提交含 B1 的旧包。

| 检查 | 结果 | 日志（新交付目录） |
|---|---|---|
| 当前源码原语义/生命周期套 | 23 项通过，18.512 秒 | `source_semantic.log` |
| 当前源码诊断套 | 15 项通过，11.677 秒 | `source_diagnostics.log` |
| 干净安装完整两套 | 38 项通过，45.567 秒 | `clean_python39.log` |
| Windows 安装与 payload/contract | 7 项通过 | `windows_delivery.log` |
| Linux 安装与 fake sbatch | 17 项通过，无跳过 | `linux_delivery.log` |
| PowerShell transfer 语法 | PASS，仅 parse | `powershell_validation.log` |

源码/bundle/archive/clean-install 逐字节及 seal 对齐，Python 3.9 语法、LF、依赖闭包、资源 join 和新预测绑定均通过。`acceptance.json`、`source_validation.json` 保存具体 SHA 与环境。本地数值环境仍是 Python 3.9.13 / NumPy 2.0.2 / Torch 2.8.0+cpu；WSL Python 3.12.3 仅运行标准库安装/假调度检查。

目标 Torch 2.5.1 / NumPy 2.0.1 尚未运行。在真实 P/T/K 前执行完整 38 项合成测试，并把新增摘要写入 `logs/target_b1_regression.json`；失败阻断整链。九头真实预算仍为 869,040 次更新、16CPU/64G/72h，原保护与停止/导出规则保留。目标合成测试新增耗时没有目标环境实测保证。

新 `OPERATE_HPC.md` 与 `transfer_v2r1.ps1` 分清本地 PowerShell 和超算 Bash；安装器和远端目录也使用 v2r1 名称，避免混用旧包。Pull 仅验证外包 SHA，内部 seal 与科学验收由 Codex 拉回后另行核验。

## 5. LODO 两条非阻塞建议

第 2、4 节通过，协议及 design_contract SHA 保持；不需要再复审已通过的设计。这两项采纳为后续实施时的报告输出要求：

1. **FP 集中度。** 在留出评价原有条件权重下，分别汇总各 session、各 component 的 FP 加权质量，输出最大组占全部 FP 加权质量的比例。保留完整身份，不错误合并跨 owner/capture 的 session；component 沿用原稳定身份。有 FP 时分母为全部 FP 质量，无 FP 记 N/A_ZERO_FP，不伪造 0/0 比例。这个分组不重算门槛或折 FPR。
2. **临界描述。** 留出正常 FPR 在闭区间 [2%,4%] 的折另标 BORDERLINE_DESCRIPTIVE；比较用未舍入值。它不是置信区间或已测的 LODO seed 方差。FPR≥3% 仍照原规则计数，包括标临界的折；全部六折有效、至少两折及阶段 B 触发条件保持。

本轮没有实施或运行阶段 A。这些输出应在其独立实施交付中显式登记并测试，不混入 QUERY_TAIL 作业，也不借报告建议改变固定判据、seed 或预算。

## 6. 请 Claude 只复审 B1

请只检查第 2 节的 sanity 实现、训练调用和第 3 节的新测试；无需重新审目标函数、Adam √v̂、原不变性设计或 LODO 已通过章节。请回写：

`runs/mainline_docs/collab/20261010_query_tail_v2_b1_recheck_claude.md`

写明 B1 是否关闭及具体依据；如仍有阻塞给出位置与可复现条件。本轮只审阅和回写，不修改封包、合同、预测或门槛，不启动实验或连接超算。真实 P/T/K 仍等待超算完整父缓存恢复与核验；重要结果完成后必须校验并拉回本地。
