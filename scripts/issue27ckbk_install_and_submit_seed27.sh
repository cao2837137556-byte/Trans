#!/bin/bash
# Run from the extracted CKBK bundle. Installs only CKBK-owned files and submits
# one isolated seed-27 copy to AMD plus one to Intel. No cache/environment/data
# is copied or modified.
set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
HERE=$(pwd)
PAYLOAD="$HERE/payload"
T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
TGN_EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_REPORT_EXT="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"

test -d "$BASE" || { echo "missing HPC project directory: $BASE" >&2; exit 2; }
test -d "$PAYLOAD" || { echo "missing bundle payload" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing provisioned environment script" >&2; exit 2; }
test -s "$T0/tgn_source_event_plan_frozen.csv" && test -d "$T0/tgn_event_cache" || { echo "missing CKBE T0" >&2; exit 2; }
test -s "$TGN_EXT/extension_ready.json" || { echo "missing completed CKBI extension" >&2; exit 2; }
test -d "$C1_ROOT/hpc_canonical_c1_cache" || { echo "missing frozen C1 cache" >&2; exit 2; }
test -s "$C1_REPORT_EXT/c1_report_extension_ready.json" || { echo "missing completed C1 report extension" >&2; exit 2; }

files=(
  repo/ood/issue27ckbk_dyglib_graphmixer_v1.py
  repo/ood/issue27ckbk_temporal_generalization_formal_v1.py
  repo/ood/issue27ckbk_temporal_generalization_contract_tests_v1.py
  repo/ood/third_party/DYGLIB_LICENSE.txt
  scripts/issue27ckbk_temporal_generalization_seed27.slurm
  runs/mainline_docs/ckbk_temporal_generalization_prereg_20260714.md
  runs/mainline_docs/ckbk_untouched_final_holdout_manifest_v1.json
  runs/mainline_docs/ckbk_untouched_final_holdout_manifest_v1.sha256
)
for relative in "${files[@]}"; do
  test -s "$PAYLOAD/$relative" || { echo "missing bundle file: $relative" >&2; exit 2; }
  target="$BASE/$relative"
  if test -e "$target" && ! cmp -s "$PAYLOAD/$relative" "$target"; then
    if cmp -s <(sed 's/\r$//' "$PAYLOAD/$relative") <(sed 's/\r$//' "$target"); then
      echo "existing target matches after LF normalization: $relative"
    else
      echo "remote CKBK target differs; refusing overwrite: $target" >&2
      exit 2
    fi
  fi
  if test ! -e "$target"; then
    install -D -m 0644 "$PAYLOAD/$relative" "$target"
  fi
done

M1_COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
[[ "$M1_COMMIT_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid bundle commit SHA: $M1_COMMIT_SHA" >&2; exit 2; }
test ! -e "$HERE/ckbk_seed27_amd_job_id.txt" || { echo "AMD job already recorded" >&2; exit 2; }
test ! -e "$HERE/ckbk_seed27_intel_job_id.txt" || { echo "Intel job already recorded" >&2; exit 2; }

submit_one() {
  local partition=$1
  local short=$2
  local job_id
  job_id=$(sbatch --parsable --partition="$partition" --job-name="ckbk_${short}" \
    --chdir="$BASE" \
    --output="$BASE/runs/issue27ckbk_seed27_${partition}_%j.out" \
    --error="$BASE/runs/issue27ckbk_seed27_${partition}_%j.err" \
    --export="ALL,M1_COMMIT_SHA=$M1_COMMIT_SHA" \
    "$BASE/scripts/issue27ckbk_temporal_generalization_seed27.slurm")
  job_id=${job_id%%;*}
  [[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid $partition job id: $job_id" >&2; exit 2; }
  printf '%s\n' "$job_id" > "$HERE/ckbk_seed27_${partition}_job_id.txt"
  printf 'CKBK_%s_JOB_ID=%s\n' "${partition^^}" "$job_id"
}

submit_one amd amd
submit_one intel int
echo "Both jobs are infrastructure copies of seed 27; outputs are partition/job isolated."
