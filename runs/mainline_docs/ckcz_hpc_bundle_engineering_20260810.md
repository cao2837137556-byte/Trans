# CKCZ HPC bundle 工程闭环（2026-08-10）

状态：**SLURM / INSTALLER / VALIDATOR / BUILDER IMPLEMENTED — BUNDLE BUILD PENDING — HPC NOT SUBMITTED**

上游授权：Kimi 已在
`ckcz_implementation_kimi_final_review_20260809.md`（commit `68ceb00`）独立复跑
18 项合同测试并给出 PASS，授权编写 Slurm、installer、validator 与构建 bundle；HPC 提交仍须
用户另行明确授权。

## 1. 新增工程文件

- `scripts/issue27ckcz_endpoint_pair_conflict_diagnostic_formal.slurm`
- `scripts/issue27ckcz_install_and_submit.sh`
- `scripts/issue27ckcz_validate_and_pack_seed27.sh`
- `scripts/issue27ckcz_build_bundle.ps1`

## 2. 运行边界

- 只提交 AMD 一份基础设施运行，不把硬件副本计作科学 seed；seed 固定为 27。
- 只读 CKBV 154917 的两个 causal cache 与 CKBW 157624 的冻结预测表；不训练、不重解码
  PCAP、不写回冻结输入。
- 仅从正向 allowlist 打开 Gotham 24 与 auxiliary 31 个 source；所有冻结 SHA、逐缓存 hash、
  schema、target 行数由正式实现再次 fail-closed 核验。
- cooler-motor 与 seed 37/47 不进入参数、allowlist、缓存打开、导出或日志。
- 输出根必须全新；工程失败保留 failure marker 且不得留下科学 verdict。

## 3. Auxiliary launch blocker 的永久门

installer 与 Slurm 计算节点均要求：

- `auxiliary_causal_cache/` 在线且恰有 31 个 NPZ；
- auxiliary manifest SHA 固定为
  `f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43`；
- 正式实现逐 allowlisted NPZ 验 SHA/schema/行数后才能输出 metadata。

登录节点存在性截图仍须在提交前由用户提供。截图不是科学证据；真正运行还会在计算节点重复
相同在线门，避免“登录节点可见、计算节点不可见”的静默落差。

## 4. Post-result validator

validator 在打 pullback 前独立验证：

- core `SHA256SUMS` 全通过；
- 297,326 状态行、五协议分母、336,123 metadata 行、55 source；
- metadata miss 只能等于冻结 ToN expected miss，unexpected miss 必须为 0；
- 四个且仅四个 scalar，每个 frontier 的 16 family、4 OOD pool、12 bootstrap 行完整；
- bootstrap 仅 source/pair cluster，200 reps；所有 cut 均为
  `FORBIDDEN_FOR_SELECTION`，review rate 为 0；
- verdict 只能是 `CKCZ_ORACLE_INFORMATION_EXISTS_LEGAL_NOT_TESTED` 或
  `CKCZ_ORACLE_NO_INFORMATION`，且须与四条 frontier 的可行性一致。

只有 validator PASS 后 phase 才进入 `resource_accounting`；installer 的 runtime gate 也只在该
阶段后返回 PASS。因此 `sbatch` 接收、heartbeat 或刚进入 Python 都不算运行成功。

## 5. 资源与产物

CKBW 157624 的冻结全链运行实测约 22 分钟；CKCZ 不训练，但增加四条全量 frontier 与每点
200-rep source/pair bootstrap。正式请求采用 8 CPU、32 GiB、8 小时时限，作为避免 bootstrap
峰值和极端 frontier 数的保守上界，不据此声称实际资源消耗。正式产物必须写出 wall time、
`sstat`/`sacct` 的 MaxRSS/TotalCPU/Elapsed 证据，结果后再按真实值校准后续任务。

bundle builder 只打包 CKCZ 自有的 14 个已审文件，执行 18 项合同测试、LF 归一化、冻结侧车
复核、全包 SHA256SUMS，随后将 tar 解到第二临时目录逐文件复验。临时目录删除前要求解析后的
绝对路径位于 Windows TEMP 且 leaf 精确匹配，避免宽路径递归删除。

## 6. 当前授权边界

本文件授权范围只到本地验包、commit、push 和交给 Kimi 独立审 bundle。installer 还设置了
第二把机械锁：未显式提供 `CKCZ_SUBMIT_AUTHORIZATION=YES` 时，即使全部预检通过也以
`CKCZ_HPC_SUBMISSION_NOT_AUTHORIZED` 退出且不调用正式 `sbatch`。

当前仍然：**HPC NOT SUBMITTED**。

## 7. 本地首包拒收与永久回归门

commit `8cb7ae2` 后的首次本地构建虽然逐文件 SHA 复验通过，但独立 tar member audit 发现合同
测试的 Python import 在 staging 内生成了未审的 `__pycache__/*.pyc`。分类为
**package/transfer validation failure**：没有上传、安装或提交 HPC，不构成任何科学证据；该首包
立即拒收。

根因是 builder 在 staging 内运行测试时没有禁止 bytecode 写入，而当时的 SHA 逻辑会忠实地把
新增文件一并纳入，故“SHA 全通过”不能替代“成员集合精确”。永久修复为：测试时强制
`PYTHONDONTWRITEBYTECODE=1`，随后显式拒绝任何 `__pycache__`/`.pyc`，并断言最终文件数严格
等于 14 个 reviewed copy + `bundle_commit.txt` + `SHA256SUMS`。只有修复后的重建包可交 Kimi
审查。
