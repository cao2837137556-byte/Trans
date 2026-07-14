"""Deterministic local contract tests for CKBK (no training or cache build)."""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbj_tgn_m1_strict_formal_v2 as old  # noqa: E402
import issue27ckbk_dyglib_graphmixer_v1 as mixer  # noqa: E402
import issue27ckbk_temporal_generalization_formal_v1 as formal  # noqa: E402


class FakeT0:
    cached_sources = {"source-a"}
    report_only_sources: set[str] = set()

    def __init__(self, root: Path):
        self.root = root

    def paths(self, source: str) -> tuple[Path, Path]:
        if source != "source-a":
            raise KeyError(source)
        return self.root / "source-a.npz", self.root / "source-a.json"

    @staticmethod
    def target_positions(source: str) -> dict[int, int]:
        if source != "source-a":
            raise KeyError(source)
        return {100: 2, 101: 3, 102: 4}


def record(uid: str, phase: str, position: int, label: int = 0) -> old.Record:
    return old.Record(
        uid, "role", phase, "source-a", 100 + position - 2, position, label,
        "attack-a" if label else "benign", "device-a", "family-a", 0.9 if label else 0.1, f"episode-{position}",
    )


def run(out: Path) -> dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / "source-a.npz", recorded_index=np.asarray([98, 99, 100, 101, 102], dtype=np.int64),
        time_ms=np.arange(5, dtype=np.int64), src=np.asarray([0, 0, 0, 1, 1], dtype=np.int64),
        dst=np.asarray([1, 1, 1, 0, 0], dtype=np.int64),
        raw_msg=np.zeros((5, formal.RAW_MSG_DIM), dtype=np.float32),
    )
    manifest = out / "target_manifest.csv"
    pd.DataFrame([
        {"source_group": "source-a", "recorded_index": 100, "stages": "fit;select", "roles": "id_calib"},
        {"source_group": "source-a", "recorded_index": 101, "stages": "select", "roles": "support_val"},
        {"source_group": "source-a", "recorded_index": 102, "stages": "report", "roles": "future_query"},
    ]).to_csv(manifest, index=False)
    sets = {
        "fit_attack": [record("fit", "fit", 2, 1)], "fit_benign": [],
        "select_attack": [record("select", "select", 3, 1)], "select_benign": [],
        "report": [record("report", "report", 4, 1)],
    }
    role_frames = {
        "id_calib": pd.DataFrame({"source_group": ["source-a"], "recorded_index": [100], "phase": ["fit"]}),
        "support_val": pd.DataFrame({"source_group": ["source-a"], "recorded_index": [101], "phase": ["select"]}),
        "future_query": pd.DataFrame({"source_group": ["source-a"], "recorded_index": [102], "phase": ["all"]}),
    }
    masks = formal.target_catalog_masks(FakeT0(out), manifest, sets, role_frames)
    interleaved_exact = (
        2 not in masks.blocked("fit", "source-a")
        and 3 in masks.blocked("fit", "source-a")
        and 4 in masks.blocked("fit", "source-a")
        and 3 not in masks.blocked("select", "source-a")
        and 4 in masks.blocked("select", "source-a")
    )

    stamp = np.asarray([0, 10, 20], dtype=np.int64)
    src = np.asarray([0, 1, 2], dtype=np.int64)
    dst = np.asarray([1, 0, 0], dtype=np.int64)
    message = np.zeros((3, formal.RAW_MSG_DIM), dtype=np.float32)
    labels = formal.dense_future_task_labels(stamp, src, dst, message, {0}, frozenset({1}))
    blocked_future_not_used = labels[0][0] == 0

    old.torch.manual_seed(27)
    encoder = old.make_encoder(8, 8, 4); encoder.eval(); encoder.reset_state()
    loader = old.LastNeighborLoader(8, size=3); store = old.ReplayStore(2)
    initial = encoder.pair_embedding(old.torch.tensor([0, 1]), loader, store).detach().cpu().numpy()
    encoder.update_state(
        old.torch.tensor([0]), old.torch.tensor([1]), old.torch.tensor([1]),
        old.torch.zeros((1, formal.RAW_MSG_DIM)), loader, store,
    )
    encoder.reset_state(); loader = old.LastNeighborLoader(8, size=3); store = old.ReplayStore(2)
    reset = encoder.pair_embedding(old.torch.tensor([0, 1]), loader, store).detach().cpu().numpy()

    source = Path(formal.__file__).read_text(encoding="utf-8")
    graph_source = Path(mixer.__file__).read_text(encoding="utf-8")
    parsed = ast.parse(graph_source)
    forward_arguments = {
        argument.arg
        for node in ast.walk(parsed) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "forward"
        for argument in node.args.args
    }
    gate_source = inspect.getsource(formal.choose_complete_gate)
    aggregate_tables = {
        "attack_summary": pd.DataFrame([
            {"candidate": "TGNMemory-Repair", "metric": "overall_attack_hard_recall", "delta_vs_c1_pp": -0.1, "rows": 100},
            {"candidate": "TGNMemory-Repair", "metric": "attack_family_recall", "delta_vs_c1_pp": -1.0, "rows": 20},
        ]),
        "strict_summary": pd.DataFrame([
            {"candidate": "M0-C1", "held_value": "iotsim-stream-consumer", "hard_rate": 1.0},
            {"candidate": "TGNMemory-Repair", "held_value": "iotsim-stream-consumer", "hard_rate": 0.8},
            {"candidate": "M0-C1", "held_value": "iotsim-hydraulic-system", "hard_rate": 1.0},
            {"candidate": "TGNMemory-Repair", "held_value": "iotsim-hydraulic-system", "hard_rate": 0.9},
        ]),
        "selection": pd.DataFrame([
            {"candidate": "TGNMemory-Repair", "selected": True, "gate_constraint_pass": True},
        ]),
        "representation_delta": pd.DataFrame([
            {"candidate": "TGNMemory-Repair", "control_candidate": "TGNMemory-Repair-Random", "protocol": "GLOBAL_ATTACK_PRESERVATION", "metric": "auroc", "delta_learned_minus_random": 0.02},
            {"candidate": "TGNMemory-Repair", "control_candidate": "TGNMemory-Repair-Random", "protocol": "GLOBAL_ATTACK_PRESERVATION", "metric": "auprc", "delta_learned_minus_random": 0.02},
            {"candidate": "TGNMemory-Repair", "control_candidate": "TGNMemory-Repair-Random", "protocol": "GLOBAL_ATTACK_PRESERVATION", "metric": "attack_benign_margin", "delta_learned_minus_random": 0.1},
        ]),
    }
    aggregate = formal.aggregate_decisions(
        aggregate_tables, [{"stage": "tgn", "status": "COMPLETED"}, {"stage": "graphmixer", "status": "FAILED"}],
    )
    tgn_decision = next(row for row in aggregate if row["candidate"] == "TGNMemory-Repair")
    result: dict[str, object] = {
        "interleaved_fit_select_resolved_by_exact_mask": interleaved_exact,
        "blocked_future_event_not_used_for_fit_outcome": blocked_future_not_used,
        "source_reset_returns_fresh_representation": bool(np.allclose(initial, reset)),
        "report_no_grad_decorator_present": "@torch.no_grad()\ndef embed_tgn_phase" in source,
        "report_label_forbidden_from_memory_audit": "labels_read_for_memory\": False" in source,
        "complete_gate_no_fallback": "complete gate search found no attack-preserving threshold" in gate_source and "max(rows" not in gate_source,
        "graphmixer_upstream_commit_frozen": mixer.UPSTREAM_COMMIT == "3aacc36b94b8d2d8293d70a74fdf6d39089b4163",
        "graphmixer_forward_has_no_node_or_source_id": not bool(forward_arguments & {"node_id", "node_ids", "source", "source_id", "source_group"}),
        "graphmixer_forward_has_no_raw_label": not bool(forward_arguments & {"label", "labels", "raw_label"}),
        "untouched_final_not_in_development_held": "iotsim-cooler-motor" not in old.HELD,
        "aggregate_go_rule_exact": tgn_decision["decision"] == "GO_SIGNAL",
    }
    result["status"] = "PASS" if all(bool(value) for value in result.values()) else "FAIL"
    (out / "ckbk_contract_tests.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run(Path(args.out))
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit("CKBK contract tests failed")


if __name__ == "__main__":
    main()
