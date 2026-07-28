#!/bin/bash
# Run from the extracted CKBV bundle on the already logged-in HPC terminal.
# The bundle's exact code is executed in place; no existing experiment file is
# overwritten, so a differing remote worktree cannot break installation.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBV_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBV_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
AMD_ID_FILE="$HERE/ckbv_seed27_amd_job_id.txt"
INTEL_ID_FILE="$HERE/ckbv_seed27_intel_job_id.txt"
CODE_ROOT="$HERE/payload/repo/ood"
SCRIPT_ROOT="$HERE/payload/scripts"
CKBT_MANIFEST="$HERE/payload/runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/aux_process_support_candidate_manifest.csv"
TON_PILOT_MANIFEST="$HERE/payload/runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv"
CKBQ_ROOT="$BASE/runs/issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_amd_153037"
PCAP_LIB_DIR="/share/software/CST/installed/MCR/bin/glnxa64"
REUSE_ROOTS=${CKBV_REUSE_RUN_ROOTS:-$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154761:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154620:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_intel_154621:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154606:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_intel_154607:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154478:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154440:$BASE/runs/issue27ckbu_unified_process_rescue_parallel_v2_2026-07-24_seed27_amd_154081}

test -d "$BASE" || {
  echo "missing experiment directory: $BASE" >&2
  exit 2
}
test -s "$BASE/scripts/00_env_issue27ckc.sh" || {
  echo "missing allowed environment script" >&2
  exit 2
}
test -s "$HERE/SHA256SUMS" || {
  echo "missing bundle SHA256SUMS" >&2
  exit 2
}
echo "=== CKBV exact bundle payload SHA-256 ==="
(cd "$HERE" && sha256sum -c SHA256SUMS)

while IFS= read -r relative; do
  test -n "$relative" || continue
  case "$relative" in
    *.py|*.sh|*.slurm|*.md|*.txt|*.csv|SHA256SUMS)
      if LC_ALL=C grep -q $'\r' "$HERE/$relative"; then
        echo "bundle text file is not LF-only: $relative" >&2
        exit 2
      fi
      ;;
  esac
done < <(awk '{print $2}' "$HERE/SHA256SUMS")

for path in \
  "$CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py" \
  "$CODE_ROOT/issue27ckbu_unified_process_rescue_formal_v1.py" \
  "$CODE_ROOT/issue27ckbu_parallel_cache_resume_v1.py" \
  "$CODE_ROOT/issue27ckbv_checkpointed_sparse_process_frontend_v1.py" \
  "$SCRIPT_ROOT/issue27ckbv_checkpointed_process_formal.slurm" \
  "$SCRIPT_ROOT/issue27ckbv_validate_and_pack_seed27.sh" \
  "$SCRIPT_ROOT/issue27ckbv_status_dual.sh" \
  "$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip" \
  "$TON_PILOT_MANIFEST" "$CKBT_MANIFEST" \
  "$CKBQ_ROOT/ckbq_record_predictions.csv.gz" \
  "$CKBQ_ROOT/ckbo_auxiliary_benign_manifest.csv" \
  "$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc/report_extension_recorded_targets.csv" \
  "$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_target_index.csv"; do
  test -s "$path" || {
    echo "missing immutable input: $path" >&2
    exit 2
  }
done

# The raw51_observable_v1 mask travels in the bundle (self-contained; no
# remote worktree pull required). Its bytes are already verified against
# SHA256SUMS at clean extraction; re-check here before submission.
RAW51_MASK="$HERE/payload/runs/raw51_observable_v1/raw51_observable_v1_mask.csv"
RAW51_MASK_SHA256=b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df
test -s "$RAW51_MASK" || { echo "bundle missing raw51 mask: $RAW51_MASK" >&2; exit 2; }
test "$(sha256sum "$RAW51_MASK" | awk '{print $1}')" = "$RAW51_MASK_SHA256" || {
  echo "raw51 mask sha256 mismatch" >&2
  exit 2
}

echo "=== CKBV immutable Gotham ZIP identity ==="
echo "Hashing the 23.8 GB ZIP can take several minutes; this is expected."
test "$(stat -c %s "$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip")" = \
  23824968355 || {
  echo "Gotham ZIP size drift" >&2
  exit 2
}
test "$(md5sum "$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip" | awk '{print $1}')" = \
  7ca78c0517ccb3d2854e823678e0f206 || {
  echo "Gotham ZIP official MD5 drift" >&2
  exit 2
}

for name in normal_1.pcap normal_2.pcap normal_scanning1.pcap \
  password_normal1.pcap injection_normal1.pcap MITM_normal1.pcap; do
  test -s "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/$name" || {
    echo "missing ToN pilot PCAP: $name" >&2
    exit 2
  }
