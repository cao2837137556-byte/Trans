#!/bin/bash
# CKBG is a bounded M1 implementation canary, not the formal full M1 job.
#SBATCH -J ckbg_canary
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH -o runs/issue27ckbg_canary_%j.out
#SBATCH -e runs/issue27ckbg_canary_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
C1PLAN="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_load_plan.csv"
C1CACHE="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/hpc_canonical_c1_cache"
OUT="$BASE/runs/issue27ckbg_tgn_m1_canary_v1_2026-07-12_hpc_canary"
PREFLIGHT="$BASE/runs/issue27ckbf_tgn_m1_preflight_v1_2026-07-12_hpc_preflight"

cd "$BASE"
test -s scripts/00_env_issue27ckc.sh || { echo "missing provisioned scripts/00_env_issue27ckc.sh" >&2; exit 2; }
source scripts/00_env_issue27ckc.sh
test -d "$T0/tgn_event_cache" || { echo "missing CKBE T0 cache" >&2; exit 2; }
test -d "$C1CACHE" || { echo "missing CKAT canonical C1 cache" >&2; exit 2; }
test -s "$PREFLIGHT/run_spec.json" || { echo "missing passing CKBF preflight" >&2; exit 2; }
grep -q '"held_exclusion_pass": true' "$PREFLIGHT/run_spec.json" || { echo "CKBF held exclusion did not pass" >&2; exit 2; }
grep -q '"support_alignment_pass": true' "$PREFLIGHT/run_spec.json" || { echo "CKBF support alignment did not pass" >&2; exit 2; }
grep -q '"target_alignment_pass": true' "$PREFLIGHT/run_spec.json" || { echo "CKBF frozen target alignment did not pass" >&2; exit 2; }

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}

python -m py_compile repo/ood/issue27ckbf_tgn_m1_preflight_v1.py repo/ood/issue27ckbg_tgn_m1_canary_v1.py
python -u repo/ood/issue27ckbg_tgn_m1_canary_v1.py \
  --t0-root "$T0" \
  --c1-cache "$C1CACHE" \
  --c1-plan "$C1PLAN" \
  --out "$OUT" \
  --held-value iotsim-ip-camera-street \
  --c1-train-cap 1200 \
  --max-events-per-source 200000 \
  --per-attack-family 2 \
  --benign-cap 64 \
  --epochs 3 \
  --detach-every 32 \
  --seed 27
