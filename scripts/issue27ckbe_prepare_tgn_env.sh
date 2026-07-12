#!/bin/bash
# One-time, fail-fast preparation before CKBE array submission.
# The school cluster's validated runtime is Python 3.9, so the pinned
# torch-geometric release must remain Python-3.9 compatible.
set -euo pipefail

WHEELHOUSE="${TGN_WHEELHOUSE:-$HOME/work/_upload_issue27ckbe_r3/wheelhouse_pyg_cp39}"
VENV="$HOME/work/venvs/kitnet_issue27_py39"
test -d "$WHEELHOUSE" || { echo "missing $WHEELHOUSE" >&2; exit 2; }

if [ -s scripts/00_env_issue27ckc.sh ]; then
  source scripts/00_env_issue27ckc.sh
elif [ -s "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
else
  echo "missing known Python environment" >&2
  exit 2
fi

# PyG imports its data module at package import time.  Install its complete
# direct, pure-Python runtime dependency closure from this offline wheelhouse;
# NumPy and Torch remain supplied by the validated issue27ckc environment.
python -m pip install --no-index --find-links "$WHEELHOUSE" --upgrade-strategy only-if-needed torch_geometric==2.6.1
python - <<'PY'
import numpy
import torch
import aiohttp
import fsspec
import jinja2
import psutil
import pyparsing
import requests
import tqdm
from torch_geometric.nn.models.tgn import TGNMemory, IdentityMessage, LastAggregator
memory = TGNMemory(4, 9, 16, 8, IdentityMessage(9, 16, 8), LastAggregator())
print("TGN ENV OK", numpy.__version__, torch.__version__, __import__('torch_geometric').__version__, fsspec.__version__, tuple(memory.memory.shape))
PY
