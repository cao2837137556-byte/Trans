#!/bin/bash
# CKBK: one seed-27 result-producing allocation with isolated child stages.
# Submitted once to AMD and once to Intel; every writable path includes the
# partition and job id, so correctness does not depend on cancelling a copy.
#SBATCH -J ckbk_s27
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
TGN_EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_PLAN="$C1_ROOT/canonical_source_load_plan.csv"
C1_TARGETS="$C1_ROOT/canonical_source_target_index.csv"
C1_CACHE="$C1_ROOT/hpc_canonical_c1_cache"
C1_REPORT_EXT="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
RUN_ROOT="$BASE/runs/issue27ckbk_temporal_generalization_formal_v1_2026-07-14_hpc_seed27_${PARTITION}_${JOB_ID}"
TGN_OUT="$RUN_ROOT/stage_1_tgn"
GRAPH_OUT="$RUN_ROOT/stage_2_graphmixer"
AGG_OUT="$RUN_ROOT/final_aggregate"

EXPECTED_T0_SHA256=b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67
EXPECTED_C1_PLAN_SHA256=414616332159eb90553213d6656c3d072a701ea93a02df464acdfa6cebc128f2
EXPECTED_C1_TARGET_SHA256=74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158
EXPECTED_UNTOUCHED_SHA256=78832e8760697f39c5df48b75cd9337d83e2a8c6c1903a494bde00c7873b3af5

cd "$BASE"
test -s scripts/00_env_issue27ckc.sh || { echo "missing provisioned environment script" >&2; exit 2; }
test -s "$T0/tgn_source_event_plan_frozen.csv" || { echo "missing frozen CKBE manifest" >&2; exit 2; }
test -s "$T0/t0_cache_audit.csv" || { echo "missing frozen CKBE audit" >&2; exit 2; }
test -d "$T0/tgn_event_cache" || { echo "missing frozen CKBE event cache" >&2; exit 2; }
test -s "$TGN_EXT/report_only_extension_manifest_frozen.csv" || { echo "missing CKBI extension manifest" >&2; exit 2; }
test -s "$TGN_EXT/extension_ready.json" || { echo "missing CKBI extension readiness" >&2; exit 2; }
test -s "$C1_PLAN" && test -s "$C1_TARGETS" && test -d "$C1_CACHE" || { echo "missing frozen C1 cache contract" >&2; exit 2; }
test -s "$C1_REPORT_EXT/c1_report_extension_ready.json" || { echo "missing completed CKBJ C1 report extension" >&2; exit 2; }
test "$(sha256sum "$T0/tgn_source_event_plan_frozen.csv" | awk '{print $1}')" = "$EXPECTED_T0_SHA256" || { echo "CKBE manifest hash changed" >&2; exit 2; }
test "$(sha256sum "$C1_PLAN" | awk '{print $1}')" = "$EXPECTED_C1_PLAN_SHA256" || { echo "C1 plan hash changed" >&2; exit 2; }
test "$(sha256sum "$C1_TARGETS" | awk '{print $1}')" = "$EXPECTED_C1_TARGET_SHA256" || { echo "C1 target hash changed" >&2; exit 2; }
test "$(sha256sum runs/mainline_docs/ckbk_untouched_final_holdout_manifest_v1.json | awk '{print $1}')" = "$EXPECTED_UNTOUCHED_SHA256" || { echo "untouched holdout manifest hash changed" >&2; exit 2; }
test ! -e "$RUN_ROOT" || { echo "refusing to mix existing run root: $RUN_ROOT" >&2; exit 2; }

source scripts/00_env_issue27ckc.sh
python - <<'PY'
import torch
import torch_geometric
print("CKBK_ENV", torch.__version__, torch_geometric.__version__)
PY

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export M1_COMMIT_SHA=${M1_COMMIT_SHA:-bundle-unset}

python -m py_compile \
  repo/ood/issue27ckbk_dyglib_graphmixer_v1.py \
  repo/ood/issue27ckbk_temporal_generalization_formal_v1.py

mkdir -p "$RUN_ROOT"
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_epoch=$(date +%s)

set +e
python -u repo/ood/issue27ckbk_temporal_generalization_formal_v1.py \
  --mode formal --stage tgn \
  --t0-root "$T0" --report-t0-extension "$TGN_EXT" \
  --c1-cache "$C1_CACHE" --c1-plan "$C1_PLAN" --c1-targets "$C1_TARGETS" \
  --c1-report-extension "$C1_REPORT_EXT" --out "$TGN_OUT" \
  --train-cap 4000 --eval-cap 3000 --seed 27 \
  --ssl-epochs 3 --verifier-epochs 30 --verifier-negative-ratio 4 \
  --history-batch-size 200 --bootstrap-reps 1000 \
  >"$RUN_ROOT/stage_1_tgn.stdout" 2>"$RUN_ROOT/stage_1_tgn.stderr"
tgn_status=$?

python -u repo/ood/issue27ckbk_temporal_generalization_formal_v1.py \
  --mode formal --stage graphmixer \
  --t0-root "$T0" --report-t0-extension "$TGN_EXT" \
  --c1-cache "$C1_CACHE" --c1-plan "$C1_PLAN" --c1-targets "$C1_TARGETS" \
  --c1-report-extension "$C1_REPORT_EXT" --out "$GRAPH_OUT" \
  --train-cap 4000 --eval-cap 3000 --seed 27 \
  --verifier-epochs 30 --verifier-negative-ratio 4 \
  --history-batch-size 200 --graph-score-batch-size 2048 --bootstrap-reps 1000 \
  >"$RUN_ROOT/stage_2_graphmixer.stdout" 2>"$RUN_ROOT/stage_2_graphmixer.stderr"
graph_status=$?

python -u repo/ood/issue27ckbk_temporal_generalization_formal_v1.py \
  --mode aggregate --tgn-stage-out "$TGN_OUT" --graph-stage-out "$GRAPH_OUT" \
  --out "$AGG_OUT" \
  >"$RUN_ROOT/final_aggregate.stdout" 2>"$RUN_ROOT/final_aggregate.stderr"
aggregate_status=$?
set -e

ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
wall_seconds=$((ended_epoch - started_epoch))
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\ntgn_exit_code=%s\ngraphmixer_exit_code=%s\naggregate_exit_code=%s\npartition=%s\njob_id=%s\n' \
  "$started_utc" "$ended_utc" "$wall_seconds" "$tgn_status" "$graph_status" "$aggregate_status" "$PARTITION" "$JOB_ID" \
  > "$RUN_ROOT/run_timing_and_exit_codes.txt"

printf 'slurm_job_id=%s\npartition=%s\ncommit_sha=%s\n' "$JOB_ID" "$PARTITION" "$M1_COMMIT_SHA" \
  > "$RUN_ROOT/slurm_identity.txt"
if command -v sstat >/dev/null 2>&1; then
  sstat -j "${JOB_ID}.batch" --format=JobID,AveCPU,AveRSS,MaxRSS,MaxVMSize -P \
    > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true
fi

if test "$aggregate_status" -ne 0; then
  echo "CKBK aggregate failed after preserving child artifacts" >&2
  exit "$aggregate_status"
fi
if test "$tgn_status" -ne 0 || test "$graph_status" -ne 0; then
  echo "CKBK completed partially; aggregate preserved available results" >&2
  exit 1
fi
echo "CKBK seed-27 result run completed; seeds 37/47 were not launched" >&2
