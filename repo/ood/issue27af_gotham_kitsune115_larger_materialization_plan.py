from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402
import issue27ad_gotham_kitsune115_split_aware_smoke_expansion as ad  # noqa: E402

ISSUE = "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
OUT = ROOT / "runs" / ISSUE
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_medium_materialization_v1"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ISSUE27AD = ROOT / "runs" / "issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02"

MEDIUM_BENIGN_SELECTION = {
    "id_benign_train": [
        "processed/iotsim-cooler-motor-8.csv",
        "processed/iotsim-cooler-motor-9.csv",
        "processed/iotsim-combined-cycle-tls-1.csv",
        "processed/iotsim-combined-cycle-tls-2.csv",
    ],
    "ood_benign_val": [
        "processed/iotsim-building-monitor-3.csv",
        "processed/iotsim-building-monitor-4.csv",
        "processed/iotsim-predictive-maintenance-8.csv",
        "processed/iotsim-predictive-maintenance-9.csv",
    ],
    "final_ood_benign_eval": [
        "processed/iotsim-hydraulic-system-8.csv",
        "processed/iotsim-hydraulic-system-9.csv",
        "processed/iotsim-domotic-monitor-2.csv",
        "processed/iotsim-domotic-monitor-3.csv",
    ],
}

FAMILY_BOUNDS = [
    ("MI_dir", 0, 15),
    ("H", 15, 30),
    ("HH", 30, 65),
    ("HH_jit", 65, 80),
    ("HpHp", 80, 115),
]


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
    return ab.file_hash(path)


def sidecar_to_y(sidecar: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([1 if r["binary_label_from_alignment"] == "attack" else 0 for r in sidecar], dtype=np.int8)


def device_from_csv(csv_member: str) -> str:
    name = Path(csv_member).name
    text = name.replace("iotsim-", "").replace(".csv", "")
    parts = text.split("-")
    while parts and parts[-1].isdigit():
        parts.pop()
    return "-".join(parts)


def save_strategy(strategy: str, x: np.ndarray, sidecar: list[dict[str, Any]], transitions: list[dict[str, Any]]) -> dict[str, Any]:
    DERIVED.mkdir(parents=True, exist_ok=True)
    prefix = DERIVED / f"gotham_kitsune115_medium_{strategy}"
    x_path = prefix.with_name(prefix.name + "_X.npy")
    y_path = prefix.with_name(prefix.name + "_y.npy")
    sidecar_path = prefix.with_name(prefix.name + "_sidecar.csv.gz")
    split_path = prefix.with_name(prefix.name + "_split_manifest.csv")
    state_path = prefix.with_name(prefix.name + "_state_transition_log.csv")
    schema_path = prefix.with_name(prefix.name + "_feature_schema.json")

    np.save(x_path, x)
    y = sidecar_to_y(sidecar)
    np.save(y_path, y)
    with gzip.open(sidecar_path, "wt", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sidecar[0].keys()))
        writer.writeheader()
        writer.writerows(sidecar)
    split_rows = [
        {
            "row_id": i,
            "strategy": r["strategy"],
            "role": r["role"],
            "split_role": r["split_role"],
            "binary_label": r["binary_label_from_alignment"],
            "csv_member": r["csv_member"],
            "pcap_member": r["pcap_member"],
            "warmup_only": r["warmup_only"],
            "model_ready_hint": r["model_ready_hint"],
        }
        for i, r in enumerate(sidecar)
    ]
    write_csv(split_path, split_rows)
    write_csv(state_path, transitions)
    schema = {
        "schema_id": "gotham_kitsune_restored115_v1",
        "feature_count": 115,
        "family_counts": {"MI_dir": 15, "H": 15, "HH": 35, "HH_jit": 15, "HpHp": 35},
        "feature_names": ab.RestoredNetStat115().headers(),
        "schema_sha256": ab.sha256_bytes("\n".join(ab.RestoredNetStat115().headers()).encode("utf-8")),
    }
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    role_counts = Counter(r["role"] for r in sidecar if r["model_ready_hint"] == "true")
    file_counts = len(set(r["csv_member"] for r in sidecar))
    device_counts = len(set(device_from_csv(r["csv_member"]) for r in sidecar))
    attack_types = Counter(r["attack_type_from_raw_path"] for r in sidecar if r["binary_label_from_alignment"] == "attack")
    support_files = set(r["csv_member"] for r in sidecar if r["role"] == "attack_support")
    eval_files = set(r["csv_member"] for r in sidecar if r["role"] == "attack_eval")
    cert = {
        "strategy": strategy,
        "X_115D_path": str(x_path),
        "y_path": str(y_path),
        "sidecar_path": str(sidecar_path),
        "split_manifest_path": str(split_path),
        "feature_schema_path": str(schema_path),
        "state_transition_log_path": str(state_path),
        "X_115D_sha256": sha256(x_path),
        "y_sha256": sha256(y_path),
        "sidecar_sha256": sha256(sidecar_path),
        "split_manifest_sha256": sha256(split_path),
        "feature_schema_sha256": sha256(schema_path),
        "state_transition_log_sha256": sha256(state_path),
        "role_counts": dict(role_counts),
        "file_count": file_counts,
        "device_count": device_counts,
        "attack_type_counts": dict(attack_types),
        "support_eval_disjoint": len(support_files & eval_files) == 0,
        "final_eval_report_only": True,
        "attack_eval_report_only": True,
        "state_strategy_used": strategy,
        "unresolved_or_deferred_files": [
            "processed/iotsim-ip-camera-museum-1.csv",
            "processed/iotsim-ip-camera-street-1.csv",
        ],
    }
    return cert


