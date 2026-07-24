#!/bin/bash
set -u

BASE=${CKBU_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
HERE=$(cd "$(dirname "$0")/../.." && pwd)
AMD=$(tr -d '\r\n' < "$HERE/ckbu_parallel_seed27_amd_job_id.txt" 2>/dev/null || true)
INTEL=$(tr -d '\r\n' < "$HERE/ckbu_parallel_seed27_intel_job_id.txt" 2>/dev/null || true)
ids=$(printf '%s,%s' "$AMD" "$INTEL" | sed 's/^,//;s/,$//')

echo "=== CKBU parallel queue ==="
test -n "$ids" && squeue -j "$ids" -o "%.18i %.9P %.22j %.10T %.10M %.10l %.6D %R" 2>/dev/null || true
echo "=== CKBU parallel accounting ==="
test -n "$ids" && sacct -j "$ids" \
  --format=JobID,JobName%22,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,ReqMem,Start,End \
  2>/dev/null || true

for item in "amd:$AMD" "intel:$INTEL"; do
  partition=${item%%:*}; job=${item#*:}
  test -n "$job" || continue
  root="$BASE/runs/issue27ckbu_unified_process_rescue_parallel_v2_2026-07-24_seed27_${partition}_${job}"
  echo "=== $partition / $job ==="
  if test -s "$root/ckbu_single_seed_go_no_go.json"; then
    cat "$root/ckbu_single_seed_go_no_go.json"
  elif test -s "$root/job_failure.txt"; then
    cat "$root/job_failure.txt"
    for log in "$root/gotham_parallel_stage.log" "$root/auxiliary_parallel_stage.log" "$root/ton_parallel_stage.log"; do
      test -s "$log" && { echo "--- $(basename "$log") ---"; tail -n 60 "$log"; }
    done
    tail -n 80 "$BASE/runs/issue27ckbu_parallel_${partition}_${job}.err" 2>/dev/null || true
  else
    gotham=0; aux=0
    test -d "$root/gotham_causal_cache" && gotham=$(find "$root/gotham_causal_cache" -maxdepth 1 -name '*.npz' | wc -l)
    test -d "$root/auxiliary_causal_cache" && aux=$(find "$root/auxiliary_causal_cache" -maxdepth 1 -name '*.npz' | wc -l)
    echo "gotham_cache=$gotham / 30"
    echo "auxiliary_cache=$aux / 31"
    for log in "$root/gotham_parallel_stage.log" "$root/auxiliary_parallel_stage.log" "$root/ton_parallel_stage.log"; do
      test -s "$log" && { echo "--- $(basename "$log") ---"; tail -n 8 "$log"; }
    done
    tail -n 12 "$BASE/runs/issue27ckbu_parallel_${partition}_${job}.out" 2>/dev/null || true
    tail -n 20 "$BASE/runs/issue27ckbu_parallel_${partition}_${job}.err" 2>/dev/null || true
  fi
done
