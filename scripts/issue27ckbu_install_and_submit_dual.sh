#!/bin/bash
# Run from the extracted upload bundle on the HPC login node.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBU_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBU_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
AMD_ID_FILE="$HERE/ckbu_seed27_amd_job_id.txt"
INTEL_ID_FILE="$HERE/ckbu_seed27_intel_job_id.txt"
CKBT_REL="runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22"
CKBT_ROOT="$BASE/$CKBT_REL"
CKBQ_ROOT="$BASE/runs/issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_amd_153037"
PCAP_LIB_DIR="/share/software/CST/installed/MCR/bin/glnxa64"

test -d "$BASE" || { echo "missing experiment directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing allowed environment script" >&2; exit 2; }
test ! -e "$AMD_ID_FILE" && test ! -e "$INTEL_ID_FILE" || {
  echo "CKBU bundle already submitted; refusing duplicate submission" >&2
  exit 2
}

FILES=(
  repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py
  repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py
  scripts/issue27ckbu_unified_process_rescue_formal.slurm
  scripts/issue27ckbu_validate_and_pack_seed27.sh
  scripts/issue27ckbu_status_dual.sh
  runs/mainline_docs/ckbu_unified_process_rescue_preregistered_20260723.md
  runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv
  runs/mainline_docs/ckbu_missing_ckbt_dependency_fix_20260724.md
  "$CKBT_REL/aux_process_support_candidate_manifest.csv"
  "$CKBT_REL/contract.json"
  "$CKBT_REL/independent_validation.json"
  "$CKBT_REL/input_file_hashes.csv"
  "$CKBT_REL/manifest.csv"
  "$CKBT_REL/pair_exact_join_audit.csv"
  "$CKBT_REL/reserved_toniot_conn_sources.csv"
  "$CKBT_REL/summary.md"
)
for relative in "${FILES[@]}"; do
  source_path="$HERE/payload/$relative"
  target_path="$BASE/$relative"
  test -s "$source_path" || { echo "bundle payload missing: $relative" >&2; exit 2; }
  if test -e "$target_path"; then
    source_hash=$(sha256sum "$source_path" | awk '{print $1}')
    target_hash=$(sha256sum "$target_path" | awk '{print $1}')
    test "$source_hash" = "$target_hash" || {
      echo "remote target differs; no overwrite allowed: $target_path" >&2
      exit 2
    }
  else
    install -D -m 0644 "$source_path" "$target_path"
  fi
done

for path in \
  "$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip" \
  "$CKBT_ROOT/aux_process_support_candidate_manifest.csv" \
  "$CKBT_ROOT/contract.json" \
  "$CKBT_ROOT/independent_validation.json" \
  "$CKBQ_ROOT/ckbq_record_predictions.csv.gz" \
  "$CKBQ_ROOT/ckbo_auxiliary_benign_manifest.csv" \
  "$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc/report_extension_recorded_targets.csv" \
  "$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_target_index.csv" \
  "$BASE/runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_2.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_scanning1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/password_normal1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/injection_normal1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/MITM_normal1.pcap"; do
  test -s "$path" || { echo "required data not uploaded: $path" >&2; exit 2; }
done
test -d "$DATA_ROOT/external/ton_iot_raw_network/extracted" || {
  echo "required immutable directory missing: $DATA_ROOT/external/ton_iot_raw_network/extracted" >&2
  exit 2
}

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
test -s "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "shared compute-node libpcap missing: $PCAP_LIB_DIR/libpcap.so.1" >&2
  exit 2
}
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
PCAP_RESOLVED=$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')
test "$PCAP_RESOLVED" = "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "TShark did not resolve shared libpcap: $PCAP_RESOLVED" >&2
  exit 2
}
TSHARK_VERSION=$("$TSHARK" --version | head -n 1)
case "$TSHARK_VERSION" in
  "TShark (Wireshark) 4.6.6"*) ;;
  *) echo "unexpected TShark: $TSHARK_VERSION" >&2; exit 2 ;;
esac
TSHARK_PROBE=$("$TSHARK" -n \
  -r "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_1.pcap" \
  -c 1 -T fields -e frame.number 2>/dev/null)
