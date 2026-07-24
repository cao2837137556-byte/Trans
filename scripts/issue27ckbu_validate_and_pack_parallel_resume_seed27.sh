#!/bin/bash
set -euo pipefail

BASE=${CKBU_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${CKBU_PARTITION:?missing CKBU_PARTITION}
JOB_ID=${CKBU_JOB_ID:?missing CKBU_JOB_ID}
ALLOW_RUNNING=${CKBU_ALLOW_RUNNING:-0}
case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac

RUN_ROOT="$BASE/runs/issue27ckbu_unified_process_rescue_parallel_v2_2026-07-24_seed27_${PARTITION}_${JOB_ID}"
ARCHIVE="$BASE/runs/issue27ckbu_parallel_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
test -d "$RUN_ROOT" || { echo "missing CKBU parallel run root: $RUN_ROOT" >&2; exit 2; }
if test "$ALLOW_RUNNING" != 1; then
  state=$(sacct -j "$JOB_ID" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
  test "$state" = COMPLETED || { echo "job is not COMPLETED: $state" >&2; exit 2; }
fi

python - "$RUN_ROOT" "$PARTITION" "$JOB_ID" <<'PY'
import json, sys
from pathlib import Path
import pandas as pd

root=Path(sys.argv[1]); partition=sys.argv[2]; job=sys.argv[3]
required=[
 "ckbu_single_seed_go_no_go.json","attack_preservation_summary.csv","strict_level2_summary.csv",
 "ckbu_candidate_selection.csv","ckbu_support_training_usage.csv","ckbu_record_predictions.csv.gz",
 "ckbu_environment.json","run_spec.json","codex_readout.md","ckbu_gotham_unified_causal_ready.json",
 "ckbu_auxiliary_unified_causal_ready.json","ckbu_ton_raw_pcap_pilot_causal_ready.json",
 "ckbu_gotham_parallel_ready.json","ckbu_auxiliary_parallel_ready.json",
 "ckbu_gotham_parallel_reuse_audit.csv","ckbu_auxiliary_parallel_reuse_audit.csv",
]
missing=[name for name in required if not (root/name).is_file() or not (root/name).stat().st_size]
if missing: raise SystemExit(f"missing CKBU result files: {missing}")
decision=json.loads((root/"ckbu_single_seed_go_no_go.json").read_text())
if decision.get("decision") not in {"GO_SIGNAL","NO_GO"}: raise SystemExit("invalid scientific decision")
g=json.loads((root/"ckbu_gotham_unified_causal_ready.json").read_text())
a=json.loads((root/"ckbu_auxiliary_unified_causal_ready.json").read_text())
t=json.loads((root/"ckbu_ton_raw_pcap_pilot_causal_ready.json").read_text())
gp=json.loads((root/"ckbu_gotham_parallel_ready.json").read_text())
ap=json.loads((root/"ckbu_auxiliary_parallel_ready.json").read_text())
if g.get("sources") != 30 or g.get("targets") != 325067: raise SystemExit(f"Gotham coverage drift: {g}")
if a.get("sources") != 31 or a.get("targets") != 18600: raise SystemExit(f"aux coverage drift: {a}")
if t.get("rows") != 12000 or t.get("reserved_injection_mitm_model_rows") != 0: raise SystemExit(f"ToN scope drift: {t}")
if gp.get("sources") != 30 or gp.get("scientific_protocol_changed") is not False:
    raise SystemExit(f"Gotham parallel audit drift: {gp}")
if ap.get("sources") != 31 or ap.get("scientific_protocol_changed") is not False:
    raise SystemExit(f"auxiliary parallel audit drift: {ap}")
for name, expected in (
    ("ckbu_gotham_parallel_reuse_audit.csv", 30),
    ("ckbu_auxiliary_parallel_reuse_audit.csv", 31),
):
    frame=pd.read_csv(root/name)
    if len(frame)!=expected or frame.source_group.nunique()!=expected:
        raise SystemExit(f"parallel reuse audit drift: {name}")
support=pd.read_csv(root/"ckbu_support_training_usage.csv")
tabm=support[support.candidate.eq("H2-TabMProcessHead")]
if len(tabm)!=385 or tabm.uid.nunique()!=385 or not tabm.used_at_least_once_each_epoch.astype(bool).all():
    raise SystemExit("385-row support usage contract failed")
review=pd.read_csv(root/"ckbu_review_audit.csv")
if int(review.review_count.sum()) or float(review.review_rate.max()) != 0.0:
    raise SystemExit("review is not zero")
env=json.loads((root/"ckbu_environment.json").read_text())
if str(env.get("slurm_job_id")) != job or env.get("slurm_partition") != partition:
    raise SystemExit("job identity drift")
print(json.dumps({
    "status":"CKBU_PARALLEL_RESULT_VALID",
    "decision":decision["decision"],
    "partition":partition,
    "job_id":job,
    "gotham_reused_sources":gp["reused_sources"],
    "auxiliary_reused_sources":ap["reused_sources"],
},indent=2))
PY

rm -f "$ARCHIVE" "$ARCHIVE.sha256"
tar -C "$RUN_ROOT" -czf "$ARCHIVE" \
  --exclude='gotham_causal_cache' --exclude='auxiliary_causal_cache' \
  --exclude='source_runtime' --exclude='parallel_source_logs' .
cd "$BASE/runs"
sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256"
sha256sum -c "$(basename "$ARCHIVE").sha256"
echo "CKBU_PARALLEL_PULLBACK_ARCHIVE=$ARCHIVE"
