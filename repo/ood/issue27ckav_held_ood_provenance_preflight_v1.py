"""issue27ckav: held-OOD semantic provenance preflight.

This is an audit, not a training or feature-selection routine.  CKAT/CKAU
showed that strict held OOD can overlap known attack manifolds in C1 space.
Before a new PCAP/Zeek/interaction frontend is allowed, this script freezes
the provenance contract for the two failing benign device families:

* every processed source must have a non-mixed all-benign or all-attack label
  provenance in the Gotham manifest;
* its candidate PCAP path must agree with that benign/attack provenance;
* a raw-PCAP frontend may use a source only when the existing CSV--PCAP
  pairing record has usable metadata *and* an exact source-stem pairing.

The last condition deliberately rejects merely plausible filename matches.
It does not relabel, repartition, train on, or tune against any report data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
ISSUE = "issue27ckav_held_ood_provenance_preflight_v1_2026-07-10"
OUT = ROOT / "runs" / ISSUE
CKAT_PLAN = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
TARGET_INDEX = CKAT_PLAN / "canonical_source_target_index.csv"
MANIFEST = ROOT / "runs" / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28" / "gotham_all_csv_file_manifest.csv"
PAIRING = ROOT / "runs" / "issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28" / "gotham_pairing_strengthened_table.csv"
HELD_TOKENS = ("iotsim-stream-consumer-", "iotsim-hydraulic-system-")


def stem_before_capture_suffix(path: str) -> str:
    """Return the source stem before the capture-specific ``_0-0_to`` suffix."""
    name = Path(str(path)).name
    return name.split("_0-0_to_", 1)[0].removesuffix(".pcap")


def build(args: argparse.Namespace) -> Path:
    out = OUT if not args.run_tag else ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)
    for path in (TARGET_INDEX, MANIFEST, PAIRING):
        if not path.exists():
            raise FileNotFoundError(path)

    targets = pd.read_csv(TARGET_INDEX, usecols=["source_group", "recorded_index"])
    if args.scope == "held_ood":
        targets = targets[targets["source_group"].astype(str).str.contains("|".join(HELD_TOKENS), regex=True)].copy()
    elif args.scope != "all_ckat_sources":
        raise ValueError(f"unknown scope: {args.scope}")
    target_summary = (
        targets.groupby("source_group", sort=True)["recorded_index"]
        .agg(target_rows="count", min_recorded_index="min", max_recorded_index="max")
        .reset_index()
    )
    manifest = pd.read_csv(MANIFEST)
    manifest = manifest.rename(columns={"csv_archive_path": "source_group"})
    manifest = manifest[manifest["source_group"].isin(target_summary["source_group"])].copy()
    pairing = pd.read_csv(PAIRING).rename(columns={"csv_archive_path": "source_group"})
    pairing = pairing[pairing["source_group"].isin(target_summary["source_group"])].copy()

    cols = [
        "source_group", "pcap_counterpart_candidate", "has_label", "all_benign_flag",
        "all_attack_flag", "unknown_label_flag", "label_values", "benign_rows", "attack_rows",
        "unknown_label_rows", "timestamp_parse_status", "timestamp_parse_failures",
    ]
    missing = [col for col in cols if col not in manifest]
    if missing:
        raise RuntimeError(f"manifest missing columns: {missing}")
    pair_cols = [
        "source_group", "candidate_pcap_archive_path", "pcap_metadata_status",
        "filename_token_match", "path_token_match", "device_token_match",
        "protocol_token_match", "timestamp_range_overlap_status", "pairing_confidence_new",
        "unresolved_reason",
    ]
    missing = [col for col in pair_cols if col not in pairing]
    if missing:
        raise RuntimeError(f"pairing table missing columns: {missing}")

    work = target_summary.merge(manifest[cols], on="source_group", how="left", validate="one_to_one")
    work = work.merge(pairing[pair_cols], on="source_group", how="left", validate="one_to_one")
    work["source_stem"] = work["source_group"].map(lambda x: Path(str(x)).stem)
    work["pcap_stem"] = work["candidate_pcap_archive_path"].map(stem_before_capture_suffix)
    work["candidate_under_raw_benign"] = work["candidate_pcap_archive_path"].astype(str).str.startswith("raw/benign/")
    work["candidate_under_raw_malicious"] = work["candidate_pcap_archive_path"].astype(str).str.startswith("raw/malicious/")
    work["exact_source_stem_pair"] = work["source_stem"].astype(str).eq(work["pcap_stem"].astype(str))
    work["source_label_semantics"] = "mixed_or_unknown"
    work.loc[work["all_benign_flag"].eq(True), "source_label_semantics"] = "benign"
    work.loc[work["all_attack_flag"].eq(True), "source_label_semantics"] = "attack"
    work["semantic_benign_provenance_pass"] = (
        work["has_label"].eq(True)
        & work["all_benign_flag"].eq(True)
        & work["all_attack_flag"].eq(False)
        & work["unknown_label_flag"].eq(False)
        & work["candidate_under_raw_benign"].eq(True)
    )
    work["source_label_provenance_pass"] = (
        work["has_label"].eq(True)
        & work["unknown_label_flag"].eq(False)
        & work["source_label_semantics"].isin(["benign", "attack"])
    )
    work["pcap_path_semantics_match"] = (
        (work["source_label_semantics"].eq("benign") & work["candidate_under_raw_benign"].eq(True))
        | (work["source_label_semantics"].eq("attack") & work["candidate_under_raw_malicious"].eq(True))
    )
    work["raw_pcap_frontend_eligible"] = (
        work["source_label_provenance_pass"].eq(True)
        & work["pcap_path_semantics_match"].eq(True)
        & work["pcap_metadata_status"].astype(str).eq("ok")
        & work["exact_source_stem_pair"].eq(True)
        & work["timestamp_range_overlap_status"].astype(str).str.contains("match|overlap", case=False, regex=True)
    )
    work["decision"] = work["raw_pcap_frontend_eligible"].map(
        {True: "eligible_for_raw_pcap_episode_frontend", False: "processed_only_until_pairing_repaired"}
    )
    work = work.sort_values("source_group", kind="stable").reset_index(drop=True)
    work.to_csv(out / "held_ood_provenance_preflight.csv", index=False)
    targets.sort_values(["source_group", "recorded_index"], kind="stable").to_csv(out / "held_ood_target_row_index.csv", index=False)

    summary = {
        "issue": ISSUE,
        "purpose": "audit-only provenance gate before raw-PCAP episode frontend",
        "scope": args.scope,
        "held_source_count": int(len(work)),
        "target_rows": int(len(targets)),
        "semantic_benign_provenance_pass_sources": int(work["semantic_benign_provenance_pass"].sum()),
        "source_label_provenance_pass_sources": int(work["source_label_provenance_pass"].sum()),
        "raw_pcap_frontend_eligible_sources": int(work["raw_pcap_frontend_eligible"].sum()),
        "raw_pcap_frontend_rejected_sources": int((~work["raw_pcap_frontend_eligible"]).sum()),
        "label_usage": "audit-only; never training, thresholding, feature selection, or report-score tuning",
        "decision_rule": "require non-mixed source labels, matching raw benign/malicious path, and exact source-stem PCAP pairing",
    }
    (out / "run_spec.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "codex_readout.md").write_text(
        "\n".join([
            f"# {ISSUE}", "", "## Scope", "",
            "- Audit-only: no model is trained and no held labels are used for model choice.",
            "- A source may be semantically benign yet ineligible for a raw-PCAP frontend if its pairing is not exact.",
            "", "## Counts", "",
            f"- held sources: {summary['held_source_count']}",
            f"- target rows: {summary['target_rows']}",
            f"- benign-provenance pass: {summary['semantic_benign_provenance_pass_sources']}",
            f"- source-label provenance pass: {summary['source_label_provenance_pass_sources']}",
            f"- raw-PCAP frontend eligible: {summary['raw_pcap_frontend_eligible_sources']}",
            "", "## Decision", "",
            "Only `raw_pcap_frontend_eligible` sources may enter the upcoming Zeek/interaction episode extractor.",
            "Rejected sources remain processed-CSV-only until their PCAP pairing is repaired with independent evidence.",
        ]) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "out": str(out), **summary}, ensure_ascii=False, indent=2))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-tag", default="local")
    parser.add_argument("--scope", choices=["held_ood", "all_ckat_sources"], default="held_ood")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
