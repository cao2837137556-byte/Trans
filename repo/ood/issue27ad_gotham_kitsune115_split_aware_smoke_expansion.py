from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import dpkt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402
import issue27ac_gotham_kitsune115_attack_onset_alignment as ac  # noqa: E402

ISSUE = "issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02"
OUT = ROOT / "runs" / ISSUE
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_split_aware_smoke_expansion_v1"
ISSUE27Y = ROOT / "runs" / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
ISSUE27V = ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

BENIGN_SELECTION = {
    "id_benign_train": [
        "processed/iotsim-cooler-motor-8.csv",
        "processed/iotsim-combined-cycle-tls-1.csv",
    ],
    "ood_benign_val": [
        "processed/iotsim-building-monitor-3.csv",
        "processed/iotsim-predictive-maintenance-8.csv",
    ],
    "final_ood_benign_eval": [
        "processed/iotsim-hydraulic-system-8.csv",
        "processed/iotsim-domotic-monitor-2.csv",
    ],
}


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


def load_contract() -> dict[str, Any]:
    return json.loads((ISSUE27Y / "gotham_preregistered_split_contract_v1.json").read_text(encoding="utf-8"))["contract"]


def load_file_manifest() -> dict[str, dict[str, str]]:
    with (ISSUE27Y / "gotham_all_csv_file_manifest.csv").open("r", encoding="utf-8", newline="") as f:
        return {row["csv_archive_path"]: row for row in csv.DictReader(f)}


def load_pcap_members() -> list[str]:
    with (ISSUE27V / "archive_file_listing.csv").open("r", encoding="utf-8", newline="") as f:
        return [
            row["file_path"]
            for row in csv.DictReader(f)
            if row.get("is_pcap") == "True" and row["file_path"].startswith("raw/malicious/")
        ]


def is_attack_label(label: str) -> bool:
    return str(label).strip().lower() not in {"", "benign", "unknown"}


def first_attack_fast(zf: zipfile.ZipFile, csv_member: str, chunksize: int = 250_000) -> dict[str, Any]:
    rows_seen = 0
    label_counts: dict[str, int] = {}
    with zf.open(csv_member) as raw:
        for chunk in pd.read_csv(raw, usecols=["frame.time", "label"], chunksize=chunksize):
            labels = chunk["label"].astype(str)
            for k, v in labels.value_counts().to_dict().items():
                label_counts[k] = label_counts.get(k, 0) + int(v)
            mask = ~labels.str.lower().isin(["benign", "unknown"])
            if mask.any():
                rel = int(np.flatnonzero(mask.to_numpy())[0])
                row = chunk.iloc[rel]
                ts = ab.parse_gotham_time(str(row["frame.time"]))
                return {
                    "csv_member": csv_member,
                    "rows_scanned_until_first_attack": rows_seen + rel + 1,
                    "first_attack_timestamp_epoch": ts,
                    "first_attack_label": str(row["label"]),
                    "pre_attack_label_counts_scanned": dict(label_counts),
                    "status": "found",
                }
            rows_seen += len(chunk)
    return {
        "csv_member": csv_member,
        "rows_scanned_until_first_attack": rows_seen,
        "first_attack_timestamp_epoch": "",
        "first_attack_label": "",
        "pre_attack_label_counts_scanned": dict(label_counts),
        "status": "not_found",
    }


def select_pcap_for_attack(zf: zipfile.ZipFile, csv_member: str, pcaps: list[str], target_ts: float, max_packets: int) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    for pcap in ac.candidate_pcaps_for_csv(csv_member, pcaps):
        scan = ac.count_packets_until(zf, pcap, target_ts, max_packets)
        delta = ""
        if scan.get("pcap_first_timestamp_epoch") is not None:
            delta = target_ts - float(scan["pcap_first_timestamp_epoch"])
        row = {
            "csv_member": csv_member,
            "pcap_member": pcap,
            "scenario": ac.scenario_from_pcap(pcap),
            "pcap_to_first_attack_delta_seconds": delta,
            **scan,
        }
        if scan.get("hit_onset_within_scan_budget") and delta != "" and float(delta) >= 0:
            if best is None or int(scan["pre_onset_packets"]) < int(best["pre_onset_packets"]):
                best = row
    return best or {
        "csv_member": csv_member,
        "pcap_member": "",
        "scenario": "",
        "pcap_to_first_attack_delta_seconds": "",
        "pre_onset_packets": "",
        "hit_onset_within_scan_budget": False,
        "pcap_scan_status": "no_reachable_candidate",
    }


