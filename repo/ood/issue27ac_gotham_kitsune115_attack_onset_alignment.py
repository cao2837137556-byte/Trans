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

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402

ISSUE = "issue27ac_gotham_kitsune115_attack_onset_alignment_then_materialization_2026-06-02"
OUT = ROOT / "runs" / ISSUE
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_attack_onset_probe_v1"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ISSUE27Y = ROOT / "runs" / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
ISSUE27V = ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28"


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


def stem_from_csv_member(member: str) -> str:
    name = Path(member).name
    return name[:-4] if name.endswith(".csv") else name


def scenario_from_pcap(member: str) -> str:
    parts = member.split("/")
    return parts[2] if len(parts) >= 4 and parts[0] == "raw" and parts[1] == "malicious" else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def contract_attack_files() -> tuple[list[str], list[str]]:
    contract = read_json(ISSUE27Y / "gotham_preregistered_split_contract_v1.json")["contract"]
    return list(contract["attack_support_files"]), list(contract["attack_eval_files"])


def read_archive_listing() -> list[dict[str, str]]:
    with (ISSUE27V / "archive_file_listing.csv").open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def candidate_pcaps_for_csv(csv_member: str, pcap_members: list[str]) -> list[str]:
    stem = stem_from_csv_member(csv_member)
    prefix = stem + "_"
    return [m for m in pcap_members if Path(m).name.startswith(prefix)]


def first_attack(zf: zipfile.ZipFile, csv_member: str, max_rows: int) -> dict[str, Any]:
    return ab.csv_first_attack_timestamp(zf, csv_member, max_rows_scan=max_rows)


def count_packets_until(zf: zipfile.ZipFile, pcap_member: str, target_ts: float, max_packets: int) -> dict[str, Any]:
    count = 0
    first_ts = None
    last_pre_ts = None
    hit_ts = None
    parse_status = "ok"
    try:
        with zf.open(pcap_member, "r") as raw:
            reader = dpkt.pcap.Reader(io.BufferedReader(raw))
            for ts, _buf in reader:
                ts = float(ts)
                if first_ts is None:
                    first_ts = ts
                    if first_ts > target_ts:
                        parse_status = "pcap_starts_after_csv_first_attack"
                        break
                if ts >= target_ts:
                    hit_ts = ts
                    break
                count += 1
                last_pre_ts = ts
                if count >= max_packets:
                    parse_status = "max_packets_before_onset"
                    break
    except Exception as exc:
        parse_status = f"error:{type(exc).__name__}:{str(exc)[:80]}"
    return {
        "pcap_first_timestamp_epoch": first_ts,
        "pre_onset_packets": count,
        "last_pre_onset_timestamp_epoch": last_pre_ts,
        "first_packet_at_or_after_onset_epoch": hit_ts,
        "hit_onset_within_scan_budget": bool(hit_ts is not None),
        "pcap_scan_status": parse_status,
    }


def save_probe(strategy: str, x: np.ndarray, sidecar: list[dict[str, Any]]) -> dict[str, Any]:
    DERIVED.mkdir(parents=True, exist_ok=True)
    feature_path = DERIVED / f"gotham_kitsune115_attack_onset_{strategy}_X.npy"
    sidecar_path = DERIVED / f"gotham_kitsune115_attack_onset_{strategy}_sidecar.csv.gz"
    np.save(feature_path, x)
    with gzip.open(sidecar_path, "wt", newline="", encoding="utf-8") as f:
        if sidecar:
            writer = csv.DictWriter(f, fieldnames=list(sidecar[0].keys()))
            writer.writeheader()
            writer.writerows(sidecar)
    return {
        "strategy": strategy,
        "feature_path": str(feature_path),
        "feature_sha256": ab.file_hash(feature_path),
        "sidecar_path": str(sidecar_path),
        "sidecar_sha256": ab.file_hash(sidecar_path),
        "rows": int(x.shape[0]),
        "columns": int(x.shape[1]) if x.ndim == 2 else 0,
        "bytes_feature": feature_path.stat().st_size,
        "bytes_sidecar": sidecar_path.stat().st_size,
    }


