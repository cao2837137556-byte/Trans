#!/usr/bin/env python3
"""Recover a completed CKBV scientific run from a pool-label audit defect.

This program is deliberately metadata-only.  It derives the missing
``core_ood_val_fit`` composition rows from the already emitted
``core_fit_benign`` rows, verifies that the frozen select pool is empty, and
proves that every scientific output hash is unchanged.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


GLOBAL = "GLOBAL_ATTACK_PRESERVATION"
MASK_SOURCE = "processed/iotsim-hydraulic-system-1.csv"
EXPECTED_FIT = (8682, 7329, 1353)
EXPECTED_SELECT = (0, 0, 0)
EXPECTED_FIT_ROLE_ROWS = {
    "id_calib": 0,
    "ood_val": 8682,
    "ood_stress": 0,
}
SCIENTIFIC_FILES = (
    "ckbu_single_seed_go_no_go.json",
    "attack_preservation_summary.csv",
    "strict_level2_summary.csv",
    "ckbu_candidate_selection.csv",
    "ckbu_support_training_usage.csv",
    "ckbu_record_predictions.csv.gz",
    "ckbu_review_audit.csv",
    "ckbu_role_usage_audit.csv",
    "ckbu_environment.json",
    "run_spec.json",
    "codex_readout.md",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scientific_hashes(root: Path) -> dict[str, str]:
    missing = [name for name in SCIENTIFIC_FILES if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"missing immutable scientific outputs: {missing}")
    return {name: sha256_file(root / name) for name in SCIENTIFIC_FILES}


def read_audit(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RuntimeError("sensitivity audit has no header")
        rows = list(reader)
        return list(reader.fieldnames), rows


def validate_role_usage(root: Path) -> dict[str, int]:
    """Prove that the GLOBAL core fit pool is exactly the ood_val role.

    The sensitivity audit records a combined ``core_fit_benign`` pool.  It is
    not scientifically valid to relabel that pool as ``core_ood_val_fit``
    merely because the total happens to be 8,682.  The immutable role-usage
    audit is the independent provenance needed to prove that id_calib and
    ood_stress contribute zero rows in this frozen run.
    """

    path = root / "ckbu_role_usage_audit.csv"
    if not path.is_file():
        raise RuntimeError(f"missing immutable role usage audit: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "protocol_run",
            "role",
            "frame_phase",
            "m1_phase",
            "eligible_role_rows",
            "frozen_target_rows",
            "outside_frozen_target_cohort",
            "target_alignment_incomplete",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise RuntimeError(f"role usage audit missing columns: {missing}")
        rows = list(reader)

    fit_rows = [
        row
        for row in rows
        if row.get("protocol_run") == GLOBAL
        and row.get("frame_phase") == "fit"
        and row.get("m1_phase") == "fit"
        and row.get("role") in EXPECTED_FIT_ROLE_ROWS
    ]
    by_role: dict[str, int] = {}
    for role, expected in EXPECTED_FIT_ROLE_ROWS.items():
        role_rows = [row for row in fit_rows if row.get("role") == role]
        if len(role_rows) != 1:
            raise RuntimeError(
                f"expected one GLOBAL fit role audit row for {role}; "
                f"got {len(role_rows)}"
            )
        row = role_rows[0]
        eligible = int(float(row["eligible_role_rows"]))
        frozen = int(float(row["frozen_target_rows"]))
        outside = int(float(row["outside_frozen_target_cohort"]))
        incomplete = int(float(row["target_alignment_incomplete"]))
        if (eligible, frozen, outside, incomplete) != (expected, expected, 0, 0):
            raise RuntimeError(
                f"GLOBAL fit role provenance drift for {role}: "
                f"{eligible}/{frozen}/{outside}/{incomplete} != "
                f"{expected}/{expected}/0/0"
            )
        by_role[role] = frozen
    return by_role


def counts(row: dict[str, str]) -> tuple[int, int, int]:
    return tuple(
        int(float(row[name]))
        for name in ("rows_full", "rows_observable", "rows_masked")
    )


def only_row(
    rows: list[dict[str, str]],
    *,
    held_value: str,
    pool: str,
    row_kind: str,
    source_group: str = "__ALL__",
) -> dict[str, str]:
    found = [
        row
        for row in rows
        if row.get("held_value") == held_value
        and row.get("pool") == pool
        and row.get("row_kind") == row_kind
        and row.get("source_group") == source_group
    ]
    if len(found) != 1:
        raise RuntimeError(
            "expected exactly one audit row: "
            f"{held_value}/{pool}/{row_kind}/{source_group}; got {len(found)}"
        )
    return found[0]


def validate_source_audit(rows: list[dict[str, str]]) -> None:
    fit = only_row(
        rows,
        held_value=GLOBAL,
        pool="core_fit_benign",
        row_kind="pool_total",
    )
    if counts(fit) != EXPECTED_FIT:
        raise RuntimeError(
            f"frozen core fit composition drift: {counts(fit)} != {EXPECTED_FIT}"
        )
    masked = only_row(
        rows,
        held_value=GLOBAL,
        pool="core_fit_benign",
        row_kind="per_source",
        source_group=MASK_SOURCE,
    )
    if counts(masked) != (1353, 0, 1353):
        raise RuntimeError(
            "hydraulic-1 frozen fit composition drift: "
            f"{counts(masked)} != (1353, 0, 1353)"
        )
    select = only_row(
        rows,
        held_value=GLOBAL,
        pool="core_ood_val_select",
        row_kind="pool_total",
    )
    if counts(select) != EXPECTED_SELECT:
        raise RuntimeError(
            f"frozen core select composition drift: {counts(select)} != {EXPECTED_SELECT}"
        )
    leaked = [
        row
        for row in rows
        if row.get("pool") == "core_ood_val_select"
        and row.get("row_kind") == "per_source"
    ]
    if leaked:
        raise RuntimeError("core ood_val select unexpectedly has per-source records")
    bad_gate = [
        row
        for row in rows
        if row.get("row_kind") == "select_c1_gate"
        and (
            int(float(row["rows_masked"])) != 0
            or int(float(row["rows_full"]))
            != int(float(row["rows_observable"]))
        )
    ]
    if bad_gate:
        raise RuntimeError("fit-only raw51 mask leaked into select C1 gate rows")


def derive_fit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    source_rows = [
        row
        for row in rows
        if row.get("pool") == "core_fit_benign"
        and row.get("row_kind") in {"per_source", "pool_total"}
    ]
    if not source_rows:
        raise RuntimeError("no core_fit_benign composition rows to derive")
    derived: list[dict[str, str]] = []
    for source in source_rows:
        row = dict(source)
        row["pool"] = "core_ood_val_fit"
        derived.append(row)
    return derived


def validate_derived(rows: list[dict[str, str]]) -> None:
    fit = only_row(
        rows,
        held_value=GLOBAL,
        pool="core_ood_val_fit",
        row_kind="pool_total",
    )
    if counts(fit) != EXPECTED_FIT:
        raise RuntimeError(
            f"recovered core fit composition drift: {counts(fit)} != {EXPECTED_FIT}"
        )
    masked = only_row(
        rows,
        held_value=GLOBAL,
        pool="core_ood_val_fit",
        row_kind="per_source",
        source_group=MASK_SOURCE,
    )
    if counts(masked) != (1353, 0, 1353):
        raise RuntimeError("recovered hydraulic-1 fit composition drift")


def atomic_write(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    fd, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def recover(
    root: Path,
    *,
    source_job_id: str,
    source_partition: str,
) -> dict[str, Any]:
    audit = root / "ckbu_raw51_mask_sensitivity_audit.csv"
    if not audit.is_file():
        raise RuntimeError(f"missing sensitivity audit: {audit}")
    before_scientific = scientific_hashes(root)
    fit_role_rows = validate_role_usage(root)
    role_usage_sha256 = sha256_file(root / "ckbu_role_usage_audit.csv")
    fieldnames, rows = read_audit(audit)
    validate_source_audit(rows)

    existing = [
        row
        for row in rows
        if row.get("pool") == "core_ood_val_fit"
        and row.get("row_kind") in {"per_source", "pool_total"}
    ]
    before_audit_sha = sha256_file(audit)
    backup = root / "ckbu_raw51_mask_sensitivity_audit.pre_pool_semantic_recovery.csv"
    if existing:
        validate_derived(rows)
        if not backup.is_file():
            raise RuntimeError("recovered audit exists but immutable pre-recovery backup is missing")
    else:
        if backup.exists():
            raise RuntimeError("pre-recovery backup exists but audit lacks recovered fit rows")
        shutil.copyfile(audit, backup)
        rows.extend(derive_fit_rows(rows))
        atomic_write(audit, fieldnames, rows)
        _, roundtrip = read_audit(audit)
        validate_source_audit(roundtrip)
        validate_derived(roundtrip)

    after_scientific = scientific_hashes(root)
    unchanged = before_scientific == after_scientific
    if not unchanged:
        raise RuntimeError("scientific outputs changed during metadata-only recovery")
    result: dict[str, Any] = {
        "status": "CKBV_POSTFORMAL_POOL_SEMANTIC_RECOVERY",
        "source_job_id": str(source_job_id),
        "source_partition": str(source_partition),
        "original_failure_phase": "validate_and_pack",
        "models_retrained": False,
        "pcap_redecoded": False,
        "scores_or_gates_changed": False,
        "scientific_hashes_unchanged": True,
        "scientific_hashes": after_scientific,
        "audit_sha256_before": sha256_file(backup),
        "audit_sha256_after": sha256_file(audit),
        "fit_pool_full": EXPECTED_FIT[0],
        "fit_pool_observable": EXPECTED_FIT[1],
        "fit_pool_masked": EXPECTED_FIT[2],
        "select_pool_full": EXPECTED_SELECT[0],
        "select_pool_observable": EXPECTED_SELECT[1],
        "select_pool_masked": EXPECTED_SELECT[2],
        "raw51_masked_source": MASK_SOURCE,
        "fit_role_rows": fit_role_rows,
        "role_usage_audit_sha256": role_usage_sha256,
        "recovery_idempotent": bool(existing),
        "input_audit_sha256_at_invocation": before_audit_sha,
    }
    output = root / "ckbv_postformal_recovery.json"
    atomic_write_json(output, result)
    return result


def synthetic_rows() -> tuple[list[str], list[dict[str, str]]]:
    fields = [
        "held_value",
        "pool",
        "source_group",
        "row_kind",
        "rows_full",
        "rows_observable",
        "rows_masked",
        "mask_rate",
    ]
    rows = [
        {
            "held_value": GLOBAL,
            "pool": "core_fit_benign",
            "source_group": MASK_SOURCE,
            "row_kind": "per_source",
            "rows_full": "1353",
            "rows_observable": "0",
            "rows_masked": "1353",
            "mask_rate": "1.0",
        },
        {
            "held_value": GLOBAL,
            "pool": "core_fit_benign",
            "source_group": "processed/other.csv",
            "row_kind": "per_source",
            "rows_full": "7329",
            "rows_observable": "7329",
            "rows_masked": "0",
            "mask_rate": "0.0",
        },
        {
            "held_value": GLOBAL,
            "pool": "core_fit_benign",
            "source_group": "__ALL__",
            "row_kind": "pool_total",
            "rows_full": "8682",
            "rows_observable": "7329",
            "rows_masked": "1353",
            "mask_rate": str(round(1353 / 8682, 6)),
        },
        {
            "held_value": GLOBAL,
            "pool": "core_ood_val_select",
            "source_group": "__ALL__",
            "row_kind": "pool_total",
            "rows_full": "0",
            "rows_observable": "0",
            "rows_masked": "0",
            "mask_rate": "0.0",
        },
        {
            "held_value": GLOBAL,
            "pool": "select_benign_c1_and_gate",
            "source_group": "__ALL__",
            "row_kind": "select_c1_gate",
            "rows_full": "4000",
            "rows_observable": "4000",
            "rows_masked": "0",
            "mask_rate": "0.0",
        },
    ]
    return fields, rows


def write_synthetic_role_usage(path: Path, *, ood_val_rows: int = 8682) -> None:
    fields = [
        "protocol_run",
        "role",
        "frame_phase",
        "m1_phase",
        "eligible_role_rows",
        "frozen_target_rows",
        "outside_frozen_target_cohort",
        "target_alignment_incomplete",
    ]
    rows = [
        {
            "protocol_run": GLOBAL,
            "role": role,
            "frame_phase": "fit",
            "m1_phase": "fit",
            "eligible_role_rows": str(
                ood_val_rows if role == "ood_val" else expected
            ),
            "frozen_target_rows": str(
                ood_val_rows if role == "ood_val" else expected
            ),
            "outside_frozen_target_cohort": "0",
            "target_alignment_incomplete": "0",
        }
        for role, expected in EXPECTED_FIT_ROLE_ROWS.items()
    ]
    atomic_write(path, fields, rows)


def contract_unit() -> None:
    fields, rows = synthetic_rows()
    validate_source_audit(rows)
    recovered = rows + derive_fit_rows(rows)
    validate_derived(recovered)

    # Exercise the actual filesystem recovery path, including immutable backup,
    # atomic CSV/JSON finalization, scientific-hash preservation, and a second
    # idempotent invocation.  This catches the class of post-computation defect
    # that only appears after all model outputs already exist.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for index, name in enumerate(SCIENTIFIC_FILES):
            if name == "ckbu_role_usage_audit.csv":
                continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f"immutable-scientific-output-{index}\n".encode())
        write_synthetic_role_usage(root / "ckbu_role_usage_audit.csv")
        audit = root / "ckbu_raw51_mask_sensitivity_audit.csv"
        atomic_write(audit, fields, rows)
        original_audit_sha = sha256_file(audit)
        original_scientific = scientific_hashes(root)

        first = recover(
            root,
            source_job_id="154917",
            source_partition="amd",
        )
        backup = (
            root
            / "ckbu_raw51_mask_sensitivity_audit.pre_pool_semantic_recovery.csv"
        )
        _, first_rows = read_audit(audit)
        validate_source_audit(first_rows)
        validate_derived(first_rows)
        if (
            first["recovery_idempotent"] is not False
            or not backup.is_file()
            or sha256_file(backup) != original_audit_sha
            or sha256_file(audit) == original_audit_sha
            or scientific_hashes(root) != original_scientific
        ):
            raise RuntimeError("first post-formal recovery contract failed")

        second = recover(
            root,
            source_job_id="154917",
            source_partition="amd",
        )
        if (
            second["recovery_idempotent"] is not True
            or sha256_file(backup) != original_audit_sha
            or scientific_hashes(root) != original_scientific
            or not (root / "ckbv_postformal_recovery.json").is_file()
        ):
            raise RuntimeError("idempotent post-formal recovery contract failed")

        # A matching aggregate count is insufficient: recovery must reject a
        # role audit that says the rows came from another fit role.
        write_synthetic_role_usage(
            root / "ckbu_role_usage_audit.csv", ood_val_rows=8681
        )
        try:
            recover(root, source_job_id="154917", source_partition="amd")
        except RuntimeError:
            pass
        else:
            raise RuntimeError("recovery accepted invalid fit-role provenance")

    bad_fit = [dict(row) for row in rows]
    bad_fit[2]["rows_full"] = "8681"
    try:
        validate_source_audit(bad_fit)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("contract unit failed to reject fit composition drift")

    bad_select = [dict(row) for row in rows]
    bad_select[3]["rows_full"] = "1"
    bad_select[3]["rows_observable"] = "1"
    try:
        validate_source_audit(bad_select)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("contract unit failed to reject select leakage")
    print(
        json.dumps(
            {
                "status": "CKBV_POSTFORMAL_RECOVERY_CONTRACT_PASS",
                "fit_pool": EXPECTED_FIT,
                "select_pool": EXPECTED_SELECT,
                "models_retrained": False,
                "pcap_redecoded": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("recover", "contract-unit"), required=True)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--source-job-id")
    parser.add_argument("--source-partition", choices=("amd", "intel"))
    args = parser.parse_args()
    if args.mode == "contract-unit":
        contract_unit()
        return
    if args.run_root is None or not args.source_job_id or not args.source_partition:
        parser.error("recover requires --run-root, --source-job-id and --source-partition")
    result = recover(
        args.run_root,
        source_job_id=args.source_job_id,
        source_partition=args.source_partition,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
