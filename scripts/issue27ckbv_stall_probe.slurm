#!/usr/bin/env bash
#SBATCH -J ckbv_stall_probe
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 06:00:00
#SBATCH --no-requeue

# Bounded compute-node root-cause probe for the CKBV mirai-dos decode stall
# (failure ledger section 10). Diagnostic only: writes no science artifact,
# cache, checkpoint, model, threshold, or metric. The probe job succeeds when
# the diagnostic matrix completes; observed stalls are recorded as data, not
# job failure.

set -euo pipefail

JOB_START_EPOCH=$(date +%s)
WALL_LIMIT_SECONDS=21600
BUDGET_MARGIN_SECONDS=900

BASE=${CKBV_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBV_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
GOTHAM_ZIP="$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip"
MEMBER='raw/malicious/mirai-dos/iotsim-building-monitor-1_0-0_to_OpenvSwitch-28_1-0.pcap'
PCAP_LIB_DIR="/share/software/CST/installed/MCR/bin/glnxa64"
PARTITION_TAG=${CKBV_PROBE_PARTITION:?CKBV_PROBE_PARTITION is required}
FROZEN_CODE_ROOT=${CKBV_FROZEN_CODE_ROOT:?CKBV_FROZEN_CODE_ROOT is required}
PROBE_DRIVER=${CKBV_PROBE_DRIVER:?CKBV_PROBE_DRIVER is required}

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
test -s "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "compute-node libpcap missing: $PCAP_LIB_DIR/libpcap.so.1" >&2
  exit 2
}
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
test -n "$TSHARK" || { echo "tshark missing after module load" >&2; exit 2; }
test "$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')" = \
  "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "TShark shared-libpcap resolution failed" >&2
  exit 2
}
test -s "$FROZEN_CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py" || {
  echo "frozen frontend missing under $FROZEN_CODE_ROOT" >&2
  exit 2
}
test -s "$PROBE_DRIVER" || { echo "probe driver missing: $PROBE_DRIVER" >&2; exit 2; }
test -s "$GOTHAM_ZIP" || { echo "frozen Gotham ZIP missing" >&2; exit 2; }
export PYTHONPATH="$FROZEN_CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1

RUN_ROOT="$BASE/runs/issue27ckbv_stall_probe_${PARTITION_TAG}_${SLURM_JOB_ID}"
test ! -e "$RUN_ROOT" || { echo "refusing existing probe run root: $RUN_ROOT" >&2; exit 2; }
mkdir -p "$RUN_ROOT"
MATRIX="$RUN_ROOT/probe_matrix.csv"
MEMBER_PCAP="$RUN_ROOT/member.pcap"
echo "name,mode,group,extra,limit,rows,elapsed,rc_main,rc_upstream,max_rss_kb" > "$MATRIX"

FINISHED=""
finish() {
  local rc=$?
  test -z "$FINISHED" || return 0
  FINISHED=1
  rm -f "$MEMBER_PCAP" 2>/dev/null || true
  if [ "$(wc -l < "$MATRIX" 2>/dev/null || echo 0)" -gt 1 ]; then
    python "$PROBE_DRIVER" --mode summarize --matrix "$MATRIX" \
      --out "$RUN_ROOT/probe_verdict.json" || echo "verdict generation failed" >&2
  fi
  echo "CKBV_STALL_PROBE_DONE run_root=$RUN_ROOT exit=$rc"
}
trap finish EXIT

TIME_WRAP=()
if test -x /usr/bin/time; then
  TIME_WRAP=(/usr/bin/time -v)
else
  echo "note: /usr/bin/time absent on $(hostname); max_rss_kb column will be empty" \
    | tee -a "$RUN_ROOT/probe_env.txt"
fi

{
  echo "tshark=$TSHARK"
  "$TSHARK" --version 2>/dev/null | head -1
  echo "frozen_frontend_sha256=$(sha256sum "$FROZEN_CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py" | awk '{print $1}')"
  echo "probe_driver_sha256=$(sha256sum "$PROBE_DRIVER" | awk '{print $1}')"
  echo "hostname=$(hostname) partition=$PARTITION_TAG job=$SLURM_JOB_ID"
} | tee -a "$RUN_ROOT/probe_env.txt"

CKBV_FROZEN_CODE_ROOT="$FROZEN_CODE_ROOT" python "$PROBE_DRIVER" --mode selftest

echo "=== TCP preference discovery (never hardcode from memory) ==="
"$TSHARK" -G defaultprefs 2>/dev/null \
  | grep -E '^#?tcp\.(analyze|desegment|track|relative)' \
  | tee "$RUN_ROOT/tcp_prefs.txt" || true
