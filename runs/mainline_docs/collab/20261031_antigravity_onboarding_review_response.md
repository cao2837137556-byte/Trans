# Antigravity：接手理解与 C1 / P-DEVONLY 实现及本地交付独立审查回执

日期：2026-10-31  
审查角色：Antigravity（只读接手与独立工程/科学合同审查；未修改任何封存实现或配置，未读取或解码真实科学 PCAP/查询载荷，未操作界面，未上传或提交超算作业）

---

## 1. 当前阶段理解：本轮方法、最近可信 A/B 基线与未知项

1. **最近可信基线（Job `179700`，`R-DENSE`）**：在冻结 netFound/E3（768 维近期表示）+ 14 维当前包描述 `q14` + 冻结 `QUERY_TAIL` 三头（seeds `27/127/227` 及固定阈值集成）+ v3 因果双距离几何支持（源 CAL 标定工作点 `λ = 0.25`，不重训头、不改源库 4,728 行、不重标定 `cuts/geometry/scales`）下，主评价视图 `post_window_primary` 的加权误报率与攻击召回为：
   - **Pool A（`CIC_DEV`）**：池级加权 FPR `3.993482%`，攻击召回 `100%`；其中 `Eufy Home Base` 为 `0.000232%`，误报集中在 `HeimVision Camera`（`7.986731%`）。
   - **Pool B（`UNSW_DEV`）**：池级加权 FPR `9.519654%`，攻击召回 `99.966594%`（保留基础头既有漏检，入网零新增攻击撤回）；其中 `WEMO Motion`（`1.187678%`）与 `Netatmo`（`1.012557%`）已低于 2%，残留误报集中在 `WEMO Power`（`26.564538%`）、`Samsung`（`9.544740%`）、`TP Link`（`9.288756%`）。
   - **视图口径边界**：在包含观察窗口内早期 `support = 0` 查询的 `full` 视图下，本轮不触碰的 `Eufy`（`3.772559%`）与 `WEMO Motion`（`2.165410%`）基线已高于 2%；因此本轮以 `post_window_primary` 作为 `PASS` 主判据，同时并列完整报告 `full` 视图，不混用按条数口径与分层加权口径。

2. **本轮方法（`C1 / P-DEVONLY`）**：不动检测头权重、源参考库与源侧校准参数，仅对上述 4 台高误报目标设备补充严格早于查询期的可信历史正常参考，检验误报瓶颈是否主要源于历史正常组件/模式覆盖不足：
   - **Pool A（`HeimVision Camera`）**：直接复用 `CIC_DEV_OLD_BANK` 中已编码封存的 11 条 2021-10-06 历史正常参考（1 TCP + 10 UDP，早于 2021-10-12 起的查询期，为 `HeimVision` 补齐触发 v3 第二异组件规则所需的第 2 个 TCP 组件），零重新解码、零重算 E3。
   - **Pool B（`TP Link`、`WEMO Power`、`Samsung`）**：采用 Dryad 官方 UNSW IoTraffic 2025 原始混合捕获（总计 `10,233,818` 包），依据已核验的 `packet_index.npy` 与 `chronological_order.npy` 生成逐块字节保留的连续有序 `chronological.pcapng`；在单一冻结 `Contexts`（`continuous_input_v3` RECENT，>60s 空闲重置，无按小时或 REF/DEV 角色边界重置）上做两遍未过滤 `tshark` 完整遍历。按非空观测 UTC 日期前 80% / 后 20% 切分为 `HIST_REF`（每 `(device, protocol)` 上限 `4,096`，优先分配 `no_old_anchor` 新组件后按确定性组件序轮转 + 精确 `_uniform_time_db` 时间均匀抽样，总上限 `24,576`）与 `HIST_DEV`（每设备跨双协议总上限 `4,096`，总上限 `12,288`），复用冻结 netFound/E3 单进程编码（含 `B1 → 16` 物理克隆逐字节一致性修复，逻辑计账仅留 1 条 UID）。
   - **双截止因果隔离与单次门控顺序**：先用带真实历史截止（`reference_end = reference_end_us / 1e6`）的 `HIST_DEV_BANK` 对 `HIST_DEV` 正常查询评分并检验 `DEV` 门（三设备均存在原始误报 `raw_fp > 0`、每设备修正后严格降误报、按选中行数加权总体相对 FPR 降幅 `≥ 50%`）。任一 `DEV` 条件不满足立即以 `STOP_DEV_FAIL` / `STOP_DEV_NO_ROOM` 终止，**绝不加载 A/B 查询载荷**。仅当 `PASS_DEV` 时，将历史参考并入原 `26,549` 行密参考（合库中新增历史行的 `reference_end` 统一对齐原池 B2 截止并保留各自 `capture_id` 帧界），仅重算 4 台目标设备的 own-bank support，其余未补设备直接复用 `179700` 支持度与判决并强校验逐位一致，执行单次终评且设全局 `EXECUTION_ATTEMPT.json` 锁禁止换目录重跑或看目标结果调参。

