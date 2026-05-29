from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = ROOT.parents[1]
OUT_DIR = ROOT / "runs" / "issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
DATASETS_ROOT = PAPER_ROOT / "datasets"

ISSUE27S = ROOT / "runs" / "issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28"
KITNET_ROOT = PAPER_ROOT / "KitNET-py-master" / "KitNET-py-master"
WORKTREES_DATA = PAPER_ROOT / "worktrees" / "data"


def ensure_out() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def write_text(name: str, text: str) -> None:
    (OUT_DIR / name).write_text(text, encoding="utf-8")


def write_json(name: str, obj: object) -> None:
    (OUT_DIR / name).write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(name: str, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    keys: list[str] = []
    if fieldnames is None:
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with (OUT_DIR / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_small(path: Path, limit: int = 50_000_000) -> str:
    if not path.exists():
        return "missing"
    if path.stat().st_size > limit:
        return f"skipped_large_{path.stat().st_size}_bytes"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_once(path: Path, marker: str, block: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in old:
        return
    sep = "" if old == "" or old.endswith("\n") else "\n"
    path.write_text(old + sep + block, encoding="utf-8")


def file_row(path: Path, dataset: str, kind: str, notes: str) -> dict:
    return {
        "dataset": dataset,
        "asset_path": str(path),
        "asset_kind": kind,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else "missing",
        "sha256": sha256_small(path),
        "notes": notes,
    }


def local_inventory() -> list[dict]:
    rows: list[dict] = []
    rows.append(
        file_row(
            KITNET_ROOT / "Mirai_dataset.csv",
            "full_mirai",
            "feature_csv_dirty116",
            "Full Mirai feature table only; paired raw missing confirmed by issue27s/user.",
        )
    )
    rows.append(file_row(KITNET_ROOT / "mirai_labels.csv", "full_mirai", "label_sidecar", "Labels only; no timestamp/capture/source."))
    rows.append(file_row(KITNET_ROOT / "mirai3.csv", "official_mirai_100k", "feature_csv_115d", "Related smaller Mirai feature path."))
    rows.append(file_row(KITNET_ROOT / "mirai3_ts.csv", "official_mirai_100k", "timestamp_sidecar", "Timestamp sidecar for 100k path only, not full 764k."))

    public_raw = KITNET_ROOT / "public_data" / "raw"
    for p in sorted(public_raw.glob("*")) if public_raw.exists() else []:
        if p.is_file():
            name = "local_iot23_or_ciciot_public_data"
            notes = "Local public_data asset; useful for intake precheck but not paired with full Mirai."
            rows.append(file_row(p, name, p.suffix.lower().lstrip(".") or "file", notes))

    ton = WORKTREES_DATA / "Train_Test_Network_dataset" / "train_test_network.csv"
    rows.append(file_row(ton, "local_ton_iot_train_test_network", "flow_csv", "Local ToN-IoT style network CSV; labels present, timestamp not obvious in header."))

    botiot_dir = WORKTREES_DATA / "5%" / "All features"
    for p in sorted(botiot_dir.glob("*.csv")) if botiot_dir.exists() else []:
        rows.append(file_row(p, "local_botiot_5pc_all_features", "flow_csv", "Local BoT-IoT 5% all-feature CSV; timestamp and labels present, benign count reported tiny in issue27l."))

    rows.append(file_row(WORKTREES_DATA / "5% (1).zip", "local_botiot_archive", "zip", "Archive present; do not stage or unpack blindly."))
    rows.append(file_row(WORKTREES_DATA / "Train_Test_Network_dataset.zip", "local_ton_iot_archive", "zip", "Archive present; do not stage or unpack blindly."))
    return rows


def candidate_rows() -> list[dict]:
    return [
        {
            "candidate": "Gotham Dataset 2025",
            "raw_pcap_available": "yes",
            "flow_records_available": "csv_available",
            "labelled_csv_available": "yes",
            "labels_available": "yes",
            "timestamp_available": "yes_in_pcap_or_metadata_expected",
            "packet_or_flow_order_available": "yes",
            "benign_multi_phase_available": "likely_yes_multi_device_multi_gateway",
            "multiple_capture_or_environment_available": "yes_device_gateway_topology",
            "attack_labels_available": "yes",
            "support_eval_disjoint_possible": "likely_yes",
            "final_ood_eval_possible": "likely_yes",
            "row_order_artifact_auditable": "yes_with_raw_and_metadata",
            "source_capture_metadata_available": "yes_metadata_reported",
            "feature_extraction_path_available": "yes_raw_pcap_to_kitsune_or_flow",
            "estimated_size": "23.8GB",
            "local_available_or_external_needed": "external_needed",
            "license_or_access_constraint": "CC-BY-4.0 on Zenodo; large download requires confirmation",
            "download_url_or_source_page": "https://zenodo.org/records/14502760",
            "fit_for_low_ood_alert_problem": "yes",
            "risk_level": "medium",
            "notes": "Best first candidate: raw PCAP, CSV, metadata, labels, realistic IoT home topology. Need verify benign phase/device splits after metadata intake.",
        },
        {
            "candidate": "ToN-IoT / TON_IoT network",
            "raw_pcap_available": "reported_yes_or_logs",
            "flow_records_available": "yes",
            "labelled_csv_available": "yes",
            "labels_available": "yes",
            "timestamp_available": "yes_in_security_events/raw; local train_test CSV lacks obvious timestamp",
            "packet_or_flow_order_available": "yes",
            "benign_multi_phase_available": "likely_yes_multi_source_IIoT_IoT",
            "multiple_capture_or_environment_available": "yes",
            "attack_labels_available": "yes",
            "support_eval_disjoint_possible": "yes",
            "final_ood_eval_possible": "likely_yes",
            "row_order_artifact_auditable": "yes_if_raw_or_security_events_used",
            "source_capture_metadata_available": "likely_yes",
            "feature_extraction_path_available": "yes_if_raw_or_logs_obtained",
            "estimated_size": "unknown_large; local network CSV 29.9MB",
            "local_available_or_external_needed": "partial_local_external_for_raw_metadata",
            "license_or_access_constraint": "UNSW dataset access/page; likely manual download",
            "download_url_or_source_page": "https://research.unsw.edu.au/projects/toniot-datasets",
            "fit_for_low_ood_alert_problem": "yes",
            "risk_level": "medium_high",
            "notes": "Strong IoT/IIoT semantic fit, but local CSV alone is not enough; need raw/log/timestamp metadata package.",
        },
        {
            "candidate": "CICIoT2023",
            "raw_pcap_available": "yes_reported",
            "flow_records_available": "yes",
            "labelled_csv_available": "yes",
            "labels_available": "yes",
            "timestamp_available": "likely_in_pcap_or_flow_order",
            "packet_or_flow_order_available": "yes",
            "benign_multi_phase_available": "likely_yes_many_devices_scenarios",
            "multiple_capture_or_environment_available": "yes_many_iot_devices",
            "attack_labels_available": "yes_33_attacks_reported",
            "support_eval_disjoint_possible": "yes",
            "final_ood_eval_possible": "likely_yes",
            "row_order_artifact_auditable": "yes_with_pcap_or_per_scenario_files",
            "source_capture_metadata_available": "scenario_file_metadata_expected",
            "feature_extraction_path_available": "yes_raw_pcap_or_csv",
            "estimated_size": "very_large",
            "local_available_or_external_needed": "small_local_subset_only_external_needed",
            "license_or_access_constraint": "CIC dataset access/download; large size requires confirmation",
            "download_url_or_source_page": "https://www.unb.ca/cic/datasets/iotdataset-2023.html",
            "fit_for_low_ood_alert_problem": "maybe",
            "risk_level": "high",
            "notes": "Good fallback if Gotham/ToN fail; major risk is volume and verifying benign OOD phases rather than scenario/file artifact.",
        },
        {
            "candidate": "Local IoT-23 public_data",
            "raw_pcap_available": "yes_local",
            "flow_records_available": "zeek_labeled_logs_local",
            "labelled_csv_available": "small_subsets_local",
            "labels_available": "yes",
            "timestamp_available": "yes_in_pcap_logs",
            "packet_or_flow_order_available": "yes",
            "benign_multi_phase_available": "weak_single_benign_capture_seen",
            "multiple_capture_or_environment_available": "partial_multiple_captures_but benign limited",
            "attack_labels_available": "yes_malicious_capture",
            "support_eval_disjoint_possible": "yes",
            "final_ood_eval_possible": "weak",
            "row_order_artifact_auditable": "yes",
            "source_capture_metadata_available": "capture_path_level",
            "feature_extraction_path_available": "yes_raw_pcap",
            "estimated_size": "local pcap total under 200MB",
            "local_available_or_external_needed": "local_available",
            "license_or_access_constraint": "local public data; original source Stratosphere/CTU",
            "download_url_or_source_page": "https://www.stratosphereips.org/datasets-iot23",
            "fit_for_low_ood_alert_problem": "maybe",
            "risk_level": "high",
            "notes": "Can be used for cheap semantic-gate rehearsal, not current main candidate because OOD benign looks limited.",
        },
        {
            "candidate": "BoT-IoT / NF-BoT-IoT",
            "raw_pcap_available": "reported_yes_for_original; local only csv_subset",
            "flow_records_available": "yes",
            "labelled_csv_available": "yes",
            "labels_available": "yes",
            "timestamp_available": "yes_in_local_flow_csv",
            "packet_or_flow_order_available": "yes",
            "benign_multi_phase_available": "unclear_local_benign_tiny",
            "multiple_capture_or_environment_available": "unclear",
            "attack_labels_available": "yes",
            "support_eval_disjoint_possible": "yes",
            "final_ood_eval_possible": "weak_until_full_benign_verified",
            "row_order_artifact_auditable": "yes_if raw/full available",
            "source_capture_metadata_available": "unclear",
            "feature_extraction_path_available": "yes_if raw/full available",
            "estimated_size": "large",
            "local_available_or_external_needed": "partial_local_external_needed_for_full_raw",
            "license_or_access_constraint": "UNSW/IMPACT access; manual download likely",
            "download_url_or_source_page": "https://research.unsw.edu.au/projects/bot-iot-dataset",
            "fit_for_low_ood_alert_problem": "maybe",
            "risk_level": "high",
            "notes": "Local 5% has only 477 benign rows per prior inventory; not enough as-is for low-OOD-alert benchmark.",
        },
        {
            "candidate": "UNSW-IoTraffic",
            "raw_pcap_available": "yes_reported",
            "flow_records_available": "yes_reported",
            "labelled_csv_available": "normal_only",
            "labels_available": "not_attack_labels",
            "timestamp_available": "yes",
            "packet_or_flow_order_available": "yes",
            "benign_multi_phase_available": "yes_multi_iot_devices",
            "multiple_capture_or_environment_available": "yes",
            "attack_labels_available": "no",
            "support_eval_disjoint_possible": "not_standalone",
            "final_ood_eval_possible": "benign_ood_only",
            "row_order_artifact_auditable": "yes",
            "source_capture_metadata_available": "yes_expected",
            "feature_extraction_path_available": "yes",
            "estimated_size": "unknown",
            "local_available_or_external_needed": "external_needed",
            "license_or_access_constraint": "UNSW dataset access",
            "download_url_or_source_page": "https://iotanalytics.unsw.edu.au/iottraces.html",
            "fit_for_low_ood_alert_problem": "no_standalone_but_good_ood_benign_auxiliary",
            "risk_level": "medium",
            "notes": "Excellent OOD benign source candidate, but not a full attack benchmark without paired attack data.",
        },
        {
            "candidate": "GeNIS 2025",
            "raw_pcap_available": "yes_pcapng_reported",
            "flow_records_available": "yes_csv_flows_reported",
            "labelled_csv_available": "yes",
            "labels_available": "yes",
            "timestamp_available": "yes_expected",
            "packet_or_flow_order_available": "yes",
            "benign_multi_phase_available": "yes_normal_activity_reported",
            "multiple_capture_or_environment_available": "likely_scenario_based",
            "attack_labels_available": "yes_sequential_attack_scenarios",
            "support_eval_disjoint_possible": "likely_yes",
            "final_ood_eval_possible": "maybe",
            "row_order_artifact_auditable": "yes_with_pcapng_metadata",
            "source_capture_metadata_available": "metadata_expected",
            "feature_extraction_path_available": "yes_pcapng_or_flows",
            "estimated_size": "large",
            "local_available_or_external_needed": "external_needed",
            "license_or_access_constraint": "Zenodo/data access; verify license",
            "download_url_or_source_page": "https://zenodo.org/records/14938238",
            "fit_for_low_ood_alert_problem": "maybe",
            "risk_level": "medium",
            "notes": "Promising non-IoT IDS fallback; lower topical match than IoT candidates but strong provenance shape.",
        },
    ]


def gate_rows(candidates: list[dict]) -> list[dict]:
    rows = []
    for c in candidates:
        fit = c["fit_for_low_ood_alert_problem"]
        if c["candidate"] == "Gotham Dataset 2025":
            priority = "P0"
            gate_verdict = "candidate_ready_for_metadata_intake_after_download_confirmation"
        elif c["candidate"] == "ToN-IoT / TON_IoT network":
            priority = "P1"
            gate_verdict = "candidate_ready_for_access_metadata_intake"
        elif c["candidate"] == "Local IoT-23 public_data":
            priority = "P1_auxiliary"
            gate_verdict = "local_auxiliary_ready_for_semantic_gate_rehearsal"
        elif c["candidate"] == "CICIoT2023":
            priority = "P2"
            gate_verdict = "candidate_promising_but_size_and_semantics_need_confirmation"
        elif c["candidate"] == "UNSW-IoTraffic":
            priority = "P2_auxiliary"
            gate_verdict = "ood_benign_auxiliary_not_standalone"
        else:
            priority = "P3"
            gate_verdict = "candidate_needs_more_metadata_before_intake"
        rows.append(
            {
                "candidate": c["candidate"],
                "priority": priority,
                "gate_verdict": gate_verdict,
                "fit_for_low_ood_alert_problem": fit,
                "blocking_risks": c["notes"],
                "requires_user_download_confirmation": c["local_available_or_external_needed"] != "local_available",
                "next_gate": "metadata_index_download_or_local_manifest; no model training",
            }
        )
    return rows


def manifest() -> None:
    rows = []
    for p in sorted(OUT_DIR.iterdir()):
        if p.is_file() and p.name != "manifest.csv":
            rows.append({"file": p.name, "size_bytes": p.stat().st_size, "sha256": sha256_small(p, 1_000_000_000)})
    write_csv("manifest.csv", rows)


def main() -> None:
    ensure_out()
    local_rows = local_inventory()
    candidates = candidate_rows()
    gates = gate_rows(candidates)
    primary_verdict = "second_dataset_candidates_need_manual_access_or_download_confirmation"

    write_csv("local_dataset_inventory.csv", local_rows)
    write_csv("second_dataset_candidate_inventory.csv", candidates)
    write_csv("dataset_gate_precheck_table.csv", gates)

    write_text(
        "full_mirai_raw_missing_confirmed.md",
        """# Full Mirai Paired Raw Missing Confirmed

User confirmation plus issue27s local inventory establish that the current local full Mirai download consists of feature CSV + label sidecar, not the paired raw pcap/input stream for `Mirai_dataset.csv`.

Consequences:

- Do not spend further large local-search time trying to rescue full Mirai raw provenance.
- Do not use full Mirai anonymous_clean115 as the main low-OOD-alert benchmark.
- Full Mirai remains diagnostic only unless paired raw/extractor-compatible provenance is later acquired.
- The project remains in Data validity gate; model execution remains blocked.
""",
    )

    intake_report = """# Second Dataset Intake Report

The candidate pool was evaluated only for Data Gate suitability. No large files were downloaded and no models were trained.

Best candidate shape:

1. Gotham Dataset 2025: strongest first target because it advertises raw PCAP, CSV, metadata, labels, device/gateway context, and realistic IoT home traffic. Its main risk is size/manual download plus the need to verify benign phase/capture splits after metadata intake.
2. ToN-IoT / TON_IoT network: strong IoT/IIoT candidate with network data and local partial CSV, but the local CSV alone lacks obvious timestamp/capture columns; raw/log/security-event package must be obtained or verified.

Useful auxiliary:

- Local IoT-23 public_data can rehearse the semantic gate cheaply because raw pcap and labeled logs exist locally, but benign OOD is likely too limited for the main benchmark.

Rejected or lower-priority as immediate main benchmark:

- full Mirai anonymous_clean115: diagnostic only.
- local BoT-IoT 5% subset: too few benign rows in prior inventory.
- UNSW-IoTraffic: good benign OOD auxiliary but lacks attack labels as standalone benchmark.
"""
    write_text("second_dataset_intake_report.md", intake_report)

    shortlist = """# Recommended Dataset Shortlist

## 1. Gotham Dataset 2025

Why it fits:

- raw PCAP plus CSV/metadata/labels are reported.
- IoT smart-home style setting with multiple devices and gateway context.
- Better chance to build ID benign / OOD benign / attack support / attack eval without row-order fiction.
- Metadata should allow row-order/source/capture artifact audit.

Largest risks:

- 23.8GB download needs user confirmation.
- Need to inspect metadata before trusting benign phases or attack labels.
- Need to define feature extraction path after intake.

## 2. ToN-IoT / TON_IoT network

Why it fits:

- IoT/IIoT network dataset family with labels and network traffic records.
- Local flow CSV already exists, so path familiarity is high.
- Raw/log/security event package may support timestamp-aware split if acquired.

Largest risks:

- Local CSV alone is not enough for Data Gate.
- Access/download may require manual steps.
- Must verify benign multi-phase/capture/source metadata before model execution.

## Auxiliary: local IoT-23

Useful for a quick Data Gate rehearsal because raw pcap and labeled logs exist locally. It should not yet be treated as the main benchmark because benign OOD depth looks weak.
"""
    write_text("recommended_dataset_shortlist.md", shortlist)

    plan = f"""# Download And Storage Plan

No large downloads were performed in issue27t.

All future data must live under:

`{DATASETS_ROOT}`

Directory template:

- `{DATASETS_ROOT}\\<dataset_name>\\raw`
- `{DATASETS_ROOT}\\<dataset_name>\\metadata`
- `{DATASETS_ROOT}\\<dataset_name>\\labels`
- `{DATASETS_ROOT}\\<dataset_name>\\derived`
- `{DATASETS_ROOT}\\<dataset_name>\\manifests`

Git rules:

- Do not stage raw PCAP, pcapng, zip, 7z, tar.gz, or large CSV files.
- Only stage small README, manifest, hash, and metadata pointer files.
- Do not download to `C:\\Users`, Downloads, Desktop, or temp directories.

Next user-confirmed downloads:

1. Gotham metadata/index first, then raw PCAP only after size confirmation.
2. ToN-IoT network raw/log/security-event metadata package if Gotham is blocked.
3. CICIoT2023 only if top two paths fail or the user wants a larger fallback.
"""
    write_text("download_and_storage_plan.md", plan)

    decision = f"""# issue27t Decision

primary_verdict = `{primary_verdict}`

Decision:

The project should not continue model experiments. Full Mirai paired raw is confirmed missing locally, so the current main path is second-dataset intake.

Recommended next step:

1. Ask user confirmation to create `{DATASETS_ROOT}` if needed and download only small Gotham metadata/index files first.
2. If Gotham metadata confirms benign phases, attack labels, and capture/source information, proceed to controlled raw download.
3. In parallel, keep ToN-IoT as the second candidate and local IoT-23 as a cheap semantic-gate rehearsal.
"""
    write_text("issue27t_decision.md", decision)

    claim = """# Claim Update After issue27t

Full Mirai paired raw is confirmed missing locally, and full Mirai anonymous_clean115 remains diagnostic only.

No model claim is allowed from issue27p rankings. DeepSADStyle_Lite is not a main method, LOW-GUARD++ is not declared failed, and external generalization is not proven.

The next claim-safe path is second-dataset intake with strict Data Gate checks before any feature/interface or model execution.
"""
    write_text("claim_update_after_issue27t.md", claim)

    next_action = """# issue27u Next Action

Recommended issue:

`issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28`

Scope:

- no model training.
- no large raw download without user confirmation.
- download or inspect only small metadata/index/README/license files if available.
- verify Gotham has enough benign phases/environments, attack labels, timestamp/order, source/capture metadata, and report-only final eval potential.
- produce a Data Gate pass/fail decision before raw PCAP download.

Fallback:

If Gotham metadata is blocked, run ToN-IoT metadata intake. Local IoT-23 can be used only as an auxiliary Data Gate rehearsal.
"""
    write_text("issue27u_next_action.md", next_action)

    summary = f"""# issue27t Second Dataset Intake Summary

1. issue27t completed: `true`.
2. primary_verdict: `{primary_verdict}`.
3. full Mirai paired raw confirmed missing: `true`; user confirmed only feature CSV + labels were downloaded, and issue27s found no paired raw pcap/input stream.
4. local available pcap / dataset candidates: local IoT23/public_data pcaps and labeled logs; small CICIoT2023 public_data CSV subsets; local ToN-IoT-style train_test_network CSV; local BoT-IoT 5% flow CSVs.
5. external candidates in pool: Gotham Dataset 2025, ToN-IoT, CICIoT2023, BoT-IoT/NF-BoT-IoT, UNSW-IoTraffic auxiliary, GeNIS 2025 fallback.
6. top recommended datasets: Gotham Dataset 2025 and ToN-IoT / TON_IoT network.
7. Gotham fit: raw PCAP + CSV + metadata + labels shape appears strongest for low-OOD-alert Data Gate; risk is 23.8GB size and metadata must be verified before raw download.
8. ToN-IoT fit: IoT/IIoT network data with labels and likely raw/log/security-event metadata; risk is access/manual download and local CSV alone is not enough.
9. user download confirmation needed: `yes`, before any PCAP/large archive download.
10. download path plan: `{DATASETS_ROOT}\\<dataset_name>\\raw|metadata|labels|derived|manifests`; never C drive/Downloads/Desktop/temp.
11. model experiments allowed now: `false`; still Data validity gate.
12. issue27u recommendation: Gotham metadata intake and Data Gate precheck; ToN-IoT fallback if Gotham blocks.
13. Slurm needed: not for issue27t; maybe later for feature extraction over large raw PCAP.
14. commit hash: pending.
"""
    write_text("summary.md", summary)

    write_text("command.txt", "python repo/ood/issue27t_second_dataset_intake.py\n")
    write_json(
        "config.json",
        {
            "issue": "issue27t",
            "no_model_training": True,
            "no_large_download": True,
            "data_root": str(DATASETS_ROOT),
            "primary_verdict": primary_verdict,
        },
    )
    write_json(
        "run_spec.json",
        {
            "task": "second_dataset_intake_with_full_mirai_raw_missing_confirmed",
            "input_issue": str(ISSUE27S),
            "external_sources_used": [
                "https://zenodo.org/records/14502760",
                "https://research.unsw.edu.au/projects/toniot-datasets",
                "https://www.unb.ca/cic/datasets/iotdataset-2023.html",
                "https://research.unsw.edu.au/projects/bot-iot-dataset",
                "https://www.stratosphereips.org/datasets-iot23",
                "https://iotanalytics.unsw.edu.au/iottraces.html",
                "https://zenodo.org/records/14938238",
            ],
            "primary_verdict": primary_verdict,
        },
    )

    marker = "<!-- issue27t_second_dataset_intake -->"
    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        marker,
        f"""
{marker}

## issue27t Second Dataset Intake

- primary_verdict: `{primary_verdict}`.
- full Mirai paired raw missing is confirmed; full Mirai anonymous_clean115 remains diagnostic only.
- current model experiments remain blocked by Data validity gate.
- recommended candidates: Gotham Dataset 2025 first, ToN-IoT network second; local IoT-23 is auxiliary for semantic-gate rehearsal.
- all future downloads must use `{DATASETS_ROOT}\\<dataset_name>\\...`; do not stage raw/large data.
- next: `issue27u_gotham_metadata_intake_and_data_gate_precheck`.
""",
    )

    map_marker = "<!-- issue27t_map_entry -->"
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        map_marker,
        f"""
{map_marker}

### issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28

- status: completed.
- primary_verdict: `{primary_verdict}`.
- outputs: `runs/issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28/`.
- role: Data validity gate second-dataset candidate intake after full Mirai paired raw was confirmed missing.
- implication: no model execution; proceed to Gotham metadata intake, with ToN-IoT as fallback and local IoT-23 as auxiliary.
""",
    )

    manifest()
    print(json.dumps({"primary_verdict": primary_verdict, "top_candidates": ["Gotham Dataset 2025", "ToN-IoT / TON_IoT network"]}, indent=2))


if __name__ == "__main__":
    main()