done
echo "=== CKBV immutable ToN pilot PCAP identities ==="
while IFS=, read -r dataset name role bytes sha container model_use raw_label; do
  test "$name" != source_file || continue
  path="$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/$name"
  echo "Checking $name"
  test "$(stat -c %s "$path")" = "$bytes" || {
    echo "ToN pilot size drift: $name" >&2
    exit 2
  }
  test "$(sha256sum "$path" | awk '{print $1}')" = "$sha" || {
    echo "ToN pilot SHA-256 drift: $name" >&2
    exit 2
  }
done < "$TON_PILOT_MANIFEST"
test -d "$DATA_ROOT/external/ton_iot_raw_network/extracted" || {
  echo "missing ToN extracted metadata root" >&2
  exit 2
}

echo "=== CKBV allowed environment and real-PCAP runtime probe ==="
cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
test -s "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "shared compute-node libpcap missing" >&2
  exit 2
}
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
test "$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')" = \
  "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "TShark shared-libpcap resolution failed" >&2
  exit 2
}
test "$("$TSHARK" -n \
  -r "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_1.pcap" \
  -c 1 -T fields -e frame.number 2>/dev/null)" = 1 || {
  echo "TShark real-PCAP probe failed" >&2
  exit 2
}

export PYTHONPATH="$CODE_ROOT:$BASE/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
echo "=== CKBV compile and contract regression suite ==="
python -m py_compile \
  "$CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py" \
  "$CODE_ROOT/issue27ckbu_unified_process_rescue_formal_v1.py" \
  "$CODE_ROOT/issue27ckbu_parallel_cache_resume_v1.py" \
  "$CODE_ROOT/issue27ckbv_checkpointed_sparse_process_frontend_v1.py"
python "$CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py" --mode unit
python "$CODE_ROOT/issue27ckbu_unified_process_rescue_formal_v1.py" --mode contract-unit
python "$CODE_ROOT/issue27ckbu_parallel_cache_resume_v1.py" --mode unit
python "$CODE_ROOT/issue27ckbv_checkpointed_sparse_process_frontend_v1.py" --mode unit

FRONTEND_SHA256=$(sha256sum "$CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py" | awk '{print $1}')
FORMAL_SHA256=$(sha256sum "$CODE_ROOT/issue27ckbu_unified_process_rescue_formal_v1.py" | awk '{print $1}')
RESUME_SHA256=$(sha256sum "$CODE_ROOT/issue27ckbu_parallel_cache_resume_v1.py" | awk '{print $1}')
CHECKPOINT_SHA256=$(sha256sum "$CODE_ROOT/issue27ckbv_checkpointed_sparse_process_frontend_v1.py" | awk '{print $1}')
SLURM="$SCRIPT_ROOT/issue27ckbv_checkpointed_process_formal.slurm"
EXPORTS="ALL,CKBV_COMMIT_SHA=$COMMIT_SHA,CKBV_CODE_ROOT=$CODE_ROOT,CKBV_SCRIPT_ROOT=$SCRIPT_ROOT,CKBV_CKBT_MANIFEST=$CKBT_MANIFEST,CKBV_TON_PILOT_MANIFEST=$TON_PILOT_MANIFEST,CKBV_FRONTEND_SHA256=$FRONTEND_SHA256,CKBV_FORMAL_SHA256=$FORMAL_SHA256,CKBV_RESUME_SHA256=$RESUME_SHA256,CKBV_CHECKPOINT_SHA256=$CHECKPOINT_SHA256,CKBV_REUSE_RUN_ROOTS=$REUSE_ROOTS,CKBV_RAW51_MASK=$RAW51_MASK,CKBV_RAW51_MASK_SHA256=$RAW51_MASK_SHA256"

echo "=== CKBV Slurm scheduler dry validation ==="
sbatch --test-only -p amd --export="$EXPORTS" "$SLURM"
sbatch --test-only -p intel --export="$EXPORTS" "$SLURM"

