"""Accept downloaded small receipts; full arrays remain on HPC."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    retrieval = read("RETRIEVAL.json")
    for name, digest in retrieval["sha256"].items():
        assert sha(HERE / name) == digest, name
    delivery = read("DELIVERY.json")
    for name, digest in delivery["pins"].items():
        assert sha(HERE / name) == digest, name
    assert sha(HERE / "receiver.py") == delivery["receiver_sha256"]
    state = retrieval["state"]
    assert state["stage"] == "SOURCE_FEATURES_READY" and state["training_jobs"] == 0
    for phase in ("ADMISSION", "FEATURE_PREFLIGHT", "FEATURE_BUILD"):
        assert state[phase + "_STOP"] is None
        job = read(phase + "_JOB.json")
        assert job["cpu"] == 1 and job["memory_gib"] == 8
        scheduler = read(phase + "_SCHEDULER.json")
        assert scheduler["returncode"] == 0
        row = scheduler["stdout"].splitlines()[0].split("|")
        assert row[:3] == [job["job_id"], "COMPLETED", "0:0"]
    admission = read("ADMISSION_RESULT.json")
    preflight = read("FEATURE_PREFLIGHT_RESULT.json")
    result = read("FEATURE_BUILD_RESULT.json")
    assert admission["status"] == preflight["status"] == result["status"] == "PASS"
    assert not admission["training_started"] and not result["training_started"]
    assert preflight["independent_checks"] == preflight["queries"] == 57
    assert preflight["restart_queries"] == 42
    catalog = {c["capture_id"]: c for c in read("RAW_CATALOG.json")}
    details = result["details"]
    assert len(details) == result["captures"] == admission["queried_captures"] == 200
    limits = read("TRAINING_SPEC_FROZEN.json")["engine_limits"]
    for capture, item in details.items():
        assert item["status"] == "PASS" and item["capture"] == capture
        assert item["source_sha256"] == catalog[capture]["sha256"]
        assert item["frames"] == catalog[capture]["expected_packets"]
        assert sum(item["parser_counts"].values()) == item["frames"]
        assert 0 < item["restart_queries"] <= item["queries"]
        assert item["max_clock_debt_ns"] <= 10**9
        assert item["peak_entries"] <= limits["max_active_queue_entries"]
        assert item["peak_groups"] <= limits["max_active_groups"]
        assert item["rss_peak_bytes"] < 6 * 1024**3
        for key in ("features_sha256", "query_sha256", "source_sha256"):
            assert re.fullmatch("[0-9a-f]{64}", item[key])
    for key in ("queries", "frames", "restart_queries", "independent_checks"):
        assert sum(x[key] for x in details.values()) == result[key]
    assert result["queries"] == sum(x["rows"] for x in admission["roles"].values()) == 1094929
    assert set(result["arrays"]) == set(admission["roles"])
    for role, array in result["arrays"].items():
        assert array["bytes"] == admission["roles"][role]["rows"] * 8 * 8 + 128
        assert re.fullmatch("[0-9a-f]{64}", array["sha256"])
    scheduler = read("FEATURE_BUILD_SCHEDULER.json")["stdout"].splitlines()
    rss = int(scheduler[1].split("|")[4].removesuffix("K"))
    assert rss < 8 * 1024**2
    out = {
        "result": "PASS", "scope": "SOURCE_FEATURES_ONLY",
        "impact": "All source rows have aligned context features; training and evaluation remain pending",
        "next": "REAL_TRAINING_RUNTIME_GATE", "training_jobs": 0,
        "job_id": "182332", "elapsed": "00:12:07", "slurm_max_rss_kib": rss,
        "captures": result["captures"], "frames": result["frames"], "queries": result["queries"],
        "preflight_independent_queries": 57, "full_restart_queries": result["restart_queries"],
        "max_clock_debt_ns": max(x["max_clock_debt_ns"] for x in details.values()),
        "max_queue_entries": max(x["peak_entries"] for x in details.values()),
        "max_groups": max(x["peak_groups"] for x in details.values()),
        "arrays": result["arrays"], "roles": {k: v["rows"] for k, v in admission["roles"].items()},
        "receipt_sha256": retrieval["sha256"], "delivery_sha256": sha(HERE / "DELIVERY.json"),
        "acceptor_sha256": sha(Path(__file__)),
        "verification_scope": "Local receipt and pinned-code audit; per-row UID, coverage, finite values and array hashes verified by pinned HPC worker; arrays not downloaded",
        "unqueried_catalog_captures": sorted(set(catalog) - set(details)),
    }
    (HERE / "FINAL_ACCEPTANCE.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("receipt_sha256", "unqueried_catalog_captures", "arrays")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
