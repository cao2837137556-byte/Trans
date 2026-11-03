"""CKBG: small, non-selecting M1 TGN canary using maintained PyG components.

This is not the formal M1 result.  It validates the M1 execution path only:
official ``TGNMemory`` reads a target before updating on that event, resets for
each source, receives fit-only self-supervision, and keeps attack support as
individual packet losses.  C1 is fitted through the existing CKAO path and is
an input to the verifier head, but no threshold, hard-rate, or model selection
is produced here.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric import __version__ as PYG_VERSION
from torch_geometric.nn.models.tgn import IdentityMessage, LastAggregator, TGNMemory

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckbd_tgn_event_contract_audit_v1 as ckbd  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckat_canonical_time_c1_canary_v1 as ckat  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import T0Cache  # noqa: E402


ISSUE = "issue27ckbg_tgn_m1_canary_v1_2026-07-12"
ROOT = cko.ROOT
DEFAULT_T0 = ROOT / "runs" / "issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
DEFAULT_C1_PLAN = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "canonical_source_load_plan.csv"
DEFAULT_C1_CACHE = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "hpc_canonical_c1_cache"
FIT_BENIGN = (("id_calib", "fit"), ("ood_val", "fit"), ("ood_stress", "fit"))


def c1_candidate() -> ckai.Candidate:
    return next(value for value in ckai.CANDIDATES if value.name == "C1_cicflow_style_only_histgb")


class Heads(nn.Module):
    """Small task heads; TGN memory and time encoding remain PyG-owned."""

    def __init__(self, memory_dim: int, message_dim: int):
        super().__init__()
        self.link = nn.Sequential(nn.Linear(memory_dim * 2 + message_dim, 64), nn.GELU(), nn.Linear(64, 1))
        self.verifier = nn.Sequential(nn.Linear(memory_dim * 2 + message_dim + 1, 64), nn.GELU(), nn.Linear(64, 1))

    def link_logit(self, src_memory: torch.Tensor, dst_memory: torch.Tensor, msg: torch.Tensor) -> torch.Tensor:
        return self.link(torch.cat([src_memory, dst_memory, msg], dim=1)).reshape(-1)

    def verifier_logit(self, src_memory: torch.Tensor, dst_memory: torch.Tensor, msg: torch.Tensor, c1: float) -> torch.Tensor:
        anchor = torch.full((1, 1), float(c1), dtype=msg.dtype, device=msg.device)
        return self.verifier(torch.cat([src_memory, dst_memory, msg, anchor], dim=1)).reshape(-1)


def make_memory(capacity: int, message_dim: int = 9, memory_dim: int = 32, time_dim: int = 16) -> TGNMemory:
    memory = TGNMemory(
        num_nodes=max(2, int(capacity)), raw_msg_dim=message_dim, memory_dim=memory_dim, time_dim=time_dim,
        message_module=IdentityMessage(message_dim, memory_dim, time_dim), aggregator_module=LastAggregator(),
    )
    memory.train()
    return memory


def legal_indices(frames: dict[str, pd.DataFrame], role: str, phase: str, held: str, cap: int) -> np.ndarray:
    return ckao.role_indices_filtered(frames, role, phase, cap, exclude=("device_family", held))


def fit_c1(
    x_by_role: dict[str, np.ndarray], frames: dict[str, pd.DataFrame], held: str, c1_cache: Path, c1_plan: Path, train_cap: int,
) -> tuple[Any, ckai.ExternalFlowFrontend, list[dict[str, Any]]]:
    cache = ckat.PersistentCanonicalTimeC1Cache(c1_cache, c1_plan)
    frontend = ckai.ExternalFlowFrontend(x_by_role, frames, cache)
    model, audit = ckao.fit_candidate(c1_candidate(), frontend, frames, held, train_cap)
    return model, frontend, audit


def score_records(
    model: Any, frontend: ckai.ExternalFlowFrontend, frames: dict[str, pd.DataFrame], held: str, train_cap: int,
) -> list[dict[str, Any]]:
    """Score only legal fit rows; report/select roles never enter the canary."""
    rows: list[dict[str, Any]] = []
    tasks = [("support_train", "fit", 1)] + [(role, phase, 0) for role, phase in FIT_BENIGN]
    for role, phase, target in tasks:
        cap = cko.FULL_CAP if role == "support_train" else int(train_cap)
        idx = legal_indices(frames, role, phase, held, cap)
        values = ckai.score_attack(model, frontend.matrix(c1_candidate(), role, idx))
        part = frames[role].iloc[idx].copy().reset_index(drop=True)
        for pos, row in part.iterrows():
            rows.append({
                "role": role,
                "phase": phase,
                "source_group": str(row["source_group"]),
                "recorded_index": int(row["recorded_index"]),
                "target": int(target),
                "attack_family": str(row.get("attack_label", "")) if target else "benign",
                "c1_attack_score": float(values[pos]),
                "device_family": str(row.get("device_family", "NA")),
            })
    return rows


def choose_canary(records: list[dict[str, Any]], cache: T0Cache, max_events: int, per_family: int, benign_cap: int) -> list[dict[str, Any]]:
    positions: dict[str, dict[int, int]] = {}
    selected: list[dict[str, Any]] = []
    attack_counts: Counter[str] = Counter()
    benign_count = 0
    for row in sorted(records, key=lambda value: (value["target"], value["attack_family"], value["source_group"], value["recorded_index"])):
        source = str(row["source_group"])
        if source not in positions:
            positions[source] = cache.target_positions(source)
        event_position = positions[source].get(int(row["recorded_index"]), -1)
        if event_position < 0 or event_position >= int(max_events):
            continue
        family = str(row["attack_family"])
        if int(row["target"]) == 1:
            if attack_counts[family] >= int(per_family):
                continue
            attack_counts[family] += 1
        else:
            if benign_count >= int(benign_cap):
                continue
            benign_count += 1
        selected.append({**row, "event_position": int(event_position)})
    expected = sorted({str(row["attack_family"]) for row in records if int(row["target"]) == 1})
    missing = [family for family in expected if attack_counts[family] == 0]
    if missing:
        raise RuntimeError(f"canary event cap excludes support families: {missing}; raise --max-events-per-source or stop")
    if not benign_count:
        raise RuntimeError("canary has no legal benign fit targets")
    return selected


def blocked_event_positions(frames: dict[str, pd.DataFrame], held: str) -> dict[str, set[int]]:
    """Select/report target events cannot update fit-time memory either."""
    blocked: defaultdict[str, set[int]] = defaultdict(set)
    for role, frame in frames.items():
        part = frame.loc[frame["phase"].astype(str).ne("fit")]
        part = part.loc[part["device_family"].astype(str).ne(held)]
        for row in part.itertuples():
            blocked[str(row.source_group)].add(int(row.recorded_index))
    return dict(blocked)


def train_canary(
    cache: T0Cache,
    records: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    blocked: dict[str, set[int]],
    max_events: int,
    epochs: int,
    detach_every: int,
    seed: int,
) -> tuple[TGNMemory, Heads, dict[str, Any], list[dict[str, Any]]]:
    torch.manual_seed(int(seed))
    np.random.seed(int(seed))
    per_source: defaultdict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    fit_events: defaultdict[str, set[int]] = defaultdict(set)
    family_counts = Counter(row["attack_family"] for row in selected if int(row["target"]) == 1)
    for row in records:
        fit_events[str(row["source_group"])].add(int(row["recorded_index"]))
    for row in selected:
        per_source[str(row["source_group"])][int(row["recorded_index"])] = row
    memory = make_memory(capacity=2 * int(max_events) + 2)
    heads = Heads(memory_dim=32, message_dim=9)
    optimizer = torch.optim.AdamW(list(memory.parameters()) + list(heads.parameters()), lr=1.5e-3, weight_decay=1e-3)
    history: list[dict[str, Any]] = []
    reset_count = 0
    total_supervised = 0
    total_negative = 0
    for epoch in range(int(epochs)):
        epoch_link: list[float] = []
        epoch_supervised: list[float] = []
        optimizer.zero_grad()
        pending: list[torch.Tensor] = []
        for source in sorted(per_source):
            npz, _meta = cache.paths(source)
            with np.load(npz, allow_pickle=False) as data:
                count = min(int(len(data["time_ms"])), int(max_events))
                recorded = data["recorded_index"][:count]
                stamp, src, dst, message = data["time_ms"][:count], data["src"][:count], data["dst"][:count], data["raw_msg"][:count]
            memory.reset_state()
            reset_count += 1
            seen: set[tuple[int, int]] = set()
            lookup = per_source[source]
            for index in range(count):
                left, right = int(src[index]), int(dst[index])
                msg = torch.from_numpy(message[index : index + 1])
                time = torch.tensor([int(stamp[index])], dtype=torch.long)
                pair = torch.tensor([left, right], dtype=torch.long)
                representation, _last = memory(pair)  # Read strictly before update_state.
                left_memory, right_memory = representation[0:1], representation[1:2]
                recorded_index = int(recorded[index])
                if index % 16 == 0 and recorded_index in fit_events[source]:
                    candidate = (right + 1) % max(2, 2 * count)
                    while candidate == right or (left, candidate) in seen:
                        candidate = (candidate + 1) % max(2, 2 * count)
                    negative_memory, _ = memory(torch.tensor([left, candidate], dtype=torch.long))
                    positive = heads.link_logit(left_memory, right_memory, msg)
                    negative = heads.link_logit(negative_memory[0:1], negative_memory[1:2], msg)
                    link_loss = F.binary_cross_entropy_with_logits(positive, torch.ones_like(positive)) + F.binary_cross_entropy_with_logits(negative, torch.zeros_like(negative))
                    pending.append(link_loss)
                    epoch_link.append(float(link_loss.detach()))
                    total_negative += 1
                record = lookup.get(recorded_index)
                if record is not None:
                    score = heads.verifier_logit(left_memory, right_memory, msg, float(record["c1_attack_score"]))
                    label = torch.tensor([float(record["target"])], dtype=torch.float32)
                    weight = 1.0
                    if int(record["target"]) == 1:
                        weight = float(max(family_counts.values()) / family_counts[str(record["attack_family"])])
                    supervised = F.binary_cross_entropy_with_logits(score, label) * weight
                    pending.append(supervised)
                    epoch_supervised.append(float(supervised.detach()))
                    total_supervised += 1
                if recorded_index not in blocked.get(source, set()):
                    memory.update_state(torch.tensor([left]), torch.tensor([right]), time, msg)
                seen.add((left, right))
                if len(pending) >= int(detach_every):
                    torch.stack(pending).mean().backward()
                    torch.nn.utils.clip_grad_norm_(list(heads.parameters()) + list(memory.parameters()), 5.0)
                    optimizer.step(); optimizer.zero_grad(); memory.detach(); pending.clear()
            if pending:
                torch.stack(pending).mean().backward()
                torch.nn.utils.clip_grad_norm_(list(heads.parameters()) + list(memory.parameters()), 5.0)
                optimizer.step(); optimizer.zero_grad(); memory.detach(); pending.clear()
        history.append({
            "epoch": epoch + 1,
            "link_loss_mean": float(np.mean(epoch_link)) if epoch_link else np.nan,
            "support_verifier_loss_mean": float(np.mean(epoch_supervised)) if epoch_supervised else np.nan,
            "supervised_packet_uses": int(len(epoch_supervised)),
            "negative_samples": int(len(epoch_link)),
        })
    audit = {
        "source_reset_count": int(reset_count),
        "supervised_packet_uses": int(total_supervised),
        "negative_samples": int(total_negative),
        "negative_sampling": "source-local, prior-seen-edge exclusion, current positive exclusion, no held-family source",
        "event_order": "read TGNMemory before loss, then update_state; reset per source; select/report target events are not fit-time memory updates",
    }
    return memory, heads, audit, history


@torch.no_grad()
def link_control(memory: TGNMemory, heads: Heads, cache: T0Cache, records: list[dict[str, Any]], blocked: dict[str, set[int]], max_events: int) -> float:
    fit_events: defaultdict[str, set[int]] = defaultdict(set)
    for row in records:
        fit_events[str(row["source_group"])].add(int(row["recorded_index"]))
    losses: list[float] = []
    memory.eval(); heads.eval()
    for source in sorted(fit_events):
        npz, _meta = cache.paths(source)
        with np.load(npz, allow_pickle=False) as data:
            count = min(int(len(data["time_ms"])), int(max_events))
            recorded = data["recorded_index"][:count]
            stamp, src, dst, message = data["time_ms"][:count], data["src"][:count], data["dst"][:count], data["raw_msg"][:count]
        memory.reset_state(); seen: set[tuple[int, int]] = set()
        for index in range(count):
            left, right = int(src[index]), int(dst[index])
            msg = torch.from_numpy(message[index : index + 1])
            current = int(recorded[index])
            if index % 16 == 0 and current in fit_events[source]:
                values, _ = memory(torch.tensor([left, right], dtype=torch.long))
                candidate = (right + 1) % max(2, 2 * int(max_events))
                while candidate == right or (left, candidate) in seen:
                    candidate = (candidate + 1) % max(2, 2 * int(max_events))
                negative, _ = memory(torch.tensor([left, candidate], dtype=torch.long))
                pos = heads.link_logit(values[0:1], values[1:2], msg)
                neg = heads.link_logit(negative[0:1], negative[1:2], msg)
                loss = F.binary_cross_entropy_with_logits(pos, torch.ones_like(pos)) + F.binary_cross_entropy_with_logits(neg, torch.zeros_like(neg))
                losses.append(float(loss))
            if current not in blocked.get(source, set()):
                memory.update_state(torch.tensor([left]), torch.tensor([right]), torch.tensor([int(stamp[index])]), msg)
            seen.add((left, right))
    return float(np.mean(losses)) if losses else math.nan


@torch.no_grad()
def actual_cache_causality(cache: T0Cache, selected: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    """Perturb a real CKBE cache without ever replaying the future into input."""
    row = next(value for value in selected if int(value["event_position"]) >= 2)
    source, target = str(row["source_group"]), int(row["event_position"])
    npz, _meta = cache.paths(source)
    with np.load(npz, allow_pickle=False) as data:
        stamp = np.asarray(data["time_ms"][: target + 2], dtype=np.int64)
        src = np.asarray(data["src"][: target + 2], dtype=np.int64)
        dst = np.asarray(data["dst"][: target + 2], dtype=np.int64)
        base_message = np.asarray(data["raw_msg"][: target + 2], dtype=np.float32)

    def signature(message: np.ndarray) -> np.ndarray:
        torch.manual_seed(int(seed))
        memory = make_memory(capacity=2 * len(message) + 2)
        memory.eval(); memory.reset_state()
        for index in range(target + 1):
            pair = torch.tensor([int(src[index]), int(dst[index])], dtype=torch.long)
            representation, last_update = memory(pair)
            if index == target:
                return torch.cat([representation.flatten(), last_update.to(torch.float32)]).cpu().numpy()
            memory.update_state(pair[0:1], pair[1:2], torch.tensor([int(stamp[index])]), torch.from_numpy(message[index : index + 1]))
        raise RuntimeError("target was not reached")

    baseline = signature(base_message)
    future = base_message.copy(); future[target + 1, 0] += 1.0
    past = base_message.copy(); past[target - 1, 0] += 1.0
    future_signature, past_signature = signature(future), signature(past)
    return {
        "source_group": source,
        "target_event_position": target,
        "raw_label_column_read": False,
        "future_event_mutation_invariant": bool(np.allclose(baseline, future_signature)),
        "past_event_changes_representation": bool(not np.allclose(baseline, past_signature)),
    }


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    held = str(args.held_value)
    cache = T0Cache(Path(args.t0_root))
    model, frontend, c1_audit = fit_c1(x_by_role, frames, held, Path(args.c1_cache), Path(args.c1_plan), int(args.c1_train_cap))
    records = score_records(model, frontend, frames, held, int(args.c1_train_cap))
    selected = choose_canary(records, cache, int(args.max_events_per_source), int(args.per_attack_family), int(args.benign_cap))
    blocked = blocked_event_positions(frames, held)
    memory, heads, train_audit, history = train_canary(
        cache, records, selected, blocked, int(args.max_events_per_source), int(args.epochs), int(args.detach_every), int(args.seed),
    )
    trained_link_loss = link_control(memory, heads, cache, records, blocked, int(args.max_events_per_source))
    torch.manual_seed(int(args.seed) + 1)
    random_link_loss = link_control(
        make_memory(capacity=2 * int(args.max_events_per_source) + 2), Heads(memory_dim=32, message_dim=9),
        cache, records, blocked, int(args.max_events_per_source),
    )
    control = [{"candidate": "M1_SSL", "fit_only_link_loss": trained_link_loss}, {"candidate": "M1_Random", "fit_only_link_loss": random_link_loss}]
    causality = ckbd.synthetic_audit()
    if not all(causality.values()):
        raise RuntimeError(f"TGN causality audit failed: {causality}")
    actual_causality = actual_cache_causality(cache, selected, int(args.seed))
    if not (actual_causality["future_event_mutation_invariant"] and actual_causality["past_event_changes_representation"]):
        raise RuntimeError(f"actual CKBE cache causality audit failed: {actual_causality}")
    pd.DataFrame(c1_audit).to_csv(out / "canary_c1_fit_audit.csv", index=False)
    pd.DataFrame(selected).to_csv(out / "canary_support_usage_audit.csv", index=False)
    pd.DataFrame(history).to_csv(out / "canary_training_audit.csv", index=False)
    pd.DataFrame(control).to_csv(out / "canary_random_control.csv", index=False)
    (out / "canary_causality_audit.json").write_text(json.dumps(causality, indent=2) + "\n", encoding="utf-8")
    (out / "canary_actual_cache_causality_audit.json").write_text(json.dumps(actual_causality, indent=2) + "\n", encoding="utf-8")
    spec = {
        "issue": ISSUE,
        "held_value": held,
        "review_rate_fixed": 0.0,
        "pyg_version": PYG_VERSION,
        "torch_version": torch.__version__,
        "official_pyg_components": ["TGNMemory", "IdentityMessage", "LastAggregator", "TGNMemory internal TimeEncoder"],
        "c1_anchor": "existing CKAO C1_cicflow_style_only_histgb fitted on legal non-held fit rows only",
        "support_policy": "per-packet loss, family-balanced inverse-frequency weighting, support_val excluded",
        "report_or_select_used_for_gradient": False,
        "input_audit": input_audit,
        "training_audit": train_audit,
        "random_control": control,
        "causality_audit": causality,
        "actual_cache_causality_audit": actual_causality,
        "seed": int(args.seed),
    }
    (out / "run_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    readout = [
        f"# {ISSUE}", "", "## Scope", "",
        "- Canary only: no threshold, hard-rate, review routing, or full-M1 claim.",
        "- C1 anchor and TGN verifier use legal non-held fit data; review is fixed at zero.",
        "- Every selected attack family has at least one packet-level supervised use; support is never episode-pooled.", "",
        "## Outcome", "",
        f"- Source resets: `{train_audit['source_reset_count']}`",
        f"- Supervised packet uses: `{train_audit['supervised_packet_uses']}`",
        f"- Negative samples: `{train_audit['negative_samples']}`",
        f"- Fit-only temporal link loss: trained `{trained_link_loss:.6f}`, random `{random_link_loss:.6f}`. This is an execution control, not a detection result.",
        "- Full M1 remains blocked pending this canary's audit review; no HPC full run is submitted by this script.",
    ]
    (out / "codex_readout.md").write_text("\n".join(readout) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), **train_audit}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "runs" / f"{ISSUE}_hpc_canary"))
    parser.add_argument("--t0-root", default=str(DEFAULT_T0))
    parser.add_argument("--c1-cache", default=str(DEFAULT_C1_CACHE))
    parser.add_argument("--c1-plan", default=str(DEFAULT_C1_PLAN))
    parser.add_argument("--held-value", default="iotsim-ip-camera-street")
    parser.add_argument("--c1-train-cap", type=int, default=1200)
    parser.add_argument("--max-events-per-source", type=int, default=200000)
    parser.add_argument("--per-attack-family", type=int, default=2)
    parser.add_argument("--benign-cap", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--detach-every", type=int, default=32)
    parser.add_argument("--seed", type=int, default=27)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
