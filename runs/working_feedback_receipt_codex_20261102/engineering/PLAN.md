# 工程预检与失败计费落实计划

结论：接受反馈第 2 项；五类故障已有局部防线，但尚无可证明的完整真实小切片端到端预检。
影响：后续长作业须补齐这道提交前门；本轮不改变 C5、数据角色或封存结果，也不启动计算。
下一步：把已有检查接成同运行时预检，先落失败账本和分阶段计费，再在下次交付中执行并留证。

状态：`PLAN_REVIEWED_NOT_EXECUTED`。本文件是实施计划，**不是 `REAL_SLICE_E2E_PASS` 回执**。

## 1. 已核实的现状

- 最终 C4 回执累计计费为 **40,235.79058704007 秒 / 46,861 秒**；追加阶段总钟包含取回、评价及独立复核，排队不计，未自动重投科学任务。
- 既有 `preflight_worker.py` 验过 Linux / Python 3.11.11 / NumPy 2.0.1 / Torch 2.5.1、246 个真实包头、旧数组与检查点、工程测试。它明确不重放原始捕获，**不能据此宣称已完成“解码→真实编码→距离→评价→回执”全链路**。
- `test_decoder_guard.py`、`test_encoding_resume.py` 等包含有价值的合成故障测试；合成通过与真实切片通过必须分栏报告。
- 本轮仅阅读代码和既有小型回执，未执行上述测试，未读取大数组，未运行编码、距离、模型或超算任务。

## 2. 五类故障与永久防线

以下路径均相对仓库根目录。`B` 表示 `runs/history_sample_coverage_c4_batch_resume_v1_20261102/`；`D` 表示 `runs/history_sample_coverage_c4_budget_deployment_20261102/`。

| 故障 | 本可提前发现吗 | 既有防线 / 证据 | 仍需接入的永久检查 |
|---|---|---|---|
| 配置字段顺序改变语义哈希 | 可以；实际已在首次 `sbatch` 前拦住，未计算 | `runs/history_sample_coverage_c4_deployment_repair_v1_20261101/build_repair.py:main` 复现旧失败，验证 JSON 值相同、原顺序哈希正确；receiver 检查尚未提交/编码 | 在打包后解包真实产物，对本地卡与远端配置执行同一语义校验；保留“重新排序会失败”的独立夹具。现有受控修复断言不能充当所有未来交付的自动回归门 |
| Slurm 的 CRLF | 可以；`sbatch` 拒绝，未产生任务编号或科学计算 | `runs/history_sample_coverage_c4_memory_submission_repair_20261101/test_delivery.py:DeliveryChecks.test_real_slurm_unix_lf` 直接检查实际 Slurm 文件的 shebang 与无 `\r` | 对归档内全部 shell/slurm 检查 LF，并在 Linux 执行 `bash -n`；检查必须针对待提交字节，不只针对源码副本 |
| 跨设备驻留编码器叠加大规模解码导致内存超限 | 可提前发现生命周期重叠；少量包不能证明全量峰值 | `B/coordinator.py:launch` 串行子进程；`B/member_worker.py:main` 区分 prepare/encode；`B/hnr/runtime.py:Runtime._usage` 汇总进程树 RSS 与未链接 SQLite 临时文件 | 增加 prepare 不导入 torch/transformers、prepare/encode 生命周期不重叠的检查；真实切片报告进程树峰值；按原包体量/组件数预估磁盘与内存并保留运行时硬上限。不能声称小切片排除了所有全量 OOM |
| TShark stderr 日志策略过严/不兼容 | 常规小切片不一定命中罕见帧；已知故障帧可提前复现 | `B/decoder_guard.py:diagnostic_signature,parse_stderr` 精确签名；`B/test_decoder_guard.py:DiagnosticParserTests.test_other_protocol_path_assertion_or_extra_text_rejected` 与 `test_pes_is_limited_to_observed_frame_and_protocol_signature_preserved`；246 帧真实头部审计 | 把既有 246 个真实故障帧及对应原始头部审计作为固定诊断夹具；新版本 TShark 的诊断须重新资格核验，不扩大白名单，不忽略未知 stderr 或非零退出码 |
| 包头布尔字段 `True/False` 被当整数 | 可以；同版本真实 TCP 切片可发现 | `B/decoder_guard.py:_equal_flag`；`B/test_decoder_guard.py:RawHeaderAuditTests.test_tshark_true_false_and_integer_flag_representations`、`test_unknown_missing_or_list_boolean_forms_are_rejected`、`test_each_boolean_flag_must_match_its_raw_header_bit`；`runs/history_sample_coverage_c4_header_deployment_20261101/REAL_HEADER_AUDIT.json` | 同运行时真实 TCP 输出须同时过字段解析和原始位比对；UDP/IPv6 仍按现有严格合同检查，禁止用宽松转换掩盖异常 |

补充：先前一次 600 秒预检超时没有持久化到具体子阶段，**不能倒推指定根因**。`D/preflight_worker.py:StagedPreflight` 以及 `D/test_preflight_worker.py` 的三项持久化回归已覆盖 START/DONE/FAIL；控制器对提交不确定性保持 `SUBMISSION_UNCERTAIN_NO_RETRY`，不得自动再次 `sbatch`。

## 3. 下次长作业必须经过的真实切片门

