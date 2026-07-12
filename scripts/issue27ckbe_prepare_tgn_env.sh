#!/bin/bash
# One-time, interactive preparation before CKBE array submission.
# Requires the uploaded pure-Python wheelhouse at ~/work/_upload_issue27ckbe.
set -euo pipefail

WHEELHOUSE="${TGN_WHEELHOUSE:-$HOME/work/_upload_issue27ckbe/wheelhouse_pyg_cp39}"
VENV="$HOME/work/venvs/kitnet_issue27_py39"
test -s "$VENV/bin/activate" || { echo "missing $VENV" >&2; exit 2; }
test -d "$WHEELHOUSE" || { echo "missing $WHEELHOUSE" >&2; exit 2; }

source "$VENV/bin/activate"
python -m pip install --no-index --find-links "$WHEELHOUSE" --no-deps torch_geometric==2.8.0
python - <<'PY'
import torch
from torch_geometric.nn.models.tgn import TGNMemory, IdentityMessage, LastAggregator
memory = TGNMemory(4, 9, 16, 8, IdentityMessage(9, 16, 8), LastAggregator())
print("TGN ENV OK", torch.__version__, __import__('torch_geometric').__version__, tuple(memory.memory.shape))
PY