PREF_CANDIDATES=()
for pref in tcp.analyze_sequence_numbers tcp.desegment_tcp_streams \
            tcp.track_bytes_in_flight; do
  if grep -qE "^#?${pref//./\\.}:" "$RUN_ROOT/tcp_prefs.txt"; then
    PREF_CANDIDATES+=("$pref")
  else
    echo "pref absent in this TShark build, skipping variant: $pref"
  fi
done

echo "=== one-time member extraction for file-input probes ==="
python - "$GOTHAM_ZIP" "$MEMBER" "$MEMBER_PCAP" <<'PYEXTRACT'
import shutil, sys, zipfile
zip_path, member, out = sys.argv[1], sys.argv[2], sys.argv[3]
with zipfile.ZipFile(zip_path) as zf, zf.open(member) as raw, open(out, "wb") as dst:
    shutil.copyfileobj(raw, dst, length=4 * 1024 * 1024)
PYEXTRACT
ls -la "$MEMBER_PCAP"
sha256sum "$MEMBER_PCAP" | tee -a "$RUN_ROOT/probe_env.txt"

TSHARK_BASE_ARGS=(-n -T fields -E header=y -E "separator=/t" -E quote=d -E occurrence=f)

budget_ok() {
  local name=$1 mode=$2 group=$3 limit=$4 tmo=$5 now rem
  now=$(date +%s)
  rem=$(( WALL_LIMIT_SECONDS - (now - JOB_START_EPOCH) - BUDGET_MARGIN_SECONDS ))
  if [ "$tmo" -gt "$rem" ]; then
    echo "$name,$mode,$group,,$limit,0,0,-9,0," >> "$MATRIX"
    echo "PROBE_SKIPPED_BUDGET name=$name tmo=$tmo remaining=$rem"
    return 1
  fi
  return 0
}

record_row() {
  local name=$1 mode=$2 group=$3 extra=$4 limit=$5 rows=$6 elapsed=$7 rc_main=$8 rc_up=$9
  local rss
  rss=$(grep -oE 'Maximum resident set size \(kbytes\): [0-9]+' \
        "$RUN_ROOT/probe_${name}.time" 2>/dev/null | grep -oE '[0-9]+$' || echo "")
  echo "$name,$mode,$group,$extra,$limit,$rows,$elapsed,$rc_main,$rc_up,$rss" >> "$MATRIX"
  echo "PROBE_ROW name=$name status_rc=$rc_main rows=$rows elapsed=${elapsed}s max_rss_kb=$rss"
}

parse_rows() {
  grep -oE 'PROBE_ROWS_TOTAL rows=[0-9]+' "$RUN_ROOT/probe_$1.rows.log" 2>/dev/null \
    | grep -oE '[0-9]+$' || echo 0
}

# tshark output includes the -E header=y line; count data lines only so
# file/pipe row counts match producer-mode counts and the -c packet limit.
AWK_TICKS='NR>1 && (NR-1)%100000==0{printf "  rows=%d\n", NR-1} END{printf "PROBE_ROWS_TOTAL rows=%d\n", (NR>0)?NR-1:0}'

probe_file() {
  local name=$1 group=$2 limit=$3 tmo=$4; shift 4
  echo "=== PROBE $name (file input, $group, limit=$limit, timeout=${tmo}s, extra: $*) ==="
  local fields start rc_main
  fields=$(python "$PROBE_DRIVER" --mode fieldargs --group "$group")
  start=$(date +%s)
  local limit_args=()
  test "$limit" -eq 0 || limit_args=(-c "$limit")
  set +e
  ${TIME_WRAP[@]+"${TIME_WRAP[@]}"} timeout -k 30 "$tmo" "$TSHARK" -r "$MEMBER_PCAP" \
      "${TSHARK_BASE_ARGS[@]}" ${limit_args[@]+"${limit_args[@]}"} "$@" $fields \
      2> "$RUN_ROOT/probe_${name}.time" \
    | awk "$AWK_TICKS" | tee "$RUN_ROOT/probe_${name}.rows.log"
  local pipestatus=("${PIPESTATUS[@]}")
  set -e
  rc_main=${pipestatus[0]}
  record_row "$name" file "$group" "$*" "$limit" "$(parse_rows "$name")" \
    "$(( $(date +%s) - start ))" "$rc_main" 0
}

