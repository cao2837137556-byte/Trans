#!/usr/bin/env python
"""Synthetic invariant tests for issue27ce support-bank protocol.

These tests intentionally use tiny in-memory fixtures. They do not read real
Gotham assets, do not train models, and do not compute detection metrics.
"""

from __future__ import annotations

from dataclasses import dataclass


FORBIDDEN_FINAL_ROLES = {
    "sealed_final_attack",
    "sealed_final_ood",
    "final_ood_benign_eval",
    "attack_eval",
    "dev_future_attack_query",
    "same_file_time_forward_dev_query",
}

FORBIDDEN_LABELS = {"Benign", "Unknown", "", None}


@dataclass(frozen=True)
class Row:
    sample_id: str
    source_role: str
    label: str | None
    timestamp_aligned: bool = True
    pcap_paired: bool = True
    quarantined: bool = False
    bank_partition: str | None = None


def is_support_eligible(row: Row) -> bool:
    if row.source_role in FORBIDDEN_FINAL_ROLES:
        return False
    if row.source_role != "attack_support_candidate_pool":
        return False
    if row.label in FORBIDDEN_LABELS:
        return False
    if not row.timestamp_aligned:
        return False
    if not row.pcap_paired:
        return False
    if row.quarantined:
        return False
    return True


def validate_support_bank(rows: list[Row], support_budget: int | None = None) -> list[str]:
    errors: list[str] = []
    seen_train = set()
    seen_val = set()
    for row in rows:
        if row.bank_partition in {"support_train", "support_val"} and not is_support_eligible(row):
            errors.append(f"ineligible_support:{row.sample_id}")
        if row.bank_partition == "support_train":
            seen_train.add(row.sample_id)
        if row.bank_partition == "support_val":
            seen_val.add(row.sample_id)
    dup = seen_train & seen_val
    if dup:
        errors.append("train_val_overlap:" + ",".join(sorted(dup)))
    if support_budget is not None and len(seen_train | seen_val) > support_budget:
        errors.append("support_budget_overflow")
    return errors


def run_tests() -> None:
    ok = Row("ok1", "attack_support_candidate_pool", "TCP Scan", bank_partition="support_train")
    assert is_support_eligible(ok)

    assert not is_support_eligible(Row("bad_final", "sealed_final_attack", "TCP Scan"))
    assert not is_support_eligible(Row("bad_label", "attack_support_candidate_pool", "Benign"))
    assert not is_support_eligible(Row("bad_unknown", "attack_support_candidate_pool", "Unknown"))
    assert not is_support_eligible(Row("bad_time", "attack_support_candidate_pool", "TCP Scan", timestamp_aligned=False))
    assert not is_support_eligible(Row("bad_pcap", "attack_support_candidate_pool", "TCP Scan", pcap_paired=False))
    assert not is_support_eligible(Row("bad_quarantine", "attack_support_candidate_pool", "TCP Scan", quarantined=True))

    errors = validate_support_bank(
        [
            Row("a", "attack_support_candidate_pool", "TCP Scan", bank_partition="support_train"),
            Row("a", "attack_support_candidate_pool", "TCP Scan", bank_partition="support_val"),
        ]
    )
    assert any(e.startswith("train_val_overlap") for e in errors)

    errors = validate_support_bank(
        [
            Row("x", "sealed_final_attack", "TCP Scan", bank_partition="support_train"),
            Row("y", "attack_support_candidate_pool", "Unknown", bank_partition="support_val"),
        ]
    )
    assert "ineligible_support:x" in errors
    assert "ineligible_support:y" in errors

    errors = validate_support_bank(
        [
            Row("a", "attack_support_candidate_pool", "TCP Scan", bank_partition="support_train"),
            Row("b", "attack_support_candidate_pool", "Telnet Brute Force", bank_partition="support_val"),
        ],
        support_budget=1,
    )
    assert "support_budget_overflow" in errors


if __name__ == "__main__":
    run_tests()
    print("issue27ce protocol invariant tests passed")