read_id() {
  local path=$1
  local value=""
  test ! -s "$path" || value=$(tr -d '\r\n' < "$path")
  if test -n "$value" && [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "invalid stored job id in $path: $value" >&2
    exit 2
  fi
  printf '%s' "$value"
}

store_id() {
  local path=$1
  local value=$2
  local temporary="${path}.tmp.$$"
  printf '%s\n' "$value" > "$temporary"
  mv "$temporary" "$path"
}

amd=$(read_id "$AMD_ID_FILE")
intel=$(read_id "$INTEL_ID_FILE")

if test -z "$amd"; then
  echo "=== CKBV submit AMD isolated copy ==="
  amd=$(sbatch --parsable -p amd \
    --output="$BASE/runs/issue27ckbv_amd_%j.out" \
    --error="$BASE/runs/issue27ckbv_amd_%j.err" \
    --export="$EXPORTS" "$SLURM")
  [[ "$amd" =~ ^[0-9]+$ ]] || {
    echo "invalid AMD job id: $amd" >&2
    exit 2
  }
  store_id "$AMD_ID_FILE" "$amd"
else
  echo "AMD job already recorded; not resubmitting: $amd"
fi

if test -z "$intel"; then
  echo "=== CKBV submit Intel isolated copy ==="
  intel=$(sbatch --parsable -p intel \
    --output="$BASE/runs/issue27ckbv_intel_%j.out" \
    --error="$BASE/runs/issue27ckbv_intel_%j.err" \
    --export="$EXPORTS" "$SLURM")
  [[ "$intel" =~ ^[0-9]+$ ]] || {
    echo "invalid Intel job id: $intel" >&2
    exit 2
  }
  store_id "$INTEL_ID_FILE" "$intel"
else
  echo "Intel job already recorded; not resubmitting: $intel"
fi

printf 'CKBV_AMD_JOB_ID=%s\nCKBV_INTEL_JOB_ID=%s\n' "$amd" "$intel"
echo "AMD and Intel outputs/checkpoints are partition-and-job isolated."
echo "Neither job is auto-cancelled."
echo "CKBV_SUBMISSION_RECORDED"

phase_rank() {
  case "$1" in
    startup) printf 1 ;;
    contract_checks) printf 2 ;;
    immutable_planning) printf 3 ;;
    auxiliary_reuse_or_repair) printf 4 ;;
    ton_file_checkpoints) printf 5 ;;
    gotham_member_checkpoints) printf 6 ;;
    aggregate_causal_features) printf 7 ;;
    formal_seed27_model) printf 8 ;;
    validate_and_pack) printf 9 ;;
    complete) printf 10 ;;
    *) printf 0 ;;
  esac
}

job_state() {
  local job=$1
  local state=""
  state=$(squeue -h -j "$job" -o '%T' 2>/dev/null | head -n 1 || true)
  if test -z "$state"; then
    state=$(sacct -j "$job" -X -n -P --format=State 2>/dev/null |
      head -n 1 | cut -d'|' -f1 | sed 's/+.*//' |
      tr -d '[:space:]' || true)
  fi
  printf '%s' "${state:-UNKNOWN}"
}

echo "=== CKBV post-submit real-input runtime gate ==="
echo "This is not a separate job. It watches the submitted result jobs for up to"
echo "${CKBV_RUNTIME_GATE_SECONDS:-600} seconds and only declares runtime pass"
echo "after the ToN real-PCAP phase has completed."

deadline=$(( $(date +%s) + ${CKBV_RUNTIME_GATE_SECONDS:-600} ))
amd_gate=pending
intel_gate=pending
runtime_failure=0
while test "$(date +%s)" -lt "$deadline"; do
  for item in "amd:$amd" "intel:$intel"; do
    partition=${item%%:*}
    job=${item#*:}
    gate_var="${partition}_gate"
    gate=${!gate_var}
    test "$gate" = pending || continue
    root="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_${partition}_${job}"
    phase=unknown
    test ! -s "$root/current_phase.txt" || \
      phase=$(awk -F= '$1 == "phase" {print $2; exit}' \
        "$root/current_phase.txt")
    state=$(job_state "$job")
    if test "$(phase_rank "$phase")" -ge 6; then
      printf -v "$gate_var" '%s' passed
      echo "CKBV_RUNTIME_GATE_PASS partition=$partition job=$job phase=$phase state=$state"
      continue
    fi
    case "$state" in
      FAILED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|BOOT_FAIL|PREEMPTED)
        printf -v "$gate_var" '%s' failed
        runtime_failure=1
        echo "CKBV_RUNTIME_GATE_FAIL partition=$partition job=$job phase=$phase state=$state" >&2
        ;;
      CANCELLED)
        printf -v "$gate_var" '%s' cancelled
        echo "CKBV_RUNTIME_GATE_CANCELLED partition=$partition job=$job phase=$phase"
        ;;
    esac
  done
  test "$runtime_failure" -eq 0 || break
  test "$amd_gate" = pending -o "$intel_gate" = pending || break
  sleep 10
done

if test "$runtime_failure" -ne 0; then
  bash "$SCRIPT_ROOT/issue27ckbv_status_dual.sh"
  echo "CKBV_SUBMISSION_RUNTIME_FAILED" >&2
  exit 4
fi
if test "$amd_gate" = passed -o "$intel_gate" = passed; then
  echo "CKBV_REAL_INPUT_RUNTIME_VALIDATED amd=$amd_gate intel=$intel_gate"
else
  echo "CKBV_SUBMITTED_NOT_YET_RUNTIME_VALIDATED amd=$amd_gate intel=$intel_gate"
  echo "Jobs may still be pending. Use the bundled status command after they start."
fi
