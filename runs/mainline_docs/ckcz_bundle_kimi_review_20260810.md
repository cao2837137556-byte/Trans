# CKCZ bundle 终审意见 — Kimi

日期：2026-08-10 | 审查者：Kimi | 对象：bundle `issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_upload_bundle.tar.gz`（HEAD `1bacc47`，bundle commit `62f929c`）

**总体结论：PASS。bundle 审查门解除。剩余唯一门：用户明确授权 HPC 提交。**

---

## 1. 独立复核明细（全部本地实测，非转述）

| 审查项（交接文档 §3） | 方法 | 结果 |
|---|---|---|
| 1. archive SHA | 本地重算 | `9c3da516…9085` 一致 ✓；bytes 38,279 一致 ✓ |
| 2. 包内哈希链 | 解包至独立临时目录执行 `sha256sum -c SHA256SUMS` | 15/15 全 OK ✓ |
| 3. bundle_commit | 读文件 | `62f929c0c738440b7e534a1d4830412f63475c70` ✓ |
| 4. member 集合 | 逐文件清点 | 严格 16 个：2 Python + 3 运行脚本 + 9 文档/侧车 + bundle_commit + SHA256SUMS；无 `.pyc`/`__pycache__`；CR 检查 0 ✓ |
| 4b. 内容真实性（加审） | 8 个 payload 文件与 git HEAD 逐一 `cmp` | 全部**逐字节一致** ✓ |
| 5. installer 授权门 | 通读 208 行 | 未设 `CKCZ_SUBMIT_AUTHORIZATION=YES` 时仅 `sbatch --test-only` 干跑，随后 exit 3，**不可能正式提交**；job id 持久化防重复提交 ✓ |
| 6. Slurm 门序与双重在线门 | 通读 206 行 + validator 180 行 | validator 在 `validate_result` 阶段运行，runtime gate 要求 phase≥resource_accounting，即 **validator 不过则无 gate PASS**；aux 31-NPZ 门在 installer（L70）与计算节点（L148）**各执行一次** ✓ |

## 2. 额外确认

- 三份脚本内全部钉死 SHA 与我此前复核值逐一相符（prereg `dad55890…`、predictions `d1e90592…`、两 manifest、两 allowlist）。
- Slurm 参数与 FROZEN 一致：`--gotham-sources 24 --gotham-rows 317523 --auxiliary-sources 31 --auxiliary-rows 18600 --seed 27 --bootstrap-reps 200`。
- validator 科学合同完备：verdict 状态与 feasibility 一致性、metadata 336,123 = 317,523+18,600、state 297,326、每 scalar 16 family × 全 frontier、4 池 × 全 frontier、每点 12 行 bootstrap、禁止 record 级 cluster、输出名 FINAL 扫描。
- 60 秒心跳（phase + 日志字节数）可支撑用户实时监控，解决此前"假运行 9 小时"的隐患。
- `--no-requeue`、拒绝复用陈旧 run root，失败时 `job_failure.txt` + 日志保留，符合失败语义。
- 首包含 bytecode 被拒并重打的过程记录于工程文档，当前包验证干净，处理得当。

## 3. launch blocker 状态

- auxiliary cache 登录节点在线门：**已解除**（`ckcz_auxiliary_cache_online_evidence_20260810.md`，NPZ_COUNT=31，commit `9bebb67`）。
- 剩余唯一门：**用户明确授权 HPC 提交**。用户授权后，提交命令需带 `CKCZ_SUBMIT_AUTHORIZATION=YES`。

## 4. 授权边界

本 PASS 仅解除 bundle 审查门，不构成 HPC 提交授权。提交后作业为只读诊断：不训练、不解码 PCAP、不触碰 FINAL（cooler-motor、seed 37/47）。
