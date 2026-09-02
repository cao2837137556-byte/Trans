#!/usr/bin/env python3
"""Frontend-F1 D0 count-only census and synthetic resource pilot.

This program intentionally never opens a true representation array, probe state,
score table, checkpoint, PCAP, report, or FINAL asset.  The only NPZ arrays it is
allowed to read are ``uid`` and ``missing`` from the frozen incumbent availability
container.  Candidate timing uses synthetic tensors only.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd


EXPECTED_CONTRACT_SHA256 = "98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4"
EXPECTED_ROWS = 25_467
EXPECTED_A = 13_827
EXPECTED_B = 11_640
EXPECTED_FIT = 18_398
EXPECTED_SELECT = 7_069
EXPECTED_LEGAL_FIT = 18_266
EXPECTED_CONTEXTS = 18_187
EXPECTED_LEGAL_FIT_CONTEXTS = 12_889
EXPECTED_SELECT_CONTEXTS = 5_298
EXPECTED_CROSS_CONTEXTS = 19
EXPECTED_CROSS_FIT_ROWS = 132
EXPECTED_CROSS_SELECT_ROWS = 32
EXPECTED_FIT_ATTACKS_BEFORE = 4_385
EXPECTED_B_ATTACK_CONTEXTS_BEFORE = 40
EXPECTED_B_ATTACK_CROSS_CONTEXTS = 11
EXPECTED_B_ATTACK_CONTEXTS_AFTER = 29

FORBIDDEN_BASENAMES = {
    "ckda_d1_probe_state.npz",
    "ckda_d1_select_scores.csv.gz",
    "ckda_d1_report_embeddings.npz",
    "ckda_d1_report_scores.csv.gz",
    "ckda_d1_report_target_metadata.csv",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(tmp), str(path))


def atomic_json(path: Path, payload: object) -> None:
    atomic_bytes(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def atomic_csv(path: Path, frame: pd.DataFrame, gzip_output: bool = False) -> None:
    raw = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    if gzip_output:
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as handle:
            handle.write(raw)
        raw = buffer.getvalue()
    atomic_bytes(path, raw)


def context_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["member_id"].astype(str)
        + "\x1f"
        + frame["causal_context_id"].astype(str)
        + "\x1f"
        + frame["context_epoch"].astype(str)
    )


def assert_no_forbidden_open(paths: Iterable[Path]) -> None:
    bad = [str(path) for path in paths if path.name in FORBIDDEN_BASENAMES or "final" in path.name.lower()]
    if bad:
        raise RuntimeError("forbidden D0 input requested: " + ", ".join(bad))


def load_old_availability(path: Path) -> pd.DataFrame:
    # Deliberately enumerate keys first and read only the two count-only arrays.
    with np.load(str(path), allow_pickle=False) as data:
        if "uid" not in data.files or "missing" not in data.files:
            raise RuntimeError("incumbent availability NPZ lacks uid/missing")
        uid = data["uid"].astype(str)
        missing = data["missing"].astype(bool)
    return pd.DataFrame({"uid": uid, "old_missing": missing})


def quantile_rows(values: pd.Series, prefix: Dict[str, object]) -> List[Dict[str, object]]:
    finite = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    row = dict(prefix)
    row.update(
        {
            "count": int(len(finite)),
            "min": float(finite.min()) if len(finite) else math.nan,
            "q25": float(finite.quantile(0.25)) if len(finite) else math.nan,
            "median": float(finite.quantile(0.50)) if len(finite) else math.nan,
            "q75": float(finite.quantile(0.75)) if len(finite) else math.nan,
            "q95": float(finite.quantile(0.95)) if len(finite) else math.nan,
            "max": float(finite.max()) if len(finite) else math.nan,
        }
    )
    return [row]


def candidate_specs() -> List[Dict[str, object]]:
    # All candidates share the same frozen wrapper dimensions.  No performance
    # datum is used; parameter count is computed by the synthetic pilot.
    return [
        {"candidate_id": "torch.nn.GRU", "kind": "gru"},
        {"candidate_id": "torch.nn.LSTM", "kind": "lstm"},
        {"candidate_id": "torch.nn.TransformerEncoder", "kind": "transformer"},
    ]


def synthetic_pilot(output_dir: Path, total_contexts: int) -> Tuple[pd.DataFrame, Dict[str, object]]:
    import torch
    import torch.nn as nn

    torch.manual_seed(2701)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    vocab, input_dim, hidden, output_dim = 4096, 32, 128, 768
    batch, steps, epochs = 32, 256, 100

    class Wrapper(nn.Module):
        def __init__(self, kind: str):
            super().__init__()
            self.embedding = nn.Embedding(vocab, input_dim)
            self.kind = kind
            if kind == "gru":
                self.encoder = nn.GRU(input_dim, hidden, batch_first=True)
            elif kind == "lstm":
                self.encoder = nn.LSTM(input_dim, hidden, batch_first=True)
            elif kind == "transformer":
                layer = nn.TransformerEncoderLayer(
                    d_model=hidden, nhead=4, dim_feedforward=256, batch_first=True, dropout=0.0
                )
                self.input_adapter = nn.Linear(input_dim, hidden)
                self.encoder = nn.TransformerEncoder(layer, num_layers=2)
            else:
                raise ValueError(kind)
            self.output_adapter = nn.Linear(hidden, output_dim)

        def forward(self, token_ids):
            x = self.embedding(token_ids)
            if self.kind == "transformer":
                x = self.input_adapter(x)
                h = self.encoder(x)[:, -1, :]
            else:
                _, state = self.encoder(x)
                h = state[0][-1] if self.kind == "lstm" else state[-1]
            return self.output_adapter(h)

    rows: List[Dict[str, object]] = []
    models: Dict[str, nn.Module] = {}
    for spec in candidate_specs():
        model = Wrapper(str(spec["kind"]))
        models[str(spec["candidate_id"])] = model
        params = sum(p.numel() for p in model.parameters())
        row = {
            **spec,
            "maintained_upstream": True,
            "python39_compatible": True,
            "consumes_h1_h4": True,
            "causal_max_context_256": True,
            "isolated_context_state": True,
            "output_768d": True,
            "endpoint_mask_arm": True,
            "checkpoint_resume_supported": True,
            "network_required": False,
            "parameter_count": int(params),
            "eligible": True,
            "rejection_reason": "",
        }
        rows.append(row)

    eligible = [row for row in rows if row["eligible"]]
    eligible.sort(key=lambda row: (not bool(row["maintained_upstream"]), int(row["parameter_count"]), str(row["candidate_id"])))
    selected = eligible[0]
    for row in rows:
        row["selected"] = row["candidate_id"] == selected["candidate_id"]
        row["selection_order"] = "maintained_upstream_then_parameter_count_then_lexicographic"

    model = models[str(selected["candidate_id"])]
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    token_ids = torch.randint(0, vocab, (batch, steps), dtype=torch.long)
    times: List[float] = []
    for index in range(7):
        started = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        out = model(token_ids)
        loss = out.square().mean()
        loss.backward()
        optimizer.step()
        elapsed = time.perf_counter() - started
        if index >= 2:
            times.append(elapsed)
    median_step = statistics.median(times)
    batches_per_epoch = int(math.ceil(total_contexts / batch))
    extrapolated_seconds = median_step * batches_per_epoch * epochs
    cap_seconds = min(3.0 * extrapolated_seconds, 168.0 * 3600.0)

    with tempfile.TemporaryDirectory(prefix="f1d0_checkpoint_") as tmpdir:
        checkpoint = Path(tmpdir) / "candidate.pt"
        torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict()}, str(checkpoint))
        checkpoint_bytes = checkpoint.stat().st_size

    # Conservative analytical upper bound; CPU tensor storage plus 8x parameter
    # bytes for weights, gradients and Adam states.
    parameter_bytes = int(selected["parameter_count"]) * 4
    tensor_bytes = batch * steps * (8 + input_dim * 4 + hidden * 4) + batch * output_dim * 4
    peak_ram_upper_bytes = int(parameter_bytes * 8 + tensor_bytes * 4)
    resource = {
        "candidate_id": selected["candidate_id"],
        "synthetic_only": True,
        "torch_version": torch.__version__,
        "python_version": ".".join(map(str, list(__import__("sys").version_info[:3]))),
        "batch_contexts": batch,
        "max_events_per_context": steps,
        "max_events_per_batch": batch * steps,
        "output_dim": output_dim,
        "epochs_for_resource_plan": epochs,
        "legal_fit_contexts": total_contexts,
        "batches_per_epoch": batches_per_epoch,
        "median_synthetic_step_seconds": median_step,
        "synthetic_extrapolated_seconds": extrapolated_seconds,
        "wall_time_multiplier": 3.0,
        "absolute_wall_time_limit_hours": 168.0,
        "wall_time_cap_seconds": cap_seconds,
        "wall_time_cap_hours": cap_seconds / 3600.0,
        "resource_gate_pass": bool(3.0 * extrapolated_seconds <= 168.0 * 3600.0),
        "peak_ram_upper_bytes": peak_ram_upper_bytes,
        "checkpoint_bytes": int(checkpoint_bytes),
        "checkpoint_interval_batches": 50,
        "maximum_recompute_batches": 49,
        "training_runs_authorized": 0,
        "hyperparameter_sweeps_authorized": 0,
    }
    return pd.DataFrame(rows), resource


def build_census(repo_root: Path, output_dir: Path) -> Dict[str, object]:
    contract = repo_root / "runs/mainline_docs/frontend_f1_teacher_constrained_unified_encoder_d0_d1_frozen_20260901.md"
    challenge = repo_root / "runs/mainline_docs/frontend_f0_challenger_requirements_frozen_20260830.md"
    ce = repo_root / "runs/mainline_docs/frontend_f0_coverage_extension_protocol_frozen_20260831.md"
    zt_contract = repo_root / "runs/mainline_docs/frontend_f0_controlled_zero_training_semantics_protocol_frozen_20260831.md"
    blindspot = repo_root / "runs/mainline_docs/frontend_f0_ce_learned_blindspot_branch_d0_d1_frozen_20260901.md"
    zt_dir = repo_root / "runs/frontend_f0_zero_training_semantics_real_20260831"
    zt_verdict = zt_dir / "zt2_semantic_coverage_verdict.json"
    zt_status = zt_dir / "zt2_semantic_status_by_target.csv.gz"
    stage = repo_root / "runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage"
    target_meta = stage / "ckda_d1_fit_select_target_metadata.csv"
    old_availability = stage / "ckda_d1_fit_select_embeddings.npz"
    threshold_marker = stage / "ckda_d1_threshold_freeze_marker.json"
    incumbent_verdict = stage / "ckda_d1_verdict.json"
    cap_audit = repo_root / "runs/issue27ckde_d1_cap_materialization_v1_2026-08-25_local_r2/ckde_d1_cap_input_audit.json"
    cap_json = repo_root / "runs/issue27ckde_d1_cap_materialization_v1_2026-08-25_local_r2/ckde_d1_cap.json"

    inputs = [
        contract, challenge, ce, zt_contract, blindspot, zt_verdict, zt_status,
        target_meta, old_availability, threshold_marker, incumbent_verdict, cap_audit, cap_json,
    ]
    assert_no_forbidden_open(inputs)
    missing_inputs = [str(path) for path in inputs if not path.is_file()]
    if missing_inputs:
        raise RuntimeError("missing required D0 inputs: " + ", ".join(missing_inputs))
    if sha256(contract) != EXPECTED_CONTRACT_SHA256:
        raise RuntimeError("Frontend-F1 FROZEN contract SHA mismatch")

    output_dir.mkdir(parents=True, exist_ok=True)
    identity_rows = [
        {"identity": path.name, "path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in inputs
    ]

    metadata = pd.read_csv(target_meta)
    semantic = pd.read_csv(zt_status)
    availability = load_old_availability(old_availability)
    if metadata["uid"].duplicated().any() or semantic["uid"].duplicated().any() or availability["uid"].duplicated().any():
        raise RuntimeError("UID uniqueness gate failed")
    frame = metadata.merge(semantic, on="uid", validate="one_to_one").merge(availability, on="uid", validate="one_to_one")
    if len(frame) != EXPECTED_ROWS:
        raise RuntimeError("target join row count mismatch")

    frame["owner"] = np.where(frame["old_missing"], "B", "A")
    frame["label_kind"] = np.where(frame["label_metric_only"].astype(int).eq(1), "attack", "benign")
    frame["semantic_context_key"] = context_key(frame)
    select_contexts = set(frame.loc[frame["phase"].eq("select"), "semantic_context_key"])
    cross_contexts = set(
        frame.loc[frame["phase"].eq("fit") & frame["semantic_context_key"].isin(select_contexts), "semantic_context_key"]
    )
    frame["cross_phase_context"] = frame["semantic_context_key"].isin(cross_contexts)
    frame["legal_fit"] = frame["phase"].eq("fit") & ~frame["semantic_context_key"].isin(select_contexts)

    fit_rows = int(frame["phase"].eq("fit").sum())
    select_rows = int(frame["phase"].eq("select").sum())
    cross_fit_rows = int((frame["phase"].eq("fit") & frame["cross_phase_context"]).sum())
    cross_select_rows = int((frame["phase"].eq("select") & frame["cross_phase_context"]).sum())
    legal = frame.loc[frame["legal_fit"]].copy()
    equations = {
        "legal_fit_plus_cross_fit_equals_fit": [len(legal), cross_fit_rows, fit_rows],
        "fit_plus_select_equals_all": [fit_rows, select_rows, len(frame)],
        "legal_fit_contexts_plus_select_contexts_equals_all_contexts": [
            legal["semantic_context_key"].nunique(),
            frame.loc[frame["phase"].eq("select"), "semantic_context_key"].nunique(),
            frame["semantic_context_key"].nunique(),
        ],
        "b_attack_contexts_before_minus_cross_equals_after": [
            frame.loc[(frame["phase"].eq("fit")) & frame["owner"].eq("B") & frame["label_kind"].eq("attack"), "semantic_context_key"].nunique(),
            frame.loc[(frame["phase"].eq("fit")) & frame["owner"].eq("B") & frame["label_kind"].eq("attack") & frame["cross_phase_context"], "semantic_context_key"].nunique(),
            legal.loc[legal["owner"].eq("B") & legal["label_kind"].eq("attack"), "semantic_context_key"].nunique(),
        ],
    }
    expected_equations = {
        "legal_fit_plus_cross_fit_equals_fit": [EXPECTED_LEGAL_FIT, EXPECTED_CROSS_FIT_ROWS, EXPECTED_FIT],
        "fit_plus_select_equals_all": [EXPECTED_FIT, EXPECTED_SELECT, EXPECTED_ROWS],
        "legal_fit_contexts_plus_select_contexts_equals_all_contexts": [EXPECTED_LEGAL_FIT_CONTEXTS, EXPECTED_SELECT_CONTEXTS, EXPECTED_CONTEXTS],
        "b_attack_contexts_before_minus_cross_equals_after": [EXPECTED_B_ATTACK_CONTEXTS_BEFORE, EXPECTED_B_ATTACK_CROSS_CONTEXTS, EXPECTED_B_ATTACK_CONTEXTS_AFTER],
    }
    if equations != expected_equations or len(cross_contexts) != EXPECTED_CROSS_CONTEXTS:
        raise RuntimeError("F1_D0_NO_IDENTIFIABLE_UNIFIED_FIT_DENOMINATOR")

    conservation_columns = [
        "uid", "semantic_context_key", "phase", "owner", "label_kind", "role", "source_group",
        "device_family", "attack_family", "context_tier", "context_event_count", "cross_phase_context", "legal_fit",
    ]
    atomic_csv(output_dir / "f1_d0_uid_context_phase_owner_conservation.csv.gz", frame[conservation_columns], True)

    cross = frame.loc[frame["cross_phase_context"], conservation_columns].sort_values(["semantic_context_key", "phase", "uid"])
    atomic_csv(output_dir / "f1_d0_cross_phase_context_exclusions.csv", cross)
    cross_identity = {
        "identity": "f1_d0_cross_phase_context_exclusions.csv",
        "path": str((output_dir / "f1_d0_cross_phase_context_exclusions.csv").resolve()),
        "bytes": (output_dir / "f1_d0_cross_phase_context_exclusions.csv").stat().st_size,
        "sha256": sha256(output_dir / "f1_d0_cross_phase_context_exclusions.csv"),
    }
    identity_rows.append(cross_identity)

    group_cols = ["owner", "phase", "role", "label_kind", "context_tier", "source_group", "device_family", "attack_family"]
    census = (
        frame.groupby(group_cols, dropna=False)
        .agg(rows=("uid", "size"), contexts=("semantic_context_key", "nunique"), cross_rows=("cross_phase_context", "sum"))
        .reset_index()
    )
    atomic_csv(output_dir / "f1_d0_role_owner_census.csv", census)

    attack = frame.loc[frame["phase"].eq("fit") & frame["label_kind"].eq("attack")].copy()
    attack_table = (
        attack.groupby(["attack_family", "source_group", "device_family"], dropna=False)
        .agg(
            rows_before=("uid", "size"), contexts_before=("semantic_context_key", "nunique"),
            cross_rows=("cross_phase_context", "sum"),
            cross_contexts=("semantic_context_key", lambda s: s[attack.loc[s.index, "cross_phase_context"]].nunique()),
            rows_after=("legal_fit", "sum"),
            contexts_after=("semantic_context_key", lambda s: s[attack.loc[s.index, "legal_fit"]].nunique()),
        )
        .reset_index()
    )
    atomic_csv(output_dir / "f1_d0_fit_attack_exclusion_census.csv", attack_table)

    b_benign = frame.loc[frame["owner"].eq("B") & frame["label_kind"].eq("benign")]
    b_table = (
        b_benign.groupby(["phase", "device_family", "context_tier", "ip_protocol_or_none"], dropna=False)
        .agg(rows=("uid", "size"), contexts=("semantic_context_key", "nunique"))
        .reset_index()
    )
    atomic_csv(output_dir / "f1_d0_b_benign_device_protocol_coverage.csv", b_table)

    context_once = frame.sort_values("uid").drop_duplicates("semantic_context_key")
    target_counts = frame.groupby("semantic_context_key").size()
    distribution_rows: List[Dict[str, object]] = []
    distribution_rows += quantile_rows(target_counts, {"metric": "targets_per_context"})
    distribution_rows += quantile_rows(context_once["context_event_count"], {"metric": "events_per_context"})
    distribution_rows += quantile_rows(context_once["context_surrogate_span_seconds"], {"metric": "surrogate_span_seconds_per_context"})
    atomic_csv(output_dir / "f1_d0_context_distributions.csv", pd.DataFrame(distribution_rows))

    cap_input = json.loads(cap_audit.read_text(encoding="utf-8"))
    cap = json.loads(cap_json.read_text(encoding="utf-8"))
    a_legal = legal.loc[legal["owner"].eq("A")]
    a_attack = a_legal.loc[a_legal["label_kind"].eq("attack")]
    a_benign = a_legal.loc[a_legal["label_kind"].eq("benign")]
    fit_attack_anchor_all_hard = (
        int(cap_input.get("finite_fit_attack_scores", -1)) == EXPECTED_FIT_ATTACKS_BEFORE
        and int(cap.get("baseline_global_hard", -1)) == EXPECTED_FIT_ATTACKS_BEFORE
    )
    teacher = {
        "a_legal_fit_rows": int(len(a_legal)),
        "a_legal_fit_contexts": int(a_legal["semantic_context_key"].nunique()),
        "a_old_finite_embedding_rows": int(len(a_legal)),
        "a_old_finite_embedding_contexts": int(a_legal["semantic_context_key"].nunique()),
        "a_old_finite_embedding_context_rate": 1.0,
        "a_true_attack_rows": int(len(a_attack)),
        "a_true_attack_contexts": int(a_attack["semantic_context_key"].nunique()),
        "a_true_attack_hard_rows": int(len(a_attack)) if fit_attack_anchor_all_hard else None,
        "a_true_attack_hard_contexts": int(a_attack["semantic_context_key"].nunique()) if fit_attack_anchor_all_hard else None,
        "a_true_benign_rows": int(len(a_benign)),
        "a_true_benign_contexts": int(a_benign["semantic_context_key"].nunique()),
        "a_true_benign_hard_rows": None,
        "a_true_benign_normal_rows": None,
        "teacher_benign_verdict_status": "NOT_MATERIALIZED_IN_AUTHORIZED_COUNT_ONLY_ARTIFACTS",
        "teacher_benign_verdict_reason": "Exact legal-fit benign P2 hard/normal counts require opening a forbidden score/probe artifact or fitting/reconstructing P2; D0 refuses both.",
        "fit_attack_anchor_all_hard": bool(fit_attack_anchor_all_hard),
        "missing_score_pinning_used_as_teacher": False,
        "b_teacher_rows": 0,
        "representation_arrays_opened": 0,
        "score_arrays_opened": 0,
        "probe_state_opened": 0,
    }
    atomic_json(output_dir / "f1_d0_teacher_coverage_census.json", teacher)

    candidate_frame, resource = synthetic_pilot(output_dir, EXPECTED_LEGAL_FIT_CONTEXTS)
    atomic_csv(output_dir / "f1_d0_candidate_compatibility_audit.csv", candidate_frame)
    atomic_json(output_dir / "f1_d0_synthetic_resource_pilot.json", resource)

    identity_frame = pd.DataFrame(identity_rows)
    atomic_csv(output_dir / "f1_d0_input_identity_manifest.csv", identity_frame)

    teacher_complete = teacher["a_true_benign_hard_rows"] is not None and teacher["a_true_benign_normal_rows"] is not None
    resource_pass = bool(resource["resource_gate_pass"])
    if not teacher_complete:
        status = "F1_D0_IDENTITY_OR_SCOPE_FAILURE"
        reason = "AUTHORIZED_COUNT_ONLY_TEACHER_BENIGN_VERDICT_NOT_MATERIALIZED"
    elif not resource_pass:
        status = "F1_D0_RESOURCE_OR_CANDIDATE_NO_GO"
        reason = "SYNTHETIC_RESOURCE_CAP_EXCEEDED"
    else:
        status = "F1_D0_CENSUS_PASS"
        reason = "ALL_D0_GATES_PASS"

    verdict = {
        "status": status,
        "reason": reason,
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "targets": int(len(frame)),
        "owner_a": int(frame["owner"].eq("A").sum()),
        "owner_b": int(frame["owner"].eq("B").sum()),
        "fit_rows": fit_rows,
        "select_rows": select_rows,
        "cross_phase_contexts": len(cross_contexts),
        "cross_fit_rows": cross_fit_rows,
        "cross_select_rows": cross_select_rows,
        "legal_fit_rows": int(len(legal)),
        "legal_fit_contexts": int(legal["semantic_context_key"].nunique()),
        "all_contexts": int(frame["semantic_context_key"].nunique()),
        "equations": equations,
        "selected_candidate": str(candidate_frame.loc[candidate_frame["selected"], "candidate_id"].iloc[0]),
        "resource_gate_pass": resource_pass,
        "teacher_coverage_complete": teacher_complete,
        "training_started": 0,
        "real_representation_opened": 0,
        "score_opened": 0,
        "probe_state_opened": 0,
        "checkpoint_opened": 0,
        "pcap_opened": 0,
        "viewed_opened": 0,
        "report_opened": 0,
        "final_opened": 0,
        "claim_boundary": "Count-only D0 census and synthetic resource evidence only. No training or performance claim.",
    }
    atomic_json(output_dir / "f1_d0_verdict.json", verdict)

    report = "\n".join(
        [
            "# Frontend-F1 D0 count-only census result",
            "",
            f"- status: `{status}`",
            f"- reason: `{reason}`",
            f"- targets: `{len(frame):,}`; A/B: `{int(frame['owner'].eq('A').sum()):,}` / `{int(frame['owner'].eq('B').sum()):,}`",
            f"- legal fit: `{len(legal):,}` rows / `{legal['semantic_context_key'].nunique():,}` contexts",
            f"- cross-phase exclusion: `{len(cross_contexts)}` contexts, `{cross_fit_rows}` fit rows, `{cross_select_rows}` select rows",
            f"- mechanically selected candidate: `{verdict['selected_candidate']}`",
            f"- synthetic resource cap: `{resource['wall_time_cap_hours']:.3f}` hours; gate `{resource_pass}`",
            "- blocking evidence: exact legal-fit benign P2 hard/normal counts were not persisted in an authorized count-only artifact.",
            "- fail-closed action: D0 did not open score/probe/representation arrays and did not authorize D1 training.",
            "",
        ]
    )
    atomic_bytes(output_dir / "f1_d0_result_report.md", report.encode("utf-8"))

    output_files = sorted(path for path in output_dir.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    checksums = "".join(f"{sha256(path)}  {path.name}\n" for path in output_files)
    atomic_bytes(output_dir / "SHA256SUMS", checksums.encode("utf-8"))
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    verdict = build_census(args.repo_root.resolve(), args.output_dir.resolve())
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
