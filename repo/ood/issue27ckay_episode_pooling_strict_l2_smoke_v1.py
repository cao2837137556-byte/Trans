"""CKAY: strict L2 test of within-role episode pooling over CKAW evidence.

The CKAW cache is packet-aligned, but deployment review and response happen at
an event/episode level.  This probe tests whether a fixed, label-free 60-second
source episode representation changes the held-family failure mode.  Crucially,
an episode is pooled *within each data role only*: report/query rows can never
change a fit or select representation.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckaw_canonical_interaction_episode_frontend_v1 as ckaw  # noqa: E402
import issue27ckax_episode_head_strict_l2_smoke_v1 as ckax  # noqa: E402


ISSUE = "issue27ckay_episode_pooling_strict_l2_smoke_v1_2026-07-11"
ROOT = cko.ROOT
DEFAULT_CACHE = ROOT / "runs" / "issue27ckaw_canonical_interaction_episode_frontend_v1_2026-07-10_local_150k"
HELD = [
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "domotic-monitor",
    "combined-cycle",
    "iotsim-ip-camera-street",
]
EVAL = {
    "ood_val": "select",
    "ood_stress": "select",
    "future_query": "select",
    "sealed_final_ood": "all",
    "sealed_final_attack": "all",
}


class Cache:
    """Immutable CKAW cache with the separately written label-free episode id."""

    def __init__(self, root: Path, plan_path: str = ""):
        plan = pd.read_csv(Path(plan_path) if plan_path else root / "episode_source_plan.csv")
        self.plan = {str(r.source_group): str(r.source_cache_key) for r in plan.itertuples()}
        self.root = root / "canonical_episode_cache"
        self.data: dict[str, dict[int, tuple[np.ndarray, str]]] = {}

    def get(self, source: str, index: int) -> tuple[np.ndarray, str] | None:
        if source not in self.plan:
            return None
        if source not in self.data:
            key = self.plan[source]
            npz = np.load(self.root / f"{key}.npz")
            audit = json.loads((self.root / f"{key}.json").read_text(encoding="utf-8"))["target_audit"]
            episode = {int(row["recorded_index"]): str(row.get("episode_id", "")) for row in audit}
            self.data[source] = {
                int(index): (npz["features"][pos], episode.get(int(index), ""))
                for pos, index in enumerate(npz["recorded_index"])
            }
        return self.data[source].get(int(index))


def pooled_rows(
    cache: Cache,
    frames: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    held: str,
    include_held: bool,
    cap: int,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Return stable episode vectors, never pooling across data-role boundaries."""
    idx = ckao.role_indices_filtered(
        frames,
        role,
        phase,
        cap,
        include=("device_family", held) if include_held else None,
        exclude=None if include_held else ("device_family", held),
    )
    bucket: dict[str, list[np.ndarray]] = {}
    members: dict[str, list[int]] = {}
    for raw_index in idx:
        row = frames[role].iloc[int(raw_index)]
        source = str(row.get("source_group", ""))
        record = cache.get(source, int(row.get("recorded_index", -1)))
        if record is None:
            continue
        feature, episode_id = record
        # A missing id cannot merge rows: it remains a singleton and is auditable.
        key = episode_id or f"singleton:{source}:{int(raw_index)}"
        bucket.setdefault(key, []).append(np.asarray(feature, dtype=np.float32))
        members.setdefault(key, []).append(int(raw_index))
    vectors: list[np.ndarray] = []
    audit_rows: list[dict[str, object]] = []
    for episode_id in sorted(bucket):
        matrix = np.vstack(bucket[episode_id]).astype(np.float32)
        # Mean captures stable mechanism evidence; max retains short bursts; log n
        # prevents a long benign episode from being silently treated as one packet.
        vector = np.concatenate(
            [matrix.mean(axis=0), matrix.max(axis=0), matrix.std(axis=0), np.array([np.log1p(len(matrix))], dtype=np.float32)]
        ).astype(np.float32)
        vectors.append(vector)
        audit_rows.append(
            {
                "role": role,
                "phase": phase,
                "held_value": held,
                "include_held": bool(include_held),
                "episode_id": episode_id,
                "member_rows": len(matrix),
                "first_frame_index": min(members[episode_id]),
                "last_frame_index": max(members[episode_id]),
            }
        )
    return (
        np.asarray([row["first_frame_index"] for row in audit_rows], dtype=np.int64),
        np.vstack(vectors).astype(np.float32) if vectors else np.zeros((0, len(ckaw.FEATURE_NAMES) * 3 + 1), dtype=np.float32),
        pd.DataFrame(audit_rows),
    )


