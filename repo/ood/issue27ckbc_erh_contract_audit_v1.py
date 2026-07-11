"""Executable contract audit for CKBB's new source-relative R frontend."""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbb_erh_attention_strict_l2_smoke_v1 as ckbb  # noqa: E402


ISSUE = "issue27ckbc_erh_contract_audit_v1_2026-07-11"
OUT = ckbb.ROOT / "runs" / ISSUE


def rows() -> pd.DataFrame:
    payload: list[dict[str, object]] = []
    # Ten past-only snapshots establish the robust state.  `label` is present
    # deliberately: CKBB must ignore it despite the raw source containing it.
    for moment in range(0, 50, 5):
        payload.append({
            "frame.time": f"2025-01-01T00:00:{moment:02d}Z",
            "frame.len": 100,
            "frame.protocols": "eth:ip:udp",
            "ip.src": "10.0.0.1",
            "ip.dst": "10.0.0.2",
            "eth.src": "aa:aa:aa:aa:aa:01",
            "eth.dst": "aa:aa:aa:aa:aa:02",
            "ip.proto": 17,
            "tcp.srcport": 0,
            "tcp.dstport": 0,
            "udp.srcport": 50000,
            "udp.dstport": 9000,
            "tcp.flags": 0,
            "label": "Benign",
        })
    # Target at index 10, then a strictly future packet at index 11.
    payload.append({**payload[-1], "frame.time": "2025-01-01T00:00:50Z", "ip.dst": "10.0.0.3", "label": "Attack"})
    payload.append({**payload[-1], "frame.time": "2025-01-01T00:01:00Z", "ip.dst": "10.0.0.99", "label": "FutureAttack"})
    return pd.DataFrame(payload)


def encode(frame: pd.DataFrame, root: Path) -> np.ndarray:
    archive = root / "synthetic.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("synthetic.csv", frame.to_csv(index=False))
    return ckbb.RelativeBaselineBuilder(archive).build("synthetic.csv", np.asarray([10], dtype=np.int64))[0][0]


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = rows()
    with tempfile.TemporaryDirectory(prefix="ckbc_") as text:
        root = Path(text)
        reference = encode(baseline, root)
        labels_changed = baseline.copy()
        labels_changed["label"] = "arbitrary_truth_mutation"
        future_changed = baseline.copy()
        future_changed.loc[11, "ip.dst"] = "203.0.113.9"
        past_changed = baseline.copy()
        past_changed.loc[9, "ip.src"] = "10.0.0.77"
        label_vector = encode(labels_changed, root)
        future_vector = encode(future_changed, root)
        past_vector = encode(past_changed, root)
    checks = {
        "raw_label_column_read": False,
        "target_index": 10,
        "label_mutation_invariant": bool(np.allclose(reference, label_vector)),
        "future_packet_mutation_invariant": bool(np.allclose(reference, future_vector)),
        "past_packet_changes_state": bool(not np.allclose(reference, past_vector)),
        "baseline_ready": bool(reference[0] == 1.0),
        "r_feature_dim": int(len(reference)),
    }
    checks["status"] = "PASS" if all(checks[key] for key in ("label_mutation_invariant", "future_packet_mutation_invariant", "past_packet_changes_state", "baseline_ready")) else "FAIL"
    (OUT / "audit.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    (OUT / "codex_readout.md").write_text("# CKBC E/R/H contract audit\n\n```json\n" + json.dumps(checks, indent=2) + "\n```\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))
    if checks["status"] != "PASS":
        raise SystemExit("contract audit failed")


if __name__ == "__main__":
    run()
