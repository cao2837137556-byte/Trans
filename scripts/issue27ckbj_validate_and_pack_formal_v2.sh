#!/bin/bash
# Validate the completed metrics-producing job and create one lightweight pullback archive.
set -euo pipefail

HERE=$(pwd)
BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
JOB_FILE="$HERE/ckbj_formal_seed27_job_id.txt"
test -s "$JOB_FILE" || { echo "missing job-id file: $JOB_FILE" >&2; exit 2; }
job_id=$(tr -d '\r\n' < "$JOB_FILE")
[[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid job id: $job_id" >&2; exit 2; }
state=$(sacct -n -X -j "$job_id" --format=State -P | head -n 1 | cut -d'|' -f1)
exit_code=$(sacct -n -X -j "$job_id" --format=ExitCode -P | head -n 1 | cut -d'|' -f1)
test "$state" = "COMPLETED" || { echo "job is not completed successfully: state=$state exit=$exit_code" >&2; exit 2; }
test "$exit_code" = "0:0" || { echo "job exit code is not 0:0: $exit_code" >&2; exit 2; }

run_name="issue27ckbj_tgn_m1_strict_formal_v2_2026-07-13_hpc_seed27_${job_id}"
run_dir="$BASE/runs/$run_name"
test -d "$run_dir" || { echo "missing formal run directory: $run_dir" >&2; exit 2; }
sacct -j "$job_id" \
  --format=JobIDRaw,JobName%24,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,MaxVMSize,Start,End -P \
  > "$run_dir/slurm_accounting.csv"
test -s "$run_dir/slurm_accounting.csv" || { echo "missing Slurm accounting export" >&2; exit 2; }
for relative in \
  attack_preservation_summary.csv \
  strict_level2_summary.csv \
  global_report_ood_metrics.csv \
  per_attack_family_metrics.csv \
  m1_single_seed_go_no_go.json \
  m1_environment.json \
  run_spec.json \
  m1_role_usage_audit.csv \
  m1_support_training_usage.csv \
  m1_support_family_training_usage.csv \
  m1_negative_sampling_audit.csv \
  m1_ssl_future_label_scope.csv \
  m1_memory_audit.csv \
  m1_loss_curves.csv \
  m1_time_v.txt \
  slurm_accounting.csv
do
  test -s "$run_dir/$relative" || { echo "missing formal output: $run_dir/$relative" >&2; exit 2; }
done

export CKBJ_RUN_DIR="$run_dir"
export CKBJ_EXPECTED_COMMIT
CKBJ_EXPECTED_COMMIT=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
python - <<'PY'
import json
import os
from pathlib import Path

import pandas as pd

run = Path(os.environ["CKBJ_RUN_DIR"])
expected_commit = os.environ["CKBJ_EXPECTED_COMMIT"]
decision = json.loads((run / "m1_single_seed_go_no_go.json").read_text(encoding="utf-8"))
environment = json.loads((run / "m1_environment.json").read_text(encoding="utf-8"))
data = pd.read_csv(run / "m1_role_usage_audit.csv")
support = pd.read_csv(run / "m1_support_training_usage.csv")
negative = pd.read_csv(run / "m1_negative_sampling_audit.csv")
attack = pd.read_csv(run / "attack_preservation_summary.csv")
strict = pd.read_csv(run / "strict_level2_summary.csv")
def booleans(series):
    return series.astype(str).str.strip().str.lower().map({"true": True, "false": False, "1": True, "0": False}).fillna(False)
checks = {
    "registered_decision": decision.get("decision") in {"GO_SIGNAL", "NO_GO", "INCONCLUSIVE_STOP"},
    "seed_27_only": environment.get("seeds") == [27],
    "commit_matches_bundle": environment.get("commit_sha") == expected_commit,
    "review_zero": bool((attack["review_rate"] == 0).all() and (strict["review_rate"] == 0).all()),
    "target_alignment_complete": bool((pd.to_numeric(data["target_alignment_incomplete"]) == 0).all()),
    "all_support_used": bool(booleans(support["used_at_least_once_each_epoch"]).all()),
    "no_ghost_negatives": int(pd.to_numeric(negative["ghost_node_negatives"]).sum()) == 0,
    "no_future_node_identity": not bool(booleans(negative["future_node_identity_used"]).any()),
}
payload = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "decision": decision}
(run / "pullback_validation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
if payload["status"] != "PASS":
    raise SystemExit("formal result validation failed")
PY

mkdir -p "$HERE/pullback"
archive="$HERE/pullback/${run_name}_pullback.tar.gz"
tar -czf "$archive" -C "$BASE" \
  "runs/$run_name" \
  "runs/issue27ckbj_m1_v2_${job_id}.out" \
  "runs/issue27ckbj_m1_v2_${job_id}.err" \
  "runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc/c1_report_extension_ready.json" \
  "runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc/c1_report_only_extension_manifest.csv" \
  "runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc/c1_report_only_extension_manifest_sha256.txt"
sha256sum "$archive" | tee "$archive.sha256"
echo "PULLBACK_ARCHIVE=$archive"
