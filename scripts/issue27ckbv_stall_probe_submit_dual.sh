#!/usr/bin/env bash
# Submit the bounded CKBV stall probe to both partitions (ledger section 10).
# Diagnostic only; does not touch formal run roots, caches, or checkpoints.
set -euo pipefail

PAYLOAD=$(cd "$(dirname "$0")/.." && pwd)
BASE=${CKBV_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
R8_ROOT=${CKBV_R8_ROOT:-/public/home/jiangxinwei.zr/work/paper04/m1_transfer/issue27ckbv_checkpointed_process_seed27_dual_20260726_r8/issue27ckbv_checkpointed_process_seed27_dual_20260726_r8}
FROZEN_CODE_ROOT="$R8_ROOT/payload/repo/ood"
DRIVER="$PAYLOAD/repo/ood/issue27ckbv_stall_probe_driver_v1.py"
SLURM_SCRIPT="$PAYLOAD/scripts/issue27ckbv_stall_probe.slurm"

test -s "$FROZEN_CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py" || {
  echo "frozen r8 frontend not found: $FROZEN_CODE_ROOT" >&2
  echo "set CKBV_R8_ROOT to the extracted r8 bundle directory" >&2
  exit 2
}
test -s "$DRIVER" || { echo "probe driver missing: $DRIVER" >&2; exit 2; }
test -s "$SLURM_SCRIPT" || { echo "probe slurm missing: $SLURM_SCRIPT" >&2; exit 2; }
test -d "$BASE/runs" || { echo "runs dir missing under $BASE" >&2; exit 2; }

echo "=== login-node static checks ==="
cd "$BASE"
source scripts/00_env_issue27ckc.sh
python -m py_compile "$DRIVER"
CKBV_FROZEN_CODE_ROOT="$FROZEN_CODE_ROOT" python "$DRIVER" --mode selftest
bash -n "$SLURM_SCRIPT"

echo "=== duplicate-submission guard ==="
if squeue -u "$USER" -n ckbv_stall_probe -h 2>/dev/null | grep -q .; then
  echo "a ckbv_stall_probe job is already queued or running; refusing" >&2
  squeue -u "$USER" -n ckbv_stall_probe
  exit 2
fi

echo "=== sbatch validation and dual submission ==="
declare -A JOB_IDS
for PART in amd intel; do
  sbatch --test-only -p "$PART" \
    --export=ALL,CKBV_PROBE_PARTITION=$PART,CKBV_FROZEN_CODE_ROOT=$FROZEN_CODE_ROOT,CKBV_PROBE_DRIVER=$DRIVER \
    -o "$BASE/runs/ckbv_stall_probe_${PART}_%j.out" \
    -e "$BASE/runs/ckbv_stall_probe_${PART}_%j.err" \
    "$SLURM_SCRIPT"
done
for PART in amd intel; do
  jid=$(sbatch -p "$PART" \
    --export=ALL,CKBV_PROBE_PARTITION=$PART,CKBV_FROZEN_CODE_ROOT=$FROZEN_CODE_ROOT,CKBV_PROBE_DRIVER=$DRIVER \
    -o "$BASE/runs/ckbv_stall_probe_${PART}_%j.out" \
    -e "$BASE/runs/ckbv_stall_probe_${PART}_%j.err" \
    "$SLURM_SCRIPT" | awk '{print $4}')
  JOB_IDS[$PART]=$jid
  echo "CKBV_STALL_PROBE_SUBMITTED partition=$PART job=$jid"
done

echo
echo "monitor with:"
echo "  squeue -u \$USER -n ckbv_stall_probe"
for PART in amd intel; do
  echo "  tail -f $BASE/runs/ckbv_stall_probe_${PART}_${JOB_IDS[$PART]}.out"
done
echo "verdict files will appear at:"
for PART in amd intel; do
  echo "  $BASE/runs/issue27ckbv_stall_probe_${PART}_${JOB_IDS[$PART]}/probe_verdict.json"
done