1. **冻结交付物。** 先生成唯一归档，记录源码、模型、配置、依赖和 shell 字节校验；归档在 Linux 解包后检查语义一致、LF、`bash -n`。版本不匹配则阻断，不能把 Windows/Python 3.10 的测试结果写成 Linux/Python 3.11 兼容证明。
2. **固定真实切片。** 从已有合法 source/development 原始捕获中，按预先登记的物理包位置/哈希，为每个设备的每个实际协议选少量真实记录，覆盖方向、TCP SYN/ACK/PSH 与 UDP；保存源 SHA、原包序号、角色、选择算法和所需前序上下文。没有某协议就登记 N/A，不伪造样本。不得依据 A/B 错误或外部模型输出挑样本。
3. **相同运行时。** 优先 Linux、Python 3.11、与待投任务一致的 TShark/NumPy/Torch 和依赖树；如本地 WSL 具备完全匹配环境可在本地完成，否则下次经授权的小额工程预检在超算完成。不能以“尽量相同”掩盖未核验的版本差异。
4. **完整链路。** 使用实际解码器、实际 descriptor、冻结编码器、真实距离和评价函数，写出独立工程命名空间的最终回执；不以 mocks 或缓存数组跳过某阶段后声称端到端通过。固定科学参数，只检测兼容性、身份、维度、有限值、计数和落盘/取回一致性，不用预检质量指标改方法。
5. **失败与续跑。** 合成层另测未知诊断、缺字段、坏 SHA、部分写入、超预算、进程异常、提交不确定性；真实层验最小正常完成和保存后重载。故障注入和已有恢复测试不得混进真实模型通过数量。已完成输出只按原校验复用，旧文件不覆盖，超预算只留现场与余量，不自动重投。
6. **写明预算和结论。** 开跑前确定切片大小、编码行数、距离对数、CPU/RSS/磁盘/总钟上限；超限或任一阶段缺失即 `FAIL`。只有完整实跑且所有必需阶段通过才可写 `REAL_SLICE_E2E_PASS`；否则写 `NOT_RUN` / `PARTIAL` / `FAIL` 和具体缺项。

实际预检接入后，长作业提交器必须验证同一交付物的通过回执、固定预算和工件哈希。该门本轮尚未接入，不能声称已强制执行。

## 4. 永久失败账本与回归注册

每次失败保留一行：`failure_id / job_id / phase / symptom / verified_cause / observed_or_inferred / could_preflight_catch / check_path_and_case / check_type(synthetic|real_slice|full_scale) / input_provenance / fixed_artifact_sha / executed_at / outcome / remaining_gap`。

本节表格是五项历史问题的初始账本；下一次 runner 改动时将其转成机器注册表，由提交门检查每项有对应检查及最近执行证据。已有测试只登记已证实覆盖的范围，尤其不能把 mock 内存测试当成全捕获资源证明。登记只引用既有失败文件，不回写封存失败。

## 5. 预算必须分开记，但不得虚构历史拆分

旧失败任务包含后来复用的有效科学输出。**不能把“失败任务总耗时”全部算作工程浪费，也不能把追加 18,000 秒全部说成工程失败成本。** 现有资料不足以把总计 40,235.79058704007 秒精确拆成科学秒与工程秒。

可确证的历史量：旧计费逻辑尝试 25,154 行，持久化复用 20,480 行；废弃/未持久化计费差额 **4,674 行**（包含保守计费的未配对 16 行 ATTEMPT）。新增 12,288 行；累计计费 37,442 行，实际持久化唯一行 32,768。**逻辑行数不等于前向调用次数，也不能无逐批计时直接折算秒数。** 最终验收中的 `new_model_forwards=0` 只指独立保存数组复核，不是整轮 C4 没用模型。

以后每阶段同时记录 UTC 与单调时钟起止，并用不重叠的顶层时间段汇总：

- `scientific_new_seconds`：成功并持久化的新科学计算；
- `scientific_reused_from_failed_jobs_seconds`：失败任务中已完成且后续复用的科学计算，引用原记录，不重复计时；
- `engineering_failed_discarded_seconds`：可定位且未形成可复用产物的失败工作；
- `engineering_preflight_setup_seconds`：测试、环境检查、设置与启动；
- `transfer_orchestration_seconds`：上传、取回、调度控制等；
- `unattributed_seconds`：旧账缺观测或仍不能归属的时间，必须保留；
- `queue_seconds` 单列且不混入授权执行钟，CPU 秒与 wall 秒另列，嵌套子进程不重复加总。

失败/复用分类变化须通过产物 SHA 和引用记账，不修改原任务耗时。总钟以既有全链路 deadline 为准；若保守计费高于观测时间，另列 `observed`、`charged` 与差额，不混用。用户只需看到已花/剩余预算、完成到哪、补完估计、可复用什么。

## 6. 完成顺序

| 阶段 | 本轮状态 | 完成标准 |
|---|---|---|
| 只读复核五故障、定位现有检查、校对预算 | 已完成 | 本计划与 `EVIDENCE.json` 可定位至既有文件 |
| 独立公共预检入口、注册表、计费字段 | 待下次 runner 工程实现 | 不改冻结科学参数，真实/合成明确分栏；提交门读取强制凭证 |
| 相同运行时真实切片实跑 | 尚未执行 | 同一交付物的完整真实链路回执及资源记录 |
| 后续阶段节点沿用 | 后续执行 | 每次冻结/验收/失败封存进 git，普通运行有进度页后不持续 AI 监测 |

本轮对文件的唯一写入范围为本目录的新计划与证据；没有科学执行或云端操作。