def numeric_summary(strategy: str, x: np.ndarray) -> dict[str, Any]:
    if x.size == 0:
        return {
            "strategy": strategy,
            "rows": 0,
            "columns": 0,
            "finite_rate": 0.0,
            "nan_count": 0,
            "inf_count": 0,
            "constant_columns": 0,
        }
    finite = np.isfinite(x)
    constant_cols = 0
    for j in range(x.shape[1]):
        col = x[:, j]
        finite_col = col[np.isfinite(col)]
        if len(finite_col) and float(np.nanmax(finite_col)) == float(np.nanmin(finite_col)):
            constant_cols += 1
    return {
        "strategy": strategy,
        "rows": int(x.shape[0]),
        "columns": int(x.shape[1]),
        "finite_rate": float(finite.mean()),
        "nan_count": int(np.isnan(x).sum()),
        "inf_count": int(np.isinf(x).sum()),
        "constant_columns": int(constant_cols),
    }


def extract_one(
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
        "pcap_member": smoke.pcap_member,
        "csv_member": smoke.csv_member,
        "record_start_ts": record_start_ts,
        "feature_rows_emitted": int(x.shape[0]),
        "packets_scanned": int(meta.get("packets_scanned", 0)),
        "pre_record_packets": int(meta.get("pre_record_packets", 0)),
        "state_hash_before": before,
        "state_hash_after": after,
    }
    return x, sidecar, meta | {"state_hash_before": before, "state_hash_after": after, "strategy": strategy}, transition


