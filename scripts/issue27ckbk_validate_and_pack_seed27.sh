#!/bin/bash
# Usage: CKBK_PARTITION=amd CKBK_JOB_ID=123 bash this_script.sh
set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
PARTITION=${CKBK_PARTITION:?set CKBK_PARTITION to amd or intel}
JOB_ID=${CKBK_JOB_ID:?set CKBK_JOB_ID}
[[ "$PARTITION" = "amd" || "$PARTITION" = "intel" ]] || { echo "invalid partition" >&2; exit 2; }
[[ "$JOB_ID" =~ ^[0-9]+$ ]] || { echo "invalid job id" >&2; exit 2; }
RUN_NAME="issue27ckbk_temporal_generalization_formal_v1_2026-07-14_hpc_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
HERE=$(cd "$(dirname "$0")/../.." && pwd)
PACK_ROOT="$HERE/pullback_${PARTITION}_${JOB_ID}"
ARCHIVE="$HERE/issue27ckbk_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"

state=$(sacct -j "$JOB_ID" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//')
exit_code=$(sacct -j "$JOB_ID" -X -n -P --format=ExitCode | head -n 1 | cut -d'|' -f1)
test "$state" = "COMPLETED" && test "$exit_code" = "0:0" || { echo "job is not COMPLETED 0:0: state=$state exit=$exit_code" >&2; exit 2; }
test -s "$RUN_ROOT/final_aggregate/single_seed_route_decision.json" || { echo "missing aggregate decision" >&2; exit 2; }
test -s "$RUN_ROOT/stage_1_tgn/stage_status.json" || { echo "missing TGN stage status" >&2; exit 2; }
test -s "$RUN_ROOT/stage_2_graphmixer/stage_status.json" || { echo "missing GraphMixer stage status" >&2; exit 2; }
test -s "$RUN_ROOT/run_timing_and_exit_codes.txt" || { echo "missing timing audit" >&2; exit 2; }
test ! -e "$PACK_ROOT" && test ! -e "$ARCHIVE" || { echo "pullback target already exists" >&2; exit 2; }

source "$BASE/scripts/00_env_issue27ckc.sh"
python - "$RUN_ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
decision = json.loads((root / "final_aggregate/single_seed_route_decision.json").read_text())
assert decision["seed"] == 27
assert decision["review_rate"] == 0.0
assert decision["seeds_37_47_launched"] is False
assert decision["untouched_final_manifest_opened"] is False
for stage in ("stage_1_tgn", "stage_2_graphmixer"):
    status = json.loads((root / stage / "stage_status.json").read_text())
    assert status["status"] == "COMPLETED"
    assert status["review_rate"] == 0.0
print("CKBK_RESULT_VALIDATION=PASS")
PY

mkdir -p "$PACK_ROOT"
cp -a "$RUN_ROOT" "$PACK_ROOT/"
cp "$BASE/runs/issue27ckbk_seed27_${PARTITION}_${JOB_ID}.out" "$PACK_ROOT/" 2>/dev/null || true
cp "$BASE/runs/issue27ckbk_seed27_${PARTITION}_${JOB_ID}.err" "$PACK_ROOT/" 2>/dev/null || true
sacct -j "$JOB_ID" --format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS,Start,End -P \
  > "$PACK_ROOT/slurm_accounting.csv"
tar -czf "$ARCHIVE" -C "$HERE" "$(basename "$PACK_ROOT")"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
echo "PULLBACK_ARCHIVE=$ARCHIVE"
cat "$ARCHIVE.sha256"
