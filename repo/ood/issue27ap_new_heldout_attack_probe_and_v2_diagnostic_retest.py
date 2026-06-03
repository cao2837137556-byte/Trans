from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402

ISSUE = "issue27ap_new_heldout_attack_probe_and_v2_diagnostic_retest_2026-06-03"
OUT = ROOT / "runs" / ISSUE
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_new_heldout_attack_probe_v1"
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AO = ROOT / "runs" / "issue27ao_repair_support_eval_contract_v2_before_head_repair_2026-06-03"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_TRAIN_ROLE = "attack_support_train_v2"
SUPPORT_VAL_ROLE = "attack_support_val_v2"
NEW_HELDOUT_ROLE = "new_heldout_attack_eval_probe"
TARGET_OOD_ALARM = 0.01
SEEDS = [42, 43, 44]

HEAVY_ATTACKS = [
    {
        "csv_member": "processed/iotsim-ip-camera-museum-1.csv",
        "pcap_member": "raw/malicious/mirai-infection/iotsim-ip-camera-museum-1_0-0_to_OpenvSwitch-29_1-0.pcap",
        "first_attack_timestamp": 1737235770.488062,
        "attack_type": "mirai-infection",
        "max_scan_packets": 760_000,
        "packet_limit": 3000,
    },
    {
        "csv_member": "processed/iotsim-ip-camera-street-1.csv",
        "pcap_member": "raw/malicious/mirai-infection/iotsim-ip-camera-street-1_0-0_to_OpenvSwitch-24_1-0.pcap",
        "first_attack_timestamp": 1737235800.982347,
        "attack_type": "mirai-infection",
        "max_scan_packets": 540_000,
        "packet_limit": 3000,
    },
]


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


def sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def role_mask(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray([r.get("role") == role and r.get("model_ready_hint", "").lower() == "true" for r in sidecar], dtype=bool)


def load_medium_asset() -> dict[str, Any]:
    cert = json.loads((ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json").read_text(encoding="utf-8"))
    c = cert["reset_at_split_boundary"]
    x = np.load(c["X_115D_path"])
    y = np.load(c["y_path"]).astype(int)
    sidecar = load_csv(Path(c["sidecar_path"]))
    return {"X": x, "y": y, "sidecar": sidecar, "certificate": c}


def load_indices(path: Path, contract_id: str) -> np.ndarray:
    rows = load_csv(path)
    return np.asarray([int(r["global_row_index"]) for r in rows if r.get("contract_id") == contract_id], dtype=np.int64)


def save_new_attack(x: np.ndarray, sidecar: list[dict[str, Any]]) -> dict[str, Any]:
    DERIVED.mkdir(parents=True, exist_ok=True)
    x_path = DERIVED / "gotham_kitsune115_new_heldout_attack_probe_X.npy"
    sidecar_path = DERIVED / "gotham_kitsune115_new_heldout_attack_probe_sidecar.csv.gz"
    np.save(x_path, x)
    with gzip.open(sidecar_path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(sidecar[0].keys()))
        writer.writeheader()
        writer.writerows(sidecar)
    return {
        "X_path": str(x_path),
        "X_sha256": sha256(x_path),
        "sidecar_path": str(sidecar_path),
        "sidecar_sha256": sha256(sidecar_path),
        "rows": int(x.shape[0]),
        "columns": int(x.shape[1]),
    }


def extract_new_heldout() -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]]]:
    arrays: list[np.ndarray] = []
    sidecars: list[dict[str, Any]] = []
    metas: list[dict[str, Any]] = []
    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        for item in HEAVY_ATTACKS:
            smoke = ab.SmokeFile(
                role=NEW_HELDOUT_ROLE,
                split_role="new_heldout_attack_eval_probe",
                pcap_member=item["pcap_member"],
                csv_member=item["csv_member"],
                expected_binary_label="attack",
                expected_attack_type=item["attack_type"],
                selection_reason="issue27ap previously deferred heavy ip-camera heldout attack probe",
            )
            nstat = ab.RestoredNetStat115()
            x, sc, meta = ab.read_pcap_vectors(
                zf,
                smoke,
                nstat,
                packet_limit=int(item["packet_limit"]),
                warmup_packets=0,
                strategy="reset_at_split_boundary_new_heldout_attack",
                state_id=f"new_heldout::{Path(item['csv_member']).stem}",
                record_start_ts=float(item["first_attack_timestamp"]),
                max_scan_packets=int(item["max_scan_packets"]),
            )
            arrays.append(x)
            sidecars.extend(sc)
            meta.update({
                "csv_member": item["csv_member"],
                "pcap_member": item["pcap_member"],
                "first_attack_timestamp": item["first_attack_timestamp"],
                "target_packet_limit": item["packet_limit"],
                "target_max_scan_packets": item["max_scan_packets"],
                "extraction_status": "ok" if x.shape[0] > 0 else "no_rows_extracted",
            })
            metas.append(meta)
    if not arrays:
        return np.empty((0, 115), dtype=np.float32), [], metas
    return np.vstack(arrays).astype(np.float32), sidecars, metas


