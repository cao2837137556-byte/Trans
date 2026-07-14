#!/bin/bash
# Run once from the extracted CKBM bundle. Install only CKBM-owned files, then
# submit one independent AMD copy and one independent Intel copy.
set -euo pipefail

BASE=${CKBM_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
HERE=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD="$HERE/payload"
EXPECTED_T0_SHA256=b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67
EXPECTED_C1_PLAN_SHA256=414616332159eb90553213d6656c3d072a701ea93a02df464acdfa6cebc128f2
EXPECTED_C1_TARGET_SHA256=74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158

T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
TGN_EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_REPORT_EXT="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"

files=(
  repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py
  repo/ood/vendor/tabm_v0_0_3/tabm.py
  repo/ood/vendor/tabm_v0_0_3/LICENSE
  repo/ood/vendor/tabm_v0_0_3/rtdl_num_embeddings.py
  repo/ood/vendor/tabm_v0_0_3/UPSTREAM_PROVENANCE.md
  runs/mainline_docs/ckbm_tabm_causal_source_calibration_prereg_20260714.md
  scripts/issue27ckbm_tabm_causal_source_calibration_seed27.slurm
  scripts/issue27ckbm_install_and_submit_seed27.sh
  scripts/issue27ckbm_status_seed27.sh
  scripts/issue27ckbm_validate_and_pack_seed27.sh
)

test -d "$BASE" || { echo "missing HPC project directory: $BASE" >&2; exit 2; }
test -d "$PAYLOAD" || { echo "missing bundle payload: $PAYLOAD" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment entry point" >&2; exit 2; }
test -s "$T0/tgn_source_event_plan_frozen.csv" || { echo "missing frozen CKBE manifest" >&2; exit 2; }
test -d "$T0/tgn_event_cache" || { echo "missing frozen CKBE cache" >&2; exit 2; }
test -s "$TGN_EXT/extension_ready.json" || { echo "missing completed CKBI report extension" >&2; exit 2; }
test -s "$C1_ROOT/canonical_source_load_plan.csv" || { echo "missing frozen C1 plan" >&2; exit 2; }
test -s "$C1_ROOT/canonical_source_target_index.csv" || { echo "missing frozen C1 targets" >&2; exit 2; }
test -d "$C1_ROOT/hpc_canonical_c1_cache" || { echo "missing frozen C1 cache" >&2; exit 2; }
test -s "$C1_REPORT_EXT/c1_report_extension_ready.json" || { echo "missing completed C1 report extension" >&2; exit 2; }
test "$(sha256sum "$T0/tgn_source_event_plan_frozen.csv" | awk '{print $1}')" = "$EXPECTED_T0_SHA256" || { echo "frozen CKBE manifest changed" >&2; exit 2; }
test "$(sha256sum "$C1_ROOT/canonical_source_load_plan.csv" | awk '{print $1}')" = "$EXPECTED_C1_PLAN_SHA256" || { echo "frozen C1 plan changed" >&2; exit 2; }
test "$(sha256sum "$C1_ROOT/canonical_source_target_index.csv" | awk '{print $1}')" = "$EXPECTED_C1_TARGET_SHA256" || { echo "frozen C1 targets changed" >&2; exit 2; }

for relative in "${files[@]}"; do
  source="$PAYLOAD/$relative"
  target="$BASE/$relative"
  test -s "$source" || { echo "missing payload file: $relative" >&2; exit 2; }
  if test -e "$target" && ! cmp -s "$source" "$target"; then
    if cmp -s <(sed 's/\r$//' "$source") <(sed 's/\r$//' "$target"); then
      echo "remote target is LF-equivalent: $relative"
    else
      echo "remote CKBM target differs; refuse overwrite: $target" >&2
      exit 2
    fi
  fi
done

for relative in "${files[@]}"; do
  source="$PAYLOAD/$relative"
  target="$BASE/$relative"
  payload_hash=$(sha256sum "$source" | awk '{print $1}')
  if test -e "$target" && test "$(sha256sum "$target" | awk '{print $1}')" = "$payload_hash"; then
    echo "already installed: $relative"
  else
    install -D -m 0644 "$source" "$target"
    test "$(sha256sum "$target" | awk '{print $1}')" = "$payload_hash" || { echo "installed hash mismatch: $relative" >&2; exit 2; }
    echo "installed: $relative"
  fi
done

if grep -E -i 'pip[[:space:]]+install|conda[[:space:]]+create|docker[[:space:]]|singularity[[:space:]]+exec' \
  "$BASE/scripts/issue27ckbm_"*.sh "$BASE/scripts/issue27ckbm_"*.slurm; then
  echo "forbidden environment/container command found in CKBM launch chain" >&2
  exit 2
fi

COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
[[ "$COMMIT_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid bundle commit SHA: $COMMIT_SHA" >&2; exit 2; }

cd "$BASE"
source scripts/00_env_issue27ckc.sh
export PYTHONDONTWRITEBYTECODE=1
python -m py_compile \
  repo/ood/vendor/tabm_v0_0_3/tabm.py \
  repo/ood/vendor/tabm_v0_0_3/rtdl_num_embeddings.py \
  repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py
python repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py --mode contract-unit --threads 2
python repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py --mode dry-run

SCRIPT_SHA256=$(sha256sum "$BASE/repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py" | awk '{print $1}')
TABM_SHA256=$(sha256sum "$BASE/repo/ood/vendor/tabm_v0_0_3/tabm.py" | awk '{print $1}')
STUB_SHA256=$(sha256sum "$BASE/repo/ood/vendor/tabm_v0_0_3/rtdl_num_embeddings.py" | awk '{print $1}')

submit_one() {
  local partition=$1
  local record="$HERE/ckbm_seed27_${partition}_job_id.txt"
  local job_id
  if test -s "$record"; then
    job_id=$(tr -d '\r\n' < "$record")
    [[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid recorded $partition job id: $job_id" >&2; exit 2; }
    printf 'CKBM_%s_JOB_ID=%s (already recorded; not resubmitted)\n' "${partition^^}" "$job_id"
    return
  fi
  test ! -e "$record" || { echo "empty job-id record: $record" >&2; exit 2; }
  job_id=$(sbatch --parsable \
    --partition="$partition" \
    --job-name="ckbm_seed27_${partition}" \
    --chdir="$BASE" \
    --output="$BASE/runs/issue27ckbm_seed27_${partition}_%j.out" \
    --error="$BASE/runs/issue27ckbm_seed27_${partition}_%j.err" \
    --export="ALL,CKBM_COMMIT_SHA=$COMMIT_SHA,CKBM_SCRIPT_SHA256=$SCRIPT_SHA256,CKBM_TABM_SHA256=$TABM_SHA256,CKBM_STUB_SHA256=$STUB_SHA256" \
    "$BASE/scripts/issue27ckbm_tabm_causal_source_calibration_seed27.slurm")
  job_id=${job_id%%;*}
  [[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid $partition job id: $job_id" >&2; exit 2; }
  printf '%s\n' "$job_id" > "$record"
  printf 'CKBM_%s_JOB_ID=%s\n' "${partition^^}" "$job_id"
}

submit_one amd
submit_one intel
echo "Both seed-27 copies are independent; cancelling the slower copy is optional for correctness."
