#!/bin/bash
# Recover the already-computed CKBM seed-27 AMD result without retraining.
# Job 151583 wrote all scientific CSVs and then failed only because the frozen
# Python runtime rejects Path.write_text(newline=...).
set -euo pipefail

BASE=${CKBM_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
HERE=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD="$HERE/payload"
PARTITION=amd
JOB_ID=151583
ORIGINAL_COMPUTE_COMMIT=37b0fb4585d2634fa45fa2db31b1fead7bce886d
ORIGINAL_COMPUTE_SCRIPT_SHA256=be2936da6cc1548d5aa773b6a36df8eca0a91dfdf9fe47284bcdbffd553f72a6

SOURCE="$PAYLOAD/repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py"
TARGET="$BASE/repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py"
RUN_ROOT="$BASE/runs/issue27ckbm_tabm_causal_source_calibration_v1_2026-07-14_seed27_${PARTITION}_${JOB_ID}"
FAILURE="$BASE/runs/issue27ckbm_seed27_${PARTITION}_${JOB_ID}.failure.txt"
T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
TGN_EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_REPORT_EXT="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"

test -s "$SOURCE" || { echo "missing recovery payload: $SOURCE" >&2; exit 2; }
test -s "$TARGET" || { echo "missing installed original CKBM source: $TARGET" >&2; exit 2; }
test -d "$RUN_ROOT" || { echo "missing completed scientific output directory: $RUN_ROOT" >&2; exit 2; }
test -s "$FAILURE" || { echo "missing original failure marker: $FAILURE" >&2; exit 2; }
grep -Fqx 'status=FAILED' "$FAILURE" || { echo "unexpected original failure status" >&2; exit 2; }
grep -Fqx 'job_id=151583' "$FAILURE" || { echo "failure marker job mismatch" >&2; exit 2; }

state=$(sacct -j "$JOB_ID" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
exit_code=$(sacct -j "$JOB_ID" -X -n -P --format=ExitCode | head -n 1 | cut -d'|' -f1 | tr -d '[:space:]')
elapsed_raw=$(sacct -j "$JOB_ID" -X -n -P --format=ElapsedRaw | head -n 1 | cut -d'|' -f1 | tr -d '[:space:]')
test "$state" = "FAILED" || { echo "original job state is not FAILED: $state" >&2; exit 2; }
test "$exit_code" = "1:0" || { echo "original job exit code changed: $exit_code" >&2; exit 2; }
[[ "$elapsed_raw" =~ ^[0-9]+$ ]] || { echo "invalid original elapsed seconds: $elapsed_raw" >&2; exit 2; }

payload_hash=$(sha256sum "$SOURCE" | awk '{print $1}')
target_hash=$(sha256sum "$TARGET" | awk '{print $1}')
case "$target_hash" in
  "$ORIGINAL_COMPUTE_SCRIPT_SHA256")
    install -D -m 0644 "$SOURCE" "$TARGET"
    ;;
  "$payload_hash")
    echo "recovery source already installed"
    ;;
  *)
    echo "remote CKBM source differs from both original compute and recovery payload; stop" >&2
    exit 2
    ;;
esac
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$payload_hash" || {
  echo "recovery source install hash mismatch" >&2
  exit 2
}

RECOVERY_COMMIT=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
[[ "$RECOVERY_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid recovery commit: $RECOVERY_COMMIT" >&2; exit 2; }

cd "$BASE"
source scripts/00_env_issue27ckc.sh
export PYTHONDONTWRITEBYTECODE=1
python -m py_compile repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py
python repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py --mode contract-unit --threads 2

metadata=(
  "$RUN_ROOT/ckbm_single_seed_go_no_go.json"
  "$RUN_ROOT/ckbm_environment.json"
  "$RUN_ROOT/run_spec.json"
  "$RUN_ROOT/codex_readout.md"
)
present=0
for path in "${metadata[@]}"; do
  test -s "$path" && present=$((present + 1))
done
if test "$present" -eq 0; then
  SLURM_JOB_ID="$JOB_ID" \
  SLURM_JOB_PARTITION="$PARTITION" \
  CKBM_COMMIT_SHA="$ORIGINAL_COMPUTE_COMMIT" \
  CKBM_RECOVERY_COMMIT_SHA="$RECOVERY_COMMIT" \
  CKBM_ORIGINAL_WALL_SECONDS="$elapsed_raw" \
  python repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py \
    --mode finalize-existing \
    --seed 27 \
    --t0-root "$T0" \
    --report-t0-extension "$TGN_EXT" \
    --c1-cache "$C1_ROOT/hpc_canonical_c1_cache" \
    --c1-plan "$C1_ROOT/canonical_source_load_plan.csv" \
    --c1-targets "$C1_ROOT/canonical_source_target_index.csv" \
    --c1-report-extension "$C1_REPORT_EXT" \
    --out "$RUN_ROOT" \
    --train-cap 4000 \
    --eval-cap 3000 \
    --epochs 48 \
    --batch-size 512 \
    --threads 8 \
    --tabm-k 16 \
    --tabm-width 256 \
    --tabm-blocks 3 \
    --extra-trees 384 \
    --bootstrap-reps 500
elif test "$present" -eq "${#metadata[@]}"; then
  echo "all recovered metadata already exists; proceeding to validation"
else
  echo "partial recovered metadata exists; stop rather than overwrite: $present/${#metadata[@]}" >&2
  exit 2
fi

{
  printf 'original_job_id=%s\n' "$JOB_ID"
  printf 'original_partition=%s\n' "$PARTITION"
  printf 'original_state=%s\n' "$state"
  printf 'original_exit_code=%s\n' "$exit_code"
  printf 'original_wall_seconds=%s\n' "$elapsed_raw"
  printf 'scientific_compute_completed_before_metadata_failure=true\n'
  printf 'models_retrained=false\n'
  printf 'metadata_recovery_commit=%s\n' "$RECOVERY_COMMIT"
  sacct -j "$JOB_ID" -P --format=JobID,JobName,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS,Start,End
} > "$RUN_ROOT/resource_usage.txt"
printf 'job_id=%s\npartition=%s\ncompute_commit_sha=%s\ncompute_script_sha256=%s\nrecovery_commit_sha=%s\nrecovery_script_sha256=%s\nmodels_retrained=false\n' \
  "$JOB_ID" "$PARTITION" "$ORIGINAL_COMPUTE_COMMIT" "$ORIGINAL_COMPUTE_SCRIPT_SHA256" \
  "$RECOVERY_COMMIT" "$payload_hash" > "$RUN_ROOT/slurm_identity.txt"

CKBM_PARTITION="$PARTITION" CKBM_JOB_ID="$JOB_ID" \
  bash "$PAYLOAD/scripts/issue27ckbm_validate_and_pack_seed27.sh"

echo '=== recovered scientific decision ==='
cat "$RUN_ROOT/ckbm_single_seed_go_no_go.json"
echo "CKBM_RECOVERED_PULLBACK=$BASE/runs/issue27ckbm_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
