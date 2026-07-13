#!/bin/bash
# Execute from the extracted CKBI/CKBH upload bundle on HPC.
# No remote Git, no pip/Conda/container, and no independent preflight job.
set -euo pipefail
echo "CKBI Stage A is complete and CKBH-v1 is superseded; use the CKBJ Stage-B-only bundle" >&2
exit 2

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
HERE=$(pwd)
PAYLOAD="$HERE/payload"
EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
BASE_MANIFEST="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3/tgn_source_event_plan_frozen.csv"
EXPECTED_BASE_SHA256=b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67

test -d "$BASE" || { echo "missing HPC project directory: $BASE" >&2; exit 2; }
test -d "$PAYLOAD" || { echo "missing upload payload" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing provisioned environment script" >&2; exit 2; }
test -s "$BASE_MANIFEST" || { echo "missing frozen CKBE manifest" >&2; exit 2; }
test "$(sha256sum "$BASE_MANIFEST" | awk '{print $1}')" = "$EXPECTED_BASE_SHA256" || { echo "frozen CKBE manifest hash changed" >&2; exit 2; }
test ! -e "$EXT" || { echo "report-only extension path already exists; stop rather than overwrite: $EXT" >&2; exit 2; }

for relative in \
  repo/ood/issue27ckbi_tgn_report_only_cache_extension_v1.py \
  repo/ood/issue27ckbh_tgn_m1_strict_formal_v1.py \
  scripts/issue27ckbi_tgn_report_extension.slurm \
  scripts/issue27ckbh_tgn_m1_formal.slurm
do
  test -s "$PAYLOAD/$relative" || { echo "missing bundle file: $relative" >&2; exit 2; }
  target="$BASE/$relative"
  if test -e "$target" && ! cmp -s "$PAYLOAD/$relative" "$target"; then
    echo "remote target differs; stop rather than overwrite: $target" >&2
    exit 2
  fi
  if test ! -e "$target"; then
    install -D -m 0644 "$PAYLOAD/$relative" "$target"
  fi
done

export M1_COMMIT_SHA
M1_COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
job_a=$(sbatch "$BASE/scripts/issue27ckbi_tgn_report_extension.slurm" | awk '{print $NF}')
[[ "$job_a" =~ ^[0-9]+$ ]] || { echo "invalid CKBI job id: $job_a" >&2; exit 2; }
job_b=$(sbatch --dependency="afterok:${job_a}" "$BASE/scripts/issue27ckbh_tgn_m1_formal.slurm" | awk '{print $NF}')
[[ "$job_b" =~ ^[0-9]+$ ]] || { echo "invalid CKBH job id: $job_b" >&2; exit 2; }
printf '%s\n' "$job_a" > "$HERE/ckbi_extension_job_id.txt"
printf '%s\n' "$job_b" > "$HERE/ckbh_formal_seed27_job_id.txt"
printf 'CKBI_JOB_ID=%s\nCKBH_JOB_ID=%s\nDEPENDENCY=afterok:%s\n' "$job_a" "$job_b" "$job_a"