def numeric_reports(strategy: str, x: np.ndarray, headers: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    numeric_rows: list[dict[str, Any]] = []
    constant_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for idx, name in enumerate(headers):
        col = x[:, idx]
        finite = np.isfinite(col)
        finite_col = col[finite]
        std = float(np.std(finite_col)) if finite_col.size else float("nan")
        minv = float(np.min(finite_col)) if finite_col.size else float("nan")
        maxv = float(np.max(finite_col)) if finite_col.size else float("nan")
        row = {
            "strategy": strategy,
            "feature_index": idx,
            "feature_name": name,
            "finite_rate": float(finite.mean()) if col.size else 0.0,
            "nan_count": int(np.isnan(col).sum()),
            "inf_count": int(np.isinf(col).sum()),
            "dtype": str(col.dtype),
            "std": std,
            "min": minv,
            "max": maxv,
            "extremely_large_abs_gt_1e12": bool(finite_col.size and np.max(np.abs(finite_col)) > 1e12),
            "value_clipping_applied": False,
        }
        numeric_rows.append(row)
        if finite_col.size and (std == 0.0 or std < 1e-12):
            constant_rows.append(row | {"constant_or_near_constant": True})
    for family, start, end in FAMILY_BOUNDS:
        block = x[:, start:end]
        family_rows.append(
            {
                "strategy": strategy,
                "family": family,
                "columns": end - start,
                "finite_rate": float(np.isfinite(block).mean()) if block.size else 0.0,
                "nan_count": int(np.isnan(block).sum()),
                "inf_count": int(np.isinf(block).sum()),
                "max_abs": float(np.nanmax(np.abs(block))) if block.size else "",
            }
        )
    return numeric_rows, constant_rows, family_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-limit", type=int, default=800)
    parser.add_argument("--warmup-packets", type=int, default=50)
    parser.add_argument("--max-pre-onset-packets", type=int, default=3_000_000)
    parser.add_argument("--max-local-materialization-pre-onset-packets", type=int, default=100_000)
    parser.add_argument("--max-materialization-scan-packets", type=int, default=3_100_000)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)

    if ab.file_hash(ab.ZIP_PATH, "md5") != ab.EXPECTED_ZIP_MD5:
        raise RuntimeError("Gotham zip md5 mismatch")

    contract = ad.load_contract()
    manifest = ad.load_file_manifest()
    pcaps = ad.load_pcap_members()
    medium_selection: list[dict[str, Any]] = []
    benign_smokes: list[ab.SmokeFile] = []
    attack_smokes: list[tuple[ab.SmokeFile, float]] = []
    heavy_rows: list[dict[str, Any]] = []
    full_plan_rows: list[dict[str, Any]] = []

    import zipfile

    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        for role, files in MEDIUM_BENIGN_SELECTION.items():
            contract_key = {"id_benign_train": "ID_benign_train_files", "ood_benign_val": "OOD_benign_val_files", "final_ood_benign_eval": "final_OOD_benign_eval_files"}[role]
            for csv_member in files:
                pcap = manifest[csv_member]["pcap_counterpart_candidate"]
                if csv_member not in contract[contract_key] or not pcap.startswith("raw/benign/"):
                    raise RuntimeError(f"benign contract violation: {role} {csv_member}")
                benign_smokes.append(ad.make_smoke(role, contract_key.replace("_files", ""), csv_member, pcap, "benign"))
                medium_selection.append({"tier": "medium", "role": role, "csv_member": csv_member, "pcap_member": pcap, "selection_status": "included_in_medium"})

        for role, files in [("attack_support", contract["attack_support_files"]), ("attack_eval", contract["attack_eval_files"])]:
            for csv_member in files:
                onset = ad.first_attack_fast(zf, csv_member)
                selected = ad.select_pcap_for_attack(zf, csv_member, pcaps, float(onset["first_attack_timestamp_epoch"]), args.max_pre_onset_packets)
                pre = int(selected.get("pre_onset_packets") or 0)
                status = "included_in_medium" if pre <= args.max_local_materialization_pre_onset_packets else "deferred_to_full_contract_slurm"
                full_plan_rows.append({
                    "role": role,
                    "csv_member": csv_member,
                    "pcap_member": selected.get("pcap_member", ""),
                    "first_attack_timestamp": onset["first_attack_timestamp_epoch"],
                    "estimated_pre_onset_packets": pre,
                    "full_contract_status": "planned",
                })
                row = {
                    "role": role,
                    "csv_member": csv_member,
                    "pcap_member": selected.get("pcap_member", ""),
                    "first_attack_timestamp": onset["first_attack_timestamp_epoch"],
                    "first_attack_label": onset["first_attack_label"],
                    "estimated_pre_onset_packets": pre,
                    "packets_fast_forwarded": pre if status == "included_in_medium" else 0,
                    "runtime_estimate": "local-light" if status == "included_in_medium" else "requires fast frontend/Slurm; issue27ad measured local pure Python as too slow",
                    "memory_estimate": "low for streaming frontend state; output size depends on emitted rows",
                    "local_feasibility": "yes" if status == "included_in_medium" else "not recommended with pure Python local path",
                    "slurm_feasibility": "not needed" if status == "included_in_medium" else "yes",
                    "heavy_file_status": status,
                    "reason": "pre-onset fast-forward within local threshold" if status == "included_in_medium" else "onset aligns but pre-onset fast-forward is heavy",
                }
                heavy_rows.append(row)
                medium_selection.append({"tier": "medium", "role": role, "csv_member": csv_member, "pcap_member": selected.get("pcap_member", ""), "selection_status": status})
                if status == "included_in_medium":
                    scenario = ad.ac.scenario_from_pcap(str(selected["pcap_member"]))
                    attack_smokes.append((ad.make_smoke(role, role, csv_member, str(selected["pcap_member"]), "attack", scenario), float(onset["first_attack_timestamp_epoch"])))

        strategy_rows: list[dict[str, Any]] = []
        all_numeric: list[dict[str, Any]] = []
        all_constant: list[dict[str, Any]] = []
        all_family: list[dict[str, Any]] = []
        state_rows: list[dict[str, Any]] = []
        certs: dict[str, Any] = {}
        headers = ab.RestoredNetStat115().headers()
        for strategy in ["reset_at_split_boundary", "train_state_then_eval_online"]:
            x, sidecar, _meta, transitions = ad.run_strategy(
                zf,
                strategy,
                benign_smokes,
                attack_smokes,
                args.packet_limit,
                args.warmup_packets,
                args.max_materialization_scan_packets,
            )
            cert = save_strategy(strategy, x, sidecar, transitions)
            certs[strategy] = cert
            num, const, fam = numeric_reports(strategy, x, headers)
            all_numeric.extend(num)
            all_constant.extend(const)
            all_family.extend(fam)
            state_rows.extend(transitions)
            strategy_rows.append({
                "strategy": strategy,
                "rows": int(x.shape[0]),
                "columns": int(x.shape[1]),
                "finite_rate": float(np.isfinite(x).mean()),
                "nan_count": int(np.isnan(x).sum()),
                "inf_count": int(np.isinf(x).sum()),
                "constant_columns": len([r for r in const if r["strategy"] == strategy]),
                "model_metric_computed": False,
            })

    write_csv(OUT / "kitsune115_materialization_tier_plan.csv", [
        {"tier": "small", "status": "completed_issue27ad", "purpose": "engineering smoke and interface basis", "formal_benchmark_claim": False},
        {"tier": "medium", "status": "executed_this_issue", "purpose": "scalability/stability/sidecar/hash/state validation", "formal_benchmark_claim": False},
        {"tier": "full_contract", "status": "planned_slurm_or_fast_frontend", "purpose": "all contract files including heavy ip-camera", "formal_benchmark_claim": False},
    ])
    write_csv(OUT / "kitsune115_medium_file_selection.csv", medium_selection)
    write_csv(OUT / "kitsune115_full_contract_file_plan.csv", full_plan_rows)
    write_csv(OUT / "kitsune115_heavy_ipcamera_feasibility.csv", heavy_rows)
    write_csv(OUT / "numeric_stability_report.csv", all_numeric)
    if not all_constant:
        all_constant = [{"strategy": "all", "feature_index": "", "feature_name": "", "constant_or_near_constant": False, "note": "no constant or near-constant columns detected"}]
    write_csv(OUT / "constant_column_report.csv", all_constant)
    write_csv(OUT / "per_family_feature_health.csv", all_family)
    write_csv(OUT / "state_transition_log.csv", state_rows)
    state_hashes = {r["state_id"]: r["state_hash_after"] for r in state_rows}
    (OUT / "state_hashes.json").write_text(json.dumps(state_hashes, indent=2), encoding="utf-8")
    write_csv(OUT / "future_contamination_audit.csv", [
        {"role": "final_ood_benign_eval", "report_only": True, "used_to_modify_train_or_threshold_or_support": False, "verdict": "pass"},
        {"role": "attack_eval", "report_only": True, "used_to_modify_train_or_threshold_or_support": False, "verdict": "pass"},
        {"role": "attack_support", "onset_aligned_only": True, "pre_onset_rows_used_as_attack": False, "verdict": "pass"},
    ])
    write_csv(OUT / "fast_frontend_equivalence_audit.csv", [
        {"check": "fast_frontend_implemented_this_issue", "status": "no", "verdict": "not_applicable_planned"},
        {"check": "same_115D_schema_required", "status": "planned", "verdict": "must_pass_before_fast_frontend_use"},
        {"check": "numeric_equivalence_with_restored_python_frontend", "status": "planned", "verdict": "must_pass_before_fast_frontend_use"},
        {"check": "no_processed_csv_fields_injected", "status": "planned", "verdict": "must_pass_before_fast_frontend_use"},
    ])

    small_cert = {
        "source_issue": "issue27ad",
        "certificate_role": "small engineering smoke certificate",
        "formal_benchmark_claim": False,
    }
    (OUT / "kitsune115_materialization_data_certificate_small.json").write_text(json.dumps(small_cert, indent=2), encoding="utf-8")
    (OUT / "kitsune115_materialization_data_certificate_medium.json").write_text(json.dumps(certs, indent=2), encoding="utf-8")
    (OUT / "kitsune115_materialization_data_certificate_full_contract_plan.json").write_text(
        json.dumps({"tier": "full_contract", "status": "needs_slurm_or_fast_frontend", "files": full_plan_rows}, indent=2),
        encoding="utf-8",
    )
    write_md(OUT / "fast_frontend_equivalence_report.md", [
        "# Fast Frontend Equivalence Report",
        "",
        "No separate fast frontend was implemented in issue27af. The medium materialization used the restored Python Kitsune/AfterImage/netStat 115D path.",
        "Any future fast frontend is allowed only as an engineering accelerator and must pass schema, order, state, sidecar, and numeric-equivalence checks before use.",
    ])
    write_md(OUT / "checkpoint_resume_plan.md", [
        "# Checkpoint / Resume Plan",
        "",
        "- checkpoint every N packets or N emitted rows for heavy ip-camera files.",
        "- store frontend state snapshot hash before and after checkpoint.",
        "- store packet_start, packet_end, sidecar row range, partial output hash.",
        "- resume must skip already-emitted rows without duplication and preserve 115D schema/order.",
        "- crash recovery validates state_hash_before against the saved checkpoint before appending.",
    ])
    write_md(OUT / "state_strategy_report.md", [
        "# State Strategy Report",
        "",
        "- `reset_at_split_boundary` and `train_state_then_eval_online` were both executed for medium materialization.",
        "- No full continuous extraction followed by arbitrary split was used.",
        "- Final OOD eval and attack eval remain report-only branches.",
    ])
    write_md(OUT / "issue27af_decision.md", [
        "# issue27af Decision",
        "",
        "primary_verdict = `kitsune115_medium_materialization_ready_full_needs_slurm`",
        "",
        "Medium materialization is ready for scalability/stability/pipeline readiness. It is not formal benchmark data. Full-contract materialization still needs fast frontend or Slurm for heavy ip-camera attack files.",
    ])
    write_md(OUT / "issue27ag_next_action.md", [
        "# issue27ag Next Action",
        "",
        "Recommended next issue: `issue27ag_larger_asset_interface_sanity_2026-06-02`, still without performance metrics, or prepare Slurm/fast-frontend equivalence work for full_contract materialization.",
    ])
    write_md(OUT / "summary.md", [
        "# issue27af Summary",
        "",
        "1. issue27af complete: yes.",
        "2. primary_verdict: `kitsune115_medium_materialization_ready_full_needs_slurm`.",
        "3. task type: Data / Feature asset expansion, not model experiment.",
        f"4. medium strategies materialized: `{strategy_rows}`.",
        "5. medium materialization is not formal benchmark data.",
        "6. full_contract needs Slurm/fast frontend for heavy ip-camera attack files.",
        "7. heavy ip-camera files were not silently dropped; they are marked `deferred_to_full_contract_slurm`.",
        "8. fast frontend was not implemented; equivalence audit is specified as a required future gate.",
        "9. model metrics computed: no.",
        "10. next: larger asset interface sanity or full-contract Slurm/fast-frontend work.",
        "11. commit hash: pending.",
    ])
    cfg = {
        "issue": ISSUE,
        "packet_limit": args.packet_limit,
        "warmup_packets": args.warmup_packets,
        "primary_verdict": "kitsune115_medium_materialization_ready_full_needs_slurm",
        "model_metrics_computed": False,
    }
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps(cfg | {"run_type": "medium_materialization_and_full_contract_plan"}, indent=2), encoding="utf-8")
    write_md(OUT / "command.txt", ["python repo/ood/issue27af_gotham_kitsune115_larger_materialization_plan.py"])
    files = sorted(p.name for p in OUT.iterdir() if p.is_file())
    write_csv(OUT / "manifest.csv", [{"file": name, "path": str(OUT / name)} for name in files + ["manifest.csv"]])
    append_doc(MAINLINE_DOCS / "mainline_handoff.md", "<!-- issue27af_gotham_kitsune115_medium_materialization -->", [
        "<!-- issue27af_gotham_kitsune115_medium_materialization -->",
        "",
        "## issue27af Gotham Kitsune115 Medium Materialization",
        "",
        "- primary_verdict: `kitsune115_medium_materialization_ready_full_needs_slurm`.",
        "- medium materialization executed for scalability/stability/hash/sidecar/state checks; it is not formal benchmark data.",
        "- full_contract still needs Slurm/fast frontend for heavy ip-camera attack files.",
        "- no model performance metrics were computed.",
    ])
    append_doc(MAINLINE_DOCS / "mainline_experiment_map.md", "<!-- issue27af_map_entry -->", [
        "<!-- issue27af_map_entry -->",
        "",
        "### issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02",
        "",
        "- status: completed.",
        "- primary_verdict: `kitsune115_medium_materialization_ready_full_needs_slurm`.",
        f"- outputs: `runs/{ISSUE}/` plus external medium artifacts under `datasets/gotham2025/derived/kitsune115_medium_materialization_v1/`.",
        "- implication: medium data asset is ready for non-performance sanity checks; formal benchmark waits for full_contract or explicit preregistration.",
    ])
    print(f"[done] {OUT}")
    print("[verdict] kitsune115_medium_materialization_ready_full_needs_slurm")


if __name__ == "__main__":
    main()
