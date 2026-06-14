from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402
import issue27bx3_500k_cache_aware_materialization_retry as bx3  # noqa: E402
import issue27by_runtime_optimized_1m_or_slurm_materialization as by  # noqa: E402

ISSUE = "issue27bz_slurm_1m_cache_execution_and_certified_merge_2026-06-14"
OUT = ROOT / "runs" / ISSUE
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_1m_certified_v1"
ASSET_TAG = "1m_certified"
TARGET_TOTAL_ROWS = 1_000_000
SUCCESS_VERDICT = "slurm_1m_certified_asset_ready_for_larger_sanity_replay"
PARTIAL_VERDICT = "slurm_1m_certified_asset_blocked_by_cache_or_merge_audit"
NEXT_RECOMMENDED_ISSUE = "issue27ca_larger_sanity_replay_on_certified_1m_asset"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def preflight() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hpc_report = by.OUT / "hpc_validation_report.txt"
    readiness = by.OUT / "role_cache_readiness.csv"
    rows: list[dict[str, object]] = []

    hpc_text = hpc_report.read_text(encoding="utf-8") if hpc_report.exists() else ""
    hpc_pass = "status=PASS" in hpc_text
    rows.append(
        {
            "check": "hpc_validation_report",
            "path": str(hpc_report),
            "status": "pass" if hpc_pass else "fail",
            "details": "status=PASS found" if hpc_pass else "missing PASS report",
        }
    )
    if not hpc_pass:
        write_csv(OUT / "merge_preflight.csv", rows)
        raise RuntimeError("HPC validation report is missing or not PASS.")

    if not readiness.exists():
        rows.append({"check": "role_cache_readiness", "path": str(readiness), "status": "fail", "details": "missing"})
        write_csv(OUT / "merge_preflight.csv", rows)
        raise RuntimeError("Missing role_cache_readiness.csv.")
    readiness_rows = read_csv(readiness)
    for row in readiness_rows:
        missing = int(row["missing"])
        rows.append(
            {
                "check": "role_missing",
                "role": row["role"],
                "target": row["target"],
                "existing": row["existing"],
                "stateful": row["stateful"],
                "status": "pass" if missing == 0 else "fail",
                "details": f"missing={missing}",
            }
        )
    if any(r["status"] == "fail" for r in rows):
        write_csv(OUT / "merge_preflight.csv", rows)
        raise RuntimeError("At least one role still has missing rows.")

    plans = by.build_plans()
    cache_rows: list[dict[str, object]] = []
    for plan in plans:
        status, cache_dir = by.cache_status(plan)
        expected = "stateful_train_chain_required" if plan.role == "id_benign_train" else "existing_valid"
        ok = status == expected
        cache_rows.append(
            {
                "role": plan.role,
                "csv_member": plan.csv_member,
                "pcap_member": plan.pcap_member,
                "target_rows": plan.target_rows,
                "cache_key": plan.cache_key,
                "cache_status": status,
                "source_cache_dir": cache_dir,
                "preflight_status": "pass" if ok else "fail",
            }
        )
    write_csv(OUT / "cache_resolution_preflight.csv", cache_rows)
    if any(row["preflight_status"] == "fail" for row in cache_rows):
        write_csv(OUT / "merge_preflight.csv", rows)
        raise RuntimeError("Cache resolution did not satisfy the strict 1M merge gate.")

    local_quarantine = sorted((by.QUARANTINE_DIR).glob("*")) if by.QUARANTINE_DIR.exists() else []
    write_csv(
        OUT / "local_stale_quarantine_audit.csv",
        [
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "decision": "ignored_not_used_for_certified_merge",
                "reason": "local historical smoke quarantine; HPC validation reported quarantine_files=0",
            }
            for path in local_quarantine
        ],
    )
    rows.append(
        {
            "check": "local_stale_quarantine",
            "status": "pass",
            "details": f"{len(local_quarantine)} local historical quarantine files ignored",
        }
    )
    write_csv(OUT / "merge_preflight.csv", rows)
    write_md(
        OUT / "merge_preflight_report.md",
        [
            "# issue27bz Merge Preflight",
            "",
            "- HPC validation report: PASS.",
            "- All roles have missing=0.",
            "- All non-ID roles resolve to valid completed caches.",
            "- `id_benign_train` remains stateful and will be regenerated serially during certified merge.",
            f"- Local historical quarantine files ignored: {len(local_quarantine)}.",
            "- No model training, threshold tuning, or benchmark is run in this issue.",
        ],
    )


def configure_bx3() -> None:
    bx3.ISSUE = ISSUE
    bx3.OUT = OUT
    bx3.PLAN_PATH = by.PLAN_PATH
    bx3.DERIVED = DERIVED
    bx3.CACHE_DIR = by.CACHE_DIR
    bx3.LOG_PATH = DERIVED / "issue27bz_certified_merge_log.txt"
    bx3.ASSET_TAG = ASSET_TAG
    bx3.SUCCESS_VERDICT = SUCCESS_VERDICT
    bx3.PARTIAL_VERDICT = PARTIAL_VERDICT
    bx3.NEXT_RECOMMENDED_ISSUE = NEXT_RECOMMENDED_ISSUE
    bx3.DECISION_FILE = "issue27bz_decision.md"
    bx3.NEXT_ACTION_FILE = "issue27ca_next_action.md"
    bx3.COMMAND_TEXT = "python repo/ood/issue27bz_slurm_1m_cache_execution_and_certified_merge.py"
    bx3.RUN_TYPE = "slurm_1m_cache_execution_and_certified_merge"
    bx3.DOC_TITLE = "issue27bz Slurm 1M Cache Execution and Certified Merge"
    bx3.CACHE_READ_DIRS = [by.CACHE_DIR, by.BX4_CACHE_DIR, by.BX3_CACHE_DIR]
    bx3.TARGET_TOTAL_ROWS = TARGET_TOTAL_ROWS


def postprocess() -> None:
    summary_path = OUT / "summary.md"
    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    summary_text += (
        "\n## issue27bz Additional Certification\n\n"
        "- HPC validation was checked before merge and was PASS.\n"
        "- No quarantine cache was used; local stale quarantine files are ignored.\n"
        "- Non-ID rows came from completed valid caches; ID train rows were regenerated as the stateful train chain.\n"
        "- This asset is a data asset only; it is not a model result.\n"
    )
    summary_path.write_text(summary_text, encoding="utf-8")

    final_report = {
        "issue": ISSUE,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "hpc_validation_report": str(by.OUT / "hpc_validation_report.txt"),
        "input_plan": str(by.PLAN_PATH),
        "cache_read_dirs": [str(p) for p in [by.CACHE_DIR, by.BX4_CACHE_DIR, by.BX3_CACHE_DIR]],
        "derived_asset_dir": str(DERIVED),
        "forbidden": ["model_training", "threshold_tuning", "formal_benchmark", "final_selection"],
    }
    (OUT / "issue27bz_certification_context.json").write_text(json.dumps(final_report, indent=2), encoding="utf-8")


def main() -> None:
    preflight()
    configure_bx3()
    bx3.main()
    postprocess()


if __name__ == "__main__":
    main()
