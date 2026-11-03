#!/usr/bin/env bash
#SBATCH --job-name=edge-preflight
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
#SBATCH --time=00:10:00
#SBATCH --no-requeue
#SBATCH --output=edge-preflight-%j.out
#SBATCH --error=edge-preflight-%j.err
set -euo pipefail
umask 077
: "${EDGE_PYTHON:?Set the existing Linux Python 3.11.11 interpreter path}"
: "${EDGE_TSHARK:?Set the existing TShark 4.6.6 executable path}"
: "${EDGE_RAW_DIRECTORY:?Set the remote directory holding the three pinned raw PCAPs}"
: "${EDGE_OUTPUT_BASE:?Set durable remote personal/project output storage}"
EDGE_PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDGE_ROOT="$(cd -- "${EDGE_PACKAGE_DIR}/../.." && pwd)"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES=""
cd -- "${EDGE_ROOT}"
EDGE_JOB_OUTPUT="${EDGE_OUTPUT_BASE}/edge_preflight_${SLURM_JOB_ID:?}"
exec "${EDGE_PYTHON}" -X utf8 -B "${EDGE_PACKAGE_DIR}/launch_preflight.py" \
  --raw-directory "${EDGE_RAW_DIRECTORY}" --tshark "${EDGE_TSHARK}" \
  --slice "${EDGE_PACKAGE_DIR}/ACTIVE_SLICE_CARD.json" --output "${EDGE_JOB_OUTPUT}"
