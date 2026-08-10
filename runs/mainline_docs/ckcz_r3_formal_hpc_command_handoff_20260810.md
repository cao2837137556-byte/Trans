# CKCZ r3 正式 HPC 命令交接（2026-08-10）

前提：Kimi 彩排审查 PASS；用户提交授权已记录于 commit `2e45f42`。唯一授权任务为
r3 / AMD / seed 27 / formal bootstrap 200。

## 1. 本地 PowerShell：上传唯一有效 r3 包

```powershell
$ErrorActionPreference = 'Stop'
$ckczTransfer = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
$ckczArchive = Join-Path $ckczTransfer 'issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3_upload_bundle.tar.gz'
$ckczSidecar = "${ckczArchive}.sha256"
$ckczExpected = '0f68b154f0d2c45cc5520e25746d30a273a096a8026cf0df6fdbb1c1d8e9d59c'
$ckczActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ckczArchive).Hash.ToLowerInvariant()
$ckczSidecarExpected = ((Get-Content -Raw -LiteralPath $ckczSidecar).Trim() -split '\s+')[0].ToLowerInvariant()
if ($ckczActual -ne $ckczExpected -or $ckczSidecarExpected -ne $ckczExpected) {
    throw "CKCZ r3 local SHA mismatch: actual=$ckczActual sidecar=$ckczSidecarExpected"
}
scp $ckczArchive $ckczSidecar school-hpc:~/work/
if ($LASTEXITCODE -ne 0) { throw "CKCZ r3 upload failed: exit $LASTEXITCODE" }
"CKCZ_R3_UPLOAD_PASS sha256=$ckczActual bytes=$((Get-Item -LiteralPath $ckczArchive).Length)"
```

## 2. 已登录 HPC Bash：验包、正式提交、监控到终态并验证 pullback

```bash
(
set -euo pipefail
WORK=/public/home/jiangxinwei.zr/work
BASE="$WORK/paper04/worktrees/kitnet-exp-mainline"
ARCHIVE="$WORK/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3_upload_bundle.tar.gz"
SIDECAR="$ARCHIVE.sha256"
INSTALL_ROOT="$WORK/upload_issue27ckcz_r3_20260810"
BUNDLE_ROOT="$INSTALL_ROOT/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3"
EXPECTED=0f68b154f0d2c45cc5520e25746d30a273a096a8026cf0df6fdbb1c1d8e9d59c
SUBMIT_LOG="$WORK/ckcz_r3_submit_$(date -u +%Y%m%dT%H%M%SZ).log"
JOB=""

exec > >(tee -a "$SUBMIT_LOG") 2>&1
finish() {
  status=$?
  trap - EXIT
  if test "$status" -ne 0; then
    echo "CKCZ_R3_HANDOFF_FAILED status=$status job=${JOB:-not_submitted}" >&2
    if test -n "${JOB:-}"; then
      CONTROL="$BASE/runs/issue27ckcz_endpoint_pair_conflict_diagnostic_v1_2026-08-10_seed27_amd_${JOB}_control"
      test ! -s "$CONTROL/current_phase.txt" || cat "$CONTROL/current_phase.txt" >&2
      test ! -s "$CONTROL/job_failure.txt" || cat "$CONTROL/job_failure.txt" >&2
      test ! -s "$CONTROL/progress_stall.txt" || cat "$CONTROL/progress_stall.txt" >&2
      test ! -s "$BASE/runs/issue27ckcz_diag_amd_${JOB}.err" || tail -80 "$BASE/runs/issue27ckcz_diag_amd_${JOB}.err" >&2
      sacct -j "$JOB" -X -n -P --format=JobID,State,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS 2>/dev/null || true
    fi
  fi
  echo "CKCZ_SUBMIT_LOG=$SUBMIT_LOG"
  return "$status"
}
trap finish EXIT

test -s "$ARCHIVE"
test -s "$SIDECAR"
sidecar_sha=$(awk 'NR==1 {gsub(/\r/, "", $1); print $1}' "$SIDECAR")
actual_sha=$(sha256sum "$ARCHIVE" | awk '{print $1}')
test "$sidecar_sha" = "$EXPECTED"
test "$actual_sha" = "$EXPECTED"
echo "CKCZ_R3_REMOTE_ARCHIVE_PASS sha256=$actual_sha bytes=$(stat -c %s "$ARCHIVE")"

if ! test -d "$BUNDLE_ROOT"; then
  test ! -e "$INSTALL_ROOT" || {
    echo "refusing unexpected partial r3 install root: $INSTALL_ROOT" >&2
    exit 2
  }
  mkdir "$INSTALL_ROOT"
  tar -xzf "$ARCHIVE" -C "$INSTALL_ROOT"
fi
test -d "$BUNDLE_ROOT"
test "$(tr -d '\r\n' < "$BUNDLE_ROOT/bundle_commit.txt")" = \
  6ec2686f690ab29021f9b5225b8c8d469bbd9e42
(
  cd "$BUNDLE_ROOT"
  sha256sum -c SHA256SUMS
)

CKCZ_SUBMIT_AUTHORIZATION=YES \
CKCZ_RUNTIME_GATE_SECONDS=3600 \
bash "$BUNDLE_ROOT/payload/scripts/issue27ckcz_install_and_submit.sh"

JOB=$(tr -d '\r\n' < "$BUNDLE_ROOT/ckcz_seed27_amd_job_id.txt")
[[ "$JOB" =~ ^[0-9]+$ ]]
echo "CKCZ_R3_JOB_ID=$JOB"
CONTROL="$BASE/runs/issue27ckcz_endpoint_pair_conflict_diagnostic_v1_2026-08-10_seed27_amd_${JOB}_control"
deadline=$(( $(date +%s) + 32400 ))
while true; do
  state=$(squeue -h -j "$JOB" -o '%T' 2>/dev/null | head -n 1 || true)
  if test -z "$state"; then
    state=$(sacct -j "$JOB" -X -n -P --format=State 2>/dev/null |
      head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]' || true)
  fi
  phase=not_created
  test ! -s "$CONTROL/current_phase.txt" || \
    phase=$(awk -F= '$1 == "phase" {print $2; exit}' "$CONTROL/current_phase.txt")
  echo "CKCZ_R3_MONITOR utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) job=$JOB state=${state:-UNKNOWN} phase=$phase"
  case "${state:-UNKNOWN}" in
    COMPLETED) break ;;
    FAILED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|BOOT_FAIL|PREEMPTED|CANCELLED)
      echo "CKCZ r3 terminal failure: $state" >&2
      exit 4
      ;;
  esac
  test "$(date +%s)" -lt "$deadline" || {
    echo "CKCZ r3 monitor deadline exceeded" >&2
    exit 5
  }
  sleep 30
done

PULLBACK="$BASE/runs/issue27ckcz_endpoint_pair_conflict_diagnostic_seed27_amd_${JOB}_pullback.tar.gz"
test -s "$PULLBACK"
test -s "$PULLBACK.sha256"
(
  cd "$BASE/runs"
  sha256sum -c "$(basename "$PULLBACK.sha256")"
)
sacct -j "$JOB" -X -n -P --format=JobID,State,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS
echo "CKCZ_R3_FORMAL_COMPLETE job=$JOB pullback=$PULLBACK"
trap - EXIT
echo "CKCZ_SUBMIT_LOG=$SUBMIT_LOG"
)
```

