from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.covariance import LedoitWolf


ROOT = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
OUT = ROOT / "runs" / "issue27cj_attack_region_instantiation_on_frozen_support_bank_2026-06-18"
ISSUE27CF = ROOT / "runs" / "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
ISSUE27CH = ROOT / "runs" / "issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17"
ISSUE27CI = ROOT / "runs" / "issue27ci_attack_region_activation_and_support_bank_protocol_refinement_2026-06-17"

ATTACK_ROOT = Path(
    r"D:\study\paper\anomaly_detection\paper04\supercompute_transfer"
    r"\issue27cd_exact_label_attack_slurm_20260614\pullback_results"
    r"\extracted_20260616_1521\datasets\gotham2025\derived"
    r"\kitsune115_exact_label_targeted_attack_v1"
)
ATTACK_CHUNKS = ATTACK_ROOT / "chunks"

CERT_ROOT = Path(
    r"D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\derived"
    r"\kitsune115_larger_sanity_1m_certified_v1"
)
CERT_X = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_X.npy"
CERT_SPLIT = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_split_manifest.csv.gz"
FEATURE_SCHEMA = CERT_ROOT / "gotham_kitsune115_1m_certified_train_state_then_eval_online_feature_schema.json"

SUPPORT_SIDECAR = ISSUE27CF / "support_bank_sidecar.csv"
CERTIFIED_CHUNKS = ISSUE27CH / "certified_chunk_manifest.csv"

