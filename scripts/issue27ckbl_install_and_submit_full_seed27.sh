#!/bin/bash
# Run from the extracted CKBL upload bundle. Copies only CKBL-owned files and
# submits one independent result job to AMD and one to Intel.
set -euo pipefail

BASE=${CKBL_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
HERE=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD="$HERE/payload"
BASE_HASHES="$HERE/REMOTE_BASE_SHA256SUMS"

test -d "$BASE" || { echo "missing HPC project directory: $BASE" >&2; exit 2; }
test -d "$PAYLOAD" || { echo "missing bundle payload: $PAYLOAD" >&2; exit 2; }
test -s "$BASE_HASHES" || { echo "missing expected remote base hashes" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }

files=(
  repo/ood/issue27ckat_canonical_time_c1_canary_v1.py
  repo/ood/issue27ckbl_frontend_observability_audit_v1.py
  scripts/issue27ckbl_frontend_observability_full_seed27.slurm
  scripts/issue27ckbl_install_and_submit_full_seed27.sh
  scripts/issue27ckbl_status_full_seed27.sh
  scripts/issue27ckbl_validate_and_pack_full_seed27.sh
)

verify_one() {
  local relative=$1
  local source="$PAYLOAD/$relative"
  local target="$BASE/$relative"
  local payload_hash target_hash target_normalized_hash expected_old
  test -s "$source" || { echo "missing payload file: $relative" >&2; exit 2; }
  payload_hash=$(sha256sum "$source" | awk '{print $1}')
  if test -e "$target"; then
    target_hash=$(sha256sum "$target" | awk '{print $1}')
    target_normalized_hash=$(sed 's/\r$//' "$target" | sha256sum | awk '{print $1}')
    if test "$target_hash" = "$payload_hash"; then
      return
    fi
    if test "$target_normalized_hash" = "$payload_hash"; then
      return
    fi
    expected_old=$(awk -v wanted="$relative" '$2 == wanted {print $1}' "$BASE_HASHES")
    test -n "$expected_old" || { echo "remote target differs and no approved base hash exists: $target" >&2; exit 2; }
    if test "$target_hash" != "$expected_old" && test "$target_normalized_hash" != "$expected_old"; then
      echo "remote target differs from approved base: $target" >&2
      exit 2
    fi
  fi
}

install_one() {
  local relative=$1
  local source="$PAYLOAD/$relative"
  local target="$BASE/$relative"
  local payload_hash
  payload_hash=$(sha256sum "$source" | awk '{print $1}')
  if test -e "$target" && test "$(sha256sum "$target" | awk '{print $1}')" = "$payload_hash"; then
    echo "already installed: $relative"
    return
  fi
  install -D -m 0644 "$source" "$target"
  test "$(sha256sum "$target" | awk '{print $1}')" = "$payload_hash" || { echo "installed hash mismatch: $target" >&2; exit 2; }
  echo "installed: $relative"
}

for relative in "${files[@]}"; do
  verify_one "$relative"
done
for relative in "${files[@]}"; do
  install_one "$relative"
done

CKBL_COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
[[ "$CKBL_COMMIT_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid bundle commit SHA: $CKBL_COMMIT_SHA" >&2; exit 2; }
CKBL_SCRIPT_SHA256=$(sha256sum "$BASE/repo/ood/issue27ckbl_frontend_observability_audit_v1.py" | awk '{print $1}')
CKAT_SCRIPT_SHA256=$(sha256sum "$BASE/repo/ood/issue27ckat_canonical_time_c1_canary_v1.py" | awk '{print $1}')

cd "$BASE"
source scripts/00_env_issue27ckc.sh
python -m py_compile \
  repo/ood/issue27ckat_canonical_time_c1_canary_v1.py \
  repo/ood/issue27ckbl_frontend_observability_audit_v1.py
python repo/ood/issue27ckbl_frontend_observability_audit_v1.py --mode contract-unit

submit_one() {
  local partition=$1
  local record="$HERE/ckbl_full_seed27_${partition}_job_id.txt"
  local job_id
  if test -s "$record"; then
    job_id=$(tr -d '\r\n' < "$record")
    [[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid recorded $partition job id: $job_id" >&2; exit 2; }
    printf 'CKBL_%s_JOB_ID=%s (already recorded; not resubmitted)\n' "${partition^^}" "$job_id"
    return
  fi
  test ! -e "$record" || { echo "empty job-id record: $record" >&2; exit 2; }
  job_id=$(sbatch --parsable \
    --partition="$partition" \
    --job-name="ckbl_full_${partition}" \
    --chdir="$BASE" \
    --output="$BASE/runs/issue27ckbl_full_seed27_${partition}_%j.out" \
    --error="$BASE/runs/issue27ckbl_full_seed27_${partition}_%j.err" \
    --export="ALL,CKBL_COMMIT_SHA=$CKBL_COMMIT_SHA,CKBL_SCRIPT_SHA256=$CKBL_SCRIPT_SHA256,CKAT_SCRIPT_SHA256=$CKAT_SCRIPT_SHA256" \
    "$BASE/scripts/issue27ckbl_frontend_observability_full_seed27.slurm")
  job_id=${job_id%%;*}
  [[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid $partition job id: $job_id" >&2; exit 2; }
  printf '%s\n' "$job_id" > "$record"
  printf 'CKBL_%s_JOB_ID=%s\n' "${partition^^}" "$job_id"
}

submit_one amd
submit_one intel
echo "Both jobs are seed-27 infrastructure copies with partition/job-isolated outputs."
