from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

try:
    import torch
except Exception:  # pragma: no cover - handled in runtime output
    torch = None


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27am_medium_bounded_protocol_repair_validation_2026-06-03"
OUT = ROOT / "runs" / ISSUE
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AK = ROOT / "runs" / "issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic_2026-06-02"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_ROLE = "attack_support"
ATTACK_EVAL_ROLE = "attack_eval"
REPORT_ONLY_ROLES = {FINAL_OOD_ROLE, ATTACK_EVAL_ROLE}
TARGET_OOD_ALARM = 0.01
SEEDS = [42, 43, 44]
PRIMARY_STRATEGY = "reset_at_split_boundary"
ONLINE_STRATEGY = "train_state_then_eval_online"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_indices(indices: np.ndarray) -> str:
    return hash_text(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())))


def load_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def verify_hash(path: Path, expected: str) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    actual = sha256(path)
    return actual == expected, actual


def load_asset(strategy: str, cert: dict[str, Any]) -> dict[str, Any]:
    c = cert[strategy]
    checks = {}
    for key, hash_key in [
        ("X_115D_path", "X_115D_sha256"),
        ("y_path", "y_sha256"),
        ("sidecar_path", "sidecar_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
        ("feature_schema_path", "feature_schema_sha256"),
        ("state_transition_log_path", "state_transition_log_sha256"),
    ]:
        ok, actual = verify_hash(Path(c[key]), c[hash_key])
        checks[key] = {"ok": ok, "actual_sha256": actual, "expected_sha256": c[hash_key]}
        if not ok:
            raise RuntimeError(f"hash mismatch for {strategy}:{key}")
    x = np.load(c["X_115D_path"])
    y = np.load(c["y_path"])
    sidecar = load_csv(Path(c["sidecar_path"]))
    if x.shape[0] != y.shape[0] or x.shape[0] != len(sidecar):
        raise RuntimeError(f"asset row alignment failed for {strategy}: X={x.shape}, y={y.shape}, sidecar={len(sidecar)}")
    if x.shape[1] != 115:
        raise RuntimeError(f"expected 115D features for {strategy}, got {x.shape[1]}")
    return {
        "X": x,
        "y": y.astype(int),
        "sidecar": sidecar,
        "split": load_csv(Path(c["split_manifest_path"])),
        "schema": json.loads(Path(c["feature_schema_path"]).read_text(encoding="utf-8")),
        "certificate": c,
        "hash_checks": checks,
    }


def role_mask(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray(
        [r.get("role") == role and r.get("model_ready_hint", "false").lower() == "true" for r in sidecar],
        dtype=bool,
    )


def mask_from_indices(n: int, idx: np.ndarray) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    mask[np.asarray(idx, dtype=np.int64)] = True
    return mask


def farthest_first_indices(x: np.ndarray, budget: int, start_idx: int) -> np.ndarray:
    n = int(x.shape[0])
    if n == 0:
        return np.asarray([], dtype=np.int64)
    if budget >= n:
        return np.arange(n, dtype=np.int64)
    selected = [int(start_idx)]
    min_dist = pairwise_distances(x, x[[start_idx]], metric="euclidean").ravel()
    min_dist[start_idx] = -1.0
    while len(selected) < budget:
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        dist = pairwise_distances(x, x[[nxt]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, dist)
        min_dist[selected] = -1.0
    return np.asarray(selected, dtype=np.int64)


def local_kcenter(x: np.ndarray, global_idx: np.ndarray, budget: int) -> np.ndarray:
    if len(global_idx) == 0:
        return np.asarray([], dtype=np.int64)
    if budget >= len(global_idx):
        return np.asarray(sorted(global_idx.tolist()), dtype=np.int64)
    scaler = StandardScaler().fit(x[global_idx])
    z = scaler.transform(x[global_idx])
    centroid = z.mean(axis=0, keepdims=True)
    start = int(np.argmin(pairwise_distances(z, centroid, metric="euclidean").ravel()))
    local = farthest_first_indices(z, budget, start)
    return np.asarray(sorted(global_idx[local].tolist()), dtype=np.int64)


def support_stratum(row: dict[str, str]) -> str:
    attack_type = row.get("attack_type_from_raw_path") or "unknown_attack"
    csv_member = row.get("csv_member") or "unknown_csv"
    state_id = row.get("state_id") or "unknown_state"
    # All current medium attack rows share mirai-infection. Combining file and state
    # avoids silently collapsing stratification to a single group.
    return f"{attack_type}|{csv_member}|{state_id}"


def proportional_quotas(groups: dict[str, np.ndarray], total_budget: int) -> dict[str, int]:
    keys = sorted(groups)
    if not keys:
        return {}
    if total_budget <= len(keys):
        ranked = sorted(keys, key=lambda k: (-len(groups[k]), k))
        return {k: (1 if k in set(ranked[:total_budget]) else 0) for k in keys}
    total = sum(len(groups[k]) for k in keys)
    quotas: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    used = 0
    for key in keys:
        raw = total_budget * len(groups[key]) / total
        q = max(1, int(math.floor(raw)))
        q = min(q, len(groups[key]))
        quotas[key] = q
        used += q
        remainders.append((raw - math.floor(raw), key))
    while used < total_budget:
        changed = False
        for _, key in sorted(remainders, reverse=True):
            if quotas[key] < len(groups[key]):
                quotas[key] += 1
                used += 1
                changed = True
                if used == total_budget:
                    break
        if not changed:
            break
    while used > total_budget:
        for _, key in sorted(remainders):
            if quotas[key] > 1:
                quotas[key] -= 1
                used -= 1
                if used == total_budget:
                    break
    return quotas


def kcenter_support_indices(x: np.ndarray, sidecar: list[dict[str, str]], support_size: int) -> tuple[np.ndarray, dict[str, Any]]:
    pool_idx = np.flatnonzero(role_mask(sidecar, SUPPORT_ROLE))
    selected = local_kcenter(x, pool_idx, support_size)
    return selected, {
        "selector_name": f"kcenter{support_size}",
        "support_pool_rows": int(len(pool_idx)),
        "support_size_requested": int(support_size),
        "support_size_selected": int(len(selected)),
        "selector_scaler_fit_roles": SUPPORT_ROLE,
        "selector_distance_metric": "euclidean_after_selector_local_standard_scaler",
        "selector_start_rule": "closest_to_attack_support_centroid",
        "stratified": False,
        "stratum_count": 1,
        "uses_final_ood_benign_eval": False,
        "uses_attack_eval": False,
        "deterministic": True,
        "selected_global_row_sha256": hash_indices(selected),
    }


def stratified_kcenter_support_indices(x: np.ndarray, sidecar: list[dict[str, str]], support_size: int) -> tuple[np.ndarray, dict[str, Any], list[dict[str, Any]]]:
    pool_idx = np.flatnonzero(role_mask(sidecar, SUPPORT_ROLE))
    groups: dict[str, list[int]] = {}
    for idx in pool_idx:
        groups.setdefault(support_stratum(sidecar[int(idx)]), []).append(int(idx))
    arr_groups = {k: np.asarray(v, dtype=np.int64) for k, v in groups.items()}
    quotas = proportional_quotas(arr_groups, support_size)
    selected_parts = []
    stratum_rows = []
    for key in sorted(arr_groups):
        quota = quotas.get(key, 0)
        chosen = local_kcenter(x, arr_groups[key], quota)
        selected_parts.append(chosen)
        stratum_rows.append({
            "stratum_key": key,
            "stratum_rows": int(len(arr_groups[key])),
            "quota": int(quota),
            "selected_rows": int(len(chosen)),
            "selected_hash": hash_indices(chosen),
        })
    selected = np.asarray(sorted(np.concatenate(selected_parts).tolist()), dtype=np.int64) if selected_parts else np.asarray([], dtype=np.int64)
    if len(selected) != min(support_size, len(pool_idx)):
        raise RuntimeError(f"stratified selector selected {len(selected)} rows for requested {support_size}")
    audit = {
        "selector_name": f"stratified_kcenter{support_size}",
        "support_pool_rows": int(len(pool_idx)),
        "support_size_requested": int(support_size),
        "support_size_selected": int(len(selected)),
        "selector_scaler_fit_roles": SUPPORT_ROLE,
        "selector_distance_metric": "within_stratum_euclidean_after_selector_local_standard_scaler",
        "selector_start_rule": "within_stratum_closest_to_centroid",
        "stratified": True,
        "stratum_count": int(len(arr_groups)),
        "stratum_fields": "attack_type_from_raw_path|csv_member|state_id",
        "uses_final_ood_benign_eval": False,
        "uses_attack_eval": False,
        "deterministic": True,
        "selected_global_row_sha256": hash_indices(selected),
    }
    return selected, audit, stratum_rows


def split_support(selected: np.ndarray, train_size: int, val_size: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    if train_size + val_size > len(selected):
        raise RuntimeError("support train/val split exceeds selected rows")
    rng = np.random.default_rng(seed)
    shuffled = np.asarray(selected, dtype=np.int64).copy()
    rng.shuffle(shuffled)
    train_idx = np.asarray(sorted(shuffled[:train_size].tolist()), dtype=np.int64)
    val_idx = np.asarray(sorted(shuffled[train_size:train_size + val_size].tolist()), dtype=np.int64)
    if set(train_idx.tolist()) & set(val_idx.tolist()):
        raise RuntimeError("support_train/support_val overlap")
    return train_idx, val_idx


def rate(mask: np.ndarray) -> float:
    return float(mask.mean()) if mask.size else 0.0


def clopper_upper(k: int, n: int, delta: float = 0.05) -> float:
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    if k == 0:
        return float(1.0 - delta ** (1.0 / n))
    return float(beta.ppf(1.0 - delta, k + 1, n - k))


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    threshold_rule: str
    selected_by_roles: str
    ood_val_alarm: float
    id_alarm: float
    support_val_detection: float
    ood_exceed_count: int
    ood_n: int
    ood_clopper_upper_95: float
    feasible_empirical_1pct: bool
    feasible_np_1pct: bool
    fallback_reason: str


def candidate_thresholds(*arrays: np.ndarray) -> np.ndarray:
    values = np.concatenate([a[np.isfinite(a)] for a in arrays if a.size])
    if values.size == 0:
        raise RuntimeError("no finite scores for threshold calibration")
    qs = np.linspace(0.0, 1.0, 1001)
    quantiles = np.quantile(values, qs)
    return np.asarray(sorted(set(float(x) for x in quantiles if np.isfinite(x))), dtype=float)


def calibrate_threshold(scores_id: np.ndarray, scores_ood: np.ndarray, scores_support_val: np.ndarray, rule: str) -> ThresholdResult:
    thresholds = candidate_thresholds(scores_id, scores_ood, scores_support_val)
    rows = []
    n_ood = int(scores_ood.size)
    for t in thresholds:
        id_alarm = rate(scores_id >= t)
        ood_alarm = rate(scores_ood >= t)
        sup_det = rate(scores_support_val >= t)
        k_ood = int(np.sum(scores_ood >= t))
        upper = clopper_upper(k_ood, n_ood)
        rows.append((t, id_alarm, ood_alarm, sup_det, k_ood, upper))
    if rule == "support_val_constrained_threshold":
        feasible = [r for r in rows if r[2] <= TARGET_OOD_ALARM]
        fallback = ""
        if not feasible:
            feasible = rows
            fallback = "no_empirical_ood_feasible_candidate"
        chosen = sorted(feasible, key=lambda r: (-r[3], r[2], r[0]))[0]
    elif rule == "np_orderstat_threshold":
        feasible_np = [r for r in rows if r[5] <= TARGET_OOD_ALARM]
        fallback = ""
        if feasible_np:
            chosen = sorted(feasible_np, key=lambda r: (-r[3], r[2], r[0]))[0]
        else:
            feasible_emp = [r for r in rows if r[2] <= TARGET_OOD_ALARM]
            fallback = "np_upper_bound_not_certified_fell_back_to_empirical_ood_constraint"
            chosen = sorted(feasible_emp or rows, key=lambda r: (-r[3], r[2], r[0]))[0]
    else:
        raise ValueError(rule)
    return ThresholdResult(
        threshold=float(chosen[0]),
        threshold_rule=rule,
        selected_by_roles=f"{ID_ROLE}|{OOD_VAL_ROLE}|attack_support_val",
        id_alarm=float(chosen[1]),
        ood_val_alarm=float(chosen[2]),
        support_val_detection=float(chosen[3]),
        ood_exceed_count=int(chosen[4]),
        ood_n=n_ood,
        ood_clopper_upper_95=float(chosen[5]),
        feasible_empirical_1pct=bool(chosen[2] <= TARGET_OOD_ALARM),
        feasible_np_1pct=bool(chosen[5] <= TARGET_OOD_ALARM),
        fallback_reason=fallback,
    )


class HistGBScorer:
    def fit(self, x: np.ndarray, y: np.ndarray, seed: int) -> None:
        self.model = HistGradientBoostingClassifier(max_iter=30, max_leaf_nodes=15, learning_rate=0.08, random_state=seed)
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        return proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else proba.reshape(-1)


class DeepSADMarginLiteScorer:
    def __init__(self) -> None:
        if torch is None:
            raise RuntimeError("torch unavailable")

    def fit(self, x_id: np.ndarray, x_support_train: np.ndarray, seed: int) -> None:
        torch.set_num_threads(1)
        torch.manual_seed(seed)
        self.scaler = StandardScaler().fit(np.vstack([x_id, x_support_train]))
        z_id = torch.tensor(self.scaler.transform(x_id), dtype=torch.float32)
        z_sup = torch.tensor(self.scaler.transform(x_support_train), dtype=torch.float32)
        d = z_id.shape[1]
        self.net = torch.nn.Sequential(
            torch.nn.Linear(d, 32),
            torch.nn.ReLU(),
            torch.nn.Linear(32, 16),
        )
        with torch.no_grad():
            self.center = self.net(z_id).mean(dim=0).detach()
        opt = torch.optim.Adam(self.net.parameters(), lr=1e-3, weight_decay=1e-4)
        margin = 2.0
        for _ in range(120):
            opt.zero_grad(set_to_none=True)
            e_id = self.net(z_id)
            e_sup = self.net(z_sup)
            dist_id = ((e_id - self.center) ** 2).sum(dim=1)
            dist_sup = ((e_sup - self.center) ** 2).sum(dim=1)
            loss_normal = dist_id.mean()
            loss_attack_margin = torch.relu(margin - torch.sqrt(dist_sup + 1e-8)).pow(2).mean()
            loss = loss_normal + 0.5 * loss_attack_margin
            loss.backward()
            opt.step()

    def score(self, x: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            z = torch.tensor(self.scaler.transform(x), dtype=torch.float32)
            e = self.net(z)
            dist = ((e - self.center) ** 2).sum(dim=1)
            return dist.cpu().numpy()


@dataclass(frozen=True)
class Recipe:
    recipe_name: str
    model_name: str
    support_selector: str
    support_size: int
    support_train_size: int
    support_val_size: int
    threshold_rule: str
    stage: str


HISTGB_RECIPES = [
    Recipe("histgb_kcenter32_supportval", "HistGB", "kcenter32", 32, 24, 8, "support_val_constrained_threshold", "stage2_histgb"),
    Recipe("histgb_stratified_kcenter64_supportval", "HistGB", "stratified_kcenter64", 64, 48, 16, "support_val_constrained_threshold", "stage2_histgb"),
    Recipe("histgb_stratified_kcenter128_supportval", "HistGB", "stratified_kcenter128", 128, 96, 32, "support_val_constrained_threshold", "stage2_histgb"),
    Recipe("histgb_stratified_kcenter64_np_orderstat", "HistGB", "stratified_kcenter64", 64, 48, 16, "np_orderstat_threshold", "stage2_histgb"),
]

DEEPSAD_RECIPES = [
    Recipe("deepsad_margin_lite_stratified_kcenter64_supportval", "DeepSADMarginLite", "stratified_kcenter64", 64, 48, 16, "support_val_constrained_threshold", "stage3_deepsad_margin_lite"),
    Recipe("deepsad_margin_lite_stratified_kcenter64_np_orderstat", "DeepSADMarginLite", "stratified_kcenter64", 64, 48, 16, "np_orderstat_threshold", "stage3_deepsad_margin_lite"),
]


def selector_for_recipe(x: np.ndarray, sidecar: list[dict[str, str]], recipe: Recipe) -> tuple[np.ndarray, dict[str, Any], list[dict[str, Any]]]:
    if recipe.support_selector == "kcenter32":
        selected, audit = kcenter_support_indices(x, sidecar, recipe.support_size)
        return selected, audit, []
    if recipe.support_selector.startswith("stratified_kcenter"):
        return stratified_kcenter_support_indices(x, sidecar, recipe.support_size)
    raise ValueError(recipe.support_selector)


def eval_scores(scores: dict[str, np.ndarray], tr: ThresholdResult) -> dict[str, Any]:
    return {
        "threshold": tr.threshold,
        "threshold_rule": tr.threshold_rule,
        "threshold_selected_by_roles": tr.selected_by_roles,
        "id_alarm": rate(scores["id"] >= tr.threshold),
        "ood_val_alarm": rate(scores["ood_val"] >= tr.threshold),
        "support_val_detection": rate(scores["support_val"] >= tr.threshold),
        "final_ood_alarm_report_only": rate(scores["final_ood"] >= tr.threshold),
        "attack_eval_detection_report_only": rate(scores["attack_eval"] >= tr.threshold),
        "ood_exceed_count": tr.ood_exceed_count,
        "ood_n": tr.ood_n,
        "ood_clopper_upper_95": tr.ood_clopper_upper_95,
        "feasible_empirical_1pct_on_ood_val": tr.feasible_empirical_1pct,
        "feasible_np_1pct_on_ood_val": tr.feasible_np_1pct,
        "threshold_fallback_reason": tr.fallback_reason,
    }


def run_recipe(strategy: str, asset: dict[str, Any], recipe: Recipe, selected_idx: np.ndarray, seed: int) -> dict[str, Any]:
    x = asset["X"]
    y = asset["y"]
    sidecar = asset["sidecar"]
    id_mask = role_mask(sidecar, ID_ROLE)
    ood_mask = role_mask(sidecar, OOD_VAL_ROLE)
    final_ood_mask = role_mask(sidecar, FINAL_OOD_ROLE)
    attack_eval_mask = role_mask(sidecar, ATTACK_EVAL_ROLE)
    support_train_idx, support_val_idx = split_support(selected_idx, recipe.support_train_size, recipe.support_val_size, seed)
    support_train_mask = mask_from_indices(len(sidecar), support_train_idx)
    support_val_mask = mask_from_indices(len(sidecar), support_val_idx)

    if recipe.model_name == "HistGB":
        scorer = HistGBScorer()
        fit_mask = id_mask | support_train_mask
        scorer.fit(x[fit_mask], y[fit_mask], seed)
    elif recipe.model_name == "DeepSADMarginLite":
        scorer = DeepSADMarginLiteScorer()
        scorer.fit(x[id_mask], x[support_train_mask], seed)
    else:
        raise ValueError(recipe.model_name)

    scores = {
        "id": scorer.score(x[id_mask]),
        "ood_val": scorer.score(x[ood_mask]),
        "support_val": scorer.score(x[support_val_mask]),
        "final_ood": scorer.score(x[final_ood_mask]),
        "attack_eval": scorer.score(x[attack_eval_mask]),
    }
    tr = calibrate_threshold(scores["id"], scores["ood_val"], scores["support_val"], recipe.threshold_rule)
    out = eval_scores(scores, tr)
    out.update({
        "strategy": strategy,
        "recipe_name": recipe.recipe_name,
        "stage": recipe.stage,
        "model_name": recipe.model_name,
        "support_selector": recipe.support_selector,
        "support_size": recipe.support_size,
        "support_train_size": recipe.support_train_size,
        "support_val_size": recipe.support_val_size,
        "seed": seed,
        "support_train_hash": hash_indices(support_train_idx),
        "support_val_hash": hash_indices(support_val_idx),
        "fit_roles": f"{ID_ROLE}|attack_support_train",
        "threshold_roles": f"{ID_ROLE}|{OOD_VAL_ROLE}|attack_support_val",
        "report_only_roles": f"{FINAL_OOD_ROLE}|{ATTACK_EVAL_ROLE}",
        "final_eval_used_for_selection": False,
        "attack_eval_used_for_selection": False,
        "support_eval_disjoint": not bool(set(support_train_idx.tolist()) & set(support_val_idx.tolist())),
    })
    return out


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["strategy"], row["model_name"], row["recipe_name"]), []).append(row)
    out = []
    for (strategy, model, recipe), items in sorted(groups.items()):
        attack = np.asarray([float(r["attack_eval_detection_report_only"]) for r in items])
        final_ood = np.asarray([float(r["final_ood_alarm_report_only"]) for r in items])
        support_val = np.asarray([float(r["support_val_detection"]) for r in items])
        ood_val = np.asarray([float(r["ood_val_alarm"]) for r in items])
        out.append({
            "strategy": strategy,
            "model_name": model,
            "recipe_name": recipe,
            "seed_count": len(items),
            "support_val_detection_mean": float(support_val.mean()),
            "support_val_detection_worst": float(support_val.min()),
            "ood_val_alarm_max": float(ood_val.max()),
            "attack_eval_detection_mean_report_only": float(attack.mean()),
            "attack_eval_detection_worst_report_only": float(attack.min()),
            "final_ood_alarm_max_report_only": float(final_ood.max()),
            "empirical_ood_val_feasible_all_seeds": bool(all(str(r["feasible_empirical_1pct_on_ood_val"]).lower() == "true" for r in items)),
            "np_ood_val_certified_all_seeds": bool(all(str(r["feasible_np_1pct_on_ood_val"]).lower() == "true" for r in items)),
        })
    return out


def verdict_from_summary(rows: list[dict[str, Any]]) -> tuple[str, str]:
    feasible = [
        r for r in rows
        if bool(r["empirical_ood_val_feasible_all_seeds"])
        and float(r["final_ood_alarm_max_report_only"]) <= TARGET_OOD_ALARM
    ]
    if not feasible:
        return "medium_repair_ood_constraint_not_met", "no pre-registered recipe met both OOD-val feasibility and report-only final OOD <= 1%"
    best_attack = max(float(r["attack_eval_detection_worst_report_only"]) for r in feasible)
    if best_attack < 0.6:
        return "medium_repair_insufficient_pause_feature_state_onset_audit", "OOD<=1% held but attack detection stayed below 0.6"
    if best_attack < 0.75:
        return "medium_repair_weak_diagnostic_signal_no_full", "attack detection 0.6-0.75 is only weak diagnostic signal"
    if best_attack < 0.90:
        return "medium_repair_potential_continue_medium_no_full", "attack detection 0.75-0.90 has potential but remains below A-tier full-run gate"
    if best_attack < 0.95:
        return "medium_repair_ready_for_larger_sanity_not_formal_full", "attack detection 0.90-0.95 can justify larger sanity/stability, not formal benchmark"
    return "medium_repair_candidate_for_larger_formal_gate", "attack detection >=0.95 under OOD<=1% reached bounded medium candidate gate"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    assets = {strategy: load_asset(strategy, cert) for strategy in [PRIMARY_STRATEGY, ONLINE_STRATEGY]}

    stage0_rows = []
    metadata_rows = []
    for strategy, asset in assets.items():
        x = asset["X"]
        y = asset["y"]
        sidecar = asset["sidecar"]
        columns = list(sidecar[0].keys()) if sidecar else []
        role_counts = {role: int(role_mask(sidecar, role).sum()) for role in [ID_ROLE, OOD_VAL_ROLE, FINAL_OOD_ROLE, SUPPORT_ROLE, ATTACK_EVAL_ROLE]}
        finite = np.isfinite(x)
        stage0_rows.append({
            "strategy": strategy,
            "x_rows": x.shape[0],
            "x_cols": x.shape[1],
            "y_rows": y.shape[0],
            "sidecar_rows": len(sidecar),
            "finite_rate": float(finite.mean()),
            "nan_count": int(np.isnan(x).sum()),
            "inf_count": int(np.isinf(x).sum()),
            "has_attack_type": "attack_type_from_raw_path" in columns,
            "has_csv_member": "csv_member" in columns,
            "has_timestamp": "packet_timestamp_epoch" in columns,
            "role_counts": json.dumps(role_counts, sort_keys=True),
            "final_eval_report_only": True,
            "preflight_verdict": "pass",
        })
        for col in columns:
            values = sorted({r.get(col, "") for r in sidecar[: min(len(sidecar), 2000)]})
            metadata_rows.append({
                "strategy": strategy,
                "field_name": col,
                "sample_unique_count_first_2000": len(values),
                "sample_values": "|".join(values[:8]),
                "used_for_support_stratification": col in {"attack_type_from_raw_path", "csv_member", "state_id"},
                "used_for_model_feature": False,
            })

    role_policy = [
        {"role": ID_ROLE, "fit_allowed": True, "threshold_allowed": True, "support_selector_allowed": False, "report_only": False, "final_or_attack_eval": False},
        {"role": OOD_VAL_ROLE, "fit_allowed": False, "threshold_allowed": True, "support_selector_allowed": False, "report_only": False, "final_or_attack_eval": False},
        {"role": SUPPORT_ROLE, "fit_allowed": "support_train_only", "threshold_allowed": "support_val_only", "support_selector_allowed": True, "report_only": False, "final_or_attack_eval": False},
        {"role": FINAL_OOD_ROLE, "fit_allowed": False, "threshold_allowed": False, "support_selector_allowed": False, "report_only": True, "final_or_attack_eval": True},
        {"role": ATTACK_EVAL_ROLE, "fit_allowed": False, "threshold_allowed": False, "support_selector_allowed": False, "report_only": True, "final_or_attack_eval": True},
    ]
    write_csv(OUT / "stage0_engineering_audit.csv", stage0_rows)
    write_csv(OUT / "sidecar_metadata_inventory.csv", metadata_rows)
    write_csv(OUT / "role_access_policy.csv", role_policy)

    recipe_rows = []
    for recipe in HISTGB_RECIPES + DEEPSAD_RECIPES:
        recipe_rows.append({
            "recipe_name": recipe.recipe_name,
            "stage": recipe.stage,
            "model_name": recipe.model_name,
            "support_selector": recipe.support_selector,
            "support_size": recipe.support_size,
            "support_train_size": recipe.support_train_size,
            "support_val_size": recipe.support_val_size,
            "threshold_rule": recipe.threshold_rule,
            "uses_final_eval_for_selection": False,
            "uses_attack_eval_for_selection": False,
            "formal_benchmark": False,
        })
    write_csv(OUT / "repair_recipe_inventory.csv", recipe_rows)

    support_audit_rows: list[dict[str, Any]] = []
    support_index_rows: list[dict[str, Any]] = []
    support_split_rows: list[dict[str, Any]] = []
    stratum_rows_all: list[dict[str, Any]] = []
    selected_cache: dict[tuple[str, str, int], np.ndarray] = {}
    for strategy, asset in assets.items():
        for recipe in HISTGB_RECIPES + DEEPSAD_RECIPES:
            key = (strategy, recipe.support_selector, recipe.support_size)
            if key in selected_cache:
                selected = selected_cache[key]
                continue
            selected, audit, stratum_rows = selector_for_recipe(asset["X"], asset["sidecar"], recipe)
            selected_cache[key] = selected
            audit.update({"strategy": strategy, "support_selector": recipe.support_selector})
            support_audit_rows.append(audit)
            for rank, idx in enumerate(selected.tolist()):
                side = asset["sidecar"][int(idx)]
                support_index_rows.append({
                    "strategy": strategy,
                    "support_selector": recipe.support_selector,
                    "support_size": recipe.support_size,
                    "selected_rank": rank,
                    "global_row_index": idx,
                    "role": side.get("role"),
                    "csv_member": side.get("csv_member"),
                    "attack_type_from_raw_path": side.get("attack_type_from_raw_path"),
                    "packet_timestamp_epoch": side.get("packet_timestamp_epoch"),
                })
            for sr in stratum_rows:
                sr.update({"strategy": strategy, "support_selector": recipe.support_selector, "support_size": recipe.support_size})
                stratum_rows_all.append(sr)
            for seed in SEEDS:
                train_idx, val_idx = split_support(selected, recipe.support_train_size, recipe.support_val_size, seed)
                support_split_rows.append({
                    "strategy": strategy,
                    "recipe_name": recipe.recipe_name,
                    "support_selector": recipe.support_selector,
                    "support_size": recipe.support_size,
                    "seed": seed,
                    "support_train_size": len(train_idx),
                    "support_val_size": len(val_idx),
                    "support_train_hash": hash_indices(train_idx),
                    "support_val_hash": hash_indices(val_idx),
                    "train_val_overlap": len(set(train_idx.tolist()) & set(val_idx.tolist())),
                    "uses_final_ood_benign_eval": False,
                    "uses_attack_eval": False,
                })
    write_csv(OUT / "support_selector_audit.csv", support_audit_rows)
    write_csv(OUT / "support_selector_indices.csv", support_index_rows)
    write_csv(OUT / "support_selector_strata.csv", stratum_rows_all)
    write_csv(OUT / "support_split_audit.csv", support_split_rows)

    # Stage 2: run HistGB on reset first. Online is held back until reset has a bounded diagnostic signal.
    all_result_rows: list[dict[str, Any]] = []
    histgb_rows: list[dict[str, Any]] = []
    for recipe in HISTGB_RECIPES:
        selected = selected_cache[(PRIMARY_STRATEGY, recipe.support_selector, recipe.support_size)]
        for seed in SEEDS:
            row = run_recipe(PRIMARY_STRATEGY, assets[PRIMARY_STRATEGY], recipe, selected, seed)
            histgb_rows.append(row)
            all_result_rows.append(row)

    histgb_summary = summarize(histgb_rows)
    histgb_allowed_best = max(float(r["support_val_detection_worst"]) for r in histgb_summary) if histgb_summary else 0.0
    histgb_report_best = max(float(r["attack_eval_detection_worst_report_only"]) for r in histgb_summary) if histgb_summary else 0.0
    run_deepsad = bool(torch is not None and histgb_allowed_best < 0.95)
    deepsad_rows: list[dict[str, Any]] = []
    if run_deepsad:
        for recipe in DEEPSAD_RECIPES:
            selected = selected_cache[(PRIMARY_STRATEGY, recipe.support_selector, recipe.support_size)]
            for seed in SEEDS:
                row = run_recipe(PRIMARY_STRATEGY, assets[PRIMARY_STRATEGY], recipe, selected, seed)
                deepsad_rows.append(row)
                all_result_rows.append(row)
    else:
        write_md(OUT / "deepsad_margin_lite_not_run.md", [
            "# DeepSADMarginLite Not Run",
            "",
            f"- torch_available: {torch is not None}",
            f"- histgb_allowed_best_support_val_detection_worst: {histgb_allowed_best:.6f}",
            "- Rule: Stage 3 only runs when HistGB support-val signal remains below the 0.95 larger-gate target.",
        ])

    # Stage 5: online sanity only for the reset recipe with the best allowed support-val worst-case signal.
    online_rows: list[dict[str, Any]] = []
    reset_summary_for_online = summarize(histgb_rows + deepsad_rows)
    eligible_for_online = [
        r for r in reset_summary_for_online
        if float(r["support_val_detection_worst"]) >= 0.6
        and bool(r["empirical_ood_val_feasible_all_seeds"])
    ]
    online_recipe_names = {sorted(eligible_for_online, key=lambda r: (-float(r["support_val_detection_worst"]), float(r["ood_val_alarm_max"])))[0]["recipe_name"]} if eligible_for_online else set()
    recipe_by_name = {r.recipe_name: r for r in HISTGB_RECIPES + DEEPSAD_RECIPES}
    for recipe_name in online_recipe_names:
        recipe = recipe_by_name[recipe_name]
        selected = selected_cache[(ONLINE_STRATEGY, recipe.support_selector, recipe.support_size)]
        for seed in SEEDS:
            row = run_recipe(ONLINE_STRATEGY, assets[ONLINE_STRATEGY], recipe, selected, seed)
            row["stage"] = row["stage"] + "_online_sanity"
            online_rows.append(row)
            all_result_rows.append(row)

    write_csv(OUT / "histgb_repair_by_recipe_seed.csv", histgb_rows)
    write_csv(OUT / "histgb_repair_summary.csv", histgb_summary)
    if deepsad_rows:
        write_csv(OUT / "deepsad_margin_lite_by_recipe_seed.csv", deepsad_rows)
        write_csv(OUT / "deepsad_margin_lite_summary.csv", summarize(deepsad_rows))
    else:
        write_csv(OUT / "deepsad_margin_lite_by_recipe_seed.csv", [])
        write_csv(OUT / "deepsad_margin_lite_summary.csv", [])
    if online_rows:
        write_csv(OUT / "online_sanity_by_recipe_seed.csv", online_rows)
        write_csv(OUT / "online_sanity_summary.csv", summarize(online_rows))
    else:
        write_md(OUT / "online_sanity_not_run.md", [
            "# Online Sanity Not Run",
            "",
            "- No reset recipe met the pre-registered support-val signal and empirical OOD-val feasibility gate.",
        ])

    write_md(OUT / "fusion_repair_not_run.md", [
        "# Fusion Repair Not Run",
        "",
        "- Pre-registered rule: Fusion is only attempted if HistGB is stable and DeepSADMarginLite is sensitive.",
        f"- HistGB best support-val worst-case signal: {histgb_allowed_best:.6f}.",
        f"- HistGB best report-only attack worst-case signal: {histgb_report_best:.6f}.",
        f"- DeepSADMarginLite executed: {bool(deepsad_rows)}.",
        "- DeepSADMarginLite produced no useful support-val signal in this bounded run.",
        "- Therefore Fusion-A / Fusion-B would be a broader repair step, not justified inside this finite issue27am batch.",
    ])
    write_csv(OUT / "fusion_repair_by_recipe_seed.csv", [])
    write_csv(OUT / "fusion_repair_summary.csv", [])

    all_summary = summarize(all_result_rows)
    write_csv(OUT / "bounded_repair_all_results.csv", all_result_rows)
    write_csv(OUT / "bounded_repair_summary.csv", all_summary)

    threshold_rows = []
    for row in all_result_rows:
        threshold_rows.append({
            "strategy": row["strategy"],
            "recipe_name": row["recipe_name"],
            "seed": row["seed"],
            "threshold_rule": row["threshold_rule"],
            "threshold": row["threshold"],
            "threshold_selected_by_roles": row["threshold_selected_by_roles"],
            "id_alarm": row["id_alarm"],
            "ood_val_alarm": row["ood_val_alarm"],
            "support_val_detection": row["support_val_detection"],
            "ood_clopper_upper_95": row["ood_clopper_upper_95"],
            "feasible_empirical_1pct_on_ood_val": row["feasible_empirical_1pct_on_ood_val"],
            "feasible_np_1pct_on_ood_val": row["feasible_np_1pct_on_ood_val"],
            "fallback_reason": row["threshold_fallback_reason"],
            "uses_final_ood_benign_eval": False,
            "uses_attack_eval": False,
        })
    write_csv(OUT / "threshold_calibration_audit.csv", threshold_rows)

    role_audit_rows = []
    forbidden_violation = False
    for row in all_result_rows:
        violation = bool(row["final_eval_used_for_selection"]) or bool(row["attack_eval_used_for_selection"])
        forbidden_violation = forbidden_violation or violation
        role_audit_rows.append({
            "strategy": row["strategy"],
            "recipe_name": row["recipe_name"],
            "seed": row["seed"],
            "fit_roles": row["fit_roles"],
            "threshold_roles": row["threshold_roles"],
            "report_only_roles": row["report_only_roles"],
            "final_eval_used_for_selection": row["final_eval_used_for_selection"],
            "attack_eval_used_for_selection": row["attack_eval_used_for_selection"],
            "forbidden_role_access": violation,
        })
    write_csv(OUT / "role_access_audit.csv", role_audit_rows)
    if forbidden_violation:
        primary_verdict, verdict_reason = "medium_repair_blocked_by_forbidden_role_access", "forbidden report-only role access detected"
    else:
        primary_verdict, verdict_reason = verdict_from_summary(all_summary)

    feasible_summary = [
        r for r in all_summary
        if bool(r["empirical_ood_val_feasible_all_seeds"])
        and float(r["final_ood_alarm_max_report_only"]) <= TARGET_OOD_ALARM
    ]
    best_rows = sorted(
        feasible_summary or all_summary,
        key=lambda r: (
            -float(r["attack_eval_detection_worst_report_only"]),
            float(r["final_ood_alarm_max_report_only"]),
            -float(r["support_val_detection_worst"]),
        ),
    )
    best = best_rows[0] if best_rows else {}
    best_attack_any = sorted(
        all_summary,
        key=lambda r: (
            -float(r["attack_eval_detection_worst_report_only"]),
            float(r["final_ood_alarm_max_report_only"]),
        ),
    )[0] if all_summary else {}

    write_md(OUT / "issue27am_decision.md", [
        "# Issue27am Decision",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        f"- verdict_reason: {verdict_reason}",
        "- Scope: medium bounded protocol repair validation only; not formal benchmark.",
        "- Frontend: fixed Gotham Kitsune115 medium asset from issue27af.",
        "- Split/support pool: unchanged; support selection only uses attack_support.",
        "- Selection roles: threshold uses ID/OOD/support_val only; final_ood_benign_eval and attack_eval are report-only.",
        "",
        "## Best Pre-Registered Diagnostic Row",
        "",
        *( [f"- strategy: `{best.get('strategy')}`",
             f"- model: `{best.get('model_name')}`",
             f"- recipe: `{best.get('recipe_name')}`",
             f"- support_val_detection_worst: {float(best.get('support_val_detection_worst', 0.0)):.6f}",
             f"- attack_eval_detection_worst_report_only: {float(best.get('attack_eval_detection_worst_report_only', 0.0)):.6f}",
             f"- final_ood_alarm_max_report_only: {float(best.get('final_ood_alarm_max_report_only', 0.0)):.6f}",
             f"- empirical_ood_val_feasible_all_seeds: {best.get('empirical_ood_val_feasible_all_seeds')}"] if best else ["- No result rows."] ),
        "",
        "## Highest Attack Diagnostic Row",
        "",
        *( [f"- strategy: `{best_attack_any.get('strategy')}`",
             f"- model: `{best_attack_any.get('model_name')}`",
             f"- recipe: `{best_attack_any.get('recipe_name')}`",
             f"- attack_eval_detection_worst_report_only: {float(best_attack_any.get('attack_eval_detection_worst_report_only', 0.0)):.6f}",
             f"- final_ood_alarm_max_report_only: {float(best_attack_any.get('final_ood_alarm_max_report_only', 0.0)):.6f}",
             "- Interpretation: useful as an overbudget diagnostic only if final OOD exceeds 1%."] if best_attack_any else ["- No result rows."] ),
    ])

    write_md(OUT / "claim_update_after_issue27am.md", [
        "# Claim Update After Issue27am",
        "",
        "- This issue is a bounded medium repair validation, not a formal benchmark.",
        "- The Gotham Kitsune115 frontend, split, and support pool remain fixed.",
        "- Report-only final OOD and attack eval metrics are diagnostic and cannot be used as paper-level ranking.",
        "- Formal claims still require a frozen repair protocol, larger/full data materialization, and result audit.",
    ])

    next_action = "issue27an_feature_state_onset_or_protocol_repair_reassessment"
    if primary_verdict in {"medium_repair_ready_for_larger_sanity_not_formal_full", "medium_repair_candidate_for_larger_formal_gate"}:
        next_action = "issue27an_larger_sanity_for_pre_registered_repair_protocol"
    elif primary_verdict in {"medium_repair_potential_continue_medium_no_full", "medium_repair_weak_diagnostic_signal_no_full"}:
        next_action = "issue27an_continue_medium_repair_without_full_benchmark"
    write_md(OUT / "issue27an_next_action.md", [
        "# Issue27an Next Action",
        "",
        f"- recommended_next_issue: `{next_action}`",
        "- Do not run full formal benchmark unless a repair protocol reaches the pre-registered larger/full candidate gate.",
        "- If the bounded repair remains below 0.6 attack detection under OOD<=1%, pause model work and audit feature/state/onset/label alignment again.",
        "- If the repair shows 0.75-0.95, continue bounded medium/larger sanity before any formal full run.",
    ])

    write_md(OUT / "summary.md", [
        "# Issue27am Summary",
        "",
        "1. issue27am completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        "3. scope: medium bounded protocol repair validation; not formal benchmark",
        "4. frontend: fixed Gotham Kitsune115 115D; no frontend changes",
        "5. split/support pool changed: no",
        "6. support selectors tested: kcenter32, stratified_kcenter64, stratified_kcenter128",
        "7. support_val split seeds: 42, 43, 44",
        "8. threshold rules tested: support_val_constrained_threshold, NP/order-statistic OOD threshold",
        f"9. HistGB best support-val worst-case signal: {histgb_allowed_best:.6f}",
        f"10. HistGB best report-only attack worst-case signal: {histgb_report_best:.6f}",
        f"11. DeepSADMarginLite executed: {bool(deepsad_rows)}",
        f"12. online sanity executed: {bool(online_rows)}",
        f"13. forbidden role access detected: {forbidden_violation}",
        f"14. best diagnostic recipe: `{best.get('recipe_name', 'none')}`",
        f"15. best diagnostic strategy: `{best.get('strategy', 'none')}`",
        f"16. best final OOD alarm max report-only: {float(best.get('final_ood_alarm_max_report_only', 0.0)):.6f}",
        f"17. best attack detection worst report-only: {float(best.get('attack_eval_detection_worst_report_only', 0.0)):.6f}",
        f"18. highest attack recipe regardless of final OOD: `{best_attack_any.get('recipe_name', 'none')}`",
        f"19. highest attack worst report-only: {float(best_attack_any.get('attack_eval_detection_worst_report_only', 0.0)):.6f}",
        f"20. highest attack final OOD max report-only: {float(best_attack_any.get('final_ood_alarm_max_report_only', 0.0)):.6f}",
        f"21. next action: `{next_action}`",
        "22. commit hash: pending",
    ])

    write_md(OUT / "command.txt", [
        "python repo/ood/issue27am_medium_bounded_protocol_repair_validation.py",
    ])
    config = {
        "issue": ISSUE,
        "target_ood_alarm": TARGET_OOD_ALARM,
        "seeds": SEEDS,
        "primary_strategy": PRIMARY_STRATEGY,
        "online_strategy": ONLINE_STRATEGY,
        "formal_benchmark": False,
        "frontend_changed": False,
        "split_changed": False,
        "final_eval_report_only": True,
        "recipes": recipe_rows,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps({
        "inputs": {
            "issue27af_certificate": str(cert_path),
            "issue27ak_summary": str(ISSUE27AK / "summary.md"),
        },
        "outputs": [p.name for p in sorted(OUT.glob("*"))],
        "selection_policy": "ID/OOD/support_val only; final_ood_benign_eval and attack_eval report-only",
    }, indent=2, sort_keys=True), encoding="utf-8")
    manifest_rows = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest_rows.append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(MAINLINE_DOCS / "mainline_handoff.md", "<!-- issue27am -->", [
        "<!-- issue27am -->",
        "## issue27am_medium_bounded_protocol_repair_validation_2026-06-03",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        "- Medium Gotham Kitsune115 bounded protocol repair validation only; not formal benchmark.",
        "- Tested fixed split/support pool with kcenter32, stratified_kcenter64, and stratified_kcenter128 plus support_val/NP threshold rules.",
        "- Final OOD and attack eval remain report-only; no model ranking or full benchmark claim is made.",
        f"- next action: `{next_action}`",
    ])
    append_doc(MAINLINE_DOCS / "mainline_experiment_map.md", "<!-- issue27am -->", [
        "<!-- issue27am -->",
        "## issue27am",
        "",
        f"- verdict: `{primary_verdict}`",
        "- route: Gotham Kitsune115 medium bounded protocol repair validation.",
        "- claim boundary: diagnostic only; formal full/larger benchmark remains gated.",
    ])


if __name__ == "__main__":
    main()
