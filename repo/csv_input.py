from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


def _is_integer_like(values: np.ndarray, tol: float = 1e-9) -> bool:
    if values.size == 0:
        return False
    rounded = np.round(values)
    return bool(np.max(np.abs(values - rounded)) <= tol)


def detect_index_like_col0(col0: np.ndarray, tol: float = 1e-9) -> Tuple[bool, str]:
    """Return whether column-0 looks like a CSV index column."""
    if col0.ndim != 1:
        return False, "col0 is not 1-D"
    if len(col0) < 3:
        return False, "too few rows to judge index-like pattern"
    if not np.all(np.isfinite(col0)):
        return False, "col0 contains non-finite values"
    if not _is_integer_like(col0, tol=tol):
        return False, "col0 is not integer-like"

    start = float(col0[0])
    if abs(start - 0.0) > tol and abs(start - 1.0) > tol:
        return False, "col0 does not start at 0/1"

    expected = start + np.arange(len(col0), dtype=np.float64)
    if np.max(np.abs(col0 - expected)) > tol:
        return False, "col0 is not strictly sequential with step=1"

    return True, "col0 matches 0/1-start sequential index pattern"


def load_numeric_csv(
    path: Path,
    nrows: Optional[int] = None,
    auto_drop_index_col0: bool = True,
) -> Tuple[np.ndarray, Dict[str, object]]:
    path = Path(path)
    raw = pd.read_csv(path, header=None, nrows=nrows).values
    raw = np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)

    info: Dict[str, object] = {
        "path": str(path),
        "rows": int(raw.shape[0]),
        "raw_dim": int(raw.shape[1]),
        "used_dim": int(raw.shape[1]),
        "auto_drop_index_col0": bool(auto_drop_index_col0),
        "col0_index_like": False,
        "col0_reason": "not_checked",
        "dropped_col0": False,
    }

    used = raw
    if auto_drop_index_col0 and raw.ndim == 2 and raw.shape[1] >= 2:
        col0 = np.asarray(raw[:, 0], dtype=np.float64)
        index_like, reason = detect_index_like_col0(col0)
        info["col0_index_like"] = bool(index_like)
        info["col0_reason"] = reason
        if index_like:
            used = raw[:, 1:]
            info["dropped_col0"] = True
    elif raw.ndim != 2 or raw.shape[1] < 2:
        info["col0_reason"] = "not_enough_columns"
    else:
        info["col0_reason"] = "auto_drop_disabled"

    used = np.nan_to_num(used, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    info["used_dim"] = int(used.shape[1]) if used.ndim == 2 else 0
    return used, info
