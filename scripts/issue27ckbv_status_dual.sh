#!/bin/bash
set -u

BASE=${CKBV_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
HERE=$(cd "$(dirname "$0")/../.." && pwd)
AMD=$(tr -d '\r\n' < "$HERE/ckbv_seed27_amd_job_id.txt" 2>/dev/null || true)
INTEL=$(tr -d '\r\n' < "$HERE/ckbv_seed27_intel_job_id.txt" 2>/dev/null || true)
ids=$(printf '%s,%s' "$AMD" "$INTEL" | sed 's/^,//;s/,$//')

echo "=== CKBV queue ==="
test -z "$ids" || squeue -j "$ids" \
  -o "%.18i %.9P %.20j %.10T %.10M %.10l %.6D %R" 2>/dev/null || true
echo "=== CKBV accounting ==="
test -z "$ids" || sacct -j "$ids" \
  --format=JobID,JobName%20,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,ReqMem,Start,End \
  2>/dev/null || true

for item in "amd:$AMD" "intel:$INTEL"; do
  partition=${item%%:*}
  job=${item#*:}
  test -n "$job" || continue
  root="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_${partition}_${job}"
  echo "=== $partition / $job ==="

  if test -s "$root/ckbu_single_seed_go_no_go.json"; then
    cat "$root/ckbu_single_seed_go_no_go.json"
    test ! -s "$root/ckbv_result_validation.json" || \
      cat "$root/ckbv_result_validation.json"
    test ! -s "$root/codex_readout.md" || cat "$root/codex_readout.md"
    continue
  fi

  if test -s "$root/job_failure.txt"; then
    cat "$root/job_failure.txt"
    echo "--- concise failure cause ---"
    grep -RhE \
      'RuntimeError:|ValueError:|AssertionError:|member watchdog|subprocess failed|timeout|returned without valid checkpoint' \
      "$root"/*.log "$root/member_logs" "$root/ton_file_logs" \
      2>/dev/null | tail -n 12 || true
    tail -n 12 "$BASE/runs/issue27ckbv_${partition}_${job}.err" \
      2>/dev/null || true
    echo "Set CKBV_STATUS_VERBOSE=1 and inspect the named log only if needed."
    if test "${CKBV_STATUS_VERBOSE:-0}" = 1; then
      tail -n 120 "$root/gotham_checkpoint_stage.log" 2>/dev/null || true
    fi
    continue
  fi

  test ! -s "$root/current_phase.txt" || cat "$root/current_phase.txt"
  gotham_sources=0
  gotham_members=0
  auxiliary=0
  ton_files=0
  member_total=0
  test ! -d "$root/gotham_causal_cache" || \
    gotham_sources=$(find "$root/gotham_causal_cache" -maxdepth 1 -name '*.npz' | wc -l)
  test ! -d "$root/gotham_member_cache" || \
    gotham_members=$(find "$root/gotham_member_cache" -maxdepth 1 -name '*.npz' | wc -l)
  test ! -d "$root/auxiliary_causal_cache" || \
    auxiliary=$(find "$root/auxiliary_causal_cache" -maxdepth 1 -name '*.npz' | wc -l)
  test ! -d "$root/ton_file_cache" || \
    ton_files=$(find "$root/ton_file_cache" -maxdepth 1 -name '*.npz' | wc -l)
  test ! -s "$root/ckbv_gotham_member_plan.csv" || \
    member_total=$(( $(wc -l < "$root/ckbv_gotham_member_plan.csv") - 1 ))
  printf 'gotham_sources=%s/30\ngotham_members=%s/%s\nauxiliary=%s/31\nton_files=%s/4\n' \
    "$gotham_sources" "$gotham_members" "$member_total" "$auxiliary" "$ton_files"

  echo "--- CPU / memory / I/O ---"
  sstat -j "${job}.batch" \
    --format=JobID,AveCPU,AveRSS,MaxRSS,MaxDiskRead,MaxDiskWrite \
    2>/dev/null || true

  echo "--- latest real progress ---"
  find "$root/member_logs" -maxdepth 1 -name '*.progress.json' \
    -type f -printf '%T@ %p\n' 2>/dev/null |
    sort -nr | head -n 4 | while read -r _ path; do
      python - "$path" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
print(
    "member_progress "
    f"index={value['member_index']} phase={value['phase']} "
    f"decoded={value['decoded_events']} heartbeat={value['heartbeat_sequence']}"
)
PY
    done
  find "$root/member_logs" "$root/ton_file_logs" \
    -maxdepth 1 -type f -printf '%T@ %TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' \
    2>/dev/null |
    sort -nr |
    head -n 8 || true
  grep -h -E \
    'CKBV_(MEMBER_(START|PROGRESS|SCAN_COMPLETE|COMPLETE|FAILED)|TON_(COUNT_PROGRESS|FEATURE_PROGRESS|ATTACK_PROGRESS|CHECKPOINT_READY|FILE_FAILED)|THROUGHPUT)' \
    "$root"/member_logs/*.log \
    "$root"/ton_file_logs/*.log \
    "$root"/gotham_checkpoint_stage.log \
    "$root"/ton_checkpoint_stage.log 2>/dev/null |
    tail -n 20 || true

  test ! -s "$root/ckbv_throughput_projection.json" || {
    echo "--- throughput projection ---"
    cat "$root/ckbv_throughput_projection.json"
  }
  echo "--- Slurm stdout/stderr tail ---"
  tail -n 15 "$BASE/runs/issue27ckbv_${partition}_${job}.out" \
    2>/dev/null || true
  tail -n 30 "$BASE/runs/issue27ckbv_${partition}_${job}.err" \
    2>/dev/null || true
done
