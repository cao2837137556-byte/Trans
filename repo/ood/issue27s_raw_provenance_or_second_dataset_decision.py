from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = ROOT.parents[1]
KITNET_ROOT = PAPER_ROOT / "KitNET-py-master" / "KitNET-py-master"
DATA_ROOT = PAPER_ROOT / "worktrees" / "data"
OUT_DIR = ROOT / "runs" / "issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

FULL_MIRAI = KITNET_ROOT / "Mirai_dataset.csv"
FULL_LABELS = KITNET_ROOT / "mirai_labels.csv"
FULL_ZIP = KITNET_ROOT / "Mirai_dataset.csv.zip"
MIRAI3 = KITNET_ROOT / "mirai3.csv"
MIRAI3_TS = KITNET_ROOT / "mirai3_ts.csv"
OFFICIAL_LABELS = KITNET_ROOT / "official_labels.npy"
MY_GOLD = KITNET_ROOT / "my_gold_mirai.csv"
MY_GOLD_LABELS = KITNET_ROOT / "my_gold_labels.npy"

ISSUE27R = ROOT / "runs" / "issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28"
ISSUE27P = ROOT / "runs" / "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27"
ISSUE27M = ROOT / "runs" / "issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild_2026-05-27"
ISSUE27L = ROOT / "runs" / "issue27l_sufficient_clean_eval_asset_and_split_aware_original100_rebuild_for_lowguard_plus_plus_2026-05-27"


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


