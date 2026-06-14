from __future__ import annotations

import csv
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402

ISSUE = "issue27ca_initial_support_bank_contract_on_certified_1m_2026-06-14"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ASSET_DIR = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_1m_certified_v1"
X_PATH = ASSET_DIR / "gotham_kitsune115_1m_certified_train_state_then_eval_online_X.npy"
Y_PATH = ASSET_DIR / "gotham_kitsune115_1m_certified_train_state_then_eval_online_y.npy"
SIDECAR_PATH = ASSET_DIR / "gotham_kitsune115_1m_certified_train_state_then_eval_online_sidecar.csv.gz"
SPLIT_MANIFEST_PATH = ASSET_DIR / "gotham_kitsune115_1m_certified_train_state_then_eval_online_split_manifest.csv.gz"
ISSUE27BZ_SUMMARY = ROOT / "runs" / "issue27bz_slurm_1m_cache_execution_and_certified_merge_2026-06-14" / "summary.md"

BUDGETS = [32, 64, 128, 256]
DEFAULT_BUDGET = 128
TRAIN_FRACTION = 0.75
REGION_CAP = 8
MAIN_SELECTOR = "phase_file_balanced_kcenter_standardized115_v1"
RANDOM_SEED = 42


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_once(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def infer_device(csv_member: str) -> str:
    name = Path(csv_member).name
    if name.startswith("iotsim-"):
        name = name[len("iotsim-") :]
    if name.endswith(".csv"):
        name = name[:-4]
    parts = name.split("-")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    return "-".join(parts)


def onset_phase(recorded_index: int) -> str:
    if recorded_index < 500:
        return "early_0_500"
    if recorded_index < 2_000:
        return "mid_500_2000"
    if recorded_index < 10_000:
        return "late_2000_10000"
    return "tail_gt_10000"


def load_candidate_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(SIDECAR_PATH, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["role"] != "attack_support_candidate_pool":
                continue
            recorded_index = int(row["recorded_index_within_file"])
            device = infer_device(row["csv_member"])
            phase = onset_phase(recorded_index)
            attack_type = row["first_attack_label"] or "unknown_attack_label"
            file_region = Path(row["csv_member"]).stem
            region_id = f"{attack_type}|{file_region}|{phase}"
            rows.append(
                {
                    "global_row_id": int(row["global_row_id"]),
                    "role": row["role"],
                    "csv_member": row["csv_member"],
                    "pcap_member": row["pcap_member"],
                    "device": device,
                    "first_attack_label": attack_type,
                    "recorded_index_within_file": recorded_index,
                    "pcap_packet_index": int(row["pcap_packet_index"]),
                    "packet_timestamp_epoch": row["packet_timestamp_epoch"],
                    "binary_label_from_alignment": row["binary_label_from_alignment"],
                    "model_ready_hint": row["model_ready_hint"].lower() == "true",
                    "warmup_only": row["warmup_only"].lower() == "true",
                    "selection_allowed": row["selection_allowed"].lower() == "true",
                    "report_only": row["report_only"].lower() == "true",
                    "sealed_final": row["sealed_final"].lower() == "true",
                    "phase": phase,
                    "file_region": file_region,
                    "support_region_id": region_id,
                }
            )
    return rows


def standardize_candidate_features(x: np.ndarray, candidate_ids: np.ndarray) -> np.ndarray:
    x_cand = np.asarray(x[candidate_ids], dtype=np.float32)
    mean = x_cand.mean(axis=0, dtype=np.float64).astype(np.float32)
    std = x_cand.std(axis=0, dtype=np.float64).astype(np.float32)
    std[std < 1e-6] = 1.0
    return (x_cand - mean) / std


def cap_pool_indices(local_indices: np.ndarray, cap: int) -> np.ndarray:
    if len(local_indices) <= cap:
        return local_indices
    take = np.linspace(0, len(local_indices) - 1, cap, dtype=np.int64)
    return local_indices[take]


def kcenter_select(z: np.ndarray, local_indices: np.ndarray, k: int, cap: int = 8_000) -> list[int]:
    if k <= 0 or len(local_indices) == 0:
        return []
    pool = cap_pool_indices(np.asarray(local_indices, dtype=np.int64), cap)
    if k >= len(pool):
        return [int(i) for i in pool[:k]]
    mat = z[pool]
    center = mat.mean(axis=0)
    first = int(np.argmin(((mat - center) ** 2).sum(axis=1)))
    selected_pos = [first]
    min_dist = ((mat - mat[first]) ** 2).sum(axis=1)
    min_dist[first] = -1.0
    for _ in range(1, k):
        nxt = int(np.argmax(min_dist))
        if min_dist[nxt] < 0:
            break
        selected_pos.append(nxt)
        d = ((mat - mat[nxt]) ** 2).sum(axis=1)
        min_dist = np.minimum(min_dist, d)
        min_dist[selected_pos] = -1.0
    return [int(pool[pos]) for pos in selected_pos]


def allocate_budget(bucket_sizes: dict[str, int], budget: int) -> dict[str, int]:
    nonempty = {k: v for k, v in bucket_sizes.items() if v > 0}
    if not nonempty:
        return {}
    if budget < len(nonempty):
        ordered = sorted(nonempty, key=lambda k: (-nonempty[k], k))[:budget]
        return {k: 1 for k in ordered}
    min_each = max(1, min(8, budget // (len(nonempty) * 2)))
    alloc = {k: min(min_each, v) for k, v in nonempty.items()}
    remaining = budget - sum(alloc.values())
    weights = {k: math.sqrt(v) for k, v in nonempty.items()}
    while remaining > 0:
        eligible = [k for k, v in nonempty.items() if alloc[k] < v]
        if not eligible:
            break
        total_w = sum(weights[k] for k in eligible)
        progressed = False
        for k in sorted(eligible, key=lambda x: (-weights[x], x)):
            if remaining <= 0:
                break
            add = max(1, int(round(remaining * weights[k] / total_w))) if total_w else 1
            add = min(add, remaining, nonempty[k] - alloc[k])
            if add > 0:
                alloc[k] += add
                remaining -= add
                progressed = True
        if not progressed:
            break
    return alloc


def split_train_val(selected: list[int], target_val: int, bucket_by_idx: dict[int, str]) -> dict[int, str]:
    by_bucket: dict[str, list[int]] = defaultdict(list)
    for idx in selected:
        by_bucket[bucket_by_idx[idx]].append(idx)
    subset = {idx: "support_train" for idx in selected}
    val_selected: list[int] = []
    for bucket, idxs in sorted(by_bucket.items()):
        if len(idxs) >= 4:
            val_selected.append(idxs[-1])
    remaining_val = max(0, target_val - len(val_selected))
    leftovers = [idx for idx in selected if idx not in set(val_selected)]
    if remaining_val > 0:
        step = max(1, len(leftovers) // remaining_val)
        for idx in leftovers[step - 1 :: step]:
            if len(val_selected) >= target_val:
                break
            val_selected.append(idx)
    if len(val_selected) > target_val:
        val_selected = val_selected[:target_val]
    for idx in val_selected:
        subset[idx] = "support_val"
    return subset


def summarize_selection(name: str, budget: int, selected: list[int], row_by_local: dict[int, dict[str, Any]]) -> dict[str, Any]:
    phases = Counter(row_by_local[i]["phase"] for i in selected)
    files = Counter(row_by_local[i]["csv_member"] for i in selected)
    labels = Counter(row_by_local[i]["first_attack_label"] for i in selected)
    regions = Counter(row_by_local[i]["support_region_id"] for i in selected)
    return {
        "selector": name,
        "budget": budget,
        "selected_rows": len(selected),
        "attack_type_count": len(labels),
        "file_count": len(files),
        "phase_count": len(phases),
        "region_bucket_count": len(regions),
        "selected_attack_types": json.dumps(dict(labels), ensure_ascii=False),
        "selected_files": json.dumps(dict(files), ensure_ascii=False),
        "selected_phases": json.dumps(dict(phases), ensure_ascii=False),
        "selected_region_buckets": len(regions),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not X_PATH.exists() or not SIDECAR_PATH.exists() or not SPLIT_MANIFEST_PATH.exists():
        raise FileNotFoundError("Certified 1M asset is missing. Run issue27bz first.")
    rows_all = load_candidate_rows()
    candidate_rows = [r for r in rows_all if r["model_ready_hint"] and r["selection_allowed"] and not r["report_only"] and not r["sealed_final"]]
    forbidden_rows = [
        r
        for r in rows_all
        if r["role"] != "attack_support_candidate_pool"
        or r["report_only"]
        or r["sealed_final"]
        or not r["selection_allowed"]
        or r["binary_label_from_alignment"] != "attack"
    ]
    if not candidate_rows:
        raise RuntimeError("No legal model-ready support candidates found.")

    candidate_ids = np.array([r["global_row_id"] for r in candidate_rows], dtype=np.int64)
    x_mm = np.load(X_PATH, mmap_mode="r")
    z = standardize_candidate_features(x_mm, candidate_ids)
    del x_mm

    row_by_local = {i: row for i, row in enumerate(candidate_rows)}
    bucket_by_idx = {i: row["support_region_id"] for i, row in row_by_local.items()}
    bucket_indices: dict[str, list[int]] = defaultdict(list)
    for i, row in row_by_local.items():
        bucket_indices[row["support_region_id"]].append(i)
    bucket_sizes = {k: len(v) for k, v in bucket_indices.items()}

    # Build selector outputs.
    rng = np.random.default_rng(RANDOM_SEED)
    random_order = list(rng.permutation(len(candidate_rows)))
    global_kcenter_order = kcenter_select(z, np.arange(len(candidate_rows), dtype=np.int64), max(BUDGETS), cap=12_000)

    selected_rows: list[dict[str, Any]] = []
    selection_audit: list[dict[str, Any]] = []
    budget_rows: list[dict[str, Any]] = []
    main_selected_by_budget: dict[int, list[int]] = {}

    for budget in BUDGETS:
        val_target = budget - int(round(budget * TRAIN_FRACTION))
        budget_rows.append(
            {
                "budget": budget,
                "support_train_target": budget - val_target,
                "support_val_target": val_target,
                "budget_scope": "global_total_attack_samples",
                "not_per_attack_type": "true",
                "candidate_pool_rows": len(candidate_rows),
            }
        )

        selectors: dict[str, list[int]] = {
            "random_seed42": [int(i) for i in random_order[:budget]],
            "global_kcenter_standardized115_sampled_pool": global_kcenter_order[:budget],
        }
        alloc = allocate_budget(bucket_sizes, budget)
        balanced: list[int] = []
        for bucket, k in sorted(alloc.items()):
            balanced.extend(kcenter_select(z, np.array(bucket_indices[bucket], dtype=np.int64), k, cap=8_000))
        balanced = balanced[:budget]
        selectors[MAIN_SELECTOR] = balanced
        main_selected_by_budget[budget] = balanced

        for selector_name, selected in selectors.items():
            selection_audit.append(summarize_selection(selector_name, budget, selected, row_by_local))
            if selector_name == MAIN_SELECTOR:
                subset = split_train_val(selected, val_target, bucket_by_idx)
                for rank, idx in enumerate(selected):
                    row = row_by_local[idx]
                    selected_rows.append(
                        {
                            "budget": budget,
                            "selector": selector_name,
                            "support_subset": subset[idx],
                            "selection_rank": rank,
                            "global_row_id": row["global_row_id"],
                            "csv_member": row["csv_member"],
                            "pcap_member": row["pcap_member"],
                            "device": row["device"],
                            "first_attack_label": row["first_attack_label"],
                            "phase": row["phase"],
                            "support_region_id": row["support_region_id"],
                            "recorded_index_within_file": row["recorded_index_within_file"],
                            "packet_timestamp_epoch": row["packet_timestamp_epoch"],
                        }
                    )

    region_rows: list[dict[str, Any]] = []
    for region, idxs in sorted(bucket_indices.items()):
        first = row_by_local[idxs[0]]
        region_rows.append(
            {
                "support_region_id": region,
                "attack_type": first["first_attack_label"],
                "csv_member": first["csv_member"],
                "device": first["device"],
                "phase": first["phase"],
                "candidate_rows": len(idxs),
                "model_ready_rows": len(idxs),
                "region_cap_policy": f"R_max={REGION_CAP}",
            }
        )

    phase_counter = Counter(r["phase"] for r in candidate_rows)
    phase_rows = [{"phase": k, "candidate_rows": v} for k, v in sorted(phase_counter.items())]
    file_counter = Counter(r["csv_member"] for r in candidate_rows)
    device_counter = Counter(r["device"] for r in candidate_rows)
    file_rows = [
        {
            "csv_member": k,
            "device": infer_device(k),
            "candidate_rows": v,
            "device_total_rows": device_counter[infer_device(k)],
        }
        for k, v in sorted(file_counter.items())
    ]
    role_access_rows = [
        {
            "source_role": "attack_support_candidate_pool",
            "allowed_for_support_selection": "true",
            "allowed_for_support_train": "true",
            "allowed_for_support_val": "true",
            "allowed_for_model_training": "support_train_only",
            "allowed_for_threshold": "support_val_only_if_declared",
        },
        {
            "source_role": "dev_future_attack_query",
            "allowed_for_support_selection": "false",
            "allowed_for_support_train": "false",
            "allowed_for_support_val": "false",
            "allowed_for_model_training": "false",
            "allowed_for_threshold": "false",
        },
        {
            "source_role": "sealed_final_attack",
            "allowed_for_support_selection": "false",
            "allowed_for_support_train": "false",
            "allowed_for_support_val": "false",
            "allowed_for_model_training": "false",
            "allowed_for_threshold": "false",
        },
        {
            "source_role": "sealed_final_ood",
            "allowed_for_support_selection": "false",
            "allowed_for_support_train": "false",
            "allowed_for_support_val": "false",
            "allowed_for_model_training": "false",
            "allowed_for_threshold": "false",
        },
    ]

    attack_types = Counter(r["first_attack_label"] for r in candidate_rows)
    region_count = len(bucket_indices)
    attack_type_caveat = len(attack_types) < 2
    region_cap_pass = region_count <= REGION_CAP
    forbidden_pass = len(forbidden_rows) == 0
    primary_verdict = (
        "initial_support_bank_contract_ready_with_attack_taxonomy_limit_caveat"
        if region_cap_pass and forbidden_pass
        else "initial_support_bank_contract_blocked_by_role_or_region_audit"
    )

    write_csv(OUT / "support_budget_grid.csv", budget_rows)
    write_csv(OUT / "support_region_taxonomy.csv", region_rows)
    write_csv(OUT / "support_phase_coverage.csv", phase_rows)
    write_csv(OUT / "support_file_device_coverage.csv", file_rows)
    write_csv(OUT / "support_train_val_split.csv", selected_rows)
    write_csv(OUT / "support_selection_audit.csv", selection_audit)
    write_csv(OUT / "support_role_access_audit.csv", role_access_rows)
    write_csv(
        OUT / "forbidden_role_contamination_audit.csv",
        [
            {
                "checked_rows": len(rows_all),
                "legal_model_ready_candidate_rows": len(candidate_rows),
                "forbidden_candidate_rows": len(forbidden_rows),
                "verdict": "pass" if forbidden_pass else "blocked",
            }
        ],
    )

    write_md(
        OUT / "initial_support_bank_contract.md",
        [
            "# Initial Support Bank Contract v1",
            "",
            "This contract separates the large `attack_support_candidate_pool` from the actual initial analyst-labelled support bank.",
            "",
            "## Definitions",
            "",
            "- `attack_support_candidate_pool`: development-side attack candidate rows that may be used to simulate analyst-confirmed support selection.",
            "- `initial_support_bank`: a bounded labelled subset selected from the candidate pool.",
            f"- default candidate budget: `B={DEFAULT_BUDGET}` total attack rows, not per attack type or per region.",
            "- default train/val split: 75% support_train and 25% support_val.",
            f"- budget grid audited: `{BUDGETS}`.",
            f"- main selector: `{MAIN_SELECTOR}`.",
            "",
            "## Hard Rules",
            "",
            "- Support can only come from `attack_support_candidate_pool` rows with `selection_allowed=true`, `model_ready_hint=true`, and `sealed_final=false`.",
            "- `dev_future_attack_query`, `sealed_final_attack`, and `sealed_final_ood` are forbidden for support selection.",
            "- `support_val` must remain separate from `support_train`.",
            "- `B` is a global support budget, not a per-region budget.",
            "- Attack regions are memory/prototype/routing units, not one model head per region.",
            f"- Region cap for this contract: `R_max={REGION_CAP}`.",
        ],
    )
    write_md(
        OUT / "support_go_nogo.md",
        [
            "# Support Bank Go/No-Go",
            "",
            f"primary_verdict: `{primary_verdict}`",
            "",
            "## Checks",
            "",
            f"- Candidate pool rows: `{len(rows_all)}` total, `{len(candidate_rows)}` legal model-ready rows.",
            f"- Attack types in legal candidate pool: `{dict(attack_types)}`.",
            f"- File/phase region buckets: `{region_count}`; region cap pass: `{region_cap_pass}`.",
            f"- Forbidden role contamination in legal candidate pool: `{len(forbidden_rows)}`.",
            "",
            "## Caveats",
            "",
            "- Current certified 1M support candidate pool contains only `Telnet Brute Force` attack labels.",
            "- The contract can define a clean initial support bank, but it does not yet prove multi-attack taxonomy coverage.",
            "- Larger or formal experiments need either additional legal attack-support candidate diversity or a scoped claim limited to this attack family.",
            "- This issue does not train models and does not report detection performance.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            f"# {ISSUE} Summary",
            "",
            f"1. issue27ca completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: initial support bank contract and coverage audit",
            "4. model training: no",
            "5. formal benchmark: no",
            "6. certified 1M asset used: yes",
            f"7. legal support candidate rows: `{len(candidate_rows)}`",
            f"8. initial support budgets audited: `{BUDGETS}`",
            f"9. default budget proposal: `B={DEFAULT_BUDGET}` total, not per attack type",
            "10. default split proposal: `support_train=96`, `support_val=32` when B=128",
            f"11. attack types in current candidate pool: `{dict(attack_types)}`",
            f"12. region buckets: `{region_count}`",
            f"13. forbidden final/report-only contamination: `{len(forbidden_rows)}`",
            "14. biggest caveat: support candidate taxonomy is currently narrow; only Telnet Brute Force appears in the 1M candidate pool.",
            "15. next recommended issue: define attack/OOD head training contract on this support bank, or revise larger attack-support contract if broader attack taxonomy is required.",
            "16. commit/push: not performed",
        ],
    )
    write_md(OUT / "command.txt", ["python repo/ood/issue27ca_initial_support_bank_contract_on_certified_1m.py"])
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "asset_dir": str(ASSET_DIR),
                "budgets": BUDGETS,
                "default_budget": DEFAULT_BUDGET,
                "train_fraction": TRAIN_FRACTION,
                "region_cap": REGION_CAP,
                "main_selector": MAIN_SELECTOR,
                "model_training": False,
                "formal_benchmark": False,
                "primary_verdict": primary_verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "run_type": "initial_support_bank_contract_on_certified_1m",
                "inputs": [str(X_PATH), str(Y_PATH), str(SIDECAR_PATH), str(SPLIT_MANIFEST_PATH)],
                "outputs": [
                    "support_budget_grid.csv",
                    "support_train_val_split.csv",
                    "support_region_taxonomy.csv",
                    "support_selection_audit.csv",
                    "support_role_access_audit.csv",
                ],
                "forbidden": ["model_training", "formal_benchmark", "sealed_final_selection", "dev_future_query_selection"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        ISSUE,
        [
            f"## issue27ca Initial Support Bank Contract on Certified 1M",
            "",
            f"marker: `{ISSUE}`",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            f"- legal support candidate rows: `{len(candidate_rows)}`.",
            f"- support budget grid: `{BUDGETS}`; default B=128 is global, not per attack type.",
            "- `attack_support_candidate_pool` is explicitly separated from the initial support bank.",
            "- Caveat: current 1M support candidate pool contains only Telnet Brute Force attack labels.",
            "- No model training or formal benchmark was run.",
        ],
    )
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        ISSUE,
        [
            f"## issue27ca Initial Support Bank Contract on Certified 1M",
            "",
            f"marker: `{ISSUE}`",
            "",
            "- Role: support-bank contract and coverage audit before larger system replay.",
            "- Main output: bounded initial support bank candidates for B=32/64/128/256 using phase-file balanced k-center.",
            "- Boundary: data/system contract only, not performance.",
        ],
    )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"path": str(path.relative_to(ROOT)), "sha256": ab.file_hash(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)
    print(json.dumps({"issue": ISSUE, "primary_verdict": primary_verdict, "legal_support_rows": len(candidate_rows)}, indent=2))


if __name__ == "__main__":
    main()