## 3. HPC 完成后，本地 PowerShell：拉回正式结果

仅在上一段打印 `CKCZ_R3_FORMAL_COMPLETE` 后运行：

```powershell
$ErrorActionPreference = 'Stop'
$ckczTransfer = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
$ckczRemoteBundle = '~/work/upload_issue27ckcz_r3_20260810/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3'
$ckczJobFile = Join-Path $ckczTransfer 'ckcz_r3_seed27_amd_job_id.txt'
scp "school-hpc:${ckczRemoteBundle}/ckcz_seed27_amd_job_id.txt" $ckczJobFile
if ($LASTEXITCODE -ne 0) { throw "CKCZ r3 job-id pullback failed: exit $LASTEXITCODE" }
$ckczJob = (Get-Content -Raw -LiteralPath $ckczJobFile).Trim()
if ($ckczJob -notmatch '^\d+$') { throw "invalid CKCZ r3 job id: $ckczJob" }
$ckczName = "issue27ckcz_endpoint_pair_conflict_diagnostic_seed27_amd_${ckczJob}_pullback.tar.gz"
$ckczLocal = Join-Path $ckczTransfer $ckczName
$ckczRemoteRuns = '~/work/paper04/worktrees/kitnet-exp-mainline/runs'
scp "school-hpc:${ckczRemoteRuns}/${ckczName}" $ckczLocal
scp "school-hpc:${ckczRemoteRuns}/${ckczName}.sha256" "${ckczLocal}.sha256"
if ($LASTEXITCODE -ne 0) { throw "CKCZ r3 result pullback failed: exit $LASTEXITCODE" }
$ckczActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ckczLocal).Hash.ToLowerInvariant()
$ckczExpected = ((Get-Content -Raw -LiteralPath "${ckczLocal}.sha256").Trim() -split '\s+')[0].ToLowerInvariant()
if ($ckczActual -ne $ckczExpected) { throw "CKCZ r3 pullback SHA mismatch" }
"CKCZ_R3_PULLBACK_PASS job=$ckczJob sha256=$ckczActual bytes=$((Get-Item -LiteralPath $ckczLocal).Length)"
```

把三段完整输出交回 Codex。`sbatch` 返回 job ID 只代表调度器接受；只有第二段最终打印
`CKCZ_R3_FORMAL_COMPLETE` 且第三段 SHA 通过，才进入拉回结果独立审查。
