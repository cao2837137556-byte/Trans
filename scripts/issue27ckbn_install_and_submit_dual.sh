#!/bin/bash
set -euo pipefail

BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD="$BUNDLE_ROOT/payload"
BASE=${CKBN_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
COMMIT_SHA=$(tr -d '\r\n' < "$BUNDLE_ROOT/bundle_commit.txt")

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }
test -s "$BASE/runs/mainline_docs/ckbk_untouched_final_holdout_manifest_v1.json" || { echo "missing sealed holdout manifest" >&2; exit 2; }
test ! -e "$BUNDLE_ROOT/ckbn_amd_job_id.txt" || { echo "AMD job already submitted" >&2; exit 2; }
test ! -e "$BUNDLE_ROOT/ckbn_intel_job_id.txt" || { echo "Intel job already submitted" >&2; exit 2; }

files=(
  repo/ood/issue27ckbn_stream_separability_diagnostic_v1.py
  runs/mainline_docs/ckbn_stream_separability_prereg_20260715.md
  scripts/issue27ckbn_stream_separability_diagnostic.slurm
  scripts/issue27ckbn_validate_and_pack_seed27.sh
  scripts/issue27ckbn_install_and_submit_dual.sh
  scripts/issue27ckbn_status_dual.sh
)
for relative in "${files[@]}"; do
  source_file="$PAYLOAD/$relative"
  target_file="$BASE/$relative"
  test -s "$source_file" || { echo "missing payload file: $source_file" >&2; exit 2; }
  if test -e "$target_file" && ! cmp -s "$source_file" "$target_file"; then
    echo "target differs; refusing to overwrite: $target_file" >&2
    exit 2
  fi
done
for relative in "${files[@]}"; do
  install -D -m 0644 "$PAYLOAD/$relative" "$BASE/$relative"
done

cd "$BASE"
source scripts/00_env_issue27ckc.sh
python -m py_compile repo/ood/issue27ckbn_stream_separability_diagnostic_v1.py
SCRIPT_SHA256=$(sha256sum repo/ood/issue27ckbn_stream_separability_diagnostic_v1.py | awk '{print $1}')
CKAO_SHA256=$(sha256sum repo/ood/issue27ckao_c1_strict_leave_device_family_canary_v1.py | awk '{print $1}')
CKAI_SHA256=$(sha256sum repo/ood/issue27ckai_external_flow_feature_probe_v1.py | awk '{print $1}')
CKAT_SHA256=$(sha256sum repo/ood/issue27ckat_canonical_time_c1_canary_v1.py | awk '{print $1}')
CKBL_SHA256=$(sha256sum repo/ood/issue27ckbl_frontend_observability_audit_v1.py | awk '{print $1}')
CKO_SHA256=$(sha256sum repo/ood/issue27cko_mechanism_frontend_v1.py | awk '{print $1}')
EXPORTS="ALL,CKBN_COMMIT_SHA=$COMMIT_SHA,CKBN_SCRIPT_SHA256=$SCRIPT_SHA256,CKAO_SHA256=$CKAO_SHA256,CKAI_SHA256=$CKAI_SHA256,CKAT_SHA256=$CKAT_SHA256,CKBL_SHA256=$CKBL_SHA256,CKO_SHA256=$CKO_SHA256"

AMD_ID=$(sbatch --parsable --partition=amd \
  --output="$BASE/runs/issue27ckbn_diag_amd_%j.out" \
  --error="$BASE/runs/issue27ckbn_diag_amd_%j.err" \
  --export="$EXPORTS" \
  "$BASE/scripts/issue27ckbn_stream_separability_diagnostic.slurm")
case "$AMD_ID" in ''|*[!0-9]*) echo "invalid AMD job id: $AMD_ID" >&2; exit 2;; esac
printf '%s\n' "$AMD_ID" > "$BUNDLE_ROOT/ckbn_amd_job_id.txt"

INTEL_ID=$(sbatch --parsable --partition=intel \
  --output="$BASE/runs/issue27ckbn_diag_intel_%j.out" \
  --error="$BASE/runs/issue27ckbn_diag_intel_%j.err" \
  --export="$EXPORTS" \
  "$BASE/scripts/issue27ckbn_stream_separability_diagnostic.slurm")
case "$INTEL_ID" in ''|*[!0-9]*) echo "invalid Intel job id: $INTEL_ID" >&2; exit 2;; esac
printf '%s\n' "$INTEL_ID" > "$BUNDLE_ROOT/ckbn_intel_job_id.txt"

echo "CKBN_AMD_JOB_ID=$AMD_ID"
echo "CKBN_INTEL_JOB_ID=$INTEL_ID"
echo "Both jobs are result-producing and use partition/job-isolated writable paths."
