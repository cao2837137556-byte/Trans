#!/bin/bash
set -euo pipefail

BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD="$BUNDLE_ROOT/payload"
BASE=${CKBO_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
COMMIT_SHA=$(tr -d '\r\n' < "$BUNDLE_ROOT/bundle_commit.txt")

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }
test -s "$BASE/runs/mainline_docs/ckbk_untouched_final_holdout_manifest_v1.json" || { echo "missing sealed holdout manifest" >&2; exit 2; }
test ! -e "$BUNDLE_ROOT/ckbo_amd_job_id.txt" || { echo "AMD job already submitted" >&2; exit 2; }
test ! -e "$BUNDLE_ROOT/ckbo_intel_job_id.txt" || { echo "Intel job already submitted" >&2; exit 2; }

files=(
  repo/ood/issue27ckbo_mature_afterimage_transfer_v1.py
  runs/mainline_docs/ckbo_mature_afterimage_transfer_prereg_20260715.md
  runs/mainline_docs/ckbo_dependency_sha256_20260715.txt
  scripts/issue27ckbo_mature_afterimage_transfer.slurm
  scripts/issue27ckbo_validate_and_pack_seed27.sh
  scripts/issue27ckbo_install_and_submit_dual.sh
  scripts/issue27ckbo_status_dual.sh
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
python -m py_compile repo/ood/issue27ckbo_mature_afterimage_transfer_v1.py
python repo/ood/issue27ckbo_mature_afterimage_transfer_v1.py --mode contract-unit >/dev/null
python - <<'PY'
import hashlib
from pathlib import Path
manifest = Path("runs/mainline_docs/ckbo_dependency_sha256_20260715.txt")
for line in manifest.read_text(encoding="utf-8").splitlines():
    expected, relative = line.split(None, 1)
    actual = hashlib.sha256(Path(relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if actual != expected:
        raise SystemExit(f"dependency hash mismatch: {relative}: {actual} != {expected}")
print("CKBO_DEPENDENCIES_OK")
PY
SCRIPT_SHA256=$(sha256sum repo/ood/issue27ckbo_mature_afterimage_transfer_v1.py | awk '{print $1}')
DEPENDENCY_SHA256=$(sha256sum runs/mainline_docs/ckbo_dependency_sha256_20260715.txt | awk '{print $1}')
EXPORTS="ALL,CKBO_COMMIT_SHA=$COMMIT_SHA,CKBO_SCRIPT_SHA256=$SCRIPT_SHA256,CKBO_DEPENDENCY_SHA256=$DEPENDENCY_SHA256"

AMD_ID=$(sbatch --parsable --partition=amd \
  --output="$BASE/runs/issue27ckbo_amd_%j.out" \
  --error="$BASE/runs/issue27ckbo_amd_%j.err" \
  --export="$EXPORTS" \
  "$BASE/scripts/issue27ckbo_mature_afterimage_transfer.slurm")
case "$AMD_ID" in ''|*[!0-9]*) echo "invalid AMD job id: $AMD_ID" >&2; exit 2;; esac
printf '%s\n' "$AMD_ID" > "$BUNDLE_ROOT/ckbo_amd_job_id.txt"

INTEL_ID=$(sbatch --parsable --partition=intel \
  --output="$BASE/runs/issue27ckbo_intel_%j.out" \
  --error="$BASE/runs/issue27ckbo_intel_%j.err" \
  --export="$EXPORTS" \
  "$BASE/scripts/issue27ckbo_mature_afterimage_transfer.slurm")
case "$INTEL_ID" in ''|*[!0-9]*) echo "invalid Intel job id: $INTEL_ID" >&2; exit 2;; esac
printf '%s\n' "$INTEL_ID" > "$BUNDLE_ROOT/ckbo_intel_job_id.txt"

echo "CKBO_AMD_JOB_ID=$AMD_ID"
echo "CKBO_INTEL_JOB_ID=$INTEL_ID"
echo "Both jobs are result-producing and use partition/job-isolated writable paths."
