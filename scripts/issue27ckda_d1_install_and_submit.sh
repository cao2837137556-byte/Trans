#!/usr/bin/env bash
# Run only from the extracted, Kimi-reviewed CKDA D1 bundle on the HPC login node.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKDA_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
D0_ROOT=${CKDA_D0_BUNDLE_ROOT:-/public/home/jiangxinwei.zr/work/issue27ckda_d0_representation_compatibility_20260811_r2}
SLURM="$HERE/payload/scripts/issue27ckda_d1_representation_probe_formal.slurm"
STATUS="$HERE/payload/scripts/issue27ckda_d1_status.sh"
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
JOB_FILE="$HERE/ckda_d1_amd_job_id.txt"

test "${CKDA_D1_SUBMIT_AUTHORIZATION:-NO}" = YES || {
  echo "CKDA D1 submission is not authorized; export CKDA_D1_SUBMIT_AUTHORIZATION=YES" >&2
  exit 3
}
for path in "$SLURM" "$STATUS" "$HERE/SHA256SUMS" "$BASE/scripts/00_env_issue27ckc.sh" \
  "$D0_ROOT/payload/vendor/netFound/PY39_COMPAT_AUDIT.json" \
  "$D0_ROOT/payload/vendor/netFound-base/model.safetensors"; do
  test -s "$path" || { echo "missing CKDA D1 immutable prerequisite: $path" >&2; exit 2; }
done

echo "=== CKDA D1 exact bundle SHA-256 ==="
(cd "$HERE" && sha256sum -c SHA256SUMS)
while IFS= read -r relative; do
  case "$relative" in
    *.py|*.sh|*.slurm|*.md|*.txt|*.csv|*.json|SHA256SUMS)
      LC_ALL=C grep -q $'\r' "$HERE/$relative" && { echo "CR byte in $relative" >&2; exit 2; }
      ;;
  esac
done < <(awk '{print $2}' "$HERE/SHA256SUMS")

source "$BASE/scripts/00_env_issue27ckc.sh"
export PYTHONPATH="$D0_ROOT/payload/vendor_py:$HERE/payload/repo/ood:$D0_ROOT/payload/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
python "$HERE/payload/repo/ood/issue27ckda_d1_representation_probe_v1.py" --python39-gate \
  "$HERE/payload/repo/ood"/*.py "$D0_ROOT/payload/repo/ood/issue27ckda_d0_resource_pilot_v1.py" \
  "$D0_ROOT/payload/vendor/netFound/src/modules/netFoundModels.py"
python -m unittest -v test_issue27ckda_d1_representation_probe_v1
python "$HERE/payload/repo/ood/issue27ckda_d1_validate_and_pack_v1.py" contract-test
bash -n "$SLURM" "$STATUS" "$HERE/payload/scripts/issue27ckda_d1_install_and_submit.sh"

if test -s "$JOB_FILE"; then
  old_job=$(tr -dc '0-9' < "$JOB_FILE")
  old_state=$(sacct -j "$old_job" -X -n -P --format=State 2>/dev/null | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
  case "$old_state" in
    PENDING|RUNNING|COMPLETED)
      echo "refusing duplicate CKDA D1 submission: job=$old_job state=$old_state" >&2
      exit 4 ;;
  esac
fi

export_spec="ALL,CKDA_D1_BUNDLE_ROOT=$HERE,CKDA_D1_COMMIT_SHA=$COMMIT_SHA,CKDA_BASE=$BASE,CKDA_D0_BUNDLE_ROOT=$D0_ROOT"
echo "=== CKDA D1 Slurm scheduler dry validation ==="
sbatch --test-only -p amd --export="$export_spec" "$SLURM"
echo "=== CKDA D1 submit complete result-producing chain ==="
job_id=$(sbatch --parsable -p amd \
  --output="$BASE/runs/issue27ckda_d1_amd_%j.out" \
  --error="$BASE/runs/issue27ckda_d1_amd_%j.err" \
  --export="$export_spec" "$SLURM")
printf '%s\n' "$job_id" > "$JOB_FILE"
printf 'job_id=%s\ncommit_sha=%s\nbundle_root=%s\nsubmitted_utc=%s\n' \
  "$job_id" "$COMMIT_SHA" "$HERE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$HERE/ckda_d1_submission_record.txt"
echo "CKDA_D1_JOB_ID=$job_id"
echo "Monitor with: bash $STATUS $job_id"
