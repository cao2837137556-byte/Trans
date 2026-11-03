"""Read-only small-schema probe; never computes external scores."""
from pathlib import Path
import importlib.metadata
import json
import platform
import sqlite3
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for relative in [
    'runs/c5_kernel_independent_replay_codex_20261102/source_cal/CAL_FIXED_INPUTS.npz',
]:
    with np.load(ROOT / relative, allow_pickle=False) as saved:
        print(relative, {name: [list(saved[name].shape), str(saved[name].dtype)] for name in saved.files})
path = ROOT / 'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/tokens.sqlite'
with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as database:
    print(database.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall())
    print(database.execute('SELECT name,COUNT(*) FROM tokens GROUP BY name').fetchall())
print('python', sys.version, platform.platform())
