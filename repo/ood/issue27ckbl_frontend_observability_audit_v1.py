"""CKBL: strict fit-only frontend observability audit.

This experiment asks the question that must be answered before another
temporal backend is promoted:

    Do portable, causal packet/process features contain enough information to
    separate an unseen benign source from an unseen attack source/family?

The experiment is deliberately a representation probe, not a new detector.
It reuses the label-free canonical Gotham frontend and sklearn HistGB.  The
old development canaries (stream-consumer and hydraulic-system) and the sealed
cooler-motor final holdout are forbidden from every feature, fit, threshold,
and route decision.  Only legal ``fit`` rows are eligible.

Two outer protocols are evaluated:

* ``unseen_source_pair``: one benign source and one attack source are absent
  from training and evaluated together.
* ``unseen_attack_family_origin``: the held attack family, every source that
  contains it, and one benign source are absent from training.

Thresholds, when the remaining source diversity permits it, are chosen from
inner leave-one-source-out predictions.  Outer rows are never used to select a
threshold.  Threshold-independent AUROC remains the primary observability
metric because this is not the final C1 candidate gate.

``--source-read-mode full`` is the chronology-complete scientific protocol.
The explicit ``prefix`` mode exists only for a bounded local real-data run and
is always labelled non-formal in the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score


OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckat_canonical_time_c1_canary_v1 as ckat  # noqa: E402
import issue27ckbe_tgn_fullsupport_event_cache_v1 as ckbe  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckbl_frontend_observability_audit_v1_2026-07-14"
DEFAULT_OUT = cko.ROOT / "runs" / ISSUE
FINAL_HOLDOUT = cko.ROOT / "runs" / "mainline_docs" / "ckbk_untouched_final_holdout_manifest_v1.json"
SEED = 27

FORBIDDEN_DEVICE_FAMILIES = {
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "iotsim-cooler-motor",
}
DEVELOPMENT_CANARIES = {"iotsim-stream-consumer", "iotsim-hydraulic-system"}


@dataclass(frozen=True)
class Bundle:
    name: str
    feature_names: tuple[str, ...]
    candidate: bool
    causal: bool
    description: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    result = subprocess.run(
        ["git", "-C", str(cko.ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def stable_seed(*parts: Any) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") & 0x7FFFFFFF


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compact_process_names() -> list[str]:
    names = list(ckai.CURRENT_FEATURES)
    state = [
        "duration_log",
        "iat_last_log",
        "iat_mean_log",
        "pkt_rate_log",
        "byte_rate_log",
        "len_mean_log",
        "syn_rate",
        "ack_rate",
        "rst_rate",
        "fin_rate",
    ]
    for window in ckai.WINDOWS:
        for scope in ["pair", "biflow"]:
            names.extend(f"{scope}_w{window}_{suffix}" for suffix in state)
        names.extend(
            [
                f"pair_rev_seen_w{window}",
                f"pair_fwd_rev_count_balance_w{window}",
                f"pair_fwd_rev_byte_balance_w{window}",
            ]
        )
    names.extend(
        [
            "pair_count_short_long_ratio_w16_128",
            "flow5_count_short_long_ratio_w16_128",
            "biflow_count_short_long_ratio_w16_128",
        ]
    )
    missing = sorted(set(names) - set(ckai.FEATURE_NAMES))
    if missing:
        raise RuntimeError(f"compact process schema references missing features: {missing}")
    if len(names) != len(set(names)):
        raise RuntimeError("compact process schema contains duplicate features")
    return names


COMPACT_NAMES = compact_process_names()
C1_NAMES = [ckai.FEATURE_NAMES[index] for index in ckai.FEATURE_BLOCK_COLUMNS["cicflow_style"]]
TGN9_NAMES = list(ckbe.RAW_MSG_NAMES)

BUNDLES = [
    Bundle(
        "TGN9_exact",
        tuple(TGN9_NAMES),
        True,
        True,
        "Exact CKBE 9D portable event message; no identity features.",
    ),
    Bundle(
        "Current20",
        tuple(ckai.CURRENT_FEATURES),
        True,
        True,
        "Current packet/protocol fields only; no historical state.",
    ),
    Bundle(
        "CompactProcess69",
        tuple(COMPACT_NAMES),
        True,
        True,
        "Preregistered current plus pair/biflow temporal process statistics.",
    ),
    Bundle(
        "CompactProcess69_history_permuted",
        tuple(COMPACT_NAMES),
        False,
        False,
        "Noncausal negative control: history columns permuted within source; never a route candidate.",
    ),
    Bundle(
        "C1_207_upper_bound",
        tuple(C1_NAMES),
        True,
        True,
        "Existing C1 CICFlow-style feature block as the engineered upper-bound control.",
    ),
]


class FullSourceCanonicalTimeC1Cache(ckat.CanonicalTimeC1Cache):
    """Use CKAT's causal feature logic while reading the complete raw source."""

    def _read_prefix(self, member: str, nrows: int) -> pd.DataFrame:  # noqa: ARG002
        with zipfile.ZipFile(self.zip_path) as archive:
            if member not in archive.namelist():
                raise FileNotFoundError(f"{member} not found inside {self.zip_path}")
            with archive.open(member) as handle:
                return pd.read_csv(handle, usecols=lambda column: column in ckat.RAW_USECOLS, low_memory=False)


def load_final_holdout() -> tuple[dict[str, Any], str]:
    if not FINAL_HOLDOUT.exists():
        raise FileNotFoundError(f"missing sealed holdout manifest: {FINAL_HOLDOUT}")
    payload = json.loads(FINAL_HOLDOUT.read_text(encoding="utf-8"))
    if payload.get("status") != "SEALED_NOT_OPENED":
        raise RuntimeError(f"unexpected final holdout status: {payload.get('status')}")
    return payload, sha256_file(FINAL_HOLDOUT)


