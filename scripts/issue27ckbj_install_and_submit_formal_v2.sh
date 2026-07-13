#!/bin/bash
# Run from the extracted CKBJ upload bundle on HPC.
# Installs exactly three new experiment files and submits exactly one
# metrics-producing Stage-B job.  CKBI Stage A is reused and never resubmitted.
set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
HERE=$(pwd)
PAYLOAD="$HERE/payload"
PARTITION=${M1_PARTITION:-intel}
T0_MANIFEST="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3/tgn_source_event_plan_frozen.csv"
TGN_EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
EXPECTED_T0_SHA256=b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67
EXPECTED_C1_PLAN_SHA256=414616332159eb90553213d6656c3d072a701ea93a02df464acdfa6cebc128f2
EXPECTED_C1_TARGET_SHA256=74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158
SUPERSEDED_R2_SLURM_SHA256=f7291416e751b900eea244535f72d60da37e82cf91628505481df02bf9c7006e

test -d "$BASE" || { echo "missing HPC project directory: $BASE" >&2; exit 2; }
test -d "$PAYLOAD" || { echo "missing bundle payload: $PAYLOAD" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing provisioned environment script" >&2; exit 2; }
test -s "$T0_MANIFEST" || { echo "missing frozen CKBE manifest" >&2; exit 2; }
test -s "$TGN_EXT/extension_ready.json" || { echo "completed CKBI Stage A is missing" >&2; exit 2; }
test -s "$TGN_EXT/report_only_extension_manifest_frozen.csv" || { echo "CKBI extension manifest is missing" >&2; exit 2; }
test -s "$C1_ROOT/canonical_source_load_plan.csv" || { echo "frozen C1 plan is missing" >&2; exit 2; }
test -s "$C1_ROOT/canonical_source_target_index.csv" || { echo "frozen C1 target manifest is missing" >&2; exit 2; }
test -d "$C1_ROOT/hpc_canonical_c1_cache" || { echo "frozen C1 cache is missing" >&2; exit 2; }
test "$(sha256sum "$T0_MANIFEST" | awk '{print $1}')" = "$EXPECTED_T0_SHA256" || { echo "frozen CKBE manifest hash changed" >&2; exit 2; }
test "$(sha256sum "$C1_ROOT/canonical_source_load_plan.csv" | awk '{print $1}')" = "$EXPECTED_C1_PLAN_SHA256" || { echo "frozen C1 plan hash changed" >&2; exit 2; }
test "$(sha256sum "$C1_ROOT/canonical_source_target_index.csv" | awk '{print $1}')" = "$EXPECTED_C1_TARGET_SHA256" || { echo "frozen C1 target hash changed" >&2; exit 2; }

for relative in \
  repo/ood/issue27ckbj_c1_report_only_cache_extension_v1.py \
  repo/ood/issue27ckbj_tgn_m1_strict_formal_v2.py \
  scripts/issue27ckbj_tgn_m1_formal_v2.slurm
do
  test -s "$PAYLOAD/$relative" || { echo "missing bundle file: $relative" >&2; exit 2; }
  target="$BASE/$relative"
  if test -e "$target" && ! cmp -s "$PAYLOAD/$relative" "$target"; then
    if test "$relative" = "scripts/issue27ckbj_tgn_m1_formal_v2.slurm" && \
       test "$(sha256sum "$target" | awk '{print $1}')" = "$SUPERSEDED_R2_SLURM_SHA256"; then
      echo "replacing exact superseded r2 Slurm launcher: $target"
      install -D -m 0644 "$PAYLOAD/$relative" "$target"
    else
      echo "remote experiment target differs from both corrected and known r2 content; stop: $target" >&2
      exit 2
    fi
  fi
  if test ! -e "$target"; then
    install -D -m 0644 "$PAYLOAD/$relative" "$target"
  fi
done

M1_COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
[[ "$M1_COMMIT_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid bundle commit SHA: $M1_COMMIT_SHA" >&2; exit 2; }
job_id=$(sbatch --parsable --partition="$PARTITION" \
  --chdir="$BASE" \
  --output="$BASE/runs/issue27ckbj_m1_v2_%j.out" \
  --error="$BASE/runs/issue27ckbj_m1_v2_%j.err" \
  --export="ALL,M1_COMMIT_SHA=$M1_COMMIT_SHA" \
  "$BASE/scripts/issue27ckbj_tgn_m1_formal_v2.slurm")
job_id=${job_id%%;*}
[[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid CKBJ job id: $job_id" >&2; exit 2; }
printf '%s\n' "$job_id" > "$HERE/ckbj_formal_seed27_job_id.txt"
printf 'CKBJ_JOB_ID=%s\nPARTITION=%s\nCKBI_STAGE_A=REUSED_NOT_RESUBMITTED\n' "$job_id" "$PARTITION"