def threshold_from_support(scores_id: np.ndarray, scores_ood: np.ndarray, scores_support_val: np.ndarray) -> tuple[float, dict[str, Any]]:
    vals = np.unique(np.quantile(np.concatenate([scores_id, scores_ood, scores_support_val]), np.linspace(0, 1, 1001)))
    candidates = []
    for t in vals:
        ood_alarm = float(np.mean(scores_ood >= t))
        support_det = float(np.mean(scores_support_val >= t))
        id_alarm = float(np.mean(scores_id >= t))
        if ood_alarm <= TARGET_OOD_ALARM:
            candidates.append((support_det, -ood_alarm, -id_alarm, float(t), ood_alarm, id_alarm))
    if not candidates:
        t = float(np.quantile(scores_ood, 1 - TARGET_OOD_ALARM))
        return t, {"fallback": "ood_quantile_no_support_feasible_candidate", "ood_val_alarm": float(np.mean(scores_ood >= t)), "support_val_detection": float(np.mean(scores_support_val >= t))}
    best = sorted(candidates, reverse=True)[0]
    t = best[3]
    return t, {"fallback": "", "ood_val_alarm": best[4], "id_alarm": best[5], "support_val_detection": best[0]}


def run_histgb_retest(medium: dict[str, Any], new_x: np.ndarray, contract_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    x = medium["X"]
    y = medium["y"]
    sidecar = medium["sidecar"]
    train_idx = load_indices(ISSUE27AO / "contract_v2_support_train_indices.csv", contract_id)
    val_idx = load_indices(ISSUE27AO / "contract_v2_support_val_indices.csv", contract_id)
    id_idx = np.flatnonzero(role_mask(sidecar, ID_ROLE))
    ood_idx = np.flatnonzero(role_mask(sidecar, OOD_VAL_ROLE))
    final_idx = np.flatnonzero(role_mask(sidecar, FINAL_OOD_ROLE))
    rows = []
    role_rows = []
    for seed in SEEDS:
        fit_idx = np.asarray(sorted(np.concatenate([id_idx, train_idx]).tolist()), dtype=np.int64)
        model = HistGradientBoostingClassifier(max_iter=30, max_leaf_nodes=15, learning_rate=0.08, random_state=seed)
        model.fit(x[fit_idx], y[fit_idx])

        def score(a: np.ndarray) -> np.ndarray:
            p = model.predict_proba(a)
            return p[:, 1] if p.ndim == 2 and p.shape[1] > 1 else p.reshape(-1)

        sid = score(x[id_idx])
        sood = score(x[ood_idx])
        sval = score(x[val_idx])
        sfinal = score(x[final_idx])
        snew = score(new_x)
        threshold, audit = threshold_from_support(sid, sood, sval)
        rows.append({
            "contract_id": contract_id,
            "model": "HistGB_fixed_issue27ak_params",
            "seed": seed,
            "threshold": threshold,
            "threshold_roles": f"{ID_ROLE}|{OOD_VAL_ROLE}|{SUPPORT_VAL_ROLE}",
            "fit_roles": f"{ID_ROLE}|{SUPPORT_TRAIN_ROLE}",
            "final_ood_alarm_report_only": float(np.mean(sfinal >= threshold)),
            "new_heldout_attack_detection_report_only": float(np.mean(snew >= threshold)),
            "ood_val_alarm": audit.get("ood_val_alarm"),
            "support_val_detection": audit.get("support_val_detection"),
            "threshold_fallback": audit.get("fallback", ""),
            "final_ood_used_for_selection": False,
            "new_heldout_attack_used_for_selection": False,
        })
        role_rows.append({
            "seed": seed,
            "fit_roles": f"{ID_ROLE}|{SUPPORT_TRAIN_ROLE}",
            "threshold_roles": f"{ID_ROLE}|{OOD_VAL_ROLE}|{SUPPORT_VAL_ROLE}",
            "score_only_roles": f"{FINAL_OOD_ROLE}|{NEW_HELDOUT_ROLE}",
            "uses_new_heldout_for_support_selection": False,
            "uses_new_heldout_for_threshold": False,
            "uses_final_ood_for_threshold": False,
            "forbidden_role_access": False,
        })
    return rows, role_rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    medium = load_medium_asset()
    new_x, new_sidecar, metas = extract_new_heldout()
    extract_status = "ok" if new_x.shape[0] > 0 else "blocked_no_new_heldout_rows"
    data_cert = save_new_attack(new_x, new_sidecar) if new_x.shape[0] > 0 else {}
    write_csv(OUT / "new_heldout_attack_extraction_report.csv", metas)
    if new_sidecar:
        write_csv(OUT / "new_heldout_attack_sidecar_preview.csv", new_sidecar[:200])
    retest_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    if extract_status == "ok":
        retest_rows, role_rows = run_histgb_retest(medium, new_x, "file_balanced_v2")
    write_csv(OUT / "new_heldout_v2_histgb_retest_by_seed.csv", retest_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)
    if retest_rows:
        attack = np.asarray([float(r["new_heldout_attack_detection_report_only"]) for r in retest_rows])
        final = np.asarray([float(r["final_ood_alarm_report_only"]) for r in retest_rows])
        ood = np.asarray([float(r["ood_val_alarm"]) for r in retest_rows])
        summary_metrics = {
            "new_heldout_attack_detection_mean": float(attack.mean()),
            "new_heldout_attack_detection_worst": float(attack.min()),
            "final_ood_alarm_max": float(final.max()),
            "ood_val_alarm_max": float(ood.max()),
        }
    else:
        summary_metrics = {}
    if extract_status != "ok":
        verdict = "new_heldout_attack_probe_blocked_by_extraction"
    elif summary_metrics["final_ood_alarm_max"] <= TARGET_OOD_ALARM and summary_metrics["new_heldout_attack_detection_worst"] >= 0.6:
        verdict = "new_heldout_v2_diagnostic_signal_positive"
    elif summary_metrics["new_heldout_attack_detection_worst"] < 0.2:
        verdict = "new_heldout_v2_diagnostic_signal_weak_support_shift_persists"
    else:
        verdict = "new_heldout_v2_diagnostic_signal_mixed"
    write_md(OUT / "issue27ap_decision.md", [
        "# Issue27ap Decision",
        "",
        f"- primary_verdict: `{verdict}`",
        "- Scope: new held-out heavy ip-camera attack probe plus v2 diagnostic retest.",
        "- Support_train/support_val are fixed from issue27ao file_balanced_v2.",
        "- New heldout attack rows were not used for support selection, threshold, or model selection.",
        "- This is still diagnostic, not formal benchmark.",
    ])
    next_action = "issue27aq_construct_larger_attack_contract_or_slurm_full_materialization"
    write_md(OUT / "issue27aq_next_action.md", [
        "# Issue27aq Next Action",
        "",
        f"- recommended_next_issue: `{next_action}`",
        "- If new heldout signal is weak, do not add more heads; expand/fix attack contract and materialization first.",
        "- Formal evaluation requires held-out attack files not consumed by support or contract design.",
    ])
    write_md(OUT / "summary.md", [
        "# Issue27ap Summary",
        "",
        "1. issue27ap completed: yes",
        f"2. primary_verdict: `{verdict}`",
        "3. new attack source: deferred heavy ip-camera PCAPs",
        f"4. new heldout extraction status: `{extract_status}`",
        f"5. new heldout rows: {int(new_x.shape[0])}",
        f"6. data certificate: `{json.dumps(data_cert, sort_keys=True) if data_cert else '{}'}`",
        "7. support source: issue27ao file_balanced_v2 support_train/support_val",
        "8. support selected from new heldout: false",
        "9. threshold uses new heldout: false",
        "10. final OOD used for selection: false",
        f"11. diagnostic metrics: `{json.dumps(summary_metrics, sort_keys=True)}`",
        "12. formal benchmark: false",
        f"13. next action: `{next_action}`",
        "14. commit hash: pending",
    ])
    write_md(OUT / "claim_update_after_issue27ap.md", [
        "# Claim Update After Issue27ap",
        "",
        "- Issue27ap is a diagnostic probe on newly materialized held-out heavy attack files.",
        "- It cannot be written as formal performance because it is still medium/probe scale.",
        "- New heldout attack is not used for support/threshold/model selection.",
    ])
    write_md(OUT / "command.txt", ["python repo/ood/issue27ap_new_heldout_attack_probe_and_v2_diagnostic_retest.py"])
    (OUT / "config.json").write_text(json.dumps({
        "issue": ISSUE,
        "contract_id": "file_balanced_v2",
        "new_heldout_files": HEAVY_ATTACKS,
        "target_ood_alarm": TARGET_OOD_ALARM,
        "seeds": SEEDS,
        "formal_benchmark": False,
    }, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps({
        "inputs": {
            "issue27ao_support_train": str(ISSUE27AO / "contract_v2_support_train_indices.csv"),
            "issue27ao_support_val": str(ISSUE27AO / "contract_v2_support_val_indices.csv"),
            "gotham_zip": str(ab.ZIP_PATH),
        },
        "outputs": [p.name for p in sorted(OUT.glob("*"))],
    }, indent=2, sort_keys=True), encoding="utf-8")
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    append_doc(MAINLINE_DOCS / "mainline_handoff.md", "<!-- issue27ap -->", [
        "<!-- issue27ap -->",
        "## issue27ap_new_heldout_attack_probe_and_v2_diagnostic_retest_2026-06-03",
        "",
        f"- primary_verdict: `{verdict}`",
        "- Newly materialized held-out heavy ip-camera attack probe; support fixed from issue27ao v2.",
        "- Diagnostic only; not formal benchmark.",
    ])
    append_doc(MAINLINE_DOCS / "mainline_experiment_map.md", "<!-- issue27ap -->", [
        "<!-- issue27ap -->",
        "## issue27ap",
        "",
        f"- verdict: `{verdict}`",
        "- route: new held-out heavy attack probe plus v2 diagnostic retest.",
        "- claim boundary: diagnostic only.",
    ])


if __name__ == "__main__":
    main()
