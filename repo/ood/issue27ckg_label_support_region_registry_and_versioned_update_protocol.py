from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ISSUE = (
    "issue27ckg_label_support_region_registry_and_versioned_"
    "update_protocol_2026-06-22"
)
OUT = ROOT / "runs" / ISSUE
CF = (
    ROOT
    / "runs"
    / "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
)
CKD = (
    ROOT
    / "runs"
    / "issue27ckd_initial_region_capacity_audit_before_controller_2026-06-21"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_csv_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_md(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_id(prefix: str, text: str, length: int = 16) -> str:
    return prefix + hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def semantic_group(label: str) -> str:
    lowered = label.lower()
    if "merlin" in lowered:
        return "merlin"
    if "mirai" in lowered:
        return "mirai"
    return "tooling"


def archive_schema() -> dict[str, Any]:
    required = [
        "archive_event_id",
        "ingest_batch_id",
        "event_timestamp_utc",
        "human_confirmed_label",
        "confirmed_by",
        "confirmation_timestamp_utc",
        "source_role",
        "selection_allowed",
        "report_only",
        "sealed_final",
        "forbidden_for_fit",
        "pcap_path",
        "csv_path",
        "pcap_packet_index",
        "csv_row_index",
        "packet_timestamp",
        "feature_asset_uri",
        "feature_vector_sha256",
        "provenance_hash",
        "append_only",
    ]
    properties = {
        key: {"type": "string"} for key in required
    }
    for key in [
        "selection_allowed",
        "report_only",
        "sealed_final",
        "forbidden_for_fit",
        "append_only",
    ]:
        properties[key] = {"type": "boolean"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "paper04://online_label_archive_schema/v1",
        "title": "online_label_archive event v1",
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def candidate_schema() -> dict[str, Any]:
    required = [
        "candidate_id",
        "archive_event_id",
        "label_region_id",
        "exact_attack_label",
        "quality_gate_status",
        "duplicate_gate_status",
        "role_gate_status",
        "promotion_status",
        "promotion_reason",
        "source_novelty",
        "time_session_novelty",
        "provenance_hash",
        "feature_asset_uri",
        "feature_vector_sha256",
    ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "paper04://region_candidate_schema/v1",
        "title": "label support region candidate v1",
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": {
            key: {"type": "string"} for key in required
        },
    }


def build_registry(
    support_rows: list[dict[str, str]],
    diagnostic_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    diagnostics = {
        row["exact_attack_label"]: row
        for row in diagnostic_rows
        if row["variant"] == "V1_frozen512_two_medoid"
    }
    rows = []
    labels = sorted({row["exact_attack_label"] for row in support_rows})
    for label in labels:
        group = [row for row in support_rows if row["exact_attack_label"] == label]
        train = [row for row in group if row["bank_partition"] == "support_train"]
        val = [row for row in group if row["bank_partition"] == "support_val"]
        sources = {
            (
                row["device_or_source_group"],
                row["pcap_path"],
                row["source_file"],
            )
            for row in group
        }
        diagnostic = diagnostics.get(label, {})
        rows.append(
            {
                "label_region_id": stable_id(
                    "label_region_", f"exact_label_v1|{label}"
                ),
                "registry_version": "label_support_region_registry_v1",
                "exact_attack_label": label,
                "semantic_attack_group": semantic_group(label),
                "region_kind": "label_support_region",
                "membership_authority": "human_confirmed_exact_label",
                "active_for_label_management": True,
                "allowed_for_unknown_traffic_autorouting": False,
                "base_support_train_rows": len(train),
                "frozen_support_val_rows": len(val),
                "base_total_rows": len(group),
                "provenance_source_count": len(sources),
                "current_training_view": "support_train_view_v1",
                "current_validation_view": "support_val_view_v1",
                "geometry_diagnostic_status": diagnostic.get(
                    "region_status", "not_available"
                ),
                "geometry_diagnostic_source": (
                    "issue27ckd_V1_frozen512_two_medoid"
                    if diagnostic
                    else ""
                ),
                "geometry_diagnostic_is_membership_gate": False,
                "production_extension_budget_profile": (
                    "not_certified_promotion_disabled"
                ),
            }
        )
    return rows


def support_view_rows(
    support_rows: list[dict[str, str]],
    partition: str,
    view_version: str,
    region_by_label: dict[str, str],
) -> list[dict[str, Any]]:
    rows = []
    for row in support_rows:
        if row["bank_partition"] != partition:
            continue
        rows.append(
            {
                "view_version": view_version,
                "view_role": partition,
                "view_row_id": stable_id(
                    "view_row_", f"{view_version}|{row['sample_id']}"
                ),
                "sample_id": row["sample_id"],
                "label_region_id": region_by_label[row["exact_attack_label"]],
                "exact_attack_label": row["exact_attack_label"],
                "source_role": row["source_role"],
                "pcap_path": row["pcap_path"],
                "csv_path": row["csv_path"],
                "pcap_packet_index": row["pcap_packet_index"],
                "csv_row_index": row["csv_row_index"],
                "packet_timestamp": row["pcap_timestamp"],
                "provenance_hash": row["provenance_hash"],
                "global_candidate_id": row["global_candidate_id"],
                "feature_asset_uri": (
                    f"issue27cd://chunk/{int(row['chunk_id']):05d}"
                    f"/row/{int(row['row_index_within_chunk'])}"
                ),
                "feature_vector_sha256": (
                    "inherited_from_certified_chunk_hash_and_row_reference"
                ),
                "origin": "initial_support_bank_v1",
                "promotion_event_id": "",
                "immutable": True,
            }
        )
    return rows


def validate_archive_event(
    event: dict[str, Any],
    schema: dict[str, Any],
    labels: set[str],
    existing_provenance: set[str],
    seen_archive_ids: set[str],
    seen_archive_provenance: set[str],
) -> tuple[str, list[str]]:
    errors = []
    for field in schema["required"]:
        if field not in event or event[field] in {"", None}:
            errors.append(f"missing:{field}")
    if event.get("archive_event_id") in seen_archive_ids:
        errors.append("duplicate_archive_event_id")
    if event.get("human_confirmed_label") not in labels:
        errors.append("unknown_exact_label")
    if not event.get("confirmed_by"):
        errors.append("missing_human_confirmation")
    if not as_bool(event.get("append_only")):
        errors.append("append_only_required")
    role_blocked = (
        not as_bool(event.get("selection_allowed"))
        or as_bool(event.get("report_only"))
        or as_bool(event.get("sealed_final"))
        or as_bool(event.get("forbidden_for_fit"))
    )
    if role_blocked:
        errors.append("forbidden_role_or_selection_state")
    provenance = str(event.get("provenance_hash", ""))
    if provenance in existing_provenance:
        errors.append("duplicate_frozen_support_provenance")
    if provenance in seen_archive_provenance:
        errors.append("duplicate_archive_provenance")
    status = "accepted_to_archive" if not errors else "quarantined"
    return status, errors


def candidate_from_event(
    event: dict[str, Any],
    region_by_label: dict[str, str],
    known_sources: dict[str, set[tuple[str, str]]],
    known_sessions: dict[str, set[str]],
) -> dict[str, str]:
    label = event["human_confirmed_label"]
    source = (event["pcap_path"], event["csv_path"])
    session = f"{event['pcap_path']}|{event['ingest_batch_id']}"
    return {
        "candidate_id": stable_id(
            "candidate_", f"{event['archive_event_id']}|{event['provenance_hash']}"
        ),
        "archive_event_id": event["archive_event_id"],
        "label_region_id": region_by_label[label],
        "exact_attack_label": label,
        "quality_gate_status": "pass",
        "duplicate_gate_status": "pass",
        "role_gate_status": "pass",
        "promotion_status": "eligible_not_promoted",
        "promotion_reason": "awaiting_frozen_budget_profile",
        "source_novelty": (
            "new_source" if source not in known_sources[label] else "known_source"
        ),
        "time_session_novelty": (
            "new_session"
            if session not in known_sessions[label]
            else "known_session"
        ),
        "provenance_hash": event["provenance_hash"],
        "feature_asset_uri": event["feature_asset_uri"],
        "feature_vector_sha256": event["feature_vector_sha256"],
    }


def simulation_events(
    support_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> list[dict[str, Any]]:
    selected_ids = {row["global_candidate_id"] for row in support_rows}
    unused = [
        row for row in candidates
        if row["global_candidate_id"] not in selected_ids
    ]
    fixtures = []
    for label in ["Mirai GRE Flooding", "Mirai UDP Flooding"]:
        row = next(r for r in unused if r["exact_attack_label"] == label)
        fixtures.append(
            {
                "archive_event_id": stable_id(
                    "archive_event_", f"simulation|{row['provenance_hash']}"
                ),
                "ingest_batch_id": "simulation_batch_v1",
                "event_timestamp_utc": "2026-06-22T00:00:00Z",
                "human_confirmed_label": label,
                "confirmed_by": "simulation_human_reviewer",
                "confirmation_timestamp_utc": "2026-06-22T00:00:00Z",
                "source_role": row["source_role"],
                "selection_allowed": as_bool(row["selection_allowed"]),
                "report_only": as_bool(row["report_only"]),
                "sealed_final": as_bool(row["sealed_final"]),
                "forbidden_for_fit": as_bool(row["forbidden_for_fit"]),
                "pcap_path": row["pcap_path"],
                "csv_path": row["csv_path"],
                "pcap_packet_index": row["pcap_packet_index"],
                "csv_row_index": row["csv_row_index"],
                "packet_timestamp": row["pcap_timestamp"],
                "feature_asset_uri": (
                    f"issue27cd://chunk/{int(row['chunk_id']):05d}"
                    f"/row/{int(row['row_index_within_chunk'])}"
                ),
                "feature_vector_sha256": (
                    "simulation_reference_to_certified_chunk_row"
                ),
                "provenance_hash": row["provenance_hash"],
                "append_only": True,
            }
        )
    duplicate = dict(fixtures[0])
    duplicate["archive_event_id"] = stable_id(
        "archive_event_", "simulation_duplicate_frozen_support"
    )
    duplicate["provenance_hash"] = support_rows[0]["provenance_hash"]
    fixtures.append(duplicate)

    forbidden = dict(fixtures[0])
    forbidden["archive_event_id"] = stable_id(
        "archive_event_", "simulation_sealed_forbidden"
    )
    forbidden["provenance_hash"] = stable_id(
        "fixture_provenance_", "sealed_forbidden"
    )
    forbidden["source_role"] = "sealed_final_attack_exact_realign"
    forbidden["selection_allowed"] = False
    forbidden["report_only"] = True
    forbidden["sealed_final"] = True
    forbidden["forbidden_for_fit"] = True
    fixtures.append(forbidden)

    unknown = dict(fixtures[0])
    unknown["archive_event_id"] = stable_id(
        "archive_event_", "simulation_unknown_label"
    )
    unknown["provenance_hash"] = stable_id(
        "fixture_provenance_", "unknown_label"
    )
    unknown["human_confirmed_label"] = "Unregistered Attack Type"
    fixtures.append(unknown)

    incomplete = dict(fixtures[0])
    incomplete["archive_event_id"] = stable_id(
        "archive_event_", "simulation_missing_provenance"
    )
    incomplete["provenance_hash"] = stable_id(
        "fixture_provenance_", "missing_provenance"
    )
    incomplete["pcap_packet_index"] = ""
    fixtures.append(incomplete)
    return fixtures


def promotion_sort_key(candidate: dict[str, str]) -> tuple[int, int, str]:
    return (
        0 if candidate["source_novelty"] == "new_source" else 1,
        0 if candidate["time_session_novelty"] == "new_session" else 1,
        candidate["candidate_id"],
    )


def simulate_promotion(
    candidates: list[dict[str, str]],
    global_cap: int,
    per_region_cap: int,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    promoted = []
    audit = []
    counts = Counter()
    for candidate in sorted(candidates, key=promotion_sort_key):
        if len(promoted) >= global_cap:
            decision = "deferred_global_cap"
        elif counts[candidate["label_region_id"]] >= per_region_cap:
            decision = "deferred_region_cap"
        else:
            decision = "promoted_simulation_only"
            promoted.append(candidate)
            counts[candidate["label_region_id"]] += 1
        audit.append(
            {
                "candidate_id": candidate["candidate_id"],
                "label_region_id": candidate["label_region_id"],
                "exact_attack_label": candidate["exact_attack_label"],
                "source_novelty": candidate["source_novelty"],
                "time_session_novelty": candidate["time_session_novelty"],
                "decision": decision,
                "budget_profile": "simulation_profile_global2_region1",
                "production_authorized": False,
            }
        )
    return promoted, audit


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    support_rows = read_csv(CF / "support_bank_sidecar.csv")
    eligible_candidates = read_csv_gz(CF / "eligible_candidate_manifest.csv.gz")
    diagnostic_rows = read_csv(CKD / "region_registry_by_variant.csv")

    if len(support_rows) != 512:
        raise RuntimeError(f"Expected frozen 512 rows, got {len(support_rows)}")
    if sum(row["bank_partition"] == "support_train" for row in support_rows) != 385:
        raise RuntimeError("Frozen support_train count changed")
    if sum(row["bank_partition"] == "support_val" for row in support_rows) != 127:
        raise RuntimeError("Frozen support_val count changed")

    registry = build_registry(support_rows, diagnostic_rows)
    if len(registry) != 10:
        raise RuntimeError(f"Expected ten label regions, got {len(registry)}")
    region_by_label = {
        row["exact_attack_label"]: row["label_region_id"] for row in registry
    }
    labels = set(region_by_label)
    train_view = support_view_rows(
        support_rows, "support_train", "support_train_view_v1", region_by_label
    )
    val_view = support_view_rows(
        support_rows, "support_val", "support_val_view_v1", region_by_label
    )
    if {row["provenance_hash"] for row in train_view} & {
        row["provenance_hash"] for row in val_view
    }:
        raise RuntimeError("support_train/support_val provenance overlap")

    archive_spec = archive_schema()
    candidate_spec = candidate_schema()
    existing_provenance = {row["provenance_hash"] for row in support_rows}
    known_sources: dict[str, set[tuple[str, str]]] = defaultdict(set)
    known_sessions: dict[str, set[str]] = defaultdict(set)
    for row in support_rows:
        label = row["exact_attack_label"]
        known_sources[label].add((row["pcap_path"], row["csv_path"]))
        known_sessions[label].add(
            f"{row['pcap_path']}|initial_predeployment_bank_v1"
        )

    events = simulation_events(support_rows, eligible_candidates)
    archive_audit = []
    accepted_events = []
    seen_ids: set[str] = set()
    seen_provenance: set[str] = set()
    for event in events:
        status, errors = validate_archive_event(
            event,
            archive_spec,
            labels,
            existing_provenance,
            seen_ids,
            seen_provenance,
        )
        archive_audit.append(
            {
                "archive_event_id": event["archive_event_id"],
                "human_confirmed_label": event.get(
                    "human_confirmed_label", ""
                ),
                "source_role": event.get("source_role", ""),
                "status": status,
                "errors": "|".join(errors) if errors else "none",
                "simulation_only": True,
            }
        )
        seen_ids.add(event["archive_event_id"])
        if event.get("provenance_hash"):
            seen_provenance.add(event["provenance_hash"])
        if status == "accepted_to_archive":
            accepted_events.append(event)

    candidate_rows = [
        candidate_from_event(
            event, region_by_label, known_sources, known_sessions
        )
        for event in accepted_events
    ]
    promoted, promotion_audit = simulate_promotion(
        candidate_rows, global_cap=2, per_region_cap=1
    )
    event_by_id = {
        event["archive_event_id"]: event for event in accepted_events
    }
    simulated_view = [dict(row) for row in train_view]
    for candidate in promoted:
        event = event_by_id[candidate["archive_event_id"]]
        simulated_view.append(
            {
                "view_version": "support_train_view_v2_simulation_only",
                "view_role": "support_train",
                "view_row_id": stable_id(
                    "view_row_",
                    (
                        "support_train_view_v2_simulation_only|"
                        + candidate["candidate_id"]
                    ),
                ),
                "sample_id": candidate["candidate_id"],
                "label_region_id": candidate["label_region_id"],
                "exact_attack_label": candidate["exact_attack_label"],
                "source_role": event["source_role"],
                "pcap_path": event["pcap_path"],
                "csv_path": event["csv_path"],
                "pcap_packet_index": event["pcap_packet_index"],
                "csv_row_index": event["csv_row_index"],
                "packet_timestamp": event["packet_timestamp"],
                "provenance_hash": event["provenance_hash"],
                "global_candidate_id": "",
                "feature_asset_uri": event["feature_asset_uri"],
                "feature_vector_sha256": event["feature_vector_sha256"],
                "origin": "simulation_online_label_archive",
                "promotion_event_id": stable_id(
                    "promotion_event_", candidate["candidate_id"]
                ),
                "immutable": False,
            }
        )

    invariant_rows = [
        {
            "check": "one_formal_region_per_exact_label",
            "pass": len(registry) == len(labels) == 10,
            "detail": f"registry_rows={len(registry)} labels={len(labels)}",
        },
        {
            "check": "all_label_regions_active_for_management",
            "pass": all(row["active_for_label_management"] for row in registry),
            "detail": "geometry status does not gate membership",
        },
        {
            "check": "unknown_traffic_autorouting_disabled",
            "pass": not any(
                row["allowed_for_unknown_traffic_autorouting"]
                for row in registry
            ),
            "detail": "label regions are memory-management objects",
        },
        {
            "check": "frozen_train_count",
            "pass": len(train_view) == 385,
            "detail": f"rows={len(train_view)}",
        },
        {
            "check": "frozen_val_count",
            "pass": len(val_view) == 127,
            "detail": f"rows={len(val_view)}",
        },
        {
            "check": "train_val_disjoint",
            "pass": not (
                {row["provenance_hash"] for row in train_view}
                & {row["provenance_hash"] for row in val_view}
            ),
            "detail": "provenance hashes disjoint",
        },
        {
            "check": "simulation_accepts_two_legal_events",
            "pass": len(accepted_events) == 2,
            "detail": f"accepted={len(accepted_events)}",
        },
        {
            "check": "simulation_quarantines_four_bad_events",
            "pass": len(events) - len(accepted_events) == 4,
            "detail": f"quarantined={len(events) - len(accepted_events)}",
        },
        {
            "check": "simulation_budgeted_promotion",
            "pass": len(promoted) == 2 and len(simulated_view) == 387,
            "detail": (
                f"promoted={len(promoted)} simulated_view={len(simulated_view)}"
            ),
        },
        {
            "check": "production_promotion_disabled",
            "pass": all(
                not row["production_authorized"] for row in promotion_audit
            ),
            "detail": "simulation profile cannot publish a model",
        },
        {
            "check": "support_val_unchanged_by_simulation",
            "pass": len(val_view) == 127,
            "detail": "support_val_view_v1 remains frozen",
        },
    ]
    errors = [row for row in invariant_rows if not row["pass"]]
    if errors:
        raise RuntimeError(f"Invariant failures: {errors}")

    write_csv(OUT / "label_region_registry_v1.csv", registry)
    write_csv(OUT / "support_train_view_v1.csv", train_view)
    write_csv(OUT / "support_val_view_v1.csv", val_view)
    write_json(OUT / "online_label_archive_schema.json", archive_spec)
    write_json(OUT / "region_candidate_schema.json", candidate_spec)
    write_json(
        OUT / "promotion_policy_v1.json",
        {
            "policy_version": "promotion_policy_v1",
            "formal_region_kind": "label_support_region",
            "membership_authority": "human_confirmed_exact_label",
            "hard_gates": [
                "registered_exact_label",
                "human_confirmation",
                "complete_provenance",
                "selection_allowed",
                "not_report_only",
                "not_sealed_final",
                "not_forbidden_for_fit",
                "not_duplicate_in_frozen_bank_archive_candidate_or_view",
            ],
            "ranking_order": [
                "new_provenance_source",
                "new_time_or_session",
                "lower_duplication_risk",
                "stable_event_id",
            ],
            "production_budget_profile": {
                "status": "not_empirically_certified",
                "global_extension_cap": None,
                "per_region_extension_cap": None,
                "promotion_enabled": False,
            },
            "simulation_budget_profile": {
                "status": "test_only",
                "global_extension_cap": 2,
                "per_region_extension_cap": 1,
                "promotion_enabled": True,
                "production_authorized": False,
            },
            "geometry_diagnostic_can_block_human_label_archive": False,
            "geometry_diagnostic_can_autoroute_unknown_traffic": False,
        },
    )
    write_csv(OUT / "simulation_archive_input.csv", events)
    write_csv(OUT / "simulation_archive_audit.csv", archive_audit)
    write_csv(OUT / "simulation_candidate_pool.csv", candidate_rows)
    write_csv(OUT / "simulation_promotion_audit.csv", promotion_audit)
    write_csv(
        OUT / "support_train_view_v2_simulation_only.csv", simulated_view
    )
    write_csv(OUT / "invariant_validation.csv", invariant_rows)
    write_json(
        OUT / "version_lineage.json",
        {
            "registry": {
                "version": "label_support_region_registry_v1",
                "parent": None,
                "rows": len(registry),
            },
            "initial_support_bank": {
                "version": "initial_support_bank_v1",
                "rows": 512,
                "immutable": True,
                "source": str(CF / "support_bank_sidecar.csv"),
                "sha256": sha256_file(CF / "support_bank_sidecar.csv"),
            },
            "support_train_view": {
                "version": "support_train_view_v1",
                "rows": 385,
                "parent": "initial_support_bank_v1",
            },
            "support_val_view": {
                "version": "support_val_view_v1",
                "rows": 127,
                "parent": "initial_support_bank_v1",
                "role_migration_allowed": False,
            },
            "simulation_view": {
                "version": "support_train_view_v2_simulation_only",
                "rows": len(simulated_view),
                "parent": "support_train_view_v1",
                "production_authorized": False,
            },
        },
    )
    write_md(
        OUT / "model_update_contract.md",
        [
            "# Model Update Contract v1",
            "",
            "## Inputs",
            "",
            "- positive attack rows: one frozen `support_train_view_vN`;",
            "- validation attack rows: frozen `support_val_view_v1` until a separately certified replacement exists;",
            "- ID and OOD benign development roles under their existing access restrictions;",
            "- one frozen training and weighting configuration.",
            "",
            "## Required Sequence",
            "",
            "1. Freeze archive cutoff and candidate pool hash.",
            "2. Freeze a certified production budget profile.",
            "3. Materialize a candidate support-train view without changing its parent.",
            "4. Freeze positive/ID/OOD sampling and label weighting.",
            "5. Train a candidate binary attack head.",
            "6. Evaluate low-FPR attack recall, AUROC/AUPRC, per-label recall, benign-OOD alarms, future-query behavior, unknown/review rate, and old-label forgetting.",
            "7. Publish only after explicit non-regression and release approval.",
            "",
            "## Prohibitions",
            "",
            "- support-val rows cannot silently migrate into training;",
            "- archive size does not define training-view size;",
            "- label regions cannot force unknown traffic into known labels;",
            "- no sealed-final tuning;",
            "- a failed candidate view remains auditable but does not replace the active view.",
        ],
    )
    write_md(
        OUT / "rollback_contract.md",
        [
            "# Rollback Contract v1",
            "",
            "Every released model records:",
            "",
            "- model version and parent model version;",
            "- support-train view version and hash;",
            "- region registry version;",
            "- training configuration hash;",
            "- evaluation report hash;",
            "- release decision and timestamp.",
            "",
            "Rollback restores the complete previous tuple, not only model weights:",
            "",
            "```text",
            "(model, support_train_view, registry, config, controller policy)",
            "```",
            "",
            "Archive events and rejected candidates are never deleted by rollback. They remain append-only evidence for later review.",
        ],
    )
    result = {
        "issue": ISSUE,
        "primary_verdict": (
            "label_support_region_registry_v1_and_versioned_update_"
            "protocol_ready"
        ),
        "formal_region_kind": "label_support_region",
        "label_regions": len(registry),
        "support_train_view_v1_rows": len(train_view),
        "support_val_view_v1_rows": len(val_view),
        "simulation_archive_events": len(events),
        "simulation_archive_accepted": len(accepted_events),
        "simulation_archive_quarantined": len(events) - len(accepted_events),
        "simulation_promoted": len(promoted),
        "simulation_support_train_view_rows": len(simulated_view),
        "production_promotion_enabled": False,
        "model_training": False,
        "controller_changed": False,
        "sealed_final_access": False,
        "initial_support_bank_mutated": False,
        "next_action": (
            "certify_update_budget_and_run_binary_attack_head_"
            "nonregression_ablation_after_issue27ckc_results"
        ),
    }
    write_json(OUT / "results.json", result)
    write_json(
        OUT / "config.json",
        {
            "formal_region_kind": "label_support_region",
            "registry_version": "label_support_region_registry_v1",
            "initial_support_bank_version": "initial_support_bank_v1",
            "support_train_view_version": "support_train_view_v1",
            "support_val_view_version": "support_val_view_v1",
            "geometric_region_role": "diagnostic_only",
            "production_budget_status": "not_empirically_certified",
        },
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27ckg Label Support Region Registry Summary",
            "",
            "primary_verdict: `label_support_region_registry_v1_and_versioned_update_protocol_ready`",
            "",
            "- formal region kind: `label_support_region`",
            "- exact-label regions: `10`",
            "- support_train_view_v1 rows: `385`",
            "- support_val_view_v1 rows: `127`",
            "- initial 512 mutated: `false`",
            "- unknown-traffic autorouting by region: `false`",
            "- geometric strong/weak role: `diagnostic only`",
            f"- simulation archive events: `{len(events)}`",
            f"- simulation accepted/quarantined: `{len(accepted_events)}` / `{len(events) - len(accepted_events)}`",
            f"- simulation promotions: `{len(promoted)}`",
            f"- simulation support view rows: `{len(simulated_view)}`",
            "- production promotion enabled: `false` pending empirical budget certification",
            "- model training: `false`",
            "- sealed-final access: `false`",
            "",
            "Close-out:",
            "",
            "```text",
            "solved: Instantiated one exact-label support-region registry, immutable initial train/validation views, append-only archive and candidate schemas, budgeted promotion policy, version lineage, model-update contract, rollback contract, and an end-to-end simulation.",
            "changed_mainline: yes",
            "active_blocker: production extension budgets and model non-regression are not yet empirically certified; wait for the frozen issue27ckc capability replay before choosing the first model-update ablation.",
            "frozen: one formal label-support-region abstraction, initial 385/127 role split, archive/candidate hard gates, version lineage, and rollback semantics.",
            "superseded: treating geometric strong/weak regions as a required deployment registry or using them to force unknown traffic into known labels.",
            "next_action: certify_update_budget_and_run_binary_attack_head_nonregression_ablation_after_issue27ckc_results.",
            "```",
        ],
    )
    write_md(
        OUT / "validation_report.md",
        [
            "# issue27ckg Validation Report",
            "",
            "Status: `PASS_PENDING_DETERMINISTIC_RERUN`",
            "",
            "- Ten unique exact-label regions instantiated.",
            "- All ten regions are active for label management regardless of geometry status.",
            "- Unknown-traffic automatic label routing is disabled.",
            "- Frozen 385 support-train and 127 support-val views reproduced with no overlap.",
            "- Two legal simulated human labels entered archive/candidate flow.",
            "- Duplicate, sealed, unknown-label, and incomplete-provenance fixtures were quarantined.",
            "- Simulation-only budget promoted two candidates and produced a 387-row candidate training view.",
            "- Production promotion remains disabled.",
            "- No model training, controller change, sealed-final access, or initial-bank mutation occurred.",
        ],
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