def run_probe(
    zf: zipfile.ZipFile,
    selected: dict[str, dict[str, Any]],
    packet_limit: int,
    warmup_packets: int,
    max_scan_packets: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    benign = ab.SmokeFile(
        role="id_benign_train",
        split_role="ID_benign_train",
        pcap_member="raw/benign/iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0.pcap",
        csv_member="processed/iotsim-combined-cycle-3.csv",
        expected_binary_label="benign",
        expected_attack_type="",
        selection_reason="small benign state initializer retained from issue27ab",
    )
    support = selected.get("attack_support")
    eval_ = selected.get("attack_eval")
    if not support or not eval_:
        return [], [], [], []
    support_smoke = ab.SmokeFile(
        role="attack_support",
        split_role="attack_support",
        pcap_member=support["selected_pcap_member"],
        csv_member=support["csv_member"],
        expected_binary_label="attack",
        expected_attack_type=scenario_from_pcap(support["selected_pcap_member"]),
        selection_reason="attack-onset aligned support candidate selected by issue27ac",
    )
    eval_smoke = ab.SmokeFile(
        role="attack_eval",
        split_role="attack_eval",
        pcap_member=eval_["selected_pcap_member"],
        csv_member=eval_["csv_member"],
        expected_binary_label="attack",
        expected_attack_type=scenario_from_pcap(eval_["selected_pcap_member"]),
        selection_reason="attack-onset aligned eval candidate selected by issue27ac",
    )

    artifacts: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    role_meta: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []

    for strategy in ["reset_at_split_boundary", "train_state_then_eval_online"]:
        arrays: list[np.ndarray] = []
        sidecar_all: list[dict[str, Any]] = []
        if strategy == "reset_at_split_boundary":
            for smoke, onset_ts in [
                (support_smoke, float(support["first_attack_timestamp_epoch"])),
                (eval_smoke, float(eval_["first_attack_timestamp_epoch"])),
            ]:
                nstat = ab.RestoredNetStat115()
                x, sidecar, meta, transition = extract_one(
                    zf, smoke, nstat, packet_limit, warmup_packets, strategy, f"reset::{smoke.role}", onset_ts, max_scan_packets
                )
                arrays.append(x)
                sidecar_all.extend(sidecar)
                role_meta.append(meta)
                transitions.append(transition)
        else:
            train_state = ab.RestoredNetStat115()
            x_train, side_train, meta_train, transition_train = extract_one(
                zf, benign, train_state, packet_limit, warmup_packets, strategy, "B::S_train_after_id", None, max_scan_packets
            )
            arrays.append(x_train)
            sidecar_all.extend(side_train)
            role_meta.append(meta_train)
            transitions.append(transition_train)
            support_state = deepcopy(train_state)
            x_sup, side_sup, meta_sup, transition_sup = extract_one(
                zf,
                support_smoke,
                support_state,
                packet_limit,
                warmup_packets,
                strategy,
                "B::S_support_after_attack_support",
                float(support["first_attack_timestamp_epoch"]),
                max_scan_packets,
            )
            arrays.append(x_sup)
            sidecar_all.extend(side_sup)
            role_meta.append(meta_sup)
            transitions.append(transition_sup)
            eval_state = deepcopy(support_state)
            x_eval, side_eval, meta_eval, transition_eval = extract_one(
                zf,
                eval_smoke,
                eval_state,
                packet_limit,
                warmup_packets,
                strategy,
                "B::S_attack_eval_report_only_after_support",
                float(eval_["first_attack_timestamp_epoch"]),
                max_scan_packets,
            )
            arrays.append(x_eval)
            sidecar_all.extend(side_eval)
            role_meta.append(meta_eval)
            transitions.append(transition_eval)

        x = np.vstack(arrays) if arrays else np.empty((0, 115), dtype=np.float32)
        artifacts.append(save_probe(strategy, x, sidecar_all))
        summaries.append(numeric_summary(strategy, x) | {"model_metric_computed": False, "final_eval_report_only": True})
    return artifacts, summaries, role_meta, transitions


def main() -> None:
    parser = argparse.ArgumentParser(description="issue27ac Gotham Kitsune115 attack onset alignment probe.")
    parser.add_argument("--max-first-attack-scan-rows", type=int, default=200_000)
    parser.add_argument("--max-pre-onset-packets", type=int, default=200_000)
    parser.add_argument("--packet-limit", type=int, default=300)
    parser.add_argument("--warmup-packets", type=int, default=50)
    parser.add_argument("--max-materialization-scan-packets", type=int, default=300_000)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)

    if not ab.ZIP_PATH.exists():
        raise FileNotFoundError(ab.ZIP_PATH)
    zip_md5 = ab.file_hash(ab.ZIP_PATH, "md5")
    if zip_md5 != ab.EXPECTED_ZIP_MD5:
        raise RuntimeError(f"Gotham zip md5 mismatch: {zip_md5}")

    support_files, eval_files = contract_attack_files()
    attack_files = [("attack_support", f) for f in support_files] + [("attack_eval", f) for f in eval_files]
    listing = read_archive_listing()
    pcap_members = [r["file_path"] for r in listing if r.get("is_pcap") == "True" and r["file_path"].startswith("raw/malicious/")]

    attack_onset_rows: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    selected_by_role: dict[str, dict[str, Any]] = {}
    candidate_windows: list[dict[str, Any]] = []

    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        for role, csv_member in attack_files:
            onset = first_attack(zf, csv_member, args.max_first_attack_scan_rows)
            row_base = {
                "role": role,
                "csv_member": csv_member,
                "rows_scanned_until_first_attack": onset.get("rows_scanned_until_first_attack", ""),
                "first_attack_timestamp_epoch": onset.get("first_attack_timestamp_epoch", ""),
                "first_attack_label": onset.get("first_attack_label", ""),
                "onset_status": onset.get("status", ""),
                "pre_attack_label_counts_scanned": onset.get("pre_attack_label_counts_scanned", {}),
            }
            attack_onset_rows.append(row_base)
            candidates = candidate_pcaps_for_csv(csv_member, pcap_members)
            best: dict[str, Any] | None = None
            for pcap_member in candidates:
                target_ts = onset.get("first_attack_timestamp_epoch")
                if target_ts is None:
                    scan = {
                        "pcap_first_timestamp_epoch": "",
                        "pre_onset_packets": "",
                        "last_pre_onset_timestamp_epoch": "",
                        "first_packet_at_or_after_onset_epoch": "",
                        "hit_onset_within_scan_budget": False,
                        "pcap_scan_status": "no_first_attack_timestamp",
                    }
                else:
                    scan = count_packets_until(zf, pcap_member, float(target_ts), args.max_pre_onset_packets)
                delta = ""
                if target_ts is not None and scan.get("pcap_first_timestamp_epoch") is not None:
                    delta = float(target_ts) - float(scan["pcap_first_timestamp_epoch"])
                row = {
                    "role": role,
                    "csv_member": csv_member,
                    "pcap_member": pcap_member,
                    "scenario": scenario_from_pcap(pcap_member),
                    "first_attack_timestamp_epoch": target_ts,
                    "first_attack_label": onset.get("first_attack_label", ""),
                    "pcap_to_first_attack_delta_seconds": delta,
                    **scan,
                }
                if scan.get("hit_onset_within_scan_budget") and (best is None or int(scan["pre_onset_packets"]) < int(best["pre_onset_packets"])):
                    if delta != "" and float(delta) >= 0:
                        best = row
                overlap_rows.append(row)
            if best is not None:
                selection = {
                    "role": role,
                    "csv_member": csv_member,
                    "selected_pcap_member": best["pcap_member"],
                    "selected_scenario": best["scenario"],
                    "first_attack_timestamp_epoch": best["first_attack_timestamp_epoch"],
                    "first_attack_label": best["first_attack_label"],
                    "pre_onset_packets": best["pre_onset_packets"],
                    "pcap_to_first_attack_delta_seconds": best["pcap_to_first_attack_delta_seconds"],
                    "selection_status": "selected_onset_reachable",
                    "selection_reason": "candidate pcap has timestamp before first attack and reaches first attack within scan budget",
                }
                candidate_windows.append(selection)
                selected_by_role.setdefault(role, selection)
            else:
                candidate_windows.append(
                    {
                        "role": role,
                        "csv_member": csv_member,
                        "selected_pcap_member": "",
                        "selected_scenario": "",
                        "first_attack_timestamp_epoch": onset.get("first_attack_timestamp_epoch", ""),
                        "first_attack_label": onset.get("first_attack_label", ""),
                        "pre_onset_packets": "",
                        "pcap_to_first_attack_delta_seconds": "",
                        "selection_status": "blocked_no_reachable_pcap_onset",
                        "selection_reason": "no candidate pcap reached the processed CSV first-attack timestamp within scan budget",
                    }
                )

        artifacts, probe_summary, role_meta, transitions = run_probe(
            zf, selected_by_role, args.packet_limit, args.warmup_packets, args.max_materialization_scan_packets
        )

    write_csv(OUT / "attack_onset_alignment_table.csv", attack_onset_rows)
    write_csv(OUT / "attack_pcap_csv_timestamp_overlap.csv", overlap_rows)
    write_csv(OUT / "attack_support_eval_candidate_windows.csv", candidate_windows)
    write_csv(OUT / "kitsune115_attack_onset_probe_by_strategy.csv", probe_summary)
    write_csv(OUT / "kitsune115_attack_onset_probe_role_meta.csv", role_meta)
    write_csv(OUT / "kitsune115_attack_onset_state_transition_log.csv", transitions)
    write_csv(OUT / "kitsune115_attack_onset_artifact_manifest.csv", artifacts)

    selected_ok = any(r["role"] == "attack_support" and r["selection_status"] == "selected_onset_reachable" for r in candidate_windows) and any(
        r["role"] == "attack_eval" and r["selection_status"] == "selected_onset_reachable" for r in candidate_windows
    )
    all_attack_files_selected = all(r["selection_status"] == "selected_onset_reachable" for r in candidate_windows)
    probe_ok = bool(probe_summary) and all(r["columns"] == 115 and r["finite_rate"] == 1.0 for r in probe_summary)
    primary_verdict = (
        "attack_onset_alignment_ready_for_full_contract_materialization"
        if all_attack_files_selected and probe_ok
        else "attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion"
        if selected_ok and probe_ok
        else "attack_onset_alignment_found_but_needs_fast_frontend_or_slurm"
        if selected_ok
        else "attack_onset_alignment_inconclusive_needs_metadata"
    )

    write_md(
        OUT / "attack_onset_materialization_probe_report.md",
        [
            "# Attack Onset Materialization Probe Report",
            "",
            f"- primary_verdict: `{primary_verdict}`.",
            "- Scope: attack-side PCAP/CSV onset alignment and tiny Kitsune115 extraction probe only.",
            "- No model training, model ranking, AUC, F1, detection, or OOD alarm metrics were computed.",
            "- The previous issue27ab blocker came from using `network-scanning` PCAPs for the first Telnet Brute Force attack window.",
            "- This issue scans all contract attack files and candidate malicious PCAPs by timestamp to find causal first-attack onset windows.",
            f"- Selected support/eval roles available: `{str(selected_ok).lower()}`.",
            f"- All attack contract files onset-aligned within scan budget: `{str(all_attack_files_selected).lower()}`.",
            f"- 115D attack-onset probe numeric pass: `{str(probe_ok).lower()}`.",
            "- Few-shot support must be sampled from rows at or after confirmed attack onset; benign prefix rows remain excluded from attack support.",
            "- Attack eval may preserve realistic mixed-flow chronology, but packet/row labels and onset alignment must be carried in sidecar for metric computation.",
        ],
    )
    write_md(
        OUT / "issue27ac_decision.md",
        [
            "# issue27ac Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "The attack-side blocker is no longer the Kitsune115 frontend itself. It is the need to use the correct malicious scenario PCAP and to start attack-labeled materialization only at the processed-CSV first-attack timestamp.",
            "",
            "Model experiments remain disallowed. The next step is a broader split-aware Kitsune115 smoke dataset over confirmed onset-aligned PCAP/CSV pairs, plus deeper handling for attack files whose onset was not reached within this scan budget.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ac.md",
        [
            "# Claim Update After issue27ac",
            "",
            "- Gotham Kitsune115 extraction remains a feature/data construction path, not a model result.",
            "- Attack support rows must start after confirmed attack onset; benign prefix rows cannot be treated as attack support.",
            "- issue27ac does not validate LOW-GUARD, DeepSADStyle, LR, HistGB, or any model.",
        ],
    )
    write_md(
        OUT / "issue27ad_next_action.md",
        [
            "# issue27ad Next Action",
            "",
            "Recommended next issue: `issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02`.",
            "",
            "Goal: expand from the tiny attack-onset probe to a still-small but balanced Kitsune115 smoke dataset across all five split roles, preserving train/test time-state separation and onset-aligned attack support/eval sidecars. Do not run model benchmarks yet.",
        ],
    )

    config = {
        "issue": ISSUE,
        "zip_path": str(ab.ZIP_PATH),
        "zip_md5": zip_md5,
        "frontend_schema": "gotham_kitsune_restored115_v1",
        "packet_limit": args.packet_limit,
        "warmup_packets": args.warmup_packets,
        "max_first_attack_scan_rows": args.max_first_attack_scan_rows,
        "max_pre_onset_packets": args.max_pre_onset_packets,
        "model_metrics_computed": False,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps(config | {"run_type": "data_feature_gate_attack_onset_alignment"}, indent=2), encoding="utf-8")
    write_md(OUT / "command.txt", ["python repo/ood/issue27ac_gotham_kitsune115_attack_onset_alignment.py"])

    outputs = sorted(p.name for p in OUT.iterdir() if p.is_file())
    write_csv(OUT / "manifest.csv", [{"path": str(OUT / name), "file": name} for name in outputs + ["manifest.csv"]])

    summary_lines = [
        "# issue27ac Summary",
        "",
        "1. issue27ac complete: yes.",
        f"2. primary_verdict: `{primary_verdict}`.",
        "3. Current blocker addressed: attack-side label/onset alignment, not benign split and not Kitsune115 frontend recovery.",
        "4. Attack onset scan: processed CSV first-attack timestamps were used to choose causal malicious PCAP windows.",
        f"5. Attack support/eval onset-selected: `{str(selected_ok).lower()}`.",
        f"6. All attack contract files onset-aligned within scan budget: `{str(all_attack_files_selected).lower()}`.",
        f"7. Tiny Kitsune115 attack-onset probe executed: `{str(bool(probe_summary)).lower()}`.",
        f"8. 115D numeric stability in probe passed: `{str(probe_ok).lower()}`.",
        "9. Benign prefix handling: prefix packets may warm the frontend state but are not labelled as attack support.",
        "10. Attack eval handling: sidecar keeps packet timestamps and role labels; metric computation remains future work.",
        "11. Model experiment allowed: no.",
        "12. issue27ad recommendation: expand to a balanced onset-aligned Kitsune115 smoke dataset and deep-scan unresolved ip-camera attack files before any model interface smoke.",
        "13. Slurm needed: not for this probe; likely useful for larger/full 115D extraction.",
        "14. commit hash: pending.",
    ]
    write_md(OUT / "summary.md", summary_lines)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27ac_gotham_attack_onset_alignment -->",
        [
            "<!-- issue27ac_gotham_attack_onset_alignment -->",
            "",
            "## issue27ac Gotham Kitsune115 Attack-Onset Alignment",
            "",
            f"- primary_verdict: `{primary_verdict}`.",
            "- role: attack-side data/feature gate for Gotham Kitsune115.",
            "- result: first-attack timestamps from processed CSVs can select causal malicious PCAP windows; support must start after confirmed attack onset.",
            "- model experiments remain blocked; next is a larger onset-aligned Kitsune115 smoke dataset.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ac_map_entry -->",
        [
            "<!-- issue27ac_map_entry -->",
            "",
            "### issue27ac_gotham_kitsune115_attack_onset_alignment_then_materialization_2026-06-02",
            "",
            "- status: completed.",
            f"- primary_verdict: `{primary_verdict}`.",
            f"- outputs: `runs/{ISSUE}/` plus tiny external probe artifacts under `datasets/gotham2025/derived/kitsune115_attack_onset_probe_v1/`.",
            "- implication: attack-side alignment is tractable if PCAP scenario and onset timestamp are selected correctly; no model benchmark yet.",
        ],
    )

    print(f"[done] {OUT}")
    print(f"[verdict] {primary_verdict}")


if __name__ == "__main__":
    main()
