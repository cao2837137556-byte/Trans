# CKCZ r2 HPC 重新提交授权交接（2026-08-10）

状态：**KIMI R2 BUNDLE PASS + USER RESUBMISSION AUTHORIZED；READY TO RUN COMMANDS**

## 1. 授权与范围

- Kimi r2 bundle 终审：PASS，commit `dd3474c`；
- 用户于 2026-08-10 明确授权重新提交；
- 唯一有效 bundle SHA-256：
  `4c29122a7844b0a772a9bad759e86ce6ede2ed9e2d842e90b8a7de33c490fc96`；
- bundle commit：`02258c43b255ccb9619ec6c5bff597f4fb5ab26f`；
- 仅提交一份 AMD seed-27、只读、result-producing 的 CKCZ Oracle 诊断；
- 不训练、不解码 PCAP、不触碰 cooler-motor、seed 37/47 或任何 FINAL 数据。

job 158015 在 `join_predictions` 阶段 22 秒即工程失败，没有完整运行的 MaxRSS/TotalCPU
证据可用于安全缩容。本次保持已审查的 `8 CPU / 32 GB / 8 h` 上限；这是资源上限，
不是预期耗时。

## 2. 本地 Windows PowerShell：上传 r2 两个文件

```powershell
$ckczTransfer = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
$ckczArchive = Join-Path $ckczTransfer 'issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r2_upload_bundle.tar.gz'
scp $ckczArchive "${ckczArchive}.sha256" school-hpc:~/work/
if ($LASTEXITCODE -ne 0) { throw "CKCZ r2 upload failed: exit $LASTEXITCODE" }
```

## 3. 已登录的 HPC Bash：验包、真实输入门、提交并等待结果门

上传成功后整段粘贴：

```bash
(
set -euo pipefail
CKCZ_WORK=/public/home/jiangxinwei.zr/work
CKCZ_ARCHIVE="$CKCZ_WORK/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r2_upload_bundle.tar.gz"
CKCZ_SIDECAR="$CKCZ_ARCHIVE.sha256"
CKCZ_INSTALL_ROOT="$CKCZ_WORK/upload_issue27ckcz_r2_20260810"
CKCZ_BUNDLE_ROOT="$CKCZ_INSTALL_ROOT/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r2"

test -s "$CKCZ_ARCHIVE"
test -s "$CKCZ_SIDECAR"
( cd "$CKCZ_WORK" && sha256sum -c "$(basename "$CKCZ_SIDECAR")" )
test ! -e "$CKCZ_INSTALL_ROOT" || {
  echo "Refusing existing CKCZ r2 install root: $CKCZ_INSTALL_ROOT" >&2
  exit 2
}
mkdir -p "$CKCZ_INSTALL_ROOT"
tar -C "$CKCZ_INSTALL_ROOT" -xzf "$CKCZ_ARCHIVE"
test -s "$CKCZ_BUNDLE_ROOT/SHA256SUMS"

CKCZ_SUBMIT_LOG="$CKCZ_INSTALL_ROOT/ckcz_r2_submit_$(date -u +%Y%m%dT%H%M%SZ).log"
CKCZ_SUBMIT_AUTHORIZATION=YES \
CKCZ_RUNTIME_GATE_SECONDS=3600 \
bash "$CKCZ_BUNDLE_ROOT/payload/scripts/issue27ckcz_install_and_submit.sh" \
  2>&1 | tee "$CKCZ_SUBMIT_LOG"
echo "CKCZ_SUBMIT_LOG=$CKCZ_SUBMIT_LOG"
)
```

该链不是单独 preflight：installer 会先验证 bundle 19/19 SHA、冻结输入及 lineage snapshot
双钉 SHA、Gotham 29 / auxiliary 31 cache、19 项合同测试、真实 253,326 Gotham 行
lineage miss=0 与 `sbatch --test-only`，然后提交一份真实诊断作业。只有真实诊断完成且
post-result validator 通过，runtime gate 才会 PASS。r2 的 job-id 文件在独立 install root
内原子落盘，重复执行不会重复提交。

## 4. 回传与失败纪律

把远端整段输出发回 Codex。至少应包含：

- `CKCZ_CACHE_ONLINE_GATE_PASS`；
- 19 项合同测试的 `status: PASS`；
- `CKCZ_REAL_LINEAGE_GATE_PASS ... missing=0`；
- scheduler dry validation 成功；
- `CKCZ_AMD_JOB_ID=<数字>`；
- `CKCZ_SUBMISSION_RECORDED`；
- `CKCZ_RUNTIME_GATE_PASS`，或明确的 queued/running 状态。

任何非零退出、`CKCZ_RUNTIME_GATE_FAIL`、`job_failure.txt` 或 Slurm 失败均只按工程失败处理：
保留日志、分类根因、补永久回归门，不得解释为科学 verdict，也不得未经新审查直接重提。