PRIMARY_SCHEME = "medium"
SHELL_SCHEMES = {
    "tight": (0.50, 0.75, 0.90),
    "medium": (0.75, 0.90, 0.975),
    "wide": (0.90, 0.975, 0.995),
}
ROLE_ORDER = [
    "id_benign_train",
    "support_train",
    "support_val",
    "ood_benign_val",
    "freeze_registry",
    "ood_benign_stress",
    "certified_dev_query",
]
EPS = 1e-8
BATCH = 20000


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_id(prefix: str, text: str) -> str:
    return prefix + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def load_role_indices() -> dict[str, np.ndarray]:
    roles: dict[str, list[int]] = defaultdict(list)
    with gzip.open(CERT_SPLIT, "rt", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            roles[row["role"]].append(int(row["global_row_id"]))
    return {role: np.asarray(indices, dtype=np.int64) for role, indices in roles.items()}


def fit_robust_scaler(x_id: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    center = np.median(x_id, axis=0)
    q25 = np.quantile(x_id, 0.25, axis=0)
    q75 = np.quantile(x_id, 0.75, axis=0)
    iqr = q75 - q25
    std = np.std(x_id, axis=0)
    scale = iqr.copy()
    fallback_std = scale <= EPS
    scale[fallback_std] = std[fallback_std]
    constant = scale <= EPS
    scale[constant] = 1.0
    audit = []
    for idx in range(x_id.shape[1]):
        audit.append(
            {
                "feature_index": idx,
                "center_median": float(center[idx]),
                "iqr": float(iqr[idx]),
                "std": float(std[idx]),
                "scale": float(scale[idx]),
                "scale_source": "iqr" if not fallback_std[idx] else ("std_fallback" if not constant[idx] else "constant_unit"),
            }
        )
    return center.astype(np.float64), scale.astype(np.float64), audit


def robust_transform(x: np.ndarray, center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (np.asarray(x, dtype=np.float64) - center) / scale


def load_support() -> tuple[list[dict[str, str]], np.ndarray]:
    rows = read_csv(SUPPORT_SIDECAR)
    cache: dict[int, np.ndarray] = {}
    features = []
    for row in rows:
        chunk_id = int(row["chunk_id"])
        if chunk_id not in cache:
            cache[chunk_id] = np.load(ATTACK_CHUNKS / f"chunk_{chunk_id:05d}_X.npy", mmap_mode="r")
        row_idx = int(row["row_index_within_chunk"])
        features.append(np.asarray(cache[chunk_id][row_idx], dtype=np.float64))
    x = np.vstack(features)
    if x.shape != (512, 115) or not np.isfinite(x).all():
        raise RuntimeError(f"Invalid support features: {x.shape}")
    return rows, x


def euclidean_distance(x: np.ndarray, prototypes: np.ndarray) -> np.ndarray:
    x2 = np.sum(x * x, axis=1, keepdims=True)
    p2 = np.sum(prototypes * prototypes, axis=1)[None, :]
    return np.sqrt(np.maximum(x2 + p2 - 2.0 * x @ prototypes.T, 0.0))


def mahalanobis_distance(x: np.ndarray, prototypes: np.ndarray, precision: np.ndarray) -> np.ndarray:
    out = np.empty((x.shape[0], prototypes.shape[0]), dtype=np.float64)
    for j, proto in enumerate(prototypes):
        delta = x - proto
        out[:, j] = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", delta, precision, delta), 0.0))
    return out


def medoid_index(x: np.ndarray, metric: str, precision: np.ndarray | None = None) -> int:
    if metric == "euclidean":
        distances = euclidean_distance(x, x)
    else:
        distances = mahalanobis_distance(x, x, precision)
    return int(np.argmin(np.sum(distances, axis=1)))


def shell_name(distance: float, radii: dict[str, float]) -> str:
    if distance <= radii["core_radius"]:
        return "core"
    if distance <= radii["near_radius"]:
        return "near"
    if distance <= radii["uncertain_radius"]:
        return "uncertain"
    return "out_of_region"


def shell_rank(name: str) -> int:
    return {"core": 0, "near": 1, "uncertain": 2, "out_of_region": 3}[name]


def shell_radii(train_dist: np.ndarray, val_dist: np.ndarray, scheme: str) -> dict[str, float]:
    q_core, q_near, q_uncertain = SHELL_SCHEMES[scheme]
    pooled = np.concatenate([train_dist, val_dist])
    core = float(np.quantile(train_dist, q_core))
    near = max(core, float(np.quantile(pooled, q_near)))
    uncertain = max(near, float(np.quantile(pooled, q_uncertain)))
    return {"core_radius": core, "near_radius": near, "uncertain_radius": uncertain}


def source_count(rows: list[dict[str, str]]) -> int:
    return len({(r["device_or_source_group"], r["pcap_path"], r["source_file"]) for r in rows})


def two_medoid_audit(x: np.ndarray, val_x: np.ndarray, rows: list[dict[str, str]]) -> dict:
    if len(x) < 24:
        return {"eligible": False, "reason": "train_count_below_24"}
    d = euclidean_distance(x, x)
    single = int(np.argmin(np.sum(d, axis=1)))
    far = int(np.argmax(d[:, single]))
    medoids = [single, far]
    for _ in range(20):
        assign = np.argmin(d[:, medoids], axis=1)
        new_medoids = []
        for cluster in (0, 1):
            members = np.where(assign == cluster)[0]
            if len(members) == 0:
                return {"eligible": False, "reason": "empty_train_cluster"}
            sub = d[np.ix_(members, members)]
            new_medoids.append(int(members[np.argmin(np.sum(sub, axis=1))]))
        if new_medoids == medoids:
            break
        medoids = new_medoids
    assign = np.argmin(d[:, medoids], axis=1)
    single_cost = float(np.sum(d[:, single]))
    two_cost = float(np.sum(np.min(d[:, medoids], axis=1)))
    reduction = 0.0 if single_cost <= EPS else 1.0 - two_cost / single_cost
    train_counts = [int(np.sum(assign == k)) for k in (0, 1)]
    val_assign = np.argmin(euclidean_distance(val_x, x[medoids]), axis=1) if len(val_x) else np.array([], dtype=int)
    val_counts = [int(np.sum(val_assign == k)) for k in (0, 1)]

    source_keys = [(r["device_or_source_group"], r["pcap_path"], r["source_file"]) for r in rows]
    cluster_sources = [{source_keys[i] for i in np.where(assign == k)[0]} for k in (0, 1)]
    all_sources = set(source_keys)
    source_shortcut = (
        len(all_sources) > 1
        and cluster_sources[0].isdisjoint(cluster_sources[1])
        and cluster_sources[0] | cluster_sources[1] == all_sources
    )
    candidate = (
        min(train_counts) >= 8
        and min(val_counts) >= 2
        and reduction >= 0.35
        and not source_shortcut
    )
    return {
        "eligible": True,
        "single_medoid_index_within_label": single,
        "two_medoid_indices_within_label": "|".join(map(str, medoids)),
        "train_cluster_counts": "|".join(map(str, train_counts)),
        "val_cluster_counts": "|".join(map(str, val_counts)),
        "within_distance_reduction": reduction,
        "source_shortcut_warning": source_shortcut,
        "split_candidate": candidate,
        "reason": "diagnostic_only_no_split_executed",
    }


def aggregate_shells(
    role: str,
    true_label: str,
    nearest_labels: np.ndarray,
    distances: np.ndarray,
    nearest_indices: np.ndarray,
    labels: list[str],
    radii_by_label: dict[str, dict[str, float]],
) -> dict:
    counts = Counter()
    label_match = 0
    for i in range(len(distances)):
        nearest_label = labels[int(nearest_indices[i])]
        shell = shell_name(float(distances[i]), radii_by_label[nearest_label])
        counts[shell] += 1
        if true_label and nearest_label == true_label:
            label_match += 1
    total = len(distances)
    return {
        "role": role,
        "true_attack_label": true_label or "not_applicable",
        "rows": total,
        "core_rows": counts["core"],
        "near_rows": counts["near"],
        "uncertain_rows": counts["uncertain"],
        "out_of_region_rows": counts["out_of_region"],
        "core_rate": counts["core"] / total if total else math.nan,
        "near_rate": counts["near"] / total if total else math.nan,
        "uncertain_rate": counts["uncertain"] / total if total else math.nan,
        "out_of_region_rate": counts["out_of_region"] / total if total else math.nan,
        "nearest_region_label_match_rate": label_match / total if total and true_label else "",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    support_rows, support_x_raw = load_support()
    role_indices = load_role_indices()
    required_roles = {"id_benign_train", "ood_benign_val", "ood_benign_stress"}
    if not required_roles.issubset(role_indices):
        raise RuntimeError(f"Missing required roles: {required_roles - set(role_indices)}")

    cert_x = np.load(CERT_X, mmap_mode="r")
    id_indices = role_indices["id_benign_train"]
    x_id = np.asarray(cert_x[id_indices], dtype=np.float64)
    center, scale, scaler_audit = fit_robust_scaler(x_id)
    x_id_scaled = robust_transform(x_id, center, scale)
    lw = LedoitWolf(assume_centered=False).fit(x_id_scaled)
    precision = np.asarray(lw.precision_, dtype=np.float64)

    support_x = robust_transform(support_x_raw, center, scale)
    train_mask = np.array([r["bank_partition"] == "support_train" for r in support_rows])
    val_mask = np.array([r["bank_partition"] == "support_val" for r in support_rows])
    labels = sorted({r["exact_attack_label"] for r in support_rows})
    label_to_index = {label: i for i, label in enumerate(labels)}

    geometry = {}
    prototype_rows = []
    split_rows = []
    radii_rows = []
    support_val_rows = []
    primary_prototypes = []
    challenger_prototypes = []

    for label in labels:
        label_train_idx = np.array(
            [i for i, r in enumerate(support_rows) if train_mask[i] and r["exact_attack_label"] == label],
            dtype=int,
        )
        label_val_idx = np.array(
            [i for i, r in enumerate(support_rows) if val_mask[i] and r["exact_attack_label"] == label],
            dtype=int,
        )
        x_train = support_x[label_train_idx]
        x_val = support_x[label_val_idx]
        p_local = medoid_index(x_train, "euclidean")
        c_local = medoid_index(x_train, "mahalanobis", precision)
        p_global = int(label_train_idx[p_local])
        c_global = int(label_train_idx[c_local])
        p_proto = support_x[p_global]
        c_proto = support_x[c_global]
        primary_prototypes.append(p_proto)
        challenger_prototypes.append(c_proto)
        region_id = stable_id("attack_region_", label)

        p_train_dist = euclidean_distance(x_train, p_proto[None, :])[:, 0]
        p_val_dist = euclidean_distance(x_val, p_proto[None, :])[:, 0]
        c_train_dist = mahalanobis_distance(x_train, c_proto[None, :], precision)[:, 0]
        c_val_dist = mahalanobis_distance(x_val, c_proto[None, :], precision)[:, 0]
        geometry[label] = {
            "region_id": region_id,
            "train_indices": label_train_idx,
            "val_indices": label_val_idx,
            "primary_train_dist": p_train_dist,
            "primary_val_dist": p_val_dist,
            "challenger_train_dist": c_train_dist,
            "challenger_val_dist": c_val_dist,
        }

        for metric, proto_global in (("primary_euclidean", p_global), ("challenger_shrinkage_mahalanobis", c_global)):
            proto_row = support_rows[proto_global]
            prototype_rows.append(
                {
                    "region_id": region_id,
                    "exact_attack_label": label,
                    "metric": metric,
                    "prototype_type": "medoid",
                    "sample_id": proto_row["sample_id"],
                    "global_candidate_id": proto_row["global_candidate_id"],
                    "chunk_id": proto_row["chunk_id"],
                    "row_index_within_chunk": proto_row["row_index_within_chunk"],
                    "device_or_source_group": proto_row["device_or_source_group"],
                    "source_file": proto_row["source_file"],
                    "pcap_path": proto_row["pcap_path"],
                    "phase": proto_row["phase"],
                    "provenance_hash": proto_row["provenance_hash"],
                }
            )

        for scheme in SHELL_SCHEMES:
            p_radii = shell_radii(p_train_dist, p_val_dist, scheme)
            c_radii = shell_radii(c_train_dist, c_val_dist, scheme)
            for metric, radii in (
                ("primary_euclidean", p_radii),
                ("challenger_shrinkage_mahalanobis", c_radii),
            ):
                radii_rows.append(
                    {
                        "region_id": region_id,
                        "exact_attack_label": label,
                        "metric": metric,
                        "shell_scheme": scheme,
                        **radii,
                        "is_preregistered_primary": metric == "primary_euclidean" and scheme == PRIMARY_SCHEME,
                    }
                )
        split = two_medoid_audit(x_train, x_val, [support_rows[i] for i in label_train_idx])
        split_rows.append(
            {
                "region_id": region_id,
                "exact_attack_label": label,
                "train_rows": len(label_train_idx),
                "val_rows": len(label_val_idx),
                **split,
            }
        )

    primary_prototypes_np = np.vstack(primary_prototypes)
    challenger_prototypes_np = np.vstack(challenger_prototypes)
    primary_radii = {
        row["exact_attack_label"]: {
            "core_radius": float(row["core_radius"]),
            "near_radius": float(row["near_radius"]),
            "uncertain_radius": float(row["uncertain_radius"]),
        }
        for row in radii_rows
        if row["metric"] == "primary_euclidean" and row["shell_scheme"] == PRIMARY_SCHEME
    }
    challenger_radii = {
        row["exact_attack_label"]: {
            "core_radius": float(row["core_radius"]),
            "near_radius": float(row["near_radius"]),
            "uncertain_radius": float(row["uncertain_radius"]),
        }
        for row in radii_rows
        if row["metric"] == "challenger_shrinkage_mahalanobis" and row["shell_scheme"] == PRIMARY_SCHEME
    }
    all_primary_radii = {
        scheme: {
            row["exact_attack_label"]: {
                "core_radius": float(row["core_radius"]),
                "near_radius": float(row["near_radius"]),
                "uncertain_radius": float(row["uncertain_radius"]),
            }
            for row in radii_rows
            if row["metric"] == "primary_euclidean" and row["shell_scheme"] == scheme
        }
        for scheme in SHELL_SCHEMES
    }

    # support_val is the last role allowed to calibrate shells.
    val_x = support_x[val_mask]
    val_rows_meta = [r for i, r in enumerate(support_rows) if val_mask[i]]
    p_val_all = euclidean_distance(val_x, primary_prototypes_np)
    c_val_all = mahalanobis_distance(val_x, challenger_prototypes_np, precision)
    for i, row in enumerate(val_rows_meta):
        true_label = row["exact_attack_label"]
        true_idx = label_to_index[true_label]
        p_nearest = int(np.argmin(p_val_all[i]))
        c_nearest = int(np.argmin(c_val_all[i]))
        support_val_rows.append(
            {
                "sample_id": row["sample_id"],
                "true_attack_label": true_label,
                "primary_nearest_label": labels[p_nearest],
                "primary_nearest_distance": float(p_val_all[i, p_nearest]),
                "primary_true_region_distance": float(p_val_all[i, true_idx]),
                "primary_true_region_shell": shell_name(float(p_val_all[i, true_idx]), primary_radii[true_label]),
                "primary_nearest_shell": shell_name(float(p_val_all[i, p_nearest]), primary_radii[labels[p_nearest]]),
                "challenger_nearest_label": labels[c_nearest],
                "challenger_nearest_distance": float(c_val_all[i, c_nearest]),
                "challenger_true_region_distance": float(c_val_all[i, true_idx]),
                "challenger_true_region_shell": shell_name(float(c_val_all[i, true_idx]), challenger_radii[true_label]),
                "challenger_nearest_shell": shell_name(float(c_val_all[i, c_nearest]), challenger_radii[labels[c_nearest]]),
            }
        )

    shell_sensitivity_rows = []
    for scheme in SHELL_SCHEMES:
        counts = Counter()
        for i, row in enumerate(val_rows_meta):
            true_label = row["exact_attack_label"]
            true_idx = label_to_index[true_label]
            counts[shell_name(float(p_val_all[i, true_idx]), all_primary_radii[scheme][true_label])] += 1
        shell_sensitivity_rows.append(
            {
                "role": "support_val_true_region",
                "shell_scheme": scheme,
                "rows": len(val_rows_meta),
                "core_rate": counts["core"] / len(val_rows_meta),
                "near_rate": counts["near"] / len(val_rows_meta),
                "uncertain_rate": counts["uncertain"] / len(val_rows_meta),
                "out_of_region_rate": counts["out_of_region"] / len(val_rows_meta),
            }
        )

    def audit_benign_role(role: str, allow_status: bool) -> tuple[list[dict], dict[str, Counter], dict]:
        indices = role_indices[role]
        primary_direct = {label: Counter() for label in labels}
        challenger_direct = {label: Counter() for label in labels}
        primary_nearest = {label: Counter() for label in labels}
        challenger_nearest = {label: Counter() for label in labels}
        primary_global = Counter()
        challenger_global = Counter()
        challenger_agree = 0
        total = 0
        scheme_counts = {scheme: Counter() for scheme in SHELL_SCHEMES}
        for start in range(0, len(indices), BATCH):
            raw = np.asarray(cert_x[indices[start : start + BATCH]], dtype=np.float64)
            x = robust_transform(raw, center, scale)
            pd = euclidean_distance(x, primary_prototypes_np)
            cd = mahalanobis_distance(x, challenger_prototypes_np, precision)
            pi = np.argmin(pd, axis=1)
            ci = np.argmin(cd, axis=1)
            challenger_agree += int(np.sum(pi == ci))
            total += len(x)
            for i in range(len(x)):
                primary_label = labels[int(pi[i])]
                challenger_label = labels[int(ci[i])]
                primary_shell = shell_name(float(pd[i, pi[i]]), primary_radii[primary_label])
                challenger_shell = shell_name(float(cd[i, ci[i]]), challenger_radii[challenger_label])
                primary_nearest[primary_label][primary_shell] += 1
                challenger_nearest[challenger_label][challenger_shell] += 1
                primary_global[primary_shell] += 1
                challenger_global[challenger_shell] += 1
                for scheme in SHELL_SCHEMES:
                    scheme_shell = shell_name(float(pd[i, pi[i]]), all_primary_radii[scheme][primary_label])
                    scheme_counts[scheme][scheme_shell] += 1
                for region_idx, label in enumerate(labels):
                    p_direct_shell = shell_name(float(pd[i, region_idx]), primary_radii[label])
                    c_direct_shell = shell_name(float(cd[i, region_idx]), challenger_radii[label])
                    primary_direct[label][p_direct_shell] += 1
                    challenger_direct[label][c_direct_shell] += 1
        rows = []
        for metric, direct_counts, nearest_counts in (
            ("primary_euclidean", primary_direct, primary_nearest),
            ("challenger_shrinkage_mahalanobis", challenger_direct, challenger_nearest),
        ):
            for label in labels:
                counts = direct_counts[label]
                assigned = nearest_counts[label]
                rows.append(
                    {
                        "role": role,
                        "metric": metric,
                        "region_id": geometry[label]["region_id"],
                        "exact_attack_label": label,
                        "nearest_assigned_rows": sum(assigned.values()),
                        "direct_core_rows": counts["core"],
                        "direct_near_rows": counts["near"],
                        "direct_uncertain_rows": counts["uncertain"],
                        "direct_out_of_region_rows": counts["out_of_region"],
                        "direct_core_rate_of_all_role_rows": counts["core"] / total,
                        "direct_core_plus_near_rate_of_all_role_rows": (counts["core"] + counts["near"]) / total,
                        "read_only_role": not allow_status,
                    }
                )
        summary = {
            "role": role,
            "rows": total,
            "primary_core_rows": primary_global["core"],
            "primary_near_rows": primary_global["near"],
            "primary_uncertain_rows": primary_global["uncertain"],
            "primary_out_of_region_rows": primary_global["out_of_region"],
            "challenger_core_rows": challenger_global["core"],
            "challenger_near_rows": challenger_global["near"],
            "challenger_uncertain_rows": challenger_global["uncertain"],
            "challenger_out_of_region_rows": challenger_global["out_of_region"],
            "primary_challenger_nearest_region_agreement": challenger_agree / total,
        }
        for scheme in SHELL_SCHEMES:
            counts = scheme_counts[scheme]
            shell_sensitivity_rows.append(
                {
                    "role": role,
                    "shell_scheme": scheme,
                    "rows": total,
                    "core_rate": counts["core"] / total,
                    "near_rate": counts["near"] / total,
                    "uncertain_rate": counts["uncertain"] / total,
                    "out_of_region_rate": counts["out_of_region"] / total,
                }
            )
        return rows, primary_direct, summary

    ood_val_rows, ood_val_counts, ood_val_summary = audit_benign_role("ood_benign_val", allow_status=True)

    registry_rows = []
    for label in labels:
        train_idx = geometry[label]["train_indices"]
        val_idx = geometry[label]["val_indices"]
        label_val_audit = [r for r in support_val_rows if r["true_attack_label"] == label]
        val_true_coverage = (
            sum(shell_rank(r["primary_true_region_shell"]) <= 2 for r in label_val_audit) / len(label_val_audit)
            if label_val_audit
            else 0.0
        )
        val_label_consistency = (
            sum(r["primary_nearest_label"] == label for r in label_val_audit) / len(label_val_audit)
            if label_val_audit
            else 0.0
        )
        sources = source_count([support_rows[i] for i in train_idx])
        counts = ood_val_counts[label]
        ood_core = counts["core"] / len(role_indices["ood_benign_val"])
        ood_core_near = (counts["core"] + counts["near"]) / len(role_indices["ood_benign_val"])
        minimum_ok = (
            len(train_idx) >= 12
            and len(val_idx) >= 3
            and val_true_coverage >= 0.80
            and val_label_consistency >= 0.80
        )
        if not minimum_ok:
            status = "ambiguous_region"
        elif sources >= 2 and ood_core <= 0.001 and ood_core_near <= 0.01:
            status = "active_strong"
        else:
            status = "active_conflict_sensitive"
        p_train = geometry[label]["primary_train_dist"]
        p_val = geometry[label]["primary_val_dist"]
        registry_rows.append(
            {
                "region_id": geometry[label]["region_id"],
                "exact_attack_label": label,
                "semantic_attack_group": next(r["semantic_attack_group"] for r in support_rows if r["exact_attack_label"] == label),
                "region_construction": "one_medoid_per_exact_label_no_split",
                "metric": "id_benign_robust_scaled_euclidean",
                "shell_scheme": PRIMARY_SCHEME,
                "train_rows": len(train_idx),
                "val_rows": len(val_idx),
                "provenance_source_count": sources,
                "train_distance_median": float(np.median(p_train)),
                "train_distance_q90": float(np.quantile(p_train, 0.90)),
                "val_distance_median": float(np.median(p_val)),
                "val_distance_q90": float(np.quantile(p_val, 0.90)),
                "support_val_true_region_uncertain_coverage": val_true_coverage,
                "support_val_nearest_label_consistency": val_label_consistency,
                "ood_val_core_intrusion_rate": ood_core,
                "ood_val_core_plus_near_intrusion_rate": ood_core_near,
                "region_status": status,
                "status_frozen_before_stress_query": True,
            }
        )

    # Freeze occurs here. Stress and query cannot alter registry_rows or radii.
    ood_stress_rows, _, ood_stress_summary = audit_benign_role("ood_benign_stress", allow_status=False)

    query_rows = []
    sensitivity_rows = []
    certified = [
        r
        for r in read_csv(CERTIFIED_CHUNKS)
        if r["role"] in {"same_file_time_forward_dev_query_exact", "dev_future_attack_query_exact"}
    ]
    query_aggregates: dict[tuple[str, str], Counter] = defaultdict(Counter)
    query_metric_agreement: dict[tuple[str, str], Counter] = defaultdict(Counter)
    query_scheme_counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for chunk in certified:
        chunk_id = int(chunk["chunk_id"])
        role = chunk["role"]
        true_label = chunk["attack_label"]
        raw = np.load(ATTACK_CHUNKS / f"chunk_{chunk_id:05d}_X.npy", mmap_mode="r")
        if len(raw) != int(chunk["emitted_rows"]):
            raise RuntimeError(f"Certified chunk row mismatch: {chunk_id}")
        for start in range(0, len(raw), BATCH):
            x = robust_transform(np.asarray(raw[start : start + BATCH], dtype=np.float64), center, scale)
            pd = euclidean_distance(x, primary_prototypes_np)
            cd = mahalanobis_distance(x, challenger_prototypes_np, precision)
            pi = np.argmin(pd, axis=1)
            ci = np.argmin(cd, axis=1)
            for i in range(len(x)):
                p_label = labels[int(pi[i])]
                c_label = labels[int(ci[i])]
                p_shell = shell_name(float(pd[i, pi[i]]), primary_radii[p_label])
                c_shell = shell_name(float(cd[i, ci[i]]), challenger_radii[c_label])
                agg = query_aggregates[(role, true_label)]
                agg["rows"] += 1
                agg[p_shell] += 1
                agg["label_match"] += int(p_label == true_label)
                agg[f"challenger_{c_shell}"] += 1
                agg["challenger_label_match"] += int(c_label == true_label)
                for scheme in SHELL_SCHEMES:
                    scheme_shell = shell_name(float(pd[i, pi[i]]), all_primary_radii[scheme][p_label])
                    query_scheme_counts[(role, scheme)][scheme_shell] += 1
                sens = query_metric_agreement[(role, true_label)]
                sens["rows"] += 1
                sens["nearest_label_agree"] += int(p_label == c_label)
                sens["shell_agree"] += int(p_shell == c_shell)

    for (role, true_label), counts in sorted(query_aggregates.items()):
        total = counts["rows"]
        query_rows.append(
            {
                "role": role,
                "true_attack_label": true_label,
                "rows": total,
                "core_rows": counts["core"],
                "near_rows": counts["near"],
                "uncertain_rows": counts["uncertain"],
                "out_of_region_rows": counts["out_of_region"],
                "core_rate": counts["core"] / total,
                "near_rate": counts["near"] / total,
                "uncertain_rate": counts["uncertain"] / total,
                "out_of_region_rate": counts["out_of_region"] / total,
                "nearest_region_label_match_rate": counts["label_match"] / total,
                "challenger_core_rate": counts["challenger_core"] / total,
                "challenger_near_rate": counts["challenger_near"] / total,
                "challenger_uncertain_rate": counts["challenger_uncertain"] / total,
                "challenger_out_of_region_rate": counts["challenger_out_of_region"] / total,
                "challenger_nearest_region_label_match_rate": counts["challenger_label_match"] / total,
                "read_only_role": True,
            }
        )
        sens = query_metric_agreement[(role, true_label)]
        sensitivity_rows.append(
            {
                "role": role,
                "true_attack_label": true_label,
                "rows": total,
                "primary_challenger_nearest_label_agreement": sens["nearest_label_agree"] / total,
                "primary_challenger_shell_agreement": sens["shell_agree"] / total,
            }
        )
    for (role, scheme), counts in sorted(query_scheme_counts.items()):
        total = sum(counts.values())
        shell_sensitivity_rows.append(
            {
                "role": role,
                "shell_scheme": scheme,
                "rows": total,
                "core_rate": counts["core"] / total,
                "near_rate": counts["near"] / total,
                "uncertain_rate": counts["uncertain"] / total,
                "out_of_region_rate": counts["out_of_region"] / total,
            }
        )

    support_val_summary_rows = []
    for label in labels:
        rows = [r for r in support_val_rows if r["true_attack_label"] == label]
        support_val_summary_rows.append(
            {
                "exact_attack_label": label,
                "rows": len(rows),
                "primary_nearest_label_consistency": sum(r["primary_nearest_label"] == label for r in rows) / len(rows),
                "primary_true_region_core_rate": sum(r["primary_true_region_shell"] == "core" for r in rows) / len(rows),
                "primary_true_region_core_near_rate": sum(shell_rank(r["primary_true_region_shell"]) <= 1 for r in rows) / len(rows),
                "primary_true_region_uncertain_coverage": sum(shell_rank(r["primary_true_region_shell"]) <= 2 for r in rows) / len(rows),
                "challenger_nearest_label_consistency": sum(r["challenger_nearest_label"] == label for r in rows) / len(rows),
                "primary_challenger_nearest_label_agreement": sum(
                    r["primary_nearest_label"] == r["challenger_nearest_label"] for r in rows
                )
                / len(rows),
            }
        )

    confusion_counts = Counter()
    for row in support_val_rows:
        confusion_counts[(row["true_attack_label"], row["primary_nearest_label"])] += 1
    confusion_rows = [
        {
            "true_attack_label": true_label,
            "nearest_region_label": nearest_label,
            "rows": count,
        }
        for (true_label, nearest_label), count in sorted(confusion_counts.items())
    ]

    feature_dominance_rows = []
    with FEATURE_SCHEMA.open(encoding="utf-8") as f:
        feature_names = json.load(f)["feature_names"]
    for label in labels:
        train_idx = geometry[label]["train_indices"]
        proto = primary_prototypes_np[label_to_index[label]]
        delta2 = np.square(support_x[train_idx] - proto)
        total = np.sum(delta2, axis=1)
        valid = total > EPS
        fractions = np.zeros_like(delta2)
        fractions[valid] = delta2[valid] / total[valid, None]
        mean_fraction = np.mean(fractions, axis=0)
        order = np.argsort(mean_fraction)[::-1][:10]
        sorted_fraction = np.sort(fractions, axis=1)[:, ::-1]
        top1 = sorted_fraction[:, 0]
        top5 = np.sum(sorted_fraction[:, :5], axis=1)
        for rank, feature_idx in enumerate(order, start=1):
            feature_dominance_rows.append(
                {
                    "region_id": geometry[label]["region_id"],
                    "exact_attack_label": label,
                    "rank": rank,
                    "feature_index": int(feature_idx),
                    "feature_name": feature_names[int(feature_idx)],
                    "mean_squared_distance_fraction": float(mean_fraction[feature_idx]),
                    "median_sample_top1_fraction": float(np.median(top1)),
                    "median_sample_top5_fraction": float(np.median(top5)),
                }
            )

    write_csv(
        OUT / "scaler_feature_audit.csv",
        scaler_audit,
        ["feature_index", "center_median", "iqr", "std", "scale", "scale_source"],
    )
    write_csv(
        OUT / "prototype_manifest.csv",
        prototype_rows,
        [
            "region_id",
            "exact_attack_label",
            "metric",
            "prototype_type",
            "sample_id",
            "global_candidate_id",
            "chunk_id",
            "row_index_within_chunk",
            "device_or_source_group",
            "source_file",
            "pcap_path",
            "phase",
            "provenance_hash",
        ],
    )
    write_csv(
        OUT / "shell_candidate_registry.csv",
        radii_rows,
        [
            "region_id",
            "exact_attack_label",
            "metric",
            "shell_scheme",
            "core_radius",
            "near_radius",
            "uncertain_radius",
            "is_preregistered_primary",
        ],
    )
    write_csv(
        OUT / "split_candidate_audit.csv",
        split_rows,
        [
            "region_id",
            "exact_attack_label",
            "train_rows",
            "val_rows",
            "eligible",
            "single_medoid_index_within_label",
            "two_medoid_indices_within_label",
            "train_cluster_counts",
            "val_cluster_counts",
            "within_distance_reduction",
            "source_shortcut_warning",
            "split_candidate",
            "reason",
        ],
    )
    write_csv(
        OUT / "support_val_shell_audit.csv",
        support_val_rows,
        list(support_val_rows[0].keys()),
    )
    write_csv(
        OUT / "support_val_region_summary.csv",
        support_val_summary_rows,
        list(support_val_summary_rows[0].keys()),
    )
    write_csv(
        OUT / "ood_overlap_audit.csv",
        ood_val_rows + ood_stress_rows,
        list((ood_val_rows + ood_stress_rows)[0].keys()),
    )
    write_csv(
        OUT / "certified_dev_query_region_stress.csv",
        query_rows,
        list(query_rows[0].keys()),
    )
    write_csv(
        OUT / "metric_sensitivity_audit.csv",
        sensitivity_rows,
        list(sensitivity_rows[0].keys()),
    )
    write_csv(
        OUT / "shell_scheme_sensitivity.csv",
        shell_sensitivity_rows,
        list(shell_sensitivity_rows[0].keys()),
    )
    write_csv(
        OUT / "support_val_confusion.csv",
        confusion_rows,
        ["true_attack_label", "nearest_region_label", "rows"],
    )
    write_csv(
        OUT / "region_feature_dominance.csv",
        feature_dominance_rows,
        [
            "region_id",
            "exact_attack_label",
            "rank",
            "feature_index",
            "feature_name",
            "mean_squared_distance_fraction",
            "median_sample_top1_fraction",
            "median_sample_top5_fraction",
        ],
    )
    write_csv(
        OUT / "initial_region_registry_v1.csv",
        registry_rows,
        list(registry_rows[0].keys()),
    )

    status_counts = Counter(r["region_status"] for r in registry_rows)
    split_count = sum(str(r.get("split_candidate", "")).lower() == "true" or r.get("split_candidate") is True for r in split_rows)
    query_total = sum(r["rows"] for r in query_rows)
    query_out = sum(r["out_of_region_rows"] for r in query_rows)
    ood_val_nearest_core_rate = ood_val_summary["primary_core_rows"] / ood_val_summary["rows"]
    if status_counts["active_strong"] == 0 or ood_val_nearest_core_rate > 0.10:
        primary_verdict = "initial_region_registry_not_qualified_115d_geometry_confounded"
    else:
        primary_verdict = "initial_region_registry_instantiated_diagnostic_only"
    result = {
        "issue": "issue27cj_attack_region_instantiation_on_frozen_support_bank_2026-06-18",
        "primary_verdict": primary_verdict,
        "roles_accessed_in_order": ROLE_ORDER,
        "model_training": False,
        "formal_benchmark": False,
        "controller_tuning": False,
        "support_reselection": False,
        "sealed_final_access": False,
        "support_train_rows": int(np.sum(train_mask)),
        "support_val_rows": int(np.sum(val_mask)),
        "region_count": len(registry_rows),
        "region_status_counts": dict(status_counts),
        "split_candidates_diagnostic_only": split_count,
        "ood_val_summary": ood_val_summary,
        "ood_stress_summary": ood_stress_summary,
        "certified_dev_query_rows": query_total,
        "certified_dev_query_out_of_region_rate": query_out / query_total,
        "scaler_constant_features": sum(r["scale_source"] == "constant_unit" for r in scaler_audit),
        "scaler_std_fallback_features": sum(r["scale_source"] == "std_fallback" for r in scaler_audit),
        "ledoit_wolf_shrinkage": float(lw.shrinkage_),
        "registry_frozen_before_ood_stress_and_dev_query": True,
    }
    with (OUT / "results.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=True)
        f.write("\n")

    config = {
        "primary_scaler": "id_benign_train_median_iqr_with_std_fallback",
        "primary_distance": "euclidean",
        "challenger_distance": "ledoit_wolf_mahalanobis",
        "prototype": "one_medoid_per_exact_label",
        "primary_shell_scheme": PRIMARY_SCHEME,
        "shell_schemes": SHELL_SCHEMES,
        "split_execution": False,
        "batch_size": BATCH,
    }
    with (OUT / "config.json").open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=True)
        f.write("\n")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