def zscore(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.nan_to_num((x - mean) / std, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def probability(model: object, x: np.ndarray, kind: str) -> np.ndarray:
    if kind == "histgb":
        return model.predict_proba(x)[:, 1]
    return ckax.score(model, x, "mlp")


def run(args: argparse.Namespace) -> None:
    out = ROOT / "runs" / (ISSUE if not args.run_tag else f"{ISSUE}_{args.run_tag}")
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    cache = Cache(Path(args.cache_root), args.plan_path)
    _, frames, _, _ = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    metrics: list[dict[str, object]] = []
    episode_audit: list[pd.DataFrame] = []
    train_audit: list[dict[str, object]] = []

    for held in [value.strip() for value in args.held_values.split(",") if value.strip()]:
        parts: list[np.ndarray] = []
        labels: list[np.ndarray] = []
        for role, label in (("support_train", 1), ("id_calib", 0), ("ood_val", 0), ("ood_stress", 0)):
            _, vector, audit = pooled_rows(
                cache, frames, role, "fit", held, False,
                args.train_cap if role != "support_train" else cko.FULL_CAP,
            )
            episode_audit.append(audit)
            parts.append(vector)
            labels.append(np.full(len(vector), label, dtype=np.int64))
            train_audit.append({"held_value": held, "role": role, "phase": "fit", "episodes": len(vector), "label_for_model": label})
        valid = [i for i, values in enumerate(parts) if len(values)]
        if not valid:
            raise RuntimeError(f"{held}: no legal fit episodes in cache")
        x_fit = np.vstack([parts[i] for i in valid])
        y_fit = np.concatenate([labels[i] for i in valid])
        mean, std = x_fit.mean(axis=0), x_fit.std(axis=0)
        std[std < 1e-6] = 1.0
        x_fit = zscore(x_fit, mean, std)
        available: dict[str, object] = {
            "episode_pool_histgb": HistGradientBoostingClassifier(max_iter=180, max_leaf_nodes=31, l2_regularization=1.0).fit(x_fit, y_fit),
            "episode_pool_mlp": ckax.fit_mlp(x_fit, y_fit),
        }
        candidates = {name: model for name, model in available.items() if name in set(args.candidates.split(","))}
        if not candidates:
            raise RuntimeError("no candidate selected")

        select_parts: list[np.ndarray] = []
        for role in ("id_calib", "ood_val", "ood_stress"):
            _, vector, audit = pooled_rows(cache, frames, role, "select", held, False, args.eval_cap)
            episode_audit.append(audit)
            if len(vector):
                select_parts.append(zscore(vector, mean, std))
        if not select_parts:
            raise RuntimeError(f"{held}: no legal select episodes")

        for name, model in candidates.items():
            kind = name.rsplit("_", 1)[1]
            threshold = float(np.quantile(np.concatenate([probability(model, values, kind) for values in select_parts]), 0.99))
            for role, phase in EVAL.items():
                _, vector, audit = pooled_rows(cache, frames, role, phase, held, True, args.eval_cap)
                episode_audit.append(audit)
                scores = probability(model, zscore(vector, mean, std), kind) if len(vector) else np.asarray([])
                metrics.append(
                    {
                        "candidate": name,
                        "held_value": held,
                        "role": role,
                        "episodes": int(len(scores)),
                        "hard_alarm_rate": float(np.mean(scores >= threshold)) if len(scores) else np.nan,
                        "mean_attack_score": float(np.mean(scores)) if len(scores) else np.nan,
                        "threshold": threshold,
                        "review_rate": 0.0,
                        "report_only": role.startswith("sealed") or role == "future_query",
                    }
                )

    pd.DataFrame(metrics).to_csv(out / "metrics.csv", index=False)
    pd.DataFrame(train_audit).to_csv(out / "train_audit.csv", index=False)
    pd.concat(episode_audit, ignore_index=True).to_csv(out / "episode_membership_audit.csv", index=False)
    lines = [f"# {ISSUE}", "", "Strict leave-family, role-isolated episode pooling. P0 hard-only (review=0).", "", "| candidate | held | role | episodes | hard | mean score |", "|---|---|---|---:|---:|---:|"]
    for row in metrics:
        lines.append(f"| {row['candidate']} | {row['held_value']} | {row['role']} | {row['episodes']} | {row['hard_alarm_rate']:.4f} | {row['mean_attack_score']:.4f} |")
    (out / "codex_readout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "run_spec.json").write_text(json.dumps({
        "issue": ISSUE,
        "cache_root": str(args.cache_root),
        "held_values": args.held_values,
        "train_cap": args.train_cap,
        "eval_cap": args.eval_cap,
        "frontend_label_free": True,
        "episode_pool_role_isolated": True,
        "report_used_for_fit_or_threshold": False,
        "seconds": time.time() - started,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), "metric_rows": len(metrics)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", default=str(DEFAULT_CACHE))
    parser.add_argument("--plan-path", default="")
    parser.add_argument("--held-values", default=",".join(HELD))
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--candidates", default="episode_pool_histgb,episode_pool_mlp")
    parser.add_argument("--run-tag", default="local_150k")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
