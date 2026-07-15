#!/bin/bash
set -euo pipefail

BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD="$BUNDLE_ROOT/payload"
BASE=${CKBP_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
AUX_REUSE_ROOT=${CKBP_AUX_REUSE_ROOT:-$BASE/runs/issue27ckbo_mature_afterimage_transfer_v1_2026-07-15_seed27_amd_151780}
COMMIT_SHA=$(tr -d '\r\n' < "$BUNDLE_ROOT/bundle_commit.txt")

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }
test -s "$BASE/runs/mainline_docs/ckbk_untouched_final_holdout_manifest_v1.json" || { echo "missing sealed holdout manifest" >&2; exit 2; }
test -d "$AUX_REUSE_ROOT/aux_afterimage_cache" || { echo "missing reusable CKBO auxiliary cache" >&2; exit 2; }
test -s "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_manifest.csv" || { echo "missing reusable CKBO auxiliary manifest" >&2; exit 2; }
test "$(sha256sum "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_manifest.csv" | awk '{print $1}')" = \
  "d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f" || {
  echo "reusable CKBO auxiliary manifest drift" >&2
  exit 2
}

files=(
  repo/ood/issue27ckbp_source_local_normal_calibration_v1.py
  runs/mainline_docs/ckbp_source_local_normal_calibration_prereg_20260715.md
  runs/mainline_docs/ckbp_dependency_sha256_20260715.txt
  scripts/issue27ckbp_source_local_normal_calibration.slurm
  scripts/issue27ckbp_validate_and_pack_seed27.sh
  scripts/issue27ckbp_install_and_submit_dual.sh
  scripts/issue27ckbp_status_dual.sh
)

for relative in "${files[@]}"; do
  source_file="$PAYLOAD/$relative"
  target_file="$BASE/$relative"
  test -s "$source_file" || { echo "missing payload file: $source_file" >&2; exit 2; }
  if test -e "$target_file" && ! cmp -s "$source_file" "$target_file"; then
    echo "refusing to overwrite a different remote file: $target_file" >&2
    echo "remote_sha256=$(sha256sum "$target_file" | awk '{print $1}')" >&2
    echo "bundle_sha256=$(sha256sum "$source_file" | awk '{print $1}')" >&2
    exit 2
  fi
done
for relative in "${files[@]}"; do
  install -D -m 0644 "$PAYLOAD/$relative" "$BASE/$relative"
done

cd "$BASE"
source scripts/00_env_issue27ckc.sh
python -m py_compile repo/ood/issue27ckbp_source_local_normal_calibration_v1.py
python repo/ood/issue27ckbp_source_local_normal_calibration_v1.py --mode contract-unit >/dev/null
python - <<'PY'
import hashlib
from pathlib import Path

manifest = Path("runs/mainline_docs/ckbp_dependency_sha256_20260715.txt")
for line in manifest.read_text(encoding="utf-8").splitlines():
    expected, relative = line.split(None, 1)
    actual = hashlib.sha256(Path(relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if actual != expected:
        raise SystemExit(f"dependency hash mismatch: {relative}: {actual} != {expected}")
print("CKBP_DEPENDENCIES_OK")
PY

SCRIPT_SHA256=$(sha256sum repo/ood/issue27ckbp_source_local_normal_calibration_v1.py | awk '{print $1}')
DEPENDENCY_SHA256=$(sha256sum runs/mainline_docs/ckbp_dependency_sha256_20260715.txt | awk '{print $1}')
EXPORTS="ALL,CKBP_COMMIT_SHA=$COMMIT_SHA,CKBP_SCRIPT_SHA256=$SCRIPT_SHA256,CKBP_DEPENDENCY_SHA256=$DEPENDENCY_SHA256,CKBP_AUX_REUSE_ROOT=$AUX_REUSE_ROOT"

submit_one() {
  partition=$1
  id_file="$BUNDLE_ROOT/ckbp_${partition}_job_id.txt"
  if test -s "$id_file"; then
    existing=$(tr -d '\r\n' < "$id_file")
    case "$existing" in ''|*[!0-9]*) echo "invalid existing job id: $id_file" >&2; exit 2;; esac
    echo "CKBP_${partition^^}_JOB_ID=$existing (already recorded; not resubmitted)"
    return
  fi
  job_id=$(sbatch --parsable --partition="$partition" \
    --output="$BASE/runs/issue27ckbp_${partition}_%j.out" \
    --error="$BASE/runs/issue27ckbp_${partition}_%j.err" \
    --export="$EXPORTS" \
    "$BASE/scripts/issue27ckbp_source_local_normal_calibration.slurm")
  case "$job_id" in ''|*[!0-9]*) echo "invalid $partition job id: $job_id" >&2; exit 2;; esac
  printf '%s\n' "$job_id" > "$id_file"
  echo "CKBP_${partition^^}_JOB_ID=$job_id"
}

submit_one amd
submit_one intel
echo "Both jobs are result-producing and use partition/job-isolated logs, run roots, archives, and hashes."
