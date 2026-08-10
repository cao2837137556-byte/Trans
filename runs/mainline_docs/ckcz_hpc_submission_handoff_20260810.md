# CKCZ HPC 提交交接（2026-08-10，已作废）

状态：**REVOKED AFTER JOB 158015 ENGINEERING FAILURE — DO NOT RUN — DO NOT RESUBMIT R1**

> 本文命令只对应 SHA `9c3da516...` 的 r1 bundle。该实现错误地把 Gotham UID 尾段当作
> recorded_index，job 158015 已在严格 join 处 fail-closed。本文以下内容仅保留为提交历史，
> 不再构成可执行指令。修复必须走 erratum、r2 bundle、Kimi 新审查与用户重新授权。

## 1. 已解除的门

- implementation Kimi final review：PASS（commit `68ceb00`）；
- bundle Kimi final review：PASS（commit `8e5a245`）；
- auxiliary 登录节点在线门：PASS，`NPZ_COUNT=31`（commit `9bebb67`）；
- 唯一有效 bundle SHA-256：
  `9c3da516cea92227c770b59d3279c258da5f3803ddd961edfe7334a8d1429085`；
- bundle commit：`62f929c0c738440b7e534a1d4830412f63475c70`。

用户在远端执行第 3 节中显式包含 `CKCZ_SUBMIT_AUTHORIZATION=YES` 的命令，即构成对这一份
AMD seed-27 只读诊断作业的提交授权。命令生成与文档落库本身不提交作业。

## 2. 本地 PowerShell：上传两份文件

在**本地 Windows PowerShell 终端**执行：

```powershell
$ckczTransfer = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
$ckczArchive = Join-Path $ckczTransfer 'issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_upload_bundle.tar.gz'
scp $ckczArchive "${ckczArchive}.sha256" school-hpc:~/work/
if ($LASTEXITCODE -ne 0) { throw "CKCZ upload failed: exit $LASTEXITCODE" }
```

## 3. 远端 VS Code HPC Bash：验包并提交

上传成功后，在当前已登录的 HPC Bash 终端整段粘贴：

```bash
(
set -euo pipefail
CKCZ_WORK=/public/home/jiangxinwei.zr/work
CKCZ_ARCHIVE="$CKCZ_WORK/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_upload_bundle.tar.gz"
CKCZ_SIDECAR="$CKCZ_ARCHIVE.sha256"
CKCZ_INSTALL_ROOT="$CKCZ_WORK/upload_issue27ckcz_20260810"
CKCZ_BUNDLE_ROOT="$CKCZ_INSTALL_ROOT/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810"

test -s "$CKCZ_ARCHIVE"
test -s "$CKCZ_SIDECAR"
( cd "$CKCZ_WORK" && sha256sum -c "$(basename "$CKCZ_SIDECAR")" )
test ! -e "$CKCZ_INSTALL_ROOT" || {
  echo "Refusing existing CKCZ install root: $CKCZ_INSTALL_ROOT" >&2
  exit 2
}
mkdir -p "$CKCZ_INSTALL_ROOT"
tar -C "$CKCZ_INSTALL_ROOT" -xzf "$CKCZ_ARCHIVE"
test -s "$CKCZ_BUNDLE_ROOT/SHA256SUMS"

CKCZ_SUBMIT_LOG="$CKCZ_INSTALL_ROOT/ckcz_submit_$(date -u +%Y%m%dT%H%M%SZ).log"
CKCZ_SUBMIT_AUTHORIZATION=YES \
CKCZ_RUNTIME_GATE_SECONDS=3600 \
bash "$CKCZ_BUNDLE_ROOT/payload/scripts/issue27ckcz_install_and_submit.sh" \
  2>&1 | tee "$CKCZ_SUBMIT_LOG"
echo "CKCZ_SUBMIT_LOG=$CKCZ_SUBMIT_LOG"
)
```

这是 result-producing chain，不是单独 preflight：installer 会先做包内 15/15 SHA、冻结输入 SHA、
Gotham 29 / auxiliary 31 在线门、18 项合同测试和 `sbatch --test-only`，随后只提交一份 AMD
作业。job id 原子落盘，重复执行不会重复提交。runtime gate 只有在真实诊断返回且 post-result
validator 通过后才 PASS。

## 4. 回传要求

把远端整段输出发回 Codex，至少应包含：

- `CKCZ_CACHE_ONLINE_GATE_PASS`；
- 合同测试 `status: PASS`；
- scheduler dry validation 成功；
- `CKCZ_AMD_JOB_ID=<数字>`；
- `CKCZ_SUBMISSION_RECORDED`；
- 后续 `CKCZ_RUNTIME_GATE_PASS` 或明确的 queued/running 状态。

任何非零退出、`CKCZ_RUNTIME_GATE_FAIL`、`job_failure.txt` 或 Slurm 失败状态都按工程失败处理，
不得解释为科学 verdict，也不得直接重提。