test "$TSHARK_PROBE" = "1" || {
  echo "TShark/shared-libpcap real-PCAP probe failed: $TSHARK_PROBE" >&2
  exit 2
}
echo "CKBU_TSHARK_SHARED_LIBPCAP_OK=$PCAP_RESOLVED"
python - "$CKBT_ROOT" <<'PY'
import csv, hashlib, json, sys
from pathlib import Path

root = Path(sys.argv[1])
expected_support = "c637e1e50d86252a590c216c286f53411b83facb60f44be3989afbab1b032fcb"
expected_contract = "9ec01f6df760cdf9bc35836dc049e03e359780bf16278daf7a2466b4904f8940"

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

support = root / "aux_process_support_candidate_manifest.csv"
contract = root / "contract.json"
validation = json.loads((root / "independent_validation.json").read_text(encoding="utf-8"))
with support.open(encoding="utf-8", newline="") as handle:
    rows = sum(1 for _ in csv.DictReader(handle))
if rows != 5000:
    raise SystemExit(f"CKBT support row drift: {rows}")
if sha256(support) != expected_support:
    raise SystemExit("CKBT support manifest SHA-256 drift")
if sha256(contract) != expected_contract:
    raise SystemExit("CKBT contract SHA-256 drift")
if validation.get("status") != "PASS" or validation.get("failures"):
    raise SystemExit("CKBT independent validation is not PASS")
if validation.get("support_manifest_sha256") != expected_support:
    raise SystemExit("CKBT validation/support hash mismatch")
if validation.get("contract_sha256") != expected_contract:
    raise SystemExit("CKBT validation/contract hash mismatch")
print("CKBU_CKBT_IMMUTABLE_INPUT_OK")
PY
python - "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1" \
  "$BASE/runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv" <<'PY'
import csv, hashlib, sys
from pathlib import Path

root=Path(sys.argv[1]); manifest=Path(sys.argv[2])
for row in csv.DictReader(manifest.open(encoding="utf-8")):
    path=root/row["source_file"]
    if path.stat().st_size != int(row["bytes"]):
        raise SystemExit(f"ToN pilot size mismatch: {path}")
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4*1024*1024), b""):
            digest.update(block)
    if digest.hexdigest() != row["sha256"]:
        raise SystemExit(f"ToN pilot SHA-256 mismatch: {path}")
print("CKBU_TON_UPLOAD_HASHES_OK")
PY
python -m py_compile \
  repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py \
  repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py
python repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py --mode unit
python repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py --mode contract-unit

FRONTEND_SHA256=$(sha256sum repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py | awk '{print $1}')
FORMAL_SHA256=$(sha256sum repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py | awk '{print $1}')
EXPORTS="ALL,CKBU_COMMIT_SHA=$COMMIT_SHA,CKBU_FRONTEND_SHA256=$FRONTEND_SHA256,CKBU_FORMAL_SHA256=$FORMAL_SHA256"

echo "CKBU_ALL_IMMUTABLE_INPUTS_OK"
amd=$(sbatch --parsable -p amd \
  --output="$BASE/runs/issue27ckbu_amd_%j.out" \
  --error="$BASE/runs/issue27ckbu_amd_%j.err" \
  --export="$EXPORTS" scripts/issue27ckbu_unified_process_rescue_formal.slurm)
[[ "$amd" =~ ^[0-9]+$ ]] || { echo "invalid AMD job id: $amd" >&2; exit 2; }
printf '%s\n' "$amd" > "$AMD_ID_FILE"

intel=$(sbatch --parsable -p intel \
  --output="$BASE/runs/issue27ckbu_intel_%j.out" \
  --error="$BASE/runs/issue27ckbu_intel_%j.err" \
  --export="$EXPORTS" scripts/issue27ckbu_unified_process_rescue_formal.slurm)
[[ "$intel" =~ ^[0-9]+$ ]] || { echo "invalid Intel job id: $intel" >&2; exit 2; }
printf '%s\n' "$intel" > "$INTEL_ID_FILE"

printf 'CKBU_AMD_JOB_ID=%s\nCKBU_INTEL_JOB_ID=%s\n' "$amd" "$intel"
echo "Both jobs are output-isolated.  This script never auto-cancels either copy."