def sha256_file(path: Path, max_size_bytes: int = 250_000_000) -> str:
    if not path.exists():
        return "missing"
    if path.stat().st_size > max_size_bytes:
        return f"skipped_large_file_{path.stat().st_size}_bytes"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_once(path: Path, marker: str, text: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in old:
        return
    sep = "" if old == "" or old.endswith("\n") else "\n"
    path.write_text(old + sep + text, encoding="utf-8")


def safe_size(path: Path) -> int | str:
    return path.stat().st_size if path.exists() else "missing"


def search_files() -> dict[str, list[Path]]:
    patterns = {
        "pcap": ["*.pcap", "*.pcapng", "*.cap"],
        "timestamp": ["*timestamp*", "*ts.csv", "*_ts.csv"],
        "label": ["*label*", "*labels*"],
        "metadata": ["*metadata*", "*sidecar*"],
        "mirai": ["*Mirai*", "*mirai*"],
        "extractor": ["*netStat.py", "*AfterImage.py", "*FeatureExtractor.py"],
        "botiot_toniot": ["*Botnet*", "*botnet*", "*TON*", "*toniot*", "*IoT_Botnet*"],
    }
    found: dict[str, list[Path]] = {k: [] for k in patterns}
    roots = [PAPER_ROOT]
    for root in roots:
        for key, pats in patterns.items():
            seen = set(found[key])
            for pat in pats:
                for p in root.rglob(pat):
                    if p.is_file() and p not in seen:
                        found[key].append(p)
                        seen.add(p)
    return found


def path_contains(path: Path, *parts: str) -> bool:
    lower = str(path).lower()
    return all(part.lower() in lower for part in parts)


def make_inventory(found: dict[str, list[Path]]) -> list[dict]:
    rows: list[dict] = []

    def add(
        asset_name: str,
        path: Path,
        asset_type: str,
        raw_pcap: bool = False,
        extracted_tsv: bool = False,
        contains_timestamp: bool | str = False,
        label_sidecar: bool | str = False,
        attack_onset_info: bool | str = False,
        capture_session_source: bool | str = False,
        packet_order: bool | str = False,
        feature_row_raw_packet_alignment: bool | str = False,
        paired_with_full_mirai: bool | str = False,
        enough_ood_benign: bool | str = "unknown",
        notes: str = "",
    ) -> None:
        rows.append(
            {
                "asset_name": asset_name,
                "asset_path": str(path),
                "exists": path.exists(),
                "asset_type": asset_type,
                "size_bytes": safe_size(path),
                "sha256": sha256_file(path) if path.exists() and (raw_pcap or path.suffix.lower() in {".py", ".json", ".npy"}) else "not_hashed_or_large_csv",
                "raw_pcap_exists": raw_pcap and path.exists(),
                "extracted_tsv_exists": extracted_tsv and path.exists(),
                "timestamp_column_exists": contains_timestamp,
                "label_sidecar_exists": label_sidecar,
                "attack_start_or_onset_info_exists": attack_onset_info,
                "capture_session_source_exists": capture_session_source,
                "packet_order_recoverable": packet_order,
                "feature_row_to_raw_packet_aligned": feature_row_raw_packet_alignment,
                "feature_extraction_script_exists": False,
                "netstat_afterimage_runnable": False,
                "clean115_traceable_to_extractor_output": False,
                "claim_safe_sidecar_possible": False,
                "can_distinguish_benign_prefix_attack_suffix": "row_order_only" if path == FULL_MIRAI else "unknown",
                "enough_ood_benign_assets": enough_ood_benign,
                "paired_with_full_mirai": paired_with_full_mirai,
                "notes": notes,
            }
        )

    add(
        "full_mirai_feature_csv_dirty116",
        FULL_MIRAI,
        "feature_csv_dirty116",
        contains_timestamp=False,
        label_sidecar=FULL_LABELS.exists(),
        packet_order="row_index_col0_and_csv_order_only",
        feature_row_raw_packet_alignment=False,
        paired_with_full_mirai=True,
        enough_ood_benign="only row-order benign prefix; not semantic OOD",
        notes="Primary full Mirai feature matrix. No raw packet, timestamp, capture/session, or feature-name mapping in this file.",
    )
    add(
        "full_mirai_label_sidecar",
        FULL_LABELS,
        "label_sidecar_csv",
        label_sidecar=True,
        packet_order="aligns by row count/order",
        feature_row_raw_packet_alignment=False,
        paired_with_full_mirai=True,
        notes="Provides labels but no attack onset timestamp or source/capture information.",
    )
    add(
        "full_mirai_feature_zip",
        FULL_ZIP,
        "compressed_feature_csv",
        paired_with_full_mirai=True,
        notes="Compressed copy of feature CSV, not raw provenance.",
    )
    add(
        "official_mirai_100k_feature_csv",
        MIRAI3,
        "feature_csv_115d_subset",
        contains_timestamp=MIRAI3_TS.exists(),
        label_sidecar=OFFICIAL_LABELS.exists(),
        packet_order="csv_order_plus_timestamp_sidecar",
        paired_with_full_mirai="subset_or_related_not_full_764k",
        enough_ood_benign="smaller candidate only",
        notes="Useful for timestamp-aware feasibility smoke, but does not prove full 764k raw provenance.",
    )
    add(
        "official_mirai_100k_timestamp_sidecar",
        MIRAI3_TS,
        "timestamp_csv_sidecar",
        contains_timestamp=True,
        label_sidecar=OFFICIAL_LABELS.exists(),
        packet_order=True,
        paired_with_full_mirai="not full_764k",
        notes="Timestamp sidecar for mirai3 path only; not evidence that full Mirai has timestamp/capture provenance.",
    )
    add(
        "my_gold_mirai_200k_feature_csv",
        MY_GOLD,
        "feature_csv_subset",
        label_sidecar=MY_GOLD_LABELS.exists(),
        packet_order="csv_order_only",
        paired_with_full_mirai="known_overlap_with_full_mirai_prefix",
        notes="Historical exploratory subset; not clean external evidence.",
    )

    for pcap in found["pcap"]:
        add(
            "local_raw_pcap_not_paired_with_full_mirai",
            pcap,
            "raw_pcap",
            raw_pcap=True,
            contains_timestamp=True,
            packet_order=True,
            capture_session_source="path_level_only",
            feature_row_raw_packet_alignment=False,
            paired_with_full_mirai=False,
            enough_ood_benign="unknown_not_full_mirai",
            notes="Raw pcap exists locally, but path/name indicates IoT23/public_data raw, not a paired full Mirai raw asset.",
        )

    for extractor in found["extractor"]:
        row = {
            "asset_name": f"feature_extractor_script_{extractor.name}",
            "asset_path": str(extractor),
            "exists": extractor.exists(),
            "asset_type": "feature_extraction_script",
            "size_bytes": safe_size(extractor),
            "sha256": sha256_file(extractor),
            "raw_pcap_exists": False,
            "extracted_tsv_exists": False,
            "timestamp_column_exists": "script_supports_packet_timestamp_if_input_available",
            "label_sidecar_exists": False,
            "attack_start_or_onset_info_exists": False,
            "capture_session_source_exists": False,
            "packet_order_recoverable": "input_order_dependent",
            "feature_row_to_raw_packet_aligned": "only if raw input and sidecar are provided",
            "feature_extraction_script_exists": True,
            "netstat_afterimage_runnable": extractor.name.lower() in {"netstat.py", "afterimage.py", "featureextractor.py"},
            "clean115_traceable_to_extractor_output": False,
            "claim_safe_sidecar_possible": "possible only with paired raw input",
            "can_distinguish_benign_prefix_attack_suffix": False,
            "enough_ood_benign_assets": "requires dataset input",
            "paired_with_full_mirai": False,
            "notes": "Extractor code exists, but full Mirai raw/input stream paired with the 764k feature rows was not found.",
        }
        rows.append(row)

    return rows


def make_problem_support_table() -> tuple[list[dict], str]:
    rows = [
        {
            "question": "full Mirai only benign prefix plus attack suffix",
            "answer": True,
            "evidence": "mirai_labels.csv: first 121621 benign rows, remaining 642516 attack rows; issue27r attack label row-order correlation=0.633630",
            "claim_safe": False,
            "notes": "This is exactly the semantic risk; attack/benign can be row-segment bound.",
        },
        {
            "question": "multiple benign phases available",
            "answer": "not proven",
            "evidence": "Benign prefix can be sliced by row order, but there is no timestamp/capture/session metadata.",
            "claim_safe": False,
            "notes": "Slicing the prefix creates distributional segments, not validated deploy-time phases.",
        },
        {
            "question": "explainable OOD benign exists",
            "answer": "not currently",
            "evidence": "issue27r ID/OOD AUC=0.998820 but split is row-order-derived and metadata absent.",
            "claim_safe": False,
            "notes": "A strong domain classifier alone is not a valid OOD story.",
        },
        {
            "question": "natural train-time to deploy-time benign drift exists",
            "answer": "blocked",
            "evidence": "No full Mirai timestamp/capture/session/source id.",
            "claim_safe": False,
            "notes": "Need timestamp/capture metadata or a second dataset.",
        },
        {
            "question": "attack support/eval can be disjoint",
            "answer": True,
            "evidence": "Row ranges can be disjoint.",
            "claim_safe": "engineering_only",
            "notes": "Disjoint rows do not solve attack suffix/source artifact risk.",
        },
        {
            "question": "purge gap/embargo possible",
            "answer": "row_order_only",
            "evidence": "No temporal units for an actual purge gap.",
            "claim_safe": False,
            "notes": "Can remove rows, but cannot call it temporal embargo.",
        },
        {
            "question": "avoid row-order artifact",
            "answer": False,
            "evidence": "Benign prefix, attack suffix, ID/OOD row-order split.",
            "claim_safe": False,
            "notes": "Core blocker.",
        },
        {
            "question": "avoid source/capture artifact",
            "answer": "unknown",
            "evidence": "No source/capture/session metadata.",
            "claim_safe": False,
            "notes": "Unknown is not safe for A-tier claim.",
        },
        {
            "question": "final eval report-only can be preserved",
            "answer": True,
            "evidence": "issue27p engineering split did this.",
            "claim_safe": "engineering_only",
            "notes": "Necessary but not sufficient.",
        },
        {
            "question": "construct ID/OOD/support/eval technically",
            "answer": True,
            "evidence": "Rows are sufficient.",
            "claim_safe": False,
            "notes": "Technically constructible, semantically weak.",
        },
        {
            "question": "role if not main benchmark",
            "answer": "feature/debug diagnostic; attack-only auxiliary; historical baseline",
            "evidence": "Clean115 can test interfaces and score mechanics.",
            "claim_safe": "diagnostic_only",
            "notes": "Do not use for main low-OOD-alert claim.",
        },
    ]
    verdict = "full_mirai_not_sufficient_for_ood_benign_problem"
    return rows, verdict


def make_raw_reconstruction_plan(inventory_rows: list[dict]) -> tuple[list[dict], str]:
    full_raw_exists = any(row["raw_pcap_exists"] and row["paired_with_full_mirai"] is True for row in inventory_rows)
    extractor_exists = any(row["feature_extraction_script_exists"] for row in inventory_rows)
    if not full_raw_exists:
        verdict = "raw_reconstruction_blocked_missing_raw"
    elif not extractor_exists:
        verdict = "raw_reconstruction_blocked_missing_extractor"
    else:
        verdict = "raw_reconstruction_feasible_slurm"

    rows = [
        {
            "task": "recover_full_mirai_raw_input",
            "required": True,
            "current_status": "missing",
            "output": "pcap/packet fields paired with Mirai_dataset.csv rows",
            "local_or_slurm": "data_acquisition_first",
            "estimated_cost": "unknown",
            "risk": "blocking",
        },
        {
            "task": "verify_feature_row_to_packet_alignment",
            "required": True,
            "current_status": "blocked_missing_raw",
            "output": "row-level sidecar with packet_id/timestamp/label/source/feature_hash",
            "local_or_slurm": "local for audit; slurm if full re-extraction",
            "estimated_cost": "medium after raw exists",
            "risk": "blocking",
        },
        {
            "task": "run_kitsune_extractor_smoke",
            "required": True,
            "current_status": "extractor_scripts_exist_but_no_full_raw_input",
            "output": "small feature reconstruction with timestamp and packet order",
            "local_or_slurm": "local smoke",
            "estimated_cost": "low after raw exists",
            "risk": "medium",
        },
        {
            "task": "full_115_feature_reconstruction",
            "required": True,
            "current_status": "blocked_missing_raw",
            "output": "reconstructed115 with feature names/order and manifest",
            "local_or_slurm": "slurm_recommended",
            "estimated_cost": "medium/high",
            "risk": "high",
        },
        {
            "task": "split_aware_feature_extraction",
            "required": True,
            "current_status": "blocked_missing_raw_and_semantic_split",
            "output": "reset_at_split_boundary and train_state_then_eval_online variants",
            "local_or_slurm": "slurm_recommended",
            "estimated_cost": "high",
            "risk": "high",
        },
        {
            "task": "construct_claim_safe_sidecar",
            "required": True,
            "current_status": "blocked_missing_timestamp_capture_source",
            "output": "packet_id,timestamp,label,split_role,capture/source,feature_hash",
            "local_or_slurm": "local once metadata exists",
            "estimated_cost": "medium",
            "risk": "blocking",
        },
    ]
    return rows, verdict


def second_dataset_requirements() -> list[dict]:
    return [
        {"requirement": "benign_multi_phase_or_multi_environment", "must": True, "why": "Needed to construct ID benign and OOD benign without row-order fiction.", "failure_action": "reject_as_main_benchmark"},
        {"requirement": "attack_labels", "must": True, "why": "Needed for attack support/eval and detection metric.", "failure_action": "reject"},
        {"requirement": "raw_pcap_or_flow_records", "must": True, "why": "Needed for provenance and feature/interface gate.", "failure_action": "downgrade_to_diagnostic"},
        {"requirement": "timestamp_or_order", "must": True, "why": "Needed for purge/embargo or deployment-like split.", "failure_action": "no_temporal_claim"},
        {"requirement": "capture_session_source_metadata", "must": "strongly_preferred", "why": "Needed to audit source/capture artifact.", "failure_action": "claim_bound_to_distributional_split"},
        {"requirement": "report_only_final_eval_possible", "must": True, "why": "Prevents selection leakage.", "failure_action": "reject"},
        {"requirement": "attack_support_eval_disjoint_possible", "must": True, "why": "Few-shot support cannot overlap attack eval.", "failure_action": "reject"},
        {"requirement": "low_ood_alert_operating_point_possible", "must": True, "why": "Core paper problem is low OOD false alarm plus attack detection.", "failure_action": "reject"},
        {"requirement": "row_order_source_artifact_auditable", "must": True, "why": "Avoid repeating full Mirai semantic failure.", "failure_action": "reject_or_raw_reconstruct"},
        {"requirement": "feature_interface_gate_possible", "must": True, "why": "Models cannot run before feature semantics and alignment pass.", "failure_action": "block_model_execution"},
    ]


def make_manifest() -> None:
    rows = []
    for p in sorted(OUT_DIR.iterdir()):
        if p.name == "manifest.csv" or not p.is_file():
            continue
        rows.append({"file": p.name, "size_bytes": p.stat().st_size, "sha256": sha256_file(p, max_size_bytes=1_000_000_000)})
    write_csv("manifest.csv", rows)


def main() -> None:
    ensure_out()
    found = search_files()
    inventory_rows = make_inventory(found)
    problem_rows, problem_verdict = make_problem_support_table()
    reconstruction_rows, reconstruction_verdict = make_raw_reconstruction_plan(inventory_rows)
    second_rows = second_dataset_requirements()

    # Decision: current full Mirai is not claim-safe; raw rescue is blocked by missing paired raw input,
    # so the strongest next move is dual-track: try to reacquire raw while starting second-dataset intake.
    primary_verdict = "dual_track_raw_rebuild_and_second_dataset_intake"

    write_csv("full_mirai_raw_provenance_inventory.csv", inventory_rows)
    write_csv("full_mirai_problem_support_table.csv", problem_rows)
    write_csv("raw_feature_reconstruction_plan.csv", reconstruction_rows)
    write_csv("second_dataset_candidate_requirements.csv", second_rows)

    raw_pcap_count = sum(1 for row in inventory_rows if row["raw_pcap_exists"])
    full_paired_raw_count = sum(1 for row in inventory_rows if row["raw_pcap_exists"] and row["paired_with_full_mirai"] is True)
    extractor_count = sum(1 for row in inventory_rows if row["feature_extraction_script_exists"])

    raw_report = f"""# Full Mirai Raw Provenance Report

Verdict: `full_mirai_raw_assets_missing_for_claim_safe_reconstruction`.

Findings:

- Full Mirai main asset exists as `Mirai_dataset.csv` plus `mirai_labels.csv`.
- No raw pcap paired with the full 764,137-row Mirai feature matrix was found.
- Local raw pcaps exist (`{raw_pcap_count}` files), but they are IoT23/public_data style assets and are not paired with the full Mirai CSV.
- `mirai3.csv` and `mirai3_ts.csv` provide a smaller timestamped 100k path, but that does not recover timestamp/capture provenance for the full 764k matrix.
- Extractor scripts exist (`{extractor_count}` script hits across worktrees / KitNET roots), including netStat/AfterImage/FeatureExtractor, but scripts alone do not make current clean115 traceable to raw packets.

Technical judgment:

The current full Mirai object cannot be rescued by paperwork alone. A claim-safe reconstruction requires the raw input stream or extractor-compatible packet/flow fields that generated the 764,137 rows, plus a row-level sidecar with packet id, timestamp, label, source/capture/session, split role, and feature hash.
"""
    write_text("full_mirai_raw_provenance_report.md", raw_report)

    problem_report = f"""# Full Mirai Problem Support Feasibility

Stage verdict: `{problem_verdict}`.

Full Mirai currently has enough rows for an engineering split, but not enough semantic evidence for the paper problem.

What is technically possible:

- ID/OOD/support/eval row ranges can be assigned.
- attack support and attack eval can be row-disjoint.
- final eval can remain report-only.

What is not claim-safe:

- OOD benign is not a validated deploy-time benign drift; it is a row-order slice from a benign prefix.
- attack rows are a contiguous suffix, so attack-vs-benign separation can reflect row segment, source, capture, or scale artifacts.
- no timestamp/capture/session/source metadata exists for the full 764k asset.
- no paired raw packets exist to test whether feature values reflect online traffic behavior rather than downstream feature-table construction.

Role if not main benchmark:

- feature/debug diagnostic
- interface stress test
- attack-only auxiliary after provenance warning
- historical exploratory baseline

It should not be the main low-OOD-alert benchmark in current anonymous_clean115 form.
"""
    write_text("full_mirai_problem_support_feasibility.md", problem_report)

    recon_report = f"""# Raw Feature Reconstruction Feasibility

Stage verdict: `{reconstruction_verdict}`.

Extractor code exists, but full Mirai raw input is missing. Therefore the next action is not model training; it is data acquisition or reconstruction feasibility:

1. Recover the raw pcap or packet/flow stream that generated `Mirai_dataset.csv`.
2. Verify row alignment against `Mirai_dataset.csv` and `mirai_labels.csv`.
3. Generate a sidecar with packet id, timestamp, label, source/capture/session, split role, and feature hash.
4. Run a small extractor smoke before any full feature rebuild.
5. Only then consider split-aware feature extraction (`reset_at_split_boundary`, `train_state_then_eval_online`).

Slurm is not needed for this decision issue. It is likely needed for full re-extraction if raw input is recovered.
"""
    write_text("raw_feature_reconstruction_feasibility.md", recon_report)

    fallback = """# Second Dataset Fallback Criteria

If full Mirai raw provenance cannot be recovered quickly, the project should start second-dataset intake instead of continuing anonymous_clean115 model work.

Hard requirements:

- benign traffic must contain multiple phases, environments, captures, or time windows so ID/OOD benign is semantically meaningful.
- attack labels must be available.
- raw pcap or flow records should exist, with timestamp/order metadata.
- capture/session/source metadata is strongly preferred.
- final OOD eval and attack eval must be report-only.
- attack support and attack eval must be disjoint.
- row-order/source artifact must be auditable before model execution.
- feature/interface gate must pass before any model claim.

Candidate families to inspect:

- IoT intrusion datasets with raw pcap and timestamps.
- CIC-style IDS datasets with PCAP/flows/timestamps.
- Bot-IoT / TON-IoT / CICIoT-style datasets only if benign count and metadata are enough.
- Any dataset with deployment-like benign drift and attack labels.

Do not choose a second dataset only because it is popular. It must satisfy the paper problem first.
"""
    write_text("second_dataset_fallback_criteria.md", fallback)

    decision = f"""# issue27s Decision

primary_verdict = `{primary_verdict}`

Supporting stage verdicts:

- full Mirai problem support: `{problem_verdict}`
- raw reconstruction feasibility: `{reconstruction_verdict}`

Decision:

Current full Mirai anonymous_clean115 cannot serve as the main low-OOD-alert benchmark. It is not abandoned as data, but it is not claim-safe in current form.

Full Mirai can be revisited only if the paired raw/extractor-compatible input stream is recovered and a row-level sidecar proves timestamp/source/capture/label alignment. Because that may take time and may fail, the next issue should run a dual-track plan:

1. try to recover full Mirai raw provenance or a small extractor-level reconstruction proof;
2. start second-dataset intake using strict semantic requirements.

Model experiments remain blocked until one track passes the data validity gate.
"""
    write_text("issue27s_decision.md", decision)

    claim_update = """# Claim Update After issue27s

Full Mirai anonymous_clean115 cannot serve as the main low-OOD-alert benchmark in its current form.

Future model claims require a semantically valid dataset, either through full Mirai raw/extractor-level reconstruction with row-level provenance or through second-dataset intake that passes the data validity gate.

Allowed statement: full Mirai may still be useful as diagnostic data or may be recoverable if raw provenance is found.

Not allowed: issue27p model rankings as main results, DeepSADStyle_Lite as main method, LOW-GUARD++ failure, full Mirai external generalization, or anonymous_clean115 equivalence to restored115/original100.
"""
    write_text("claim_update_after_issue27s.md", claim_update)

    issue27t = """# issue27t Next Action

Recommended next issue:

`issue27t_dual_track_full_mirai_raw_provenance_search_and_second_dataset_intake_2026-05-28`

P0 tasks:

1. Search or reacquire the raw/extractor-compatible source for the full 764,137-row Mirai matrix.
2. If found, build a minimal row-level sidecar and extractor smoke on a small range.
3. In parallel, inventory second-dataset candidates against the hard semantic requirements.
4. Select one path only after the data validity gate passes.

Do not train models in issue27t. The project is still in Data validity gate, not Feature/interface or Model execution gate.

Slurm: not needed for intake; likely needed for full raw reconstruction or large second-dataset feature extraction.
"""
    write_text("issue27t_next_action.md", issue27t)

    summary = f"""# issue27s Raw Provenance Or Second Dataset Semantic Reconstruction Summary

1. issue27s completed: `true`.
2. primary_verdict: `{primary_verdict}`.
3. full Mirai raw pcap exists: `false` for a pcap paired with `Mirai_dataset.csv`; unrelated local IoT23 pcaps exist.
4. timestamp / packet order / label recovery: labels and CSV row order are recoverable; full 764k timestamp/capture/session provenance is not recoverable from current assets. `mirai3_ts.csv` is only a smaller related timestamp sidecar.
5. feature row to raw packet alignment: `blocked`; no paired raw packet/input stream found.
6. claim-safe ID/OOD benign construction: `false` in current full Mirai anonymous_clean115; only row-order benign slices exist.
7. claim-safe attack support/eval construction: row-disjoint attack support/eval is technically possible, but not semantically claim-safe because attack rows are a contiguous suffix and source/capture provenance is missing.
8. full Mirai as main benchmark: not in current form; possible only if paired raw/extractor-level provenance is recovered and a semantic split is rebuilt.
9. if not main benchmark, role: feature/debug diagnostic, interface stress test, attack-only auxiliary with caveats, historical exploratory baseline.
10. raw reconstruction feasible: `{reconstruction_verdict}`; extractor scripts exist, but full raw input is missing.
11. Slurm needed: not for issue27s; likely for full re-extraction if raw input is recovered.
12. should turn to second dataset: `yes, in parallel`; do not stall model line on anonymous_clean115.
13. second dataset hard conditions: multi-phase/environment benign, attack labels, raw or flow records, timestamp/order, source/capture auditability, report-only final eval, attack support/eval disjointness, low-OOD-alert operating point support.
14. issue27t recommendation: dual-track full Mirai raw provenance search and second-dataset semantic intake.
15. commit hash: pending.
"""
    write_text("summary.md", summary)

    write_json(
        "config.json",
        {
            "issue": "issue27s",
            "no_model_training": True,
            "data_validity_gate_only": True,
            "full_mirai_current_feature_schema": "anonymous_clean115_diagnostic_only",
            "paired_full_mirai_raw_found": full_paired_raw_count > 0,
            "primary_verdict": primary_verdict,
        },
    )
    write_json(
        "run_spec.json",
        {
            "task": "raw_provenance_or_second_dataset_semantic_reconstruction_decision",
            "inputs": {
                "issue27r": str(ISSUE27R),
                "issue27p_manifest": str(ISSUE27P / "anonymous_clean115_dataset_manifest.csv"),
                "issue27m_asset_report": str(ISSUE27M / "full_mirai_asset_identity_report.md"),
                "issue27l_inventory": str(ISSUE27L / "full_botnet_dataset_inventory.csv"),
            },
            "stage_verdicts": {
                "full_mirai_problem_support": problem_verdict,
                "raw_reconstruction": reconstruction_verdict,
            },
            "primary_verdict": primary_verdict,
        },
    )
    write_text("command.txt", "python repo/ood/issue27s_raw_provenance_or_second_dataset_decision.py\n")

    marker = "<!-- issue27s_raw_provenance_or_second_dataset -->"
    handoff = f"""
{marker}

## issue27s Raw Provenance Or Second Dataset Decision

- primary_verdict: `{primary_verdict}`.
- issue27r data semantics gate did not pass for full Mirai anonymous_clean115.
- full Mirai paired raw pcap/input stream was not found; local pcaps are unrelated IoT23/public_data assets.
- full 764k timestamp/capture/session provenance is missing; `mirai3_ts.csv` is only a smaller related path.
- current full Mirai anonymous_clean115 is diagnostic only, not main low-OOD-alert benchmark.
- model experiments remain blocked by Data validity gate.
- next: dual-track full Mirai raw provenance search plus second-dataset semantic intake.
"""
    append_once(MAINLINE_DOCS / "mainline_handoff.md", marker, handoff)

    map_marker = "<!-- issue27s_map_entry -->"
    exp_map = f"""
{map_marker}

### issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28

- status: completed.
- primary_verdict: `{primary_verdict}`.
- outputs: `runs/issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28/`.
- role: Data validity gate fork after issue27r semantic failure.
- implication: full Mirai anonymous_clean115 is not current main benchmark; proceed with raw provenance recovery and second-dataset intake before any model execution.
"""
    append_once(MAINLINE_DOCS / "mainline_experiment_map.md", map_marker, exp_map)

    make_manifest()
    print(json.dumps({"primary_verdict": primary_verdict, "raw_pcap_count": raw_pcap_count, "paired_full_mirai_raw_count": full_paired_raw_count}, indent=2))


if __name__ == "__main__":
    main()