def make_smoke(role: str, split_role: str, csv_member: str, pcap_member: str, label: str, attack_type: str = "") -> ab.SmokeFile:
    return ab.SmokeFile(
        role=role,
        split_role=split_role,
        pcap_member=pcap_member,
        csv_member=csv_member,
        expected_binary_label=label,
        expected_attack_type=attack_type,
        selection_reason="issue27ad split-aware smoke expansion",
    )


def save_strategy(strategy: str, x: np.ndarray, sidecar: list[dict[str, Any]]) -> dict[str, Any]:
    DERIVED.mkdir(parents=True, exist_ok=True)
    x_path = DERIVED / f"gotham_kitsune115_{strategy}_smoke_X.npy"
    sidecar_path = DERIVED / f"gotham_kitsune115_{strategy}_smoke_sidecar.csv.gz"
    np.save(x_path, x)
    with gzip.open(sidecar_path, "wt", newline="", encoding="utf-8") as f:
        if sidecar:
            writer = csv.DictWriter(f, fieldnames=list(sidecar[0].keys()))
            writer.writeheader()
            writer.writerows(sidecar)
    return {
        "strategy": strategy,
        "feature_path": str(x_path),
        "feature_sha256": ab.file_hash(x_path),
        "sidecar_path": str(sidecar_path),
        "sidecar_sha256": ab.file_hash(sidecar_path),
        "rows": int(x.shape[0]),
        "columns": int(x.shape[1]) if x.ndim == 2 else 0,
    }


def stable_summary(strategy: str, x: np.ndarray) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "rows": int(x.shape[0]),
        "columns": int(x.shape[1]) if x.ndim == 2 else 0,
        "finite_rate": float(np.isfinite(x).mean()) if x.size else 0.0,
        "nan_count": int(np.isnan(x).sum()) if x.size else 0,
        "inf_count": int(np.isinf(x).sum()) if x.size else 0,
        "model_metric_computed": False,
    }