probe_pipe() {
  local name=$1 group=$2 limit=$3 tmo=$4
  echo "=== PROBE $name (stdin pipe input, $group, limit=$limit, timeout=${tmo}s) ==="
  local fields start rc_main rc_up feeder
  fields=$(python "$PROBE_DRIVER" --mode fieldargs --group "$group")
  start=$(date +%s)
  if command -v unzip >/dev/null 2>&1; then
    feeder=(unzip -p "$GOTHAM_ZIP" "$MEMBER")
  else
    feeder=(cat "$MEMBER_PCAP")
  fi
  echo "feeder: ${feeder[0]}"
  set +e
  "${feeder[@]}" 2>/dev/null \
    | ${TIME_WRAP[@]+"${TIME_WRAP[@]}"} timeout -k 30 "$tmo" "$TSHARK" -r - \
        "${TSHARK_BASE_ARGS[@]}" -c "$limit" $fields \
        2> "$RUN_ROOT/probe_${name}.time" \
    | awk "$AWK_TICKS" | tee "$RUN_ROOT/probe_${name}.rows.log"
  local pipestatus=("${PIPESTATUS[@]}")
  set -e
  rc_up=${pipestatus[0]}
  rc_main=${pipestatus[1]}
  # Upstream 141 (SIGPIPE) is the designed consequence of -c; not a failure.
  record_row "$name" pipe "$group" "" "$limit" "$(parse_rows "$name")" \
    "$(( $(date +%s) - start ))" "$rc_main" "$rc_up"
}

probe_producer() {
  local name=$1 limit=$2 deadline=$3 tmo=$4
  echo "=== PROBE $name (formal Python producer path, limit=$limit, deadline=${deadline}s) ==="
  local start rc_main
  start=$(date +%s)
  set +e
  ${TIME_WRAP[@]+"${TIME_WRAP[@]}"} timeout -k 30 "$tmo" \
    python "$PROBE_DRIVER" --mode producer --zip "$GOTHAM_ZIP" --member "$MEMBER" \
      --tshark "$TSHARK" --limit "$limit" --deadline-seconds "$deadline" \
    > "$RUN_ROOT/probe_${name}.rows.log" 2> "$RUN_ROOT/probe_${name}.time"
  rc_main=$?
  set -e
  tail -n 4 "$RUN_ROOT/probe_${name}.rows.log" || true
  record_row "$name" producer P4 "" "$limit" "$(parse_rows "$name")" \
    "$(( $(date +%s) - start ))" "$rc_main" 0
}

STALL_LIMIT=2450000

echo "=== stage 1: input-path isolation at $STALL_LIMIT packets ==="
probe_producer A_producer_P4 "$STALL_LIMIT" 1500 1560
probe_pipe     B_stdinpipe_P4 P4 "$STALL_LIMIT" 1500
probe_file     C_file_P4      P4 "$STALL_LIMIT" 1500

echo "=== stage 2: field-group escalation (file input) ==="
for group in P0 P1 P2; do
  if budget_ok "C_file_${group}" file "$group" "$STALL_LIMIT" 900; then
    probe_file "C_file_${group}" "$group" "$STALL_LIMIT" 900
  fi
done

echo "=== stage 3: preference variants on the full production field set ==="
for pref in ${PREF_CANDIDATES[@]+"${PREF_CANDIDATES[@]}"}; do
  short=${pref#tcp.}
  if budget_ok "C_file_P4_no_${short}" file P4 "$STALL_LIMIT" 900; then
    probe_file "C_file_P4_no_${short}" P4 "$STALL_LIMIT" 900 -o "${pref}:FALSE"
  fi
done

echo "=== stage 4: depth beyond the wall ==="
if budget_ok DEPTH_FULL_P0 file P0 0 1500; then
  probe_file DEPTH_FULL_P0 P0 0 1500
fi
DEPTH_DONE=""
for pref in ${PREF_CANDIDATES[@]+"${PREF_CANDIDATES[@]}"}; do
  test -z "$DEPTH_DONE" || break
  short=${pref#tcp.}
  name="C_file_P4_no_${short}"
  if awk -F, -v n="$name" '$1==n && $8==0 {found=1} END{exit !found}' "$MATRIX"; then
    DEPTH_DONE=1
    if budget_ok "DEPTH_3M_no_${short}" file P4 3000000 1500; then
      probe_file "DEPTH_3M_no_${short}" P4 3000000 1500 -o "${pref}:FALSE"
    fi
    if budget_ok "DEPTH_FULL_no_${short}" file P4 0 3600; then
      probe_file "DEPTH_FULL_no_${short}" P4 0 3600 -o "${pref}:FALSE"
    fi
  fi
done

echo "=== matrix complete; verdict is generated by the exit handler ==="
