from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22"
DATA = (
    ROOT.parents[1]
    / "datasets"
    / "external"
    / "ton_iot_raw_network"
    / "extracted"
)
SUPPORT = OUT / "aux_process_support_candidate_manifest.csv"
PAIR_AUDIT = OUT / "pair_exact_join_audit.csv"
RESERVED = OUT / "reserved_toniot_conn_sources.csv"
INPUT_HASHES = OUT / "input_file_hashes.csv"
CONTRACT = OUT / "contract.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def as_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized not in {"true", "false"}:
        raise RuntimeError(f"invalid boolean value: {value!r}")
    return normalized == "true"


def normalized_port(value: str) -> str:
    return str(int(float(str(value).strip())))


def exact_key(
    ts: str,
    src_ip: str,
    src_port: str,
    dst_ip: str,
    dst_port: str,
    proto: str,
) -> tuple[int, str, str, str, str, str]:
    return (
        math.floor(float(ts)),
        str(src_ip).strip(),
        normalized_port(src_port),
        str(dst_ip).strip(),
        normalized_port(dst_port),
        str(proto).strip().lower(),
    )


def key_hash(key: tuple[int, str, str, str, str, str]) -> str:
    payload = "\x1f".join(str(part) for part in key).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def zeek_fields(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#fields\t"):
                return line.rstrip("\r\n").split("\t")[1:]
            if not line.startswith("#"):
                break
    raise RuntimeError(f"Zeek #fields header missing: {path}")


def write_manifest(paths: list[Path]) -> None:
    with (OUT / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["artifact", "path", "sha256", "bytes"])
        writer.writeheader()
        for path in sorted(paths, key=lambda item: item.name):
            writer.writerow(
                {
                    "artifact": path.name,
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )


def main() -> None:
    for path in (SUPPORT, PAIR_AUDIT, RESERVED, INPUT_HASHES, CONTRACT):
        if not path.is_file():
            raise FileNotFoundError(path)
    rows = read_csv(SUPPORT)
    pair_audit = read_csv(PAIR_AUDIT)
    reserved = read_csv(RESERVED)
    checks: dict[str, bool] = {}

    checks["support_rows_5000"] = len(rows) == 5_000
    checks["unique_record_ids"] = len({row["record_id"] for row in rows}) == 5_000
    checks["no_raw_ip_columns"] = not any(
        field in rows[0] for field in ("src_ip", "dst_ip", "id.orig_h", "id.resp_h")
    )
    counts = Counter((row["mechanism_family"], row["role"]) for row in rows)
    checks["balanced_fit_select_counts"] = counts == Counter(
        {
            ("reconnaissance_scan", "aux_process_fit"): 2_000,
            ("reconnaissance_scan", "aux_process_select"): 500,
            ("credential_bruteforce", "aux_process_fit"): 2_000,
            ("credential_bruteforce", "aux_process_select"): 500,
        }
    )
    fit_sources = {row["conn_relative_path"] for row in rows if row["role"] == "aux_process_fit"}
    select_sources = {
        row["conn_relative_path"] for row in rows if row["role"] == "aux_process_select"
    }
    checks["fit_select_source_files_disjoint"] = bool(fit_sources) and not (fit_sources & select_sources)
    reserved_paths = {row["relative_path"] for row in reserved}
    checks["seven_reserved_sources_zero_use"] = (
        len(reserved_paths) == 7
        and all(int(row["used_rows"]) == 0 for row in reserved)
        and not ({row["conn_relative_path"] for row in rows} & reserved_paths)
    )
    checks["scope_flags_fail_closed"] = all(
        as_bool(row["allowed_for_static_completed_connection_supervision"])
        and not as_bool(row["allowed_for_temporal_replay"])
        and not as_bool(row["allowed_for_Gotham_C1_fit"])
        and not as_bool(row["allowed_for_Gotham_threshold_selection"])
        and not as_bool(row["report_or_sealed"])
        for row in rows
    )
    checks["mechanism_mapping_not_label_equivalence"] = all(
        row["cross_dataset_mapping"]
        == "mechanism_family_only_not_exact_Gotham_label_equivalence"
        for row in rows
    )

    by_conn: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_gt: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_conn[row["conn_relative_path"]].append(row)
        by_gt[row["groundtruth_relative_path"]].append(row)

    raw_conn: dict[str, dict[str, str]] = {}
    conn_occurrences: Counter[tuple[str, str]] = Counter()
    for relative, selected in by_conn.items():
        path = DATA / relative
        fields = zeek_fields(path)
        targets = {int(row["conn_line_index"]): row for row in selected}
        selected_keys = {row["key_sha256"] for row in selected}
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            data_index = 0
            for line in f:
                if not line or line.startswith("#"):
                    continue
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) != len(fields):
                    raise RuntimeError(f"raw Zeek column mismatch: {relative}:{data_index}")
                raw = dict(zip(fields, parts))
                try:
                    digest = key_hash(
                        exact_key(
                            raw["ts"],
                            raw["id.orig_h"],
                            raw["id.orig_p"],
                            raw["id.resp_h"],
                            raw["id.resp_p"],
                            raw["proto"],
                        )
                    )
                except (ValueError, TypeError):
                    data_index += 1
                    continue
                if digest in selected_keys:
                    conn_occurrences[(relative, digest)] += 1
                if data_index in targets:
                    record = targets[data_index]
                    if digest != record["key_sha256"]:
                        raise RuntimeError(f"conn line/key mismatch: {relative}:{data_index}")
                    raw_conn[record["record_id"]] = raw
                data_index += 1

    raw_gt: dict[str, dict[str, str]] = {}
    gt_occurrences: Counter[tuple[str, str]] = Counter()
    for relative, selected in by_gt.items():
        path = DATA / relative
        targets = {int(row["groundtruth_line_index"]): row for row in selected}
        selected_keys = {row["key_sha256"] for row in selected}
        expected_labels = {row["key_sha256"]: row["ton_groundtruth_label"] for row in selected}
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for line_index, raw in enumerate(csv.DictReader(f)):
                try:
                    digest = key_hash(
                        exact_key(
                            raw["ts"],
                            raw["src_ip"],
                            raw["src_port"],
                            raw["dst_ip"],
                            raw["dst_port"],
                            raw["proto"],
                        )
                    )
                except (ValueError, TypeError):
                    continue
                if (
                    digest in selected_keys
                    and raw["type"].strip().lower() == expected_labels[digest]
                ):
                    gt_occurrences[(relative, digest)] += 1
                if line_index in targets:
                    record = targets[line_index]
                    if digest != record["key_sha256"]:
                        raise RuntimeError(f"GT line/key mismatch: {relative}:{line_index}")
                    if raw["type"].strip().lower() != record["ton_groundtruth_label"]:
                        raise RuntimeError(f"GT label mismatch: {relative}:{line_index}")
                    raw_gt[record["record_id"]] = raw

    checks["all_selected_raw_conn_lines_verified"] = len(raw_conn) == 5_000
    checks["all_selected_raw_gt_lines_verified"] = len(raw_gt) == 5_000
    checks["selected_conn_keys_unique_in_source"] = all(
        conn_occurrences[(row["conn_relative_path"], row["key_sha256"])] == 1
        for row in rows
    )
    checks["selected_gt_keys_unique_for_label"] = all(
        gt_occurrences[(row["groundtruth_relative_path"], row["key_sha256"])] == 1
        for row in rows
    )
    checks["manifest_features_match_raw_conn"] = all(
        raw_conn[row["record_id"]]["id.orig_p"] == row["orig_p"]
        and raw_conn[row["record_id"]]["id.resp_p"] == row["resp_p"]
        and raw_conn[row["record_id"]]["proto"] == row["proto"]
        and raw_conn[row["record_id"]]["service"] == row["service"]
        and raw_conn[row["record_id"]]["duration"] == row["duration"]
        and raw_conn[row["record_id"]]["conn_state"] == row["conn_state"]
        and raw_conn[row["record_id"]]["history"] == row["history"]
        for row in rows
    )
    source_local_ids_ok = True
    for pair_id in {row["pair_id"] for row in rows}:
        selected = [row for row in rows if row["pair_id"] == pair_id]
        nodes = sorted(
            {raw_conn[row["record_id"]]["id.orig_h"] for row in selected}
            | {raw_conn[row["record_id"]]["id.resp_h"] for row in selected}
        )
        ids = {node: index for index, node in enumerate(nodes)}
        source_local_ids_ok &= all(
            ids[raw_conn[row["record_id"]]["id.orig_h"]]
            == int(row["source_local_orig_node_id"])
            and ids[raw_conn[row["record_id"]]["id.resp_h"]]
            == int(row["source_local_resp_node_id"])
            for row in selected
        )
    checks["source_local_anonymous_node_ids_reproduced"] = source_local_ids_ok

    recorded_hashes = {row["path"]: row for row in read_csv(INPUT_HASHES)}
    def recorded_path(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT / path

    checks["all_input_hashes_reproduced"] = all(
        recorded_path(path).is_file()
        and sha256(recorded_path(path)) == row["sha256"]
        and recorded_path(path).stat().st_size == int(row["bytes"])
        for path, row in recorded_hashes.items()
    )
    checks["pair_audit_counts_cover_manifest"] = (
        len(pair_audit) == 4
        and sum(int(row["selected_rows"]) for row in pair_audit) == 5_000
        and all(int(row["unambiguous_exact_join_rows"]) >= int(row["selected_rows"]) for row in pair_audit)
    )

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    checks["contract_is_candidate_not_model_result"] = (
        contract.get("status")
        == "TONIOT_AUX_PROCESS_SUPPORT_CANDIDATE_READY_FOR_STATIC_EXPERT_ONLY"
        and contract.get("model_training") is False
        and contract.get("hpc_submission") is False
        and contract.get("Gotham_support_mutated") is False
        and contract.get("active_Gotham_support_train_rows") == 385
        and contract.get("active_Gotham_support_val_rows") == 127
        and contract.get("permanent_Gotham_report_families_used") == 0
    )

    failures = sorted(name for name, passed in checks.items() if not passed)
    result: dict[str, Any] = {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "support_manifest_sha256": sha256(SUPPORT),
        "contract_sha256": sha256(CONTRACT),
        "scientific_scope": "external_auxiliary_support_gate_only_not_model_performance",
    }
    (OUT / "independent_validation.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_manifest(
        [
            path
            for path in OUT.iterdir()
            if path.is_file() and path.name != "manifest.csv"
        ]
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
