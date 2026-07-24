#!/bin/bash
# Run once from the extracted CKBU parallel-resume bundle on the HPC login node.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBU_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBU_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
AMD_ID_FILE="$HERE/ckbu_parallel_seed27_amd_job_id.txt"
INTEL_ID_FILE="$HERE/ckbu_parallel_seed27_intel_job_id.txt"
PREDECESSOR_JOB=153973
PREDECESSOR_ROOT="$BASE/runs/issue27ckbu_unified_process_rescue_formal_v1_2026-07-23_seed27_amd_${PREDECESSOR_JOB}"
CKBT_REL="runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22"
CKBQ_ROOT="$BASE/runs/issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_amd_153037"
PCAP_LIB_DIR="/share/software/CST/installed/MCR/bin/glnxa64"

test -d "$BASE" || { echo "missing experiment directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing allowed environment script" >&2; exit 2; }
test ! -e "$AMD_ID_FILE" && test ! -e "$INTEL_ID_FILE" || {
  echo "parallel-resume bundle already submitted; refusing duplicate submission" >&2
  exit 2
}
if squeue -h -j "$PREDECESSOR_JOB" 2>/dev/null | grep -q .; then
  echo "predecessor job $PREDECESSOR_JOB is still queued/running; cancel it before installing" >&2
  exit 2
fi

NEW_FILES=(
  repo/ood/issue27ckbu_parallel_cache_resume_v1.py
  scripts/issue27ckbu_unified_process_rescue_parallel_resume.slurm
  scripts/issue27ckbu_validate_and_pack_parallel_resume_seed27.sh
  scripts/issue27ckbu_status_parallel_resume_dual.sh
  runs/mainline_docs/ckbu_parallel_resume_runtime_fix_20260724.md
)
EXISTING_FILES=(
  repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py
  repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py
)
for relative in "${EXISTING_FILES[@]}"; do
  source_path="$HERE/payload/$relative"
  target_path="$BASE/$relative"
  test -s "$source_path" && test -s "$target_path" || {
    echo "missing frozen existing file: $relative" >&2
    exit 2
  }
  test "$(sha256sum "$source_path" | awk '{print $1}')" = \
       "$(sha256sum "$target_path" | awk '{print $1}')" || {
    echo "frozen existing file differs; no overwrite: $target_path" >&2
    exit 2
  }
done
for relative in "${NEW_FILES[@]}"; do
  source_path="$HERE/payload/$relative"
  target_path="$BASE/$relative"
  test -s "$source_path" || { echo "bundle payload missing: $relative" >&2; exit 2; }
  if test -e "$target_path"; then
    test "$(sha256sum "$source_path" | awk '{print $1}')" = \
         "$(sha256sum "$target_path" | awk '{print $1}')" || {
      echo "new target differs; no overwrite: $target_path" >&2
      exit 2
    }
  else
    install -D -m 0644 "$source_path" "$target_path"
  fi
done

for path in \
  "$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip" \
  "$BASE/$CKBT_REL/aux_process_support_candidate_manifest.csv" \
  "$CKBQ_ROOT/ckbq_record_predictions.csv.gz" \
  "$CKBQ_ROOT/ckbo_auxiliary_benign_manifest.csv" \
  "$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc/report_extension_recorded_targets.csv" \
  "$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_target_index.csv" \
  "$BASE/runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv"; do
  test -s "$path" || { echo "missing immutable input: $path" >&2; exit 2; }
done
for name in normal_1.pcap normal_2.pcap normal_scanning1.pcap password_normal1.pcap injection_normal1.pcap MITM_normal1.pcap; do
  test -s "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/$name" || {
    echo "missing ToN pilot PCAP: $name" >&2
    exit 2
  }
done
test -d "$DATA_ROOT/external/ton_iot_raw_network/extracted" || {
  echo "missing ToN extracted metadata root" >&2
  exit 2
}

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
test -s "$PCAP_LIB_DIR/libpcap.so.1" || { echo "shared compute-node libpcap missing" >&2; exit 2; }
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
test "$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')" = "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "TShark shared-libpcap resolution failed" >&2
  exit 2
}
test "$("$TSHARK" -n -r "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_1.pcap" \
  -c 1 -T fields -e frame.number 2>/dev/null)" = 1 || {
  echo "TShark real-PCAP probe failed" >&2
  exit 2
}
python -m py_compile \
  repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py \
  repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py \
  repo/ood/issue27ckbu_parallel_cache_resume_v1.py
python repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py --mode unit
python repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py --mode contract-unit
python repo/ood/issue27ckbu_parallel_cache_resume_v1.py --mode unit

FRONTEND_SHA256=$(sha256sum repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py | awk '{print $1}')
FORMAL_SHA256=$(sha256sum repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py | awk '{print $1}')
RESUME_SHA256=$(sha256sum repo/ood/issue27ckbu_parallel_cache_resume_v1.py | awk '{print $1}')
EXPORTS="ALL,CKBU_COMMIT_SHA=$COMMIT_SHA,CKBU_FRONTEND_SHA256=$FRONTEND_SHA256,CKBU_FORMAL_SHA256=$FORMAL_SHA256,CKBU_RESUME_SHA256=$RESUME_SHA256,CKBU_REUSE_RUN_ROOT=$PREDECESSOR_ROOT"
SLURM="scripts/issue27ckbu_unified_process_rescue_parallel_resume.slurm"

sbatch --test-only -p amd --export="$EXPORTS" "$SLURM"
sbatch --test-only -p intel --export="$EXPORTS" "$SLURM"

amd=$(sbatch --parsable -p amd \
  --output="$BASE/runs/issue27ckbu_parallel_amd_%j.out" \
  --error="$BASE/runs/issue27ckbu_parallel_amd_%j.err" \
  --export="$EXPORTS" "$SLURM")
[[ "$amd" =~ ^[0-9]+$ ]] || { echo "invalid AMD job id: $amd" >&2; exit 2; }
printf '%s\n' "$amd" > "$AMD_ID_FILE"

intel=$(sbatch --parsable -p intel \
  --output="$BASE/runs/issue27ckbu_parallel_intel_%j.out" \
  --error="$BASE/runs/issue27ckbu_parallel_intel_%j.err" \
  --export="$EXPORTS" "$SLURM")
[[ "$intel" =~ ^[0-9]+$ ]] || { echo "invalid Intel job id: $intel" >&2; exit 2; }
printf '%s\n' "$intel" > "$INTEL_ID_FILE"

printf 'CKBU_PARALLEL_AMD_JOB_ID=%s\nCKBU_PARALLEL_INTEL_JOB_ID=%s\n' "$amd" "$intel"
echo "Both runs are fully output-isolated; neither is auto-cancelled."
