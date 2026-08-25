#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "issue27ckde_d0_identifiability_audit_v1.py"
SPEC = importlib.util.spec_from_file_location("ckde", str(MODULE_PATH))
assert SPEC and SPEC.loader
ckde = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckde)
ROOT = HERE.parents[1]


def synthetic(include_attack=True, one_session=False):
    rows = []
    for i in range(8):
        rows.append({"uid": "b%d" % i, "role": "aux_fit", "source_group": "dev", "device_family": "fam", "recorded_index": i, "global_pool": "fit", "plan_scope": "FIT_PROBE_ONLY"})
    if include_attack:
        rows.append({"uid": "a", "role": "support_train", "source_group": "dev", "device_family": "fam", "recorded_index": 9, "global_pool": "fit", "plan_scope": "FIT_PROBE_ONLY"})
    plan = pd.DataFrame(rows)
    target = pd.DataFrame([{"uid": row["uid"], "source_group": "dev", "raw_source_path": "dev.pcap", "dataset_kind": "direct_pcap", "target_event_position_within_capture": row["recorded_index"]} for row in rows])
    sessions = pd.DataFrame([{"uid": row["uid"], "session_id": "one" if one_session else "s%s" % row["uid"], "timestamp_epoch": row["recorded_index"], "event_position": row["recorded_index"]} for row in rows])
    return plan, target, sessions


class CKDED0Tests(unittest.TestCase):
    def test_01_python39_module(self):
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_02_python39_tests(self):
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_03_contract_hash(self):
        self.assertEqual(ckde.sha256_file(ROOT / ckde.CONTRACT_REL), ckde.CONTRACT_SHA256)

    def test_04_pin_inputs(self):
        self.assertIn("session_metadata", ckde.pin_inputs(ROOT))

    def test_05_paired_synthetic(self):
        census, pairing, summary = ckde.build_census(*synthetic(include_attack=True))
        self.assertEqual(ckde.choose_verdict(summary), "CKDE_D0_PAIRED_CALIBRATION_IDENTIFIABLE")
        self.assertTrue(bool(pairing.loc[0, "paired_device_eligible"]))

    def test_06_unpaired_synthetic(self):
        _, _, summary = ckde.build_census(*synthetic(include_attack=False))
        self.assertEqual(ckde.choose_verdict(summary), "CKDE_D0_UNPAIRED_DEVELOPMENT_ONLY")

    def test_07_one_session_not_independent(self):
        _, _, summary = ckde.build_census(*synthetic(include_attack=False, one_session=True))
        self.assertEqual(ckde.choose_verdict(summary), "CKDE_D0_NO_CAUSAL_BENIGN_PREFIX")

    def test_08_source_lineage_mismatch_rejected(self):
        plan, target, sessions = synthetic()
        target.loc[0, "source_group"] = "other"
        with self.assertRaises(RuntimeError):
            ckde.build_census(plan, target, sessions)

    def test_09_exact_uid_join_rejected(self):
        plan, target, sessions = synthetic()
        sessions = sessions.iloc[:-1]
        with self.assertRaises(RuntimeError):
            ckde.build_census(plan, target, sessions)

    def test_10_live_verdict(self):
        payload = json.loads((ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_verdict.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "CKDE_D0_UNPAIRED_DEVELOPMENT_ONLY")

    def test_11_live_device_count(self):
        payload = json.loads((ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_verdict.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["devices_total"], 28)
        self.assertEqual(payload["devices_with_causal_benign_prefix_suffix"], 23)

    def test_12_no_paired_live_device(self):
        frame = pd.read_csv(ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_same_device_pairing.csv")
        self.assertEqual(int(frame["paired_device_eligible"].sum()), 0)

    def test_13_session_counts_positive(self):
        payload = json.loads((ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_verdict.json").read_text(encoding="utf-8"))
        self.assertGreater(payload["eligible_prefix_sessions"], 0)
        self.assertGreater(payload["eligible_suffix_sessions"], 0)

    def test_14_no_label_or_score_reads(self):
        payload = json.loads((ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_role_open_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["row_labels_read"], 0)
        self.assertEqual(payload["report_score_files_opened"], 0)
        self.assertEqual(payload["final_files_opened"], 0)

    def test_15_d1_not_executable(self):
        payload = json.loads((ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_verdict.json").read_text(encoding="utf-8"))
        self.assertFalse(payload["d1_executable"])

    def test_16_no_strict_conformal_claim(self):
        payload = json.loads((ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_verdict.json").read_text(encoding="utf-8"))
        self.assertFalse(payload["strict_session_conformal_claim_authorized"])

    def test_17_sha256s_validate(self):
        base = ROOT / "runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local"
        for line in (base / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, name = line.split(maxsplit=1)
            self.assertEqual(ckde.sha256_file(base / name.strip()), digest)

    def test_18_failure_has_no_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "out"
            try:
                raise RuntimeError("synthetic")
            except RuntimeError as exc:
                ckde.failure_only(out, exc)
            self.assertFalse((out / "ckde_d0_verdict.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