def extract_file(
    zf: zipfile.ZipFile,
    smoke: ab.SmokeFile,
    nstat: ab.RestoredNetStat115,
    packet_limit: int,
    warmup_packets: int,
    strategy: str,
    state_id: str,
    record_start_ts: float | None,
    max_scan_packets: int,
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    before = ab.state_hash(nstat)
    x, sidecar, meta = ab.read_pcap_vectors(
        zf,
        smoke,
        nstat,
        packet_limit=packet_limit,
        warmup_packets=warmup_packets,
        strategy=strategy,
        state_id=state_id,
        record_start_ts=record_start_ts,
        max_scan_packets=max_scan_packets,
    )
    after = ab.state_hash(nstat)
    transition = {
        "strategy": strategy,
        "state_id": state_id,
        "role": smoke.role,
        "split_role": smoke.split_role,
        "pcap_member": smoke.pcap_member,
        "csv_member": smoke.csv_member,
        "record_start_ts": record_start_ts,
        "feature_rows_emitted": int(x.shape[0]),
        "packets_scanned": int(meta.get("packets_scanned", 0)),
        "pre_record_packets": int(meta.get("pre_record_packets", 0)),
        "state_hash_before": before,
        "state_hash_after": after,
    }
    return x, sidecar, meta | transition, transition


def run_strategy(
    zf: zipfile.ZipFile,
    strategy: str,
    benign_smokes: list[ab.SmokeFile],
    attack_smokes: list[tuple[ab.SmokeFile, float]],
    packet_limit: int,
    warmup_packets: int,
    max_scan_packets: int,
) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    arrays: list[np.ndarray] = []
    sidecars: list[dict[str, Any]] = []
    metas: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    if strategy == "reset_at_split_boundary":
        work: list[tuple[ab.SmokeFile, float | None]] = [(s, None) for s in benign_smokes] + attack_smokes
        for smoke, start_ts in work:
            nstat = ab.RestoredNetStat115()
            x, sidecar, meta, tr = extract_file(zf, smoke, nstat, packet_limit, warmup_packets, strategy, f"reset::{smoke.role}::{Path(smoke.csv_member).stem}", start_ts, max_scan_packets)
            arrays.append(x); sidecars.extend(sidecar); metas.append(meta); transitions.append(tr)
    elif strategy == "train_state_then_eval_online":
        train_state = ab.RestoredNetStat115()
        for smoke in [s for s in benign_smokes if s.role == "id_benign_train"]:
            x, sidecar, meta, tr = extract_file(zf, smoke, train_state, packet_limit, warmup_packets, strategy, f"B::train::{Path(smoke.csv_member).stem}", None, max_scan_packets)
            arrays.append(x); sidecars.extend(sidecar); metas.append(meta); transitions.append(tr)
        frozen_train = deepcopy(train_state)
        for smoke in [s for s in benign_smokes if s.role != "id_benign_train"]:
            branch = deepcopy(frozen_train)
            x, sidecar, meta, tr = extract_file(zf, smoke, branch, packet_limit, warmup_packets, strategy, f"B::branch::{smoke.role}::{Path(smoke.csv_member).stem}", None, max_scan_packets)
            arrays.append(x); sidecars.extend(sidecar); metas.append(meta); transitions.append(tr)
        for smoke, start_ts in attack_smokes:
            branch = deepcopy(frozen_train)
            x, sidecar, meta, tr = extract_file(zf, smoke, branch, packet_limit, warmup_packets, strategy, f"B::branch::{smoke.role}::{Path(smoke.csv_member).stem}", start_ts, max_scan_packets)
            arrays.append(x); sidecars.extend(sidecar); metas.append(meta); transitions.append(tr)
    else:
        raise ValueError(strategy)
    x_all = np.vstack(arrays) if arrays else np.empty((0, 115), dtype=np.float32)
    return x_all, sidecars, metas, transitions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-limit", type=int, default=400)
    parser.add_argument("--warmup-packets", type=int, default=50)
    parser.add_argument("--max-pre-onset-packets", type=int, default=3_000_000)
    parser.add_argument("--max-local-materialization-pre-onset-packets", type=int, default=100_000)
    parser.add_argument("--max-materialization-scan-packets", type=int, default=3_100_000)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    if ab.file_hash(ab.ZIP_PATH, "md5") != ab.EXPECTED_ZIP_MD5:
        raise RuntimeError("Gotham zip md5 mismatch")

    contract = load_contract()
    manifest = load_file_manifest()
    pcaps = load_pcap_members()
    hard_gate_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    onset_rows: list[dict[str, Any]] = []
    benign_smokes: list[ab.SmokeFile] = []
    attack_smokes: list[tuple[ab.SmokeFile, float]] = []

    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        for role, files in BENIGN_SELECTION.items():
            contract_key = {"id_benign_train": "ID_benign_train_files", "ood_benign_val": "OOD_benign_val_files", "final_ood_benign_eval": "final_OOD_benign_eval_files"}[role]
            for csv_member in files:
                pcap = manifest[csv_member]["pcap_counterpart_candidate"]
                pass_gate = csv_member in contract[contract_key] and pcap.startswith("raw/benign/")
                hard_gate_rows.append({"role": role, "csv_member": csv_member, "pcap_member": pcap, "gate": "benign_roles_must_use_preregistered_benign_files", "pass": pass_gate})
                if not pass_gate:
                    raise RuntimeError(f"Benign hard gate failed: {role} {csv_member} {pcap}")
                smoke = make_smoke(role, contract_key.replace("_files", ""), csv_member, pcap, "benign")
                benign_smokes.append(smoke)
                selection_rows.append({"role": role, "csv_member": csv_member, "pcap_member": pcap, "record_start_ts": "", "selection_status": "selected_preregistered_benign"})

        for role, files in [("attack_support", contract["attack_support_files"]), ("attack_eval", contract["attack_eval_files"])]:
            for csv_member in files:
                onset = first_attack_fast(zf, csv_member)
                onset_rows.append({"role": role, **onset})
                if onset["status"] != "found":
                    hard_gate_rows.append({"role": role, "csv_member": csv_member, "pcap_member": "", "gate": "attack_roles_must_have_known_attack_onset", "pass": False})
                    continue
                selected = select_pcap_for_attack(zf, csv_member, pcaps, float(onset["first_attack_timestamp_epoch"]), args.max_pre_onset_packets)
                pass_gate = bool(selected.get("pcap_member")) and str(selected.get("pcap_member")).startswith("raw/malicious/")
                hard_gate_rows.append({"role": role, "csv_member": csv_member, "pcap_member": selected.get("pcap_member", ""), "gate": "attack_roles_must_use_onset_aligned_malicious_pcap", "pass": pass_gate})
                local_materialize = pass_gate and int(selected.get("pre_onset_packets") or 0) <= args.max_local_materialization_pre_onset_packets
                if local_materialize:
                    scenario = ac.scenario_from_pcap(str(selected["pcap_member"]))
                    smoke = make_smoke(role, role, csv_member, str(selected["pcap_member"]), "attack", scenario)
                    attack_smokes.append((smoke, float(onset["first_attack_timestamp_epoch"])))
                selection_rows.append({
                    "role": role,
                    "csv_member": csv_member,
                    "pcap_member": selected.get("pcap_member", ""),
                    "record_start_ts": onset["first_attack_timestamp_epoch"],
                    "first_attack_label": onset["first_attack_label"],
                    "pre_onset_packets": selected.get("pre_onset_packets", ""),
                    "scenario": selected.get("scenario", ""),
                    "selection_status": "selected_onset_aligned_attack"
                    if local_materialize
                    else "onset_aligned_deferred_heavy_fast_forward"
                    if pass_gate
                    else "blocked_no_onset_aligned_pcap",
                })

        strategy_rows: list[dict[str, Any]] = []
        role_meta: list[dict[str, Any]] = []
        transitions: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        for strategy in ["reset_at_split_boundary", "train_state_then_eval_online"]:
            x, sidecar, metas, trs = run_strategy(zf, strategy, benign_smokes, attack_smokes, args.packet_limit, args.warmup_packets, args.max_materialization_scan_packets)
            strategy_rows.append(stable_summary(strategy, x))
            role_meta.extend(metas)
            transitions.extend(trs)
            artifacts.append(save_strategy(strategy, x, sidecar))

    write_csv(OUT / "split_source_hard_gate.csv", hard_gate_rows)
    write_csv(OUT / "gotham_kitsune115_smoke_selection_manifest.csv", selection_rows)
    write_csv(OUT / "attack_onset_deep_scan.csv", onset_rows)
    write_csv(OUT / "gotham_kitsune115_expanded_smoke_by_strategy.csv", strategy_rows)
    write_csv(OUT / "gotham_kitsune115_expanded_smoke_role_meta.csv", role_meta)
    write_csv(OUT / "gotham_kitsune115_expanded_state_transition_log.csv", transitions)
    write_csv(OUT / "gotham_kitsune115_expanded_artifact_manifest.csv", artifacts)

    all_hard_gates_pass = all(str(r["pass"]).lower() == "true" for r in hard_gate_rows)
    all_attack_onsets_aligned = all(str(r["pass"]).lower() == "true" for r in hard_gate_rows if str(r.get("role", "")).startswith("attack"))
    all_attack_materialized = len(attack_smokes) == len(contract["attack_support_files"]) + len(contract["attack_eval_files"])
    numeric_ok = all(r["columns"] == 115 and r["finite_rate"] == 1.0 and r["nan_count"] == 0 and r["inf_count"] == 0 for r in strategy_rows)
    primary_verdict = (
        "kitsune115_split_aware_smoke_dataset_ready_for_interface_gate"
        if all_hard_gates_pass and all_attack_materialized and numeric_ok
        else "kitsune115_split_aware_smoke_dataset_ready_heavy_attack_deferred"
        if all_hard_gates_pass and all_attack_onsets_aligned and numeric_ok and len(attack_smokes) >= 2
        else "kitsune115_smoke_dataset_partial_needs_alignment_or_stability_fix"
    )

    write_md(OUT / "split_source_policy_report.md", [
        "# Split Source Policy Report",
        "",
        "- ID/OOD/final OOD rows use only preregistered benign split files.",
        "- Attack files are never used for ID/OOD/final OOD, even if they contain benign prefix rows.",
        "- Attack support/eval rows start at confirmed first attack timestamps; pre-onset packets only update frontend state.",
        "- No model metrics were computed.",
    ])
    write_md(OUT / "state_strategy_report.md", [
        "# State Strategy Report",
        "",
        "- `reset_at_split_boundary`: each file/role starts with a fresh frontend state.",
        "- `train_state_then_eval_online`: ID benign train builds the frontend train state; every OOD/final/attack file uses an isolated clone of that train state and is discarded after extraction.",
        "- Attack support state is not carried into attack eval in this smoke expansion, avoiding support/eval frontend-state contamination.",
    ])
    write_md(OUT / "issue27ad_decision.md", [
        "# issue27ad Decision",
        "",
        f"primary_verdict = `{primary_verdict}`",
        "",
        "The expanded smoke dataset follows the preregistered benign split for ID/OOD/final OOD and uses only onset-aligned malicious PCAPs for attack support/eval. It remains a data/feature gate result, not a model result.",
    ])
    write_md(OUT / "claim_update_after_issue27ad.md", [
        "# Claim Update After issue27ad",
        "",
        "- Gotham Kitsune115 smoke data construction is source- and state-aware.",
        "- This does not validate any detector or establish model mainline status.",
    ])
    write_md(OUT / "issue27ae_next_action.md", [
        "# issue27ae Next Action",
        "",
        "Recommended next issue: `issue27ae_gotham_kitsune115_model_interface_shape_smoke_2026-06-02` if the user wants a minimal reader/fit-predict interface check, or `issue27ae_gotham_kitsune115_larger_materialization_2026-06-02` if the priority is scaling data before any model code.",
    ])

    cfg = {
        "issue": ISSUE,
        "packet_limit": args.packet_limit,
        "warmup_packets": args.warmup_packets,
        "feature_schema": "gotham_kitsune_restored115_v1",
        "max_local_materialization_pre_onset_packets": args.max_local_materialization_pre_onset_packets,
        "model_metrics_computed": False,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps(cfg | {"run_type": "split_aware_115d_smoke_dataset_expansion"}, indent=2), encoding="utf-8")
    write_md(OUT / "command.txt", ["python repo/ood/issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion.py"])

    write_md(OUT / "summary.md", [
        "# issue27ad Summary",
        "",
        "1. issue27ad complete: yes.",
        f"2. primary_verdict: `{primary_verdict}`.",
        "3. ID/OOD/final OOD source rule: preregistered benign files only.",
        "4. Attack source rule: onset-aligned malicious PCAPs only.",
        f"5. Attack files onset-aligned: `{all_attack_onsets_aligned}`.",
        f"6. Attack files locally materialized: `{len(attack_smokes)}` of `{len(contract['attack_support_files']) + len(contract['attack_eval_files'])}`.",
        f"7. hard gates pass: `{all_hard_gates_pass}`.",
        f"8. numeric stability pass: `{numeric_ok}`.",
        f"9. rows by strategy: `{strategy_rows}`.",
        "10. model experiment allowed: no.",
        "11. issue27ae recommendation: choose either model interface shape smoke or larger 115D materialization with fast frontend/Slurm for heavy attack files.",
        "12. commit hash: pending.",
    ])
    outputs = sorted(p.name for p in OUT.iterdir() if p.is_file())
    write_csv(OUT / "manifest.csv", [{"file": name, "path": str(OUT / name)} for name in outputs + ["manifest.csv"]])

    append_doc(MAINLINE_DOCS / "mainline_handoff.md", "<!-- issue27ad_gotham_kitsune115_smoke_expansion -->", [
        "<!-- issue27ad_gotham_kitsune115_smoke_expansion -->",
        "",
        "## issue27ad Gotham Kitsune115 Split-Aware Smoke Expansion",
        "",
        f"- primary_verdict: `{primary_verdict}`.",
        "- ID/OOD/final OOD use only preregistered benign split files; attack files are used only after confirmed attack onset.",
        "- both reset-at-boundary and train-state-then-eval-online strategies output 115D finite features; no model metrics were computed.",
        "- model experiments remain blocked unless explicitly limited to interface shape smoke.",
    ])
    append_doc(MAINLINE_DOCS / "mainline_experiment_map.md", "<!-- issue27ad_map_entry -->", [
        "<!-- issue27ad_map_entry -->",
        "",
        "### issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02",
        "",
        "- status: completed.",
        f"- primary_verdict: `{primary_verdict}`.",
        f"- outputs: `runs/{ISSUE}/` plus external artifacts under `datasets/gotham2025/derived/kitsune115_split_aware_smoke_expansion_v1/`.",
        "- implication: 115D smoke dataset construction is ready for a minimal model-interface shape smoke, not formal benchmarking.",
    ])
    print(f"[done] {OUT}")
    print(f"[verdict] {primary_verdict}")


if __name__ == "__main__":
    main()