def legal_fit_table(frame_by_role: dict[str, pd.DataFrame], max_recorded_index: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    audit_rows: list[dict[str, Any]] = []
    specs = [
        ("support_train", "attack", 1),
        ("id_calib", "benign", 0),
        ("ood_val", "benign", 0),
    ]
    for role, class_name, label in specs:
        frame = frame_by_role[role].copy()
        before = int(len(frame))
        frame = frame.loc[frame["phase"].astype(str).eq("fit")].copy()
        fit_rows = int(len(frame))
        forbidden = frame["device_family"].astype(str).isin(FORBIDDEN_DEVICE_FAMILIES)
        forbidden_counts = frame.loc[forbidden].groupby("device_family", dropna=False).size().to_dict()
        frame = frame.loc[~forbidden].copy()
        after_forbidden = int(len(frame))
        frame["recorded_index"] = pd.to_numeric(frame["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
        frame = frame.loc[frame["recorded_index"].ge(0)].copy()
        before_index_cap = int(len(frame))
        if int(max_recorded_index) > 0:
            frame = frame.loc[frame["recorded_index"].le(int(max_recorded_index))].copy()
        frame["role"] = role
        frame["role_row"] = frame.index.to_numpy(dtype=np.int64)
        frame["class_name"] = class_name
        frame["y"] = int(label)
        if "attack_label" not in frame:
            frame["attack_label"] = "benign"
        frame["attack_label"] = np.where(
            frame["y"].to_numpy(dtype=np.int64) == 1,
            frame["attack_label"].astype(str),
            "benign",
        )
        parts.append(frame)
        audit_rows.append(
            {
                "role": role,
                "phase": "fit",
                "class_name": class_name,
                "role_rows_before_phase": before,
                "fit_rows_before_forbidden_exclusion": fit_rows,
                "forbidden_rows_removed": int(fit_rows - after_forbidden),
                "forbidden_breakdown_json": json.dumps(forbidden_counts, sort_keys=True),
                "rows_before_recorded_index_cap": before_index_cap,
                "rows_selected": int(len(frame)),
                "max_recorded_index_cap": int(max_recorded_index),
            }
        )
    table = pd.concat(parts, ignore_index=True)
    table["row_uid"] = [f"{role}:{int(row)}" for role, row in zip(table["role"], table["role_row"])]
    if table["row_uid"].duplicated().any():
        raise RuntimeError("duplicate role-row UID in legal fit table")
    used_forbidden = sorted(set(table["device_family"].astype(str)) & FORBIDDEN_DEVICE_FAMILIES)
    if used_forbidden:
        raise RuntimeError(f"forbidden family entered legal fit table: {used_forbidden}")
    return table.reset_index(drop=True), pd.DataFrame(audit_rows)


def source_plan(table: pd.DataFrame, read_mode: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source, part in table.groupby("source_group", sort=True):
        rows.append(
            {
                "source_group": str(source),
                "device_families": ";".join(sorted(part["device_family"].astype(str).unique())),
                "class_names": ";".join(sorted(part["class_name"].astype(str).unique())),
                "target_rows": int(len(part)),
                "min_recorded_index": int(part["recorded_index"].min()),
                "max_recorded_index": int(part["recorded_index"].max()),
                "raw_read_mode": str(read_mode),
                "raw_label_column_read": False,
            }
        )
    return pd.DataFrame(rows)


def assert_scope(table: pd.DataFrame, final_manifest: dict[str, Any]) -> None:
    forbidden_sources = set(str(value) for value in final_manifest.get("source_groups", []))
    used_sources = set(table["source_group"].astype(str))
    collision = sorted(used_sources & forbidden_sources)
    if collision:
        raise RuntimeError(f"sealed final source entered model scope: {collision}")
    if set(table["device_family"].astype(str)) & FORBIDDEN_DEVICE_FAMILIES:
        raise RuntimeError("forbidden device family entered model scope")
    if set(table["role"].astype(str)) - {"support_train", "id_calib", "ood_val"}:
        raise RuntimeError("non-fit role entered model scope")
    if not table["phase"].astype(str).eq("fit").all():
        raise RuntimeError("non-fit phase entered model scope")


def known_nonfit_target_blocks(
    frame_by_role: dict[str, pd.DataFrame],
    table: pd.DataFrame,
) -> tuple[dict[str, set[int]], pd.DataFrame]:
    """Block every known non-selected target from fit-time passive state.

    Raw events without a role assignment remain eligible as label-free,
    past-only memory context.  A target explicitly assigned to select, query,
    future, sealed, report, or a locally capped-out fit row is not allowed to
    update a selected fit target's history.
    """
    relevant_sources = set(table["source_group"].astype(str))
    selected = {
        (str(source), int(recorded))
        for source, recorded in zip(table["source_group"], table["recorded_index"])
    }
    blocked: dict[str, set[int]] = {source: set() for source in relevant_sources}
    audit_rows: list[dict[str, Any]] = []
    selected_collisions: list[tuple[str, int, str, str]] = []
    for role, frame in frame_by_role.items():
        if "source_group" not in frame or "recorded_index" not in frame:
            continue
        work = frame.loc[frame["source_group"].astype(str).isin(relevant_sources)].copy()
        if work.empty:
            continue
        work["recorded_index"] = pd.to_numeric(work["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
        work = work.loc[work["recorded_index"].ge(0)].copy()
        phase_values = work.get("phase", pd.Series("NA", index=work.index)).astype(str)
        for phase, part in work.groupby(phase_values, sort=True):
            added = 0
            selected_rows = 0
            for source, recorded in zip(part["source_group"].astype(str), part["recorded_index"].astype(int)):
                key = (source, int(recorded))
                if key in selected:
                    selected_rows += 1
                    if not (str(role) in {"support_train", "id_calib", "ood_val"} and str(phase) == "fit"):
                        selected_collisions.append((source, int(recorded), str(role), str(phase)))
                    continue
                before = len(blocked[source])
                blocked[source].add(int(recorded))
                added += int(len(blocked[source]) > before)
            audit_rows.append(
                {
                    "role": str(role),
                    "phase": str(phase),
                    "relevant_source_target_rows": int(len(part)),
                    "selected_fit_rows_seen": int(selected_rows),
                    "new_known_target_rows_blocked": int(added),
                    "raw_label_column_read": False,
                }
            )
    if selected_collisions:
        raise RuntimeError(f"selected fit target also has a non-fit assignment: {selected_collisions[:8]}")
    if any((source, recorded) in selected for source, values in blocked.items() for recorded in values):
        raise RuntimeError("selected fit target entered passive-state block list")
    return blocked, pd.DataFrame(audit_rows)


def exact_tgn9(external: np.ndarray, audit_rows: list[dict[str, Any]]) -> np.ndarray:
    index = {name: position for position, name in enumerate(ckai.FEATURE_NAMES)}
    ports = np.asarray([int(row.get("processed_dst_port", 0)) for row in audit_rows], dtype=np.int64)
    out = np.column_stack(
        [
            external[:, index["cur_len_log"]],
            external[:, index["cur_is_tcp"]],
            external[:, index["cur_is_udp"]],
            external[:, index["cur_is_icmp"]],
            np.asarray([ckbe.port_bucket(int(port)) for port in ports], dtype=np.float32),
            external[:, index["cur_tcp_syn"]],
            external[:, index["cur_tcp_ack"]],
            external[:, index["cur_tcp_rst"]],
            external[:, index["cur_tcp_fin"]],
        ]
    ).astype(np.float32)
    if out.shape[1] != len(TGN9_NAMES):
        raise RuntimeError("exact TGN9 schema drift")
    return out


def feature_matrices(
    table: pd.DataFrame,
    frame_by_role: dict[str, pd.DataFrame],
    x_by_role: dict[str, np.ndarray],
    read_mode: str,
    seed: int,
    state_blocked_rows: dict[str, set[int]] | None = None,
    progress_path: Path | None = None,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]], list[dict[str, Any]]]:
    cache_cls = FullSourceCanonicalTimeC1Cache if read_mode == "full" else ckat.CanonicalTimeC1Cache
    cache = cache_cls(cko.GOTHAM_ZIP, state_blocked_rows=state_blocked_rows)
    frontend = ckai.ExternalFlowFrontend(x_by_role, frame_by_role, cache)
    external = np.zeros((len(table), len(ckai.FEATURE_NAMES)), dtype=np.float32)
    row_audits_by_position: list[dict[str, Any] | None] = [None] * len(table)
    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.write_text("", encoding="utf-8")
    for source_number, (source, part) in enumerate(table.groupby("source_group", sort=True), start=1):
        roles = part["role"].astype(str).unique().tolist()
        if len(roles) != 1:
            raise RuntimeError(f"source spans multiple selected roles: {source}: {roles}")
        role = str(roles[0])
        idx = part["role_row"].to_numpy(dtype=np.int64)
        print(
            f"CKBL_SOURCE_START {source_number}/{table['source_group'].nunique()} "
            f"source={source} targets={len(part)} max_recorded={int(part['recorded_index'].max())}",
            flush=True,
        )
        source_started = time.time()
        source_external = frontend.external_matrix(role, idx)
        positions = part.index.to_numpy(dtype=np.int64)
        external[positions] = source_external
        for position, (_, row) in zip(positions.tolist(), part.iterrows()):
            audit = cache.audit_for_member(str(source)).get(int(row["recorded_index"]), {})
            row_audits_by_position[int(position)] = {
                    "row_uid": str(row["row_uid"]),
                    "role": str(role),
                    "source_group": str(source),
                    "recorded_index": int(row["recorded_index"]),
                    "alignment_ok": bool(audit.get("alignment_ok", False)),
                    "raw_label_column_read": bool(audit.get("raw_label_column_read", True)),
                    "chronology_status": str(audit.get("chronology_status", "")),
                    "canonical_rank": int(audit.get("canonical_rank", -1)),
                    "processed_dst_port": int(audit.get("processed_dst_port", 0)),
                    "state_update_allowed": bool(audit.get("state_update_allowed", True)),
            }
        progress = {
            "source_number": int(source_number),
            "source_count": int(table["source_group"].nunique()),
            "source_group": str(source),
            "target_rows": int(len(part)),
            "seconds": float(time.time() - source_started),
            "status": "FEATURES_COMPLETE",
        }
        if progress_path is not None:
            with progress_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(progress, sort_keys=True) + "\n")
        print(f"CKBL_SOURCE_DONE {json.dumps(progress, sort_keys=True)}", flush=True)
    row_audits = [row for row in row_audits_by_position if row is not None]
    if len(external) != len(table) or len(row_audits) != len(table):
        raise RuntimeError("feature/table alignment length mismatch")
    if not all(row["alignment_ok"] for row in row_audits):
        missing = [row["row_uid"] for row in row_audits if not row["alignment_ok"]]
        raise RuntimeError(f"canonical frontend alignment incomplete: {missing[:8]}")
    if any(row["raw_label_column_read"] for row in row_audits):
        raise RuntimeError("raw label column was read by frontend")

    feature_index = {name: index for index, name in enumerate(ckai.FEATURE_NAMES)}
    compact_cols = [feature_index[name] for name in COMPACT_NAMES]
    current_cols = [feature_index[name] for name in ckai.CURRENT_FEATURES]
    c1_cols = [feature_index[name] for name in C1_NAMES]
    compact = external[:, compact_cols].astype(np.float32)
    permuted = compact.copy()
    history_cols = np.arange(len(ckai.CURRENT_FEATURES), compact.shape[1], dtype=np.int64)
    for source, positions in table.groupby("source_group", sort=True).indices.items():
        pos = np.asarray(positions, dtype=np.int64)
        if len(pos) <= 1:
            continue
        rng = np.random.default_rng(stable_seed(seed, "history_permutation", source))
        perm = rng.permutation(pos)
        permuted[np.ix_(pos, history_cols)] = compact[np.ix_(perm, history_cols)]
    if not np.array_equal(permuted[:, : len(ckai.CURRENT_FEATURES)], compact[:, : len(ckai.CURRENT_FEATURES)]):
        raise RuntimeError("history negative control modified current-event columns")

    matrices = {
        "TGN9_exact": exact_tgn9(external, row_audits),
        "Current20": external[:, current_cols].astype(np.float32),
        "CompactProcess69": compact,
        "CompactProcess69_history_permuted": permuted,
        "C1_207_upper_bound": external[:, c1_cols].astype(np.float32),
    }
    expected = {bundle.name: len(bundle.feature_names) for bundle in BUNDLES}
    actual = {name: int(matrix.shape[1]) for name, matrix in matrices.items()}
    if actual != expected:
        raise RuntimeError(f"feature bundle dimension mismatch: actual={actual}, expected={expected}")
    return matrices, row_audits, list(cache.audit_rows)


def feature_value_audit(matrices: dict[str, np.ndarray], table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    ordered = matrices["CompactProcess69"]
    permuted = matrices["CompactProcess69_history_permuted"]
    history_start = len(ckai.CURRENT_FEATURES)
    for name, matrix in matrices.items():
        rows.append(
            {
                "scope": "all",
                "source_group": "ALL",
                "bundle": name,
                "rows": int(matrix.shape[0]),
                "feature_dim": int(matrix.shape[1]),
                "nonzero_fraction": float(np.mean(matrix != 0.0)),
                "finite_fraction": float(np.mean(np.isfinite(matrix))),
                "varying_columns": int(np.sum(np.ptp(matrix, axis=0) > 0.0)),
                "matrix_sha256": hashlib.sha256(np.ascontiguousarray(matrix).tobytes()).hexdigest(),
            }
        )
    for source, positions in table.groupby("source_group", sort=True).indices.items():
        pos = np.asarray(positions, dtype=np.int64)
        history = ordered[pos, history_start:]
        changed = history != permuted[pos, history_start:]
        rows.append(
            {
                "scope": "compact_history_control",
                "source_group": str(source),
                "bundle": "CompactProcess69_vs_history_permuted",
                "rows": int(len(pos)),
                "feature_dim": int(history.shape[1]),
                "nonzero_fraction": float(np.mean(history != 0.0)),
                "finite_fraction": float(np.mean(np.isfinite(history))),
                "varying_columns": int(np.sum(np.ptp(history, axis=0) > 0.0)),
                "changed_cell_fraction": float(np.mean(changed)),
                "changed_row_fraction": float(np.mean(np.any(changed, axis=1))),
                "matrix_sha256": hashlib.sha256(np.ascontiguousarray(history).tobytes()).hexdigest(),
            }
        )
    compact_changed = ordered[:, history_start:] != permuted[:, history_start:]
    if not bool(np.any(compact_changed)):
        raise RuntimeError("history-permuted negative control did not change any history value")
    return pd.DataFrame(rows)


def group_balanced_weights(meta: pd.DataFrame) -> np.ndarray:
    y = meta["y"].to_numpy(dtype=np.int64)
    weights = np.zeros(len(meta), dtype=np.float64)
    for label in sorted(np.unique(y).tolist()):
        class_pos = np.flatnonzero(y == int(label))
        if int(label) == 1:
            keys = meta.iloc[class_pos]["attack_label"].astype(str).to_numpy()
        else:
            keys = meta.iloc[class_pos]["source_group"].astype(str).to_numpy()
        groups = sorted(set(keys.tolist()))
        for group in groups:
            pos = class_pos[keys == group]
            weights[pos] = 1.0 / (2.0 * len(groups) * len(pos))
    if not np.isfinite(weights).all() or float(weights.sum()) <= 0:
        raise RuntimeError("invalid group-balanced weights")
    weights *= len(weights) / float(weights.sum())
    return weights


def fit_probe(x: np.ndarray, meta: pd.DataFrame, seed: int, max_iter: int) -> HistGradientBoostingClassifier:
    if set(meta["y"].astype(int).unique().tolist()) != {0, 1}:
        raise RuntimeError("probe training requires attack and benign rows")
    model = HistGradientBoostingClassifier(
        max_iter=int(max_iter),
        learning_rate=0.05,
        max_leaf_nodes=8,
        min_samples_leaf=10,
        l2_regularization=0.1,
        random_state=int(seed),
    )
    model.fit(np.asarray(x, dtype=np.float32), meta["y"].to_numpy(dtype=np.int64), sample_weight=group_balanced_weights(meta))
    return model


def score_probe(model: HistGradientBoostingClassifier, x: np.ndarray) -> np.ndarray:
    classes = list(model.classes_)
    if 1 not in classes:
        raise RuntimeError("trained probe lacks attack class")
    score = np.asarray(model.predict_proba(np.asarray(x, dtype=np.float32))[:, classes.index(1)], dtype=np.float64)
    if not np.isfinite(score).all():
        raise RuntimeError("probe emitted non-finite scores")
    return score


def inner_oof_scores(x: np.ndarray, meta: pd.DataFrame, seed: int, max_iter: int) -> tuple[np.ndarray, str]:
    scores = np.full(len(meta), np.nan, dtype=np.float64)
    sources = sorted(meta["source_group"].astype(str).unique().tolist())
    for source in sources:
        held = meta["source_group"].astype(str).eq(source).to_numpy()
        train = ~held
        if set(meta.loc[train, "y"].astype(int).unique().tolist()) != {0, 1}:
            continue
        model = fit_probe(x[train], meta.loc[train].reset_index(drop=True), stable_seed(seed, "inner", source), max_iter)
        scores[held] = score_probe(model, x[held])
    coverage = float(np.mean(np.isfinite(scores))) if len(scores) else 0.0
    status = "INNER_SOURCE_OOF_COMPLETE" if coverage == 1.0 else f"INNER_SOURCE_OOF_INCOMPLETE_{coverage:.6f}"
    return scores, status


def select_threshold(meta: pd.DataFrame, scores: np.ndarray) -> tuple[float, dict[str, Any]]:
    valid = np.isfinite(scores)
    if int(valid.sum()) != len(meta):
        return float("nan"), {"status": "UNAVAILABLE_INCOMPLETE_INNER_OOF", "rows": int(valid.sum())}
    y = meta["y"].to_numpy(dtype=np.int64)
    attack = y == 1
    benign = y == 0
    if not bool(attack.any()) or not bool(benign.any()):
        return float("nan"), {"status": "UNAVAILABLE_MISSING_CLASS", "rows": int(len(meta))}
    family_counts = meta.loc[attack].groupby("attack_label").size()
    major = set(family_counts[family_counts >= 10].index.astype(str).tolist())
    if not major:
        major = set(family_counts.index.astype(str).tolist())
    weights = group_balanced_weights(meta)
    candidates = np.unique(np.concatenate([scores, [np.nextafter(float(np.min(scores)), -np.inf)]]))[::-1]
    selected: tuple[float, float, float, float] | None = None
    for threshold in candidates:
        pred = scores >= float(threshold)
        attack_recall = float(np.sum(weights[attack] * pred[attack]) / np.sum(weights[attack]))
        family_recall = []
        for family in sorted(major):
            mask = attack & meta["attack_label"].astype(str).eq(family).to_numpy()
            family_recall.append(float(np.mean(pred[mask])))
        worst_major = min(family_recall) if family_recall else float("nan")
        if attack_recall + 1e-12 < 0.995 or worst_major + 1e-12 < 0.98:
            continue
        benign_fpr = float(np.sum(weights[benign] * pred[benign]) / np.sum(weights[benign]))
        selected = (float(threshold), attack_recall, worst_major, benign_fpr)
        break
    if selected is None:
        return float("nan"), {"status": "UNAVAILABLE_NO_ATTACK_PRESERVING_THRESHOLD", "rows": int(len(meta))}
    threshold, attack_recall, worst_major, benign_fpr = selected
    return threshold, {
        "status": "SELECTED_FROM_INNER_SOURCE_OOF",
        "rows": int(len(meta)),
        "threshold": threshold,
        "inner_attack_recall": attack_recall,
        "inner_worst_major_family_recall": worst_major,
        "inner_benign_fpr": benign_fpr,
        "major_family_count": int(len(major)),
    }


def safe_auc(y: np.ndarray, score: np.ndarray) -> tuple[float, float]:
    if set(np.unique(y).tolist()) != {0, 1}:
        return float("nan"), float("nan")
    return float(roc_auc_score(y, score)), float(average_precision_score(y, score))


def evaluate_fold(
    bundle: Bundle,
    x: np.ndarray,
    table: pd.DataFrame,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    protocol: str,
    fold: str,
    seed: int,
    max_iter: int,
) -> dict[str, Any]:
    train_meta = table.loc[train_mask].reset_index(drop=True)
    test_meta = table.loc[test_mask].reset_index(drop=True)
    if set(train_meta["y"].astype(int).unique().tolist()) != {0, 1}:
        raise RuntimeError(f"{protocol}/{fold}/{bundle.name}: outer training lost a class")
    if set(test_meta["y"].astype(int).unique().tolist()) != {0, 1}:
        raise RuntimeError(f"{protocol}/{fold}/{bundle.name}: outer test lost a class")
    model_seed = stable_seed(seed, protocol, fold, bundle.name)
    inner_scores, inner_status = inner_oof_scores(x[train_mask], train_meta, model_seed, max_iter)
    threshold, threshold_audit = select_threshold(train_meta, inner_scores)
    model = fit_probe(x[train_mask], train_meta, model_seed, max_iter)
    scores = score_probe(model, x[test_mask])
    y = test_meta["y"].to_numpy(dtype=np.int64)
    auc, ap = safe_auc(y, scores)
    attack = y == 1
    benign = y == 0
    result: dict[str, Any] = {
        "protocol": protocol,
        "fold": fold,
        "bundle": bundle.name,
        "candidate": bundle.candidate,
        "causal": bundle.causal,
        "feature_dim": int(x.shape[1]),
        "train_rows": int(train_mask.sum()),
        "train_sources": int(train_meta["source_group"].nunique()),
        "train_attack_families": int(train_meta.loc[train_meta["y"].eq(1), "attack_label"].nunique()),
        "test_rows": int(test_mask.sum()),
        "test_attack_rows": int(attack.sum()),
        "test_benign_rows": int(benign.sum()),
        "test_sources": int(test_meta["source_group"].nunique()),
        "test_attack_families": int(test_meta.loc[test_meta["y"].eq(1), "attack_label"].nunique()),
        "auroc": auc,
        "average_precision": ap,
        "attack_score_mean": float(np.mean(scores[attack])),
        "benign_score_mean": float(np.mean(scores[benign])),
        "score_margin": float(np.mean(scores[attack]) - np.mean(scores[benign])),
        "inner_oof_status": inner_status,
        "threshold_status": str(threshold_audit["status"]),
        "threshold": threshold,
        "model_seed": int(model_seed),
    }
    if np.isfinite(threshold):
        hard = scores >= threshold
        result["outer_attack_recall"] = float(np.mean(hard[attack]))
        result["outer_benign_fpr"] = float(np.mean(hard[benign]))
        per_family = []
        for family, positions in test_meta.loc[attack].groupby("attack_label", sort=True).indices.items():
            attack_positions = np.flatnonzero(attack)[np.asarray(positions, dtype=np.int64)]
            per_family.append(float(np.mean(hard[attack_positions])))
        result["outer_worst_attack_family_recall"] = min(per_family) if per_family else float("nan")
    else:
        result["outer_attack_recall"] = float("nan")
        result["outer_benign_fpr"] = float("nan")
        result["outer_worst_attack_family_recall"] = float("nan")
    return result


def build_folds(table: pd.DataFrame) -> list[dict[str, Any]]:
    y = table["y"].to_numpy(dtype=np.int64)
    sources = table["source_group"].astype(str)
    benign_sources = sorted(table.loc[y == 0, "source_group"].astype(str).unique().tolist())
    attack_sources = sorted(table.loc[y == 1, "source_group"].astype(str).unique().tolist())
    folds: list[dict[str, Any]] = []
    for benign_source in benign_sources:
        for attack_source in attack_sources:
            test = ((y == 0) & sources.eq(benign_source).to_numpy()) | ((y == 1) & sources.eq(attack_source).to_numpy())
            train = ~sources.isin({benign_source, attack_source}).to_numpy()
            if set(table.loc[train, "y"].astype(int).unique().tolist()) == {0, 1}:
                folds.append(
                    {
                        "protocol": "unseen_source_pair",
                        "fold": f"benign={benign_source}|attack={attack_source}",
                        "train": train,
                        "test": test,
                    }
                )
    attack_families = sorted(table.loc[y == 1, "attack_label"].astype(str).unique().tolist())
    for number, family in enumerate(attack_families):
        benign_source = benign_sources[number % len(benign_sources)]
        family_attack = (y == 1) & table["attack_label"].astype(str).eq(family).to_numpy()
        origin_sources = set(table.loc[family_attack, "source_group"].astype(str).tolist())
        excluded_sources = set(origin_sources) | {benign_source}
        train = (~sources.isin(excluded_sources).to_numpy()) & (~table["attack_label"].astype(str).eq(family).to_numpy())
        test = family_attack | ((y == 0) & sources.eq(benign_source).to_numpy())
        if set(table.loc[train, "y"].astype(int).unique().tolist()) == {0, 1}:
            folds.append(
                {
                    "protocol": "unseen_attack_family_origin",
                    "fold": f"family={family}|origins={';'.join(sorted(origin_sources))}|benign={benign_source}",
                    "train": train,
                    "test": test,
                }
            )
    return folds


def aggregate_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (protocol, bundle), part in metrics.groupby(["protocol", "bundle"], sort=True):
        finite_threshold = part["outer_attack_recall"].notna()
        rows.append(
            {
                "protocol": protocol,
                "bundle": bundle,
                "folds": int(len(part)),
                "macro_auroc": float(part["auroc"].mean()),
                "worst_fold_auroc": float(part["auroc"].min()),
                "macro_average_precision": float(part["average_precision"].mean()),
                "macro_score_margin": float(part["score_margin"].mean()),
                "threshold_evaluable_folds": int(finite_threshold.sum()),
                "macro_attack_recall": float(part.loc[finite_threshold, "outer_attack_recall"].mean()) if bool(finite_threshold.any()) else float("nan"),
                "worst_attack_family_recall": float(part.loc[finite_threshold, "outer_worst_attack_family_recall"].min()) if bool(finite_threshold.any()) else float("nan"),
                "macro_benign_fpr": float(part.loc[finite_threshold, "outer_benign_fpr"].mean()) if bool(finite_threshold.any()) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def metric_lookup(aggregate: pd.DataFrame, protocol: str, bundle: str, metric: str) -> float:
    row = aggregate.loc[aggregate["protocol"].eq(protocol) & aggregate["bundle"].eq(bundle)]
    return float(row.iloc[0][metric]) if len(row) else float("nan")


def decide(table: pd.DataFrame, aggregate: pd.DataFrame, args: argparse.Namespace) -> dict[str, Any]:
    complete = bool(
        args.source_read_mode == "full"
        and int(args.max_recorded_index) <= 0
        and int((table["y"] == 1).sum()) == 385
        and int(table.loc[table["y"].eq(1), "attack_label"].nunique()) == 10
        and int(table["source_group"].nunique()) == 8
    )
    source_compact = metric_lookup(aggregate, "unseen_source_pair", "CompactProcess69", "macro_auroc")
    family_compact = metric_lookup(aggregate, "unseen_attack_family_origin", "CompactProcess69", "macro_auroc")
    source_tgn9 = metric_lookup(aggregate, "unseen_source_pair", "TGN9_exact", "macro_auroc")
    family_tgn9 = metric_lookup(aggregate, "unseen_attack_family_origin", "TGN9_exact", "macro_auroc")
    source_shuffle = metric_lookup(aggregate, "unseen_source_pair", "CompactProcess69_history_permuted", "macro_auroc")
    family_shuffle = metric_lookup(aggregate, "unseen_attack_family_origin", "CompactProcess69_history_permuted", "macro_auroc")
    source_c1 = metric_lookup(aggregate, "unseen_source_pair", "C1_207_upper_bound", "macro_auroc")
    family_c1 = metric_lookup(aggregate, "unseen_attack_family_origin", "C1_207_upper_bound", "macro_auroc")
    checks = {
        "source_compact_macro_auroc_ge_0_75": bool(source_compact >= 0.75),
        "family_compact_macro_auroc_ge_0_70": bool(family_compact >= 0.70),
        "source_compact_minus_tgn9_ge_0_03": bool(source_compact - source_tgn9 >= 0.03),
        "family_compact_minus_tgn9_ge_0_03": bool(family_compact - family_tgn9 >= 0.03),
        "source_order_minus_shuffle_ge_0_02": bool(source_compact - source_shuffle >= 0.02),
        "family_order_minus_shuffle_ge_0_02": bool(family_compact - family_shuffle >= 0.02),
    }
    signal = all(checks.values())
    if complete:
        verdict = "OBSERVABILITY_GO_SIGNAL" if signal else "OBSERVABILITY_NO_GO"
    else:
        verdict = "TRUNCATED_LOCAL_SIGNAL" if signal else "TRUNCATED_LOCAL_NO_SIGNAL"
    if source_c1 >= 0.75 and family_c1 >= 0.70 and not signal:
        interpretation = "engineered_upper_bound_has_signal_but_compact_process_adapter_is_insufficient"
    elif source_c1 < 0.75 or family_c1 < 0.70:
        interpretation = "even_c1_upper_bound_lacks_robust_strict_fit_generalization_signal"
    else:
        interpretation = "compact_causal_process_features_show_transferable_signal"
    return {
        "verdict": verdict,
        "formal_complete_protocol": complete,
        "interpretation": interpretation,
        "checks": checks,
        "metrics": {
            "source_compact_macro_auroc": source_compact,
            "family_compact_macro_auroc": family_compact,
            "source_tgn9_macro_auroc": source_tgn9,
            "family_tgn9_macro_auroc": family_tgn9,
            "source_shuffle_macro_auroc": source_shuffle,
            "family_shuffle_macro_auroc": family_shuffle,
            "source_c1_macro_auroc": source_c1,
            "family_c1_macro_auroc": family_c1,
        },
        "claim_boundary": "This is a fit-only representation gate, not formal report-canary performance and not final IDS evidence.",
    }


def write_summary(out: Path, table: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any], elapsed: float) -> None:
    columns = aggregate.columns.astype(str).tolist()
    markdown_rows = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for record in aggregate.to_dict(orient="records"):
        values = []
        for column in columns:
            value = record.get(column, "")
            if isinstance(value, float):
                value = "NA" if not math.isfinite(value) else f"{value:.6g}"
            values.append(str(value).replace("|", "\\|"))
        markdown_rows.append("| " + " | ".join(values) + " |")
    lines = [
        "# CKBL frontend observability audit",
        "",
        f"- Verdict: `{decision['verdict']}`",
        f"- Formal complete protocol: `{decision['formal_complete_protocol']}`",
        f"- Interpretation: `{decision['interpretation']}`",
        f"- Selected rows: `{len(table)}`; sources: `{table['source_group'].nunique()}`; attack families: `{table.loc[table['y'].eq(1), 'attack_label'].nunique()}`",
        f"- Runtime seconds: `{elapsed:.3f}`",
        "- stream-consumer/hydraulic-system/cooler-motor model use: `0`",
        "- Raw label column read by frontend: `false`",
        "- Identity fields are split/audit metadata only and are absent from feature matrices.",
        "",
        "## Aggregate metrics",
        "",
        "\n".join(markdown_rows),
        "",
        "## Claim boundary",
        "",
        str(decision["claim_boundary"]),
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def contract_unit() -> None:
    assert len(TGN9_NAMES) == 9
    assert len(ckai.CURRENT_FEATURES) == 20
    assert len(COMPACT_NAMES) == 69
    assert len(C1_NAMES) == 207
    assert ckbe.port_bucket(0) == 0.0
    assert ckbe.port_bucket(53) == 0.25
    assert ckbe.port_bucket(8080) == 0.5
    assert ckbe.port_bucket(60000) == 0.75
    toy = pd.DataFrame(
        {
            "y": [0, 0, 1, 1, 1],
            "source_group": ["b1", "b2", "a1", "a2", "a2"],
            "attack_label": ["benign", "benign", "f1", "f2", "f2"],
        }
    )
    weights = group_balanced_weights(toy)
    assert np.isclose(weights[toy["y"].eq(0)].sum(), weights[toy["y"].eq(1)].sum())
    assert np.isclose(weights[toy["source_group"].eq("b1")].sum(), weights[toy["source_group"].eq("b2")].sum())
    assert np.isclose(weights[toy["attack_label"].eq("f1")].sum(), weights[toy["attack_label"].eq("f2")].sum())
    with tempfile.TemporaryDirectory() as temporary:
        archive_path = Path(temporary) / "toy.zip"
        member = "processed/toy.csv"
        toy_raw = pd.DataFrame(
            {
                "frame.time": ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z"],
                "frame.len": [100, 200, 300],
                "frame.protocols": ["eth:ip:tcp"] * 3,
                "eth.src": ["a", "a", "a"],
                "eth.dst": ["b", "b", "b"],
                "ip.src": ["10.0.0.1"] * 3,
                "ip.dst": ["10.0.0.2"] * 3,
                "ip.proto": [6, 6, 6],
                "tcp.srcport": [1000, 1000, 1000],
                "tcp.dstport": [80, 80, 80],
                "tcp.flags": [2, 16, 4],
            }
        )
        csv_bytes = toy_raw.to_csv(index=False).encode("utf-8")
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(member, csv_bytes)
        unmasked = ckat.CanonicalTimeC1Cache(archive_path)
        masked = ckat.CanonicalTimeC1Cache(archive_path, state_blocked_rows={member: {1}})
        target = np.asarray([2], dtype=np.int64)
        unmasked_feature = unmasked.features_for_member(member, target)[2]
        masked_feature = masked.features_for_member(member, target)[2]
        count_col = ckai.FEATURE_NAMES.index("file_w16_count_frac")
        assert np.isclose(unmasked_feature[count_col], 2.0 / 16.0)
        assert np.isclose(masked_feature[count_col], 1.0 / 16.0)
        assert masked.audit_rows[-1]["known_target_state_rows_blocked"] == 1
    print(json.dumps({"status": "CKBL_CONTRACT_UNIT_PASS", "dims": {bundle.name: len(bundle.feature_names) for bundle in BUNDLES}}, indent=2))


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"CKBL_RUN_STARTED out={out} mode={args.mode} read_mode={args.source_read_mode}", flush=True)
    final_manifest, final_hash = load_final_holdout()
    x_by_role, frame_by_role, input_audit, _ = cko.load_role_inputs(False)
    print("CKBL_ROLE_INPUTS_LOADED", flush=True)
    ckao.add_family_columns(frame_by_role)
    table, scope_audit = legal_fit_table(frame_by_role, int(args.max_recorded_index))
    assert_scope(table, final_manifest)
    state_blocked_rows, memory_scope_audit = known_nonfit_target_blocks(frame_by_role, table)
    print(
        f"CKBL_LEGAL_SCOPE rows={len(table)} attack={int(table['y'].sum())} "
        f"sources={table['source_group'].nunique()} families={table.loc[table['y'].eq(1), 'attack_label'].nunique()} "
        f"known_targets_blocked={sum(len(values) for values in state_blocked_rows.values())}",
        flush=True,
    )
    if int((table["y"] == 1).sum()) == 0 or int((table["y"] == 0).sum()) == 0:
        raise RuntimeError("selected local scope does not contain both classes")
    plan = source_plan(table, args.source_read_mode)
    scope_audit.to_csv(out / "data_scope_audit.csv", index=False)
    memory_scope_audit.to_csv(out / "memory_target_scope_audit.csv", index=False)
    plan.to_csv(out / "source_plan.csv", index=False)
    table[
        ["row_uid", "role", "phase", "class_name", "source_group", "device_family", "recorded_index", "attack_label"]
    ].to_csv(out / "selected_fit_rows.csv", index=False)
    pd.DataFrame(
        [
            {
                "bundle": bundle.name,
                "feature_dim": len(bundle.feature_names),
                "candidate": bundle.candidate,
                "causal": bundle.causal,
                "description": bundle.description,
                "feature_names_sha256": hashlib.sha256("\n".join(bundle.feature_names).encode("utf-8")).hexdigest(),
            }
            for bundle in BUNDLES
        ]
    ).to_csv(out / "feature_bundles.csv", index=False)
    run_spec = {
        "issue": ISSUE,
        "mode": args.mode,
        "seed": int(args.seed),
        "source_read_mode": args.source_read_mode,
        "max_recorded_index": int(args.max_recorded_index),
        "max_folds": int(args.max_folds),
        "histgb_max_iter": int(args.max_iter),
        "raw_label_column_read": False,
        "passive_state_policy": "label-free actual-past raw events; known non-selected target rows blocked from state update",
        "known_nonselected_target_state_rows_blocked": int(sum(len(values) for values in state_blocked_rows.values())),
        "allowed_roles": ["support_train/fit", "id_calib/fit", "ood_val/fit"],
        "forbidden_device_families": sorted(FORBIDDEN_DEVICE_FAMILIES),
        "development_canaries": sorted(DEVELOPMENT_CANARIES),
        "sealed_final_holdout_manifest": str(FINAL_HOLDOUT),
        "sealed_final_holdout_manifest_sha256": final_hash,
        "sealed_final_holdout_model_use_rows": 0,
        "identity_feature_use": False,
        "review": 0,
        "git_head_at_run": git_head(),
        "declared_commit_sha": os.environ.get("CKBL_COMMIT_SHA", git_head()),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "input_audit_hash": hashlib.sha256(json.dumps(json_ready(input_audit), sort_keys=True).encode("utf-8")).hexdigest(),
    }
    dump_json(out / "run_spec.json", run_spec)
    if args.mode == "plan":
        print(json.dumps({"status": "CKBL_PLAN_OK", "out": str(out), "rows": len(table), "sources": len(plan)}, indent=2))
        return

    matrices, row_audits, cache_audits = feature_matrices(
        table,
        frame_by_role,
        x_by_role,
        args.source_read_mode,
        int(args.seed),
        state_blocked_rows=state_blocked_rows,
        progress_path=out / "source_progress.jsonl",
    )
    pd.DataFrame(row_audits).to_csv(out / "frontend_alignment_audit.csv", index=False)
    pd.DataFrame(cache_audits).to_csv(out / "frontend_source_runtime_audit.csv", index=False)
    feature_value_audit(matrices, table).to_csv(out / "feature_value_audit.csv", index=False)
    folds = build_folds(table)
    if int(args.max_folds) > 0:
        folds = folds[: int(args.max_folds)]
    fold_contract_rows = []
    metrics: list[dict[str, Any]] = []
    for fold_index, fold in enumerate(folds, start=1):
        train_mask = np.asarray(fold["train"], dtype=bool)
        test_mask = np.asarray(fold["test"], dtype=bool)
        train_sources = set(table.loc[train_mask, "source_group"].astype(str))
        test_sources = set(table.loc[test_mask, "source_group"].astype(str))
        if train_sources & test_sources:
            raise RuntimeError(f"outer source leakage in {fold['protocol']}/{fold['fold']}")
        fold_contract_rows.append(
            {
                "protocol": fold["protocol"],
                "fold": fold["fold"],
                "train_rows": int(train_mask.sum()),
                "test_rows": int(test_mask.sum()),
                "train_sources": ";".join(sorted(train_sources)),
                "test_sources": ";".join(sorted(test_sources)),
                "source_overlap": 0,
                "test_labels_used_for_fit_or_threshold": 0,
            }
        )
        for bundle in BUNDLES:
            metrics.append(
                evaluate_fold(
                    bundle,
                    matrices[bundle.name],
                    table,
                    train_mask,
                    test_mask,
                    str(fold["protocol"]),
                    str(fold["fold"]),
                    int(args.seed),
                    int(args.max_iter),
                )
            )
        print(f"CKBL_FOLD {fold_index}/{len(folds)} {fold['protocol']} {fold['fold']}", flush=True)
    pd.DataFrame(fold_contract_rows).to_csv(out / "fold_contract_audit.csv", index=False)
    metric_frame = pd.DataFrame(metrics)
    metric_frame.to_csv(out / "fold_metrics.csv", index=False)
    aggregate = aggregate_metrics(metric_frame)
    aggregate.to_csv(out / "aggregate_metrics.csv", index=False)
    decision = decide(table, aggregate, args)
    elapsed = time.time() - started
    decision["elapsed_seconds"] = elapsed
    decision["selected_rows"] = int(len(table))
    decision["selected_attack_rows"] = int(table["y"].sum())
    decision["selected_benign_rows"] = int((table["y"] == 0).sum())
    decision["source_count"] = int(table["source_group"].nunique())
    decision["attack_family_count"] = int(table.loc[table["y"].eq(1), "attack_label"].nunique())
    decision["forbidden_family_model_use"] = {family: 0 for family in sorted(FORBIDDEN_DEVICE_FAMILIES)}
    dump_json(out / "decision.json", decision)
    write_summary(out, table, aggregate, decision, elapsed)
    print(json.dumps(json_ready({"status": "CKBL_RUN_COMPLETE", "out": out, **decision}), indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["contract-unit", "plan", "run"], default="plan")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--source-read-mode", choices=["prefix", "full"], default="full")
    parser.add_argument("--max-recorded-index", type=int, default=0, help="Explicit local truncation; 0 means no target cap.")
    parser.add_argument("--max-folds", type=int, default=0, help="Test-only fold cap; 0 means all preregistered folds.")
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--seed", type=int, default=SEED)
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.mode == "contract-unit":
        contract_unit()
    else:
        run(parsed)