3. **当前已知与未知边界**：
   - **已完成**：冻结协议绑定、原始 PCAP/时间索引核验、`runs/history_normal_reference_v1_20261031/` 实现与本地 Python 3.10 合成测试（56/56）、`runs/history_normal_reference_deployment_20261031/` 本地路径重定位交付构建与部署测试（4/4）。
   - **尚未知（全部为 0 / 未发生）**：远端文件上传 `0`、远端超算 Python 3.11.11 + `numpy201` 环境实测 `0`、Slurm 作业提交 `0`（无 `job_id`）、真实历史包 `tshark` 解码 `0`、真实新增 E3 前向 `0`、`HIST_DEV` 门是否通过未知、2016–2017 历史正常几何能否覆盖 2018 A/B 残留误报并把双池及全部原设备 `post_window_primary` 加权 FPR 压到 `≤ 2%` 同时守住四后缀累计攻击召回/零低召回 TP 撤回**完全未知**。

---

## 2. 独立工程与科学合同核查结论

**未发现阻塞项。**

独立逐文件核查了 `runs/history_normal_reference_v1_20261031/`、`runs/history_normal_reference_deployment_20261031/` 及上游 `repo/ood/`、`runs/dense_reference_ab_stage_candidate_v1_20261028/src/` 的调用闭包与封存清单，未发现会阻断上传/运行、破坏因果与冻结科学合同、或造成口径误读的硬伤。关键高风险接口核验摘要如下：

