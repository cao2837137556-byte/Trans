#!/bin/bash
# Run from the extracted upload bundle on the HPC login node.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBU_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBU_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
AMD_ID_FILE="$HERE/ckbu_seed27_amd_job_id.txt"
INTEL_ID_FILE="$HERE/ckbu_seed27_intel_job_id.txt"

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
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_2.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/normal_scanning1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/password_normal1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/injection_normal1.pcap" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1/MITM_normal1.pcap"; do
  test -s "$path" || { echo "required data not uploaded: $path" >&2; exit 2; }
done

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
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
