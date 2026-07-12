#!/bin/bash
# Read-only CKBE runtime validation before array submission.
# This cluster policy forbids self-managed package installation.  The project
# must use its already-provisioned runtime via 00_env_issue27ckc.sh.
set -euo pipefail

if [ -s scripts/00_env_issue27ckc.sh ]; then
  source scripts/00_env_issue27ckc.sh
else
  echo "missing provisioned scripts/00_env_issue27ckc.sh" >&2
  exit 2
fi

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