| 核查维度 | 核对文件与位置 | 独立核验事实 |
|---|---|---|
| 封存哈希、路径修正链与 LF 脚本 | `collab/*r2*.md`、原包与重定位 `CODE_MANIFEST.json`、`DELIVERY_INPUTS.json`、`decoder_mapping_correction/`、`transport/`、`hpc/run_history.slurm` | r2 原文（`dc566523...`）、复核稿（`f73c0bdd...`）、原科学包 `CODE_MANIFEST.json`（`31ab70c4...`）未变；交接稿记录的首版重定位快照（`d64f2e80...` / `f7897396...`）完整保存在 `decoder_mapping_correction/*.original.json`，当前交付已由 `map_verified_decoder.py` 修正 `tshark` 路径并更新为重定位 `CODE_MANIFEST.json` `5f6156601d0d3d9223c7ca7646b3b6e21547c5d703e4ef9046e6a08e81b1a0a3`、`DELIVERY_INPUTS.json` `95bf17e2be0a46cedff33cd2efe15f73975eaa99c111354e75a96658093242e9`（与 `BUILD_RECEIPT.json`、`local_client.py:13`、`remote_receiver.py:17` 一致）；1,361 个代码封印键仅 `config/EXECUTION.json` 改变；两处 `.slurm` 均为纯 LF（`CR=0, LF=43`）。 |
| 整成员连续上下文与防预筛 | `hnr/history.py:28-57, 79-105, 138-190, 239-258`；`repo/ood/continuous_input_engineering_v1.py`；`repo/ood/spill_mapping_v1.py` | `chronological_copy` 校验 SHB/IDB/EPB 偏移、微秒时间戳与捕获长度；两遍解码均把每条未过滤帧先送入同一 `Contexts.append`（保留缺头污染传播及跨角色边界 4.80s / 51.81s 连续状态），并强校验 Pass 1/2 `legal_endpoints` 与 `frontend_reasons` 完全一致。 |
| 确定性有界选点与独立回放 | `hnr/selection.py:23-119, 121-225`；`hnr/encoding.py:76-83` | `_uniform_time_db` 精确复现 `binding._uniform_time` 贪心区间与 `(abs(t - target), rank, uid)` 决胜规则；SQLite 临时表置于进程内存（`PRAGMA temp_store=MEMORY`），纳入 `Runtime` 16 GiB RSS 守卫；编码前独立二次回放 `select_candidates` 校验 `uid_sha256` 与行内容。 |
| 角色描述符、单编码器与克隆修复 | `hnr/encoding.py:11-27, 55-153`；`run.py:103-119` | `REFERENCE` 与 `QUERY` 分别调用 `reference_descriptor` / `query_descriptor` 并复核 `q14`；单编码器实例跨三成员复用后 `del encoder` 释放内存；`logical == 1` 时构造 16 份完全相同输入并校验 16 行输出 `tobytes()` 逐字节相等，逻辑行数计入 `36,864` 上限，物理位置单独记账。 |
| 双截止合库、重叠审计与基线回放 | `hnr/evaluation.py:128-188, 260-280, 308-372`；`repo/ood/constrained_onboarding_core_v3.py:164-198` | `DEV` 门失败直接在 `run.py:126-128` 终止，不构造 A/B 加载器；`union_bank` 保持原密库 `26,549` 行字节不变，`HeimVision` 11 条旧行不含 `bank_end_frame: None` 脏键，合库通过 `ReferenceBank(..., allow_prebank_history=True)` 及 `causal_reference_overlap_v1.py` 检查；未触碰设备支持度与修正后四后缀判决强制 `np.array_equal` 对齐 `179700`。 |
| 四后缀累计保护与终评判据 | `hnr/evaluation.py:191-258` | 保护门覆盖全部四后缀（`27/127/227/ensemble`），直接相对 `RAW` 基础头检验累计撤回（设备损失 `≤ 1pp`、攻击活动/标注组损失 `≤ 5pp`、且 `raw_recall < 0.99` 组零 TP 撤回用整数正例计数避免浮点舍入漏检），不设池级攻击损失容差；`PASS` 严格要求双池与全部原始正常评估设备 `post_window_primary` 加权 FPR `≤ 2%` 且池召回 `≥ 99%`。 |
| 超算环境、传输桥与单次提交锁 | `staged_root/.../EXECUTION.json:123`；`remote_preflight.py`；`submit_once.py`；`transport/{local_client,remote_receiver}.py` | 重定位后 `tshark` 指向超算已实测通过的 `/share/software/tshark-4.6.6/bin/tshark`（消除了首版默认 `/usr/bin/tshark` 在超算缺失的潜在阻断），配合 `frontend_compat_v1/environment.sh`（SHA `8da8564e...`）、Python `3.11.11` 与私有 `numpy201` overlay；峰值中间盘（Samsung 阶段约 `11.2 GiB`）在 `20 GiB` 输出守卫内且逐成员释放 4 个中间大文件；`SUBMISSION_LOCK.json` 与 `EXECUTION_ATTEMPT.json` 均采用 `open('x')` 独占锁且未知状态零自动重提。 |

