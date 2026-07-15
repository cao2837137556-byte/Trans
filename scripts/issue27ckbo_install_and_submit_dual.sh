#!/bin/bash
set -euo pipefail

BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD="$BUNDLE_ROOT/payload"
BASE=${CKBO_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
AUX_REUSE_ROOT=${CKBO_AUX_REUSE_ROOT:-}
COMMIT_SHA=$(tr -d '\r\n' < "$BUNDLE_ROOT/bundle_commit.txt")

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }
test -s "$BASE/runs/mainline_docs/ckbk_untouched_final_holdout_manifest_v1.json" || { echo "missing sealed holdout manifest" >&2; exit 2; }
test ! -e "$BUNDLE_ROOT/ckbo_amd_job_id.txt" || { echo "AMD job already submitted" >&2; exit 2; }
test ! -e "$BUNDLE_ROOT/ckbo_intel_job_id.txt" || { echo "Intel job already submitted" >&2; exit 2; }
if test -n "$AUX_REUSE_ROOT"; then
  test -d "$AUX_REUSE_ROOT/aux_afterimage_cache" || { echo "missing CKBO_AUX_REUSE_ROOT cache: $AUX_REUSE_ROOT" >&2; exit 2; }
  test -s "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_ready.json" || { echo "missing CKBO_AUX_REUSE_ROOT ready marker" >&2; exit 2; }
fi

files=(
  repo/ood/issue27ckbo_mature_afterimage_transfer_v1.py
  runs/mainline_docs/ckbo_mature_afterimage_transfer_prereg_20260715.md
  runs/mainline_docs/ckbo_dependency_sha256_20260715.txt
  scripts/issue27ckbo_mature_afterimage_transfer.slurm
  scripts/issue27ckbo_validate_and_pack_seed27.sh
  scripts/issue27ckbo_install_and_submit_dual.sh
  scripts/issue27ckbo_status_dual.sh
)
known_predecessor_sha256() {
  case "$1" in
    repo/ood/issue27ckbo_mature_afterimage_transfer_v1.py) echo afea03e9eb9bcdc4c37b584941ca00a698b1a863e773cbd6ca945b64ce8744b6 ;;
    runs/mainline_docs/ckbo_mature_afterimage_transfer_prereg_20260715.md) echo 7574d318d830e4efc52e0dbeb6aa1d48abc736f09ed29b51b69cf42a40ed00a0 ;;
    runs/mainline_docs/ckbo_dependency_sha256_20260715.txt) echo f5227c3065bd70ddef688bf6bafcfd1cf397925c1d4ae2fba06e9b6e8aa14da1 ;;
    scripts/issue27ckbo_mature_afterimage_transfer.slurm) echo ee7c7c32aeef92a22e491d74eb3a1b19d1fbc72c480f07269595a2003546eb1c ;;
    scripts/issue27ckbo_validate_and_pack_seed27.sh) echo 3fd0701d2d8a781b6a0d98754ef95d6830477ffd874007d1ff720d86953c67cb ;;
    scripts/issue27ckbo_install_and_submit_dual.sh) echo 68116501e9383062e3503e97f8b39e15c73479b402399d1877066dd3e4f446d7 ;;
    scripts/issue27ckbo_status_dual.sh) echo 2b6d306670683c4c7cc823cb59f9be328a38bd5fb264f89c54aeb071a0bd61b2 ;;
    *) return 1 ;;
  esac
}
for relative in "${files[@]}"; do
  source_file="$PAYLOAD/$relative"
  target_file="$BASE/$relative"
  test -s "$source_file" || { echo "missing payload file: $source_file" >&2; exit 2; }
  if test -e "$target_file" && ! cmp -s "$source_file" "$target_file"; then
    expected=$(known_predecessor_sha256 "$relative") || { echo "no predecessor allowlist for: $relative" >&2; exit 2; }
    actual=$(sha256sum "$target_file" | awk '{print $1}')
    test "$actual" = "$expected" || {
      echo "target is neither this bundle nor the exact job-151772 predecessor: $target_file" >&2
      echo "actual_sha256=$actual expected_predecessor_sha256=$expected" >&2
      exit 2
    }
    echo "CKBO_KNOWN_PREDECESSOR_OK $relative $actual"
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
if test -n "$AUX_REUSE_ROOT"; then
  EXPORTS="$EXPORTS,CKBO_AUX_REUSE_ROOT=$AUX_REUSE_ROOT"
fi

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