**附：非阻塞台账说明（无需改动封存文件）**：`map_verified_decoder.py:39-47` 在更新 `DELIVERY_INPUTS.json` 的 `files[]` 两项条目（`config/EXECUTION.json` 与 `CODE_MANIFEST.json`）及同步更新 `BUILD_RECEIPT.json` 时，未同步刷新 `DELIVERY_INPUTS.json` 顶层摘要字段 `relocated_code_manifest_sha256`（仍为首版 `d64f2e80...`，实际条目与 `BUILD_RECEIPT.json` 为 `5f615660...`）与 `total_unique_bytes`（仍为 `5720467819`，实际 `files[]` 求和与 `BUILD_RECEIPT.json` 为 `5720467843`，差值为 `tshark` 路径字符串增长 24 字节）。经逐行核对 `local_client.py:102`、`remote_receiver.py:78-90`、`install_delivery.py:23-50` 与 `remote_preflight.py:65-79`，四处执行器均直接读取并校验 `files[]` 明细，不读取上述两个顶层摘要字段，**不影响上传、安装、预检或运行，当前不应为修顶层描述重刷 `MANIFEST_SHA`（`95bf17e2...`）**；此处仅作审计备忘，避免后续人工复核误判为封印不一致。

---

## 3. 后续应验收的具体结果（无需再写原则确认稿）

由 Codex 按既有单次交付链继续推进；后续仅针对真实运行产物逐项验收以下具体证据：

1. **远端安装与只读预检回执（提交前必验）**：
   - `install_delivery.py` 回执：`status == "INSTALLED_WITHOUT_OVERWRITE"`，全部 `1,433` 个文件 SHA/字节核验通过、既有同路径文件零覆盖。
   - `remote_preflight/PREFLIGHT_RESULT.json`：`status == "PASS"`，确认超算实际运行环境为 `Linux / Python 3.11.11 / NumPy 2.0.1 / Torch 2.5.1`，`input_readiness == "READY"`（`blockers == []`），远端合成测试 `56/56 OK`，且预检前后 `seals` 未变、`real_packet_decodes == 0`、`real_model_forwards == 0`。

2. **单次提交与运行期资源/完整性回执**：
   - `SUBMISSION_RECEIPT.json`：唯一真实 `job_id` 与独占锁记录。
   - `outputs/c1_once_20261031/` 下各成员 `PREPARE_RESULT.json`、`ENCODE_RESULT.json`、`INTERMEDIATE_CLEANUP.json` 以及总 `STAGE_RECEIPT.json`：核对 Pass 1/2 合法端点计数一致、新增逻辑 E3 行数 `≤ 36,864`、距离对数 `≤ 579,614,444`、进程树峰值 RSS `≤ 16 GiB`、输出峰值磁盘 `≤ 20 GiB`、运行前后代码与输入资产 SHA 未变。

3. **科学门控与终评结果（按实际停止位置如实判读）**：
   - **先验 `DEV_RESULT.json`（及 `dev/AUDIT_RECEIPT.json`）**：核对 `TP Link`、`WEMO Power`、`Samsung` 各自选中行数、新覆盖 `no_old_anchor` 组件数、原始与修正后 `HIST_DEV` FPR 及总体加权相对降幅。若触发 `STOP_DEV_NO_ROOM` 或 `STOP_DEV_FAIL`，确认 `AB_evaluated == False` 且未生成 `ab/` 目录，直接按独立历史开发门失败收口诊断。
   - **若进入 `ab/RESULT.json`**：同时核对 ① 四后缀（`27/127/227/ensemble`）在 A/B 双池的 `protection` 是否全部 `PASS`（特别是低原始召回分组零 TP 撤回）；② 未触碰设备（`Eufy`、`WEMO Motion`、`Netatmo`）判决与 `179700` 是否 `untouched_decisions_exact == True`；③ `post_window_primary`（主判据）与 `full`（并列对照）下双池及逐设备加权 FPR、攻击召回相对 `179700` 的精确变化，明确区分 `PASS`、`IMPROVED_NOT_PASS`、`NOT_IMPROVED` 或 `FAIL_PROTECTION`，并据此规划下一阶段实验或论文消融叙事。
