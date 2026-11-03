"""Synthetic contracts; no real source, saved score, model or tokenizer reads."""

import copy
import hashlib
import random
import unittest

import legacy_commissioning_attack_v1 as audit


def row(index, correct=True, **changes):
    result = dict(uid="uid-%03d" % index, role="DEV", owner="owner-dev", device="device-dev",
                  capture_id="capture-a", source_sha256="a" * 64,
                  component_id="component-%03d" % index, protocol=6, activity="attack-http",
                  candidate_rank=2, timestamp=1000.0 + index, frame=index + 1,
                  observed_transport_streams=1, saved_q_correct=correct)
    result.update(changes)
    return result


def fixture():
    rows = [row(i, correct=False) for i in range(11)] + [row(i) for i in range(11, 21)]
    return rows, [r["uid"] for r in rows[:11]]


def query():
    return dict(row(10, correct=False), stream_id="tcp:2")


def packet(frame, stream="tcp:2", **changes):
    result = {k: query()[k] for k in audit.IDENTITY_KEYS}
    result.update(frame=frame, timestamp=999.0 + frame, stream_id=stream, direction=0, burst_id=0)
    result.update(changes)
    return result


def tokenizer(inputs, outputs, complete=True):
    return dict(input_frame_ids=inputs, output_source_frame_ids=outputs, complete=complete,
                tokenizer_sha256="b" * 64, config_sha256="c" * 64)


def label(**changes):
    q = query()
    result = {k: q[k] for k in ("owner", "capture_id", "source_sha256")}
    result.update(target_frame=q["frame"], rule_sha256="d" * 64, rule_applies_to_target=True)
    result.update(changes)
    return result


class Selection(unittest.TestCase):
    def test_all_eleven_misses_and_order_independence(self):
        rows, misses = fixture()
        before = copy.deepcopy(rows)
        expected = audit.select_attack_audit(rows, misses)
        random.Random(41).shuffle(rows)
        self.assertEqual(expected, audit.select_attack_audit(rows, list(reversed(misses))))
        self.assertEqual(before, sorted(rows, key=lambda r: r["uid"]))
        selected = [x["metadata"]["uid"] for x in expected["selected"]]
        self.assertTrue(set(misses).issubset(selected))
        self.assertEqual(len(selected), len(set(selected)))
        self.assertEqual(expected["real_source_reads"], 0)
        self.assertFalse(expected["source_bytes_verified"])

    def test_exact_hash_order(self):
        rows, misses = fixture()
        result = audit.select_attack_audit(rows, misses)
        for pair in result["matched_correct"]:
            wanted = sorted(rows[11:], key=lambda r: (
                hashlib.sha256((audit.AUDIT_SALT + "|" + pair["miss_uid"] + "|" + r["uid"]).encode()).hexdigest(),
                r["uid"]))[:2]
            self.assertEqual(pair["correct_uids"], [r["uid"] for r in wanted])

    def test_eleven_is_not_a_configurable_fixture_limit(self):
        rows, misses = fixture()
        for roster in (misses[:10], misses + ["extra"], misses[:10] + [misses[0]]):
            with self.assertRaises(audit.AuditError):
                audit.select_attack_audit(rows, roster)
        with self.assertRaisesRegex(audit.AuditError, "ROSTER_MISMATCH"):
            audit.select_attack_audit(rows, misses[:10] + ["different"])
        rows.append(row(90, correct=False))
        with self.assertRaisesRegex(audit.AuditError, "ROSTER_MISMATCH"):
            audit.select_attack_audit(rows, misses)

    def test_shortages_do_not_relax_matching(self):
        rows, misses = fixture()
        rows = rows[:11] + [row(30), row(31, protocol=17), row(32, activity="other"),
                           row(33, candidate_rank=4), row(34, capture_id="capture-b")]
        result = audit.select_attack_audit(rows, misses)
        for pair in result["matched_correct"]:
            self.assertEqual(pair["correct_uids"], ["uid-030"])
        self.assertEqual(sum(s["kind"] == "MATCHED_Q_CORRECT" for s in result["shortages"]), 11)
        self.assertTrue(all(not s["conditions_relaxed"] for s in result["shortages"]))

    def test_same_component_cannot_match_its_miss(self):
        rows, misses = fixture()
        rows = rows[:11] + [row(30, component_id=rows[0]["component_id"], candidate_rank=3)]
        result = audit.select_attack_audit(rows, misses)
        self.assertEqual(result["matched_correct"][0]["correct_uids"], [])
        self.assertEqual(result["matched_correct"][1]["correct_uids"], ["uid-030"])

    def test_structural_is_component_sampled_with_earliest_endpoint(self):
        rows, misses = fixture()
        # New, isolated stratum with three components and two endpoints each.
        extra = [row(40 + i * 2 + j, protocol=17, activity="udp", candidate_rank=16 + j,
                     observed_transport_streams=3, component_id="udp-%d" % i)
                 for i in range(3) for j in range(2)]
        result = audit.select_attack_audit(rows + list(reversed(extra)), misses)
        strata = next(s for s in result["structural_strata"] if s["stratum"][1] == "udp")
        chosen_components = sorted({r["component_id"] for r in extra}, key=lambda cid: (
            hashlib.sha256((audit.AUDIT_SALT + "|" + cid).encode()).hexdigest(), cid))[:2]
        wanted = [min((r for r in extra if r["component_id"] == cid), key=lambda r: r["timestamp"])["uid"]
                  for cid in chosen_components]
        self.assertEqual(strata["chosen_uids"], wanted)
        self.assertEqual(strata["eligible_components"], 3)

    def test_unknown_stream_count_is_auditable_not_invented(self):
        rows, misses = fixture()
        rows[0]["observed_transport_streams"] = None
        result = audit.select_attack_audit(rows, misses)
        entry = next(s for s in result["shortages"] if s["kind"] == "INCONCLUSIVE_TRANSPORT_STREAM_METADATA")
        self.assertEqual(entry["uids"], [misses[0]])
        self.assertIn(misses[0], [x["metadata"]["uid"] for x in result["selected"]])

    def test_no_score_label_or_hypothesis_fields(self):
        rows, misses = fixture()
        for name in ("label", "score", "token_contents", "target_in_prefix", "cross_stream_tokens"):
            bad = copy.deepcopy(rows)
            bad[0][name] = 1
            with self.subTest(name=name), self.assertRaisesRegex(audit.AuditError, "ROW_SCHEMA"):
                audit.select_attack_audit(bad, misses)

    def test_roles_and_learn_rows(self):
        rows, misses = fixture()
        learn = row(60, correct=False, role="LEARN", owner="owner-learn", device="device-learn")
        result = audit.select_attack_audit(rows + [learn], misses)
        self.assertEqual(result["validated_learn_rows_not_selected"], 1)
        self.assertNotIn(learn["uid"], [x["metadata"]["uid"] for x in result["selected"]])
        for role in ("DEVICE_HOLDOUT", "CONFIRMATION", "CAL", "FINAL"):
            with self.subTest(role=role), self.assertRaisesRegex(audit.AuditError, "FORBIDDEN_ROLE"):
                audit.select_attack_audit(rows + [dict(learn, role=role)], misses)

    def test_conflicting_duplicate_and_lineage_fail_closed(self):
        rows, misses = fixture()
        cases = [rows[0], dict(rows[0], uid="different"),
                 row(60, component_id=rows[0]["component_id"], protocol=17),
                 row(60, source_sha256="f" * 64), row(60, role="LEARN"),
                 row(60, owner="alias-owner")]
        for extra in cases:
            with self.subTest(extra=extra), self.assertRaises(audit.AuditError):
                audit.select_attack_audit(rows + [extra], misses)

    def test_type_boundaries(self):
        rows, misses = fixture()
        cases = [("candidate_rank", -1), ("candidate_rank", True), ("protocol", True),
                 ("protocol", 1), ("frame", 0), ("timestamp", float("nan")),
                 ("timestamp", float("inf")), ("saved_q_correct", 1),
                 ("observed_transport_streams", 0), ("uid", "bad|uid")]
        for key, value in cases:
            bad = copy.deepcopy(rows)
            bad[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(audit.AuditError):
                audit.select_attack_audit(bad, misses)
        self.assertEqual([audit.rank_bucket(x) for x in (0, 1, 3, 4, 15, 16, 99)],
                         ["0", "1-3", "1-3", "4-15", "4-15", "16+", "16+"])

    def test_candidate_rank_and_time_cannot_conflict_with_frame_order(self):
        rows, misses = fixture()
        for rank in (0, 2):
            extra = row(50, component_id=rows[0]["component_id"], candidate_rank=rank)
            with self.assertRaisesRegex(audit.AuditError, "CANDIDATE_RANK_ORDER"):
                audit.select_attack_audit(rows + [extra], misses)
        extra = row(50, component_id=rows[0]["component_id"], candidate_rank=3, timestamp=999)
        with self.assertRaisesRegex(audit.AuditError, "SESSION_TIME_ORDER"):
            audit.select_attack_audit(rows + [extra], misses)


class Trace(unittest.TestCase):
    def test_complete_trace_and_no_causal_claim(self):
        result = audit.trace_attack_sample(query(), [packet(10), packet(11)],
                                          tokenizer([10, 11], [10, 11, 11]), label())
        self.assertEqual(result["status"], "OBSERVATIONS_COMPLETE_NOT_CAUSAL_ATTRIBUTION")
        self.assertTrue(result["target_in_prefix"])
        self.assertTrue(result["target_survives_tokenizer"])
        self.assertFalse(result["cross_stream_prefix"])
        self.assertEqual(result["causal_attribution"], "NOT_ESTABLISHED")
        self.assertEqual(result["model_forwards"], 0)

    def test_prefix_presence_does_not_imply_tokenizer_presence(self):
        result = audit.trace_attack_sample(query(), [packet(10), packet(11)], tokenizer([10, 11], [10]), label())
        self.assertTrue(result["target_in_prefix"])
        self.assertFalse(result["target_survives_tokenizer"])
        result = audit.trace_attack_sample(query(), [packet(10), packet(11)])
        self.assertIsNone(result["target_survives_tokenizer"])
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_missing_semantics_remain_unknown(self):
        result = audit.trace_attack_sample(query(), None)
        self.assertIsNone(result["target_in_prefix"])
        self.assertIsNone(result["cross_stream_prefix"])
        self.assertEqual(result["label_rule_status"], "INCONCLUSIVE")
        self.assertEqual(len(result["missing_evidence"]), 5)
        result = audit.trace_attack_sample(query(), [packet(11, stream=None, direction=None, burst_id=None)])
        self.assertIsNone(result["cross_stream_prefix"])
        self.assertEqual(result["prefix_saturation"]["status"], "INCONCLUSIVE")

    def test_incomplete_tokenizer_cannot_prove_absence(self):
        result = audit.trace_attack_sample(query(), [packet(10), packet(11)], tokenizer([10, 11], [10], False))
        self.assertIsNone(result["target_survives_tokenizer"])
        result = audit.trace_attack_sample(query(), [packet(10), packet(11)], tokenizer([10, 11], [11], False))
        self.assertTrue(result["target_survives_tokenizer"])

    def test_retained_past_stream_mixing_is_a_finding_only(self):
        result = audit.trace_attack_sample(query(), [packet(9, "tcp:1"), packet(10, None), packet(11)])
        self.assertTrue(result["cross_stream_prefix"])
        self.assertEqual(result["past_stream_ids"], ["tcp:1", "tcp:2"])
        self.assertEqual(result["causal_attribution"], "NOT_ESTABLISHED")

    def test_owner_capture_source_component_protocol_are_enforced(self):
        for key, value in (("owner", "other"), ("capture_id", "other"), ("source_sha256", "f" * 64),
                           ("component_id", "other"), ("protocol", 17)):
            with self.subTest(key=key), self.assertRaisesRegex(audit.AuditError, "MISMATCH"):
                audit.trace_attack_sample(query(), [packet(10, **{key: value})])

    def test_future_frame_and_future_timestamp_both_forbidden(self):
        for p in (packet(12, timestamp=1000), packet(10, timestamp=1011)):
            with self.assertRaisesRegex(audit.AuditError, "FUTURE_PREFIX_PACKET"):
                audit.trace_attack_sample(query(), [p])

    def test_duplicate_reversal_and_target_conflict_forbidden(self):
        for packets in ([packet(10), packet(10)], [packet(11), packet(10)],
                        [packet(9, timestamp=1005), packet(10, timestamp=1004)],
                        [packet(11, timestamp=1005)], [packet(11, "tcp:other")]):
            with self.subTest(packets=packets), self.assertRaises(audit.AuditError):
                audit.trace_attack_sample(query(), packets)

    def test_token_provenance_cannot_introduce_foreign_or_future_frame(self):
        for provenance in (tokenizer([10, 11], [12]), tokenizer([10, 11], [9]),
                           tokenizer([10], [10]), tokenizer([10, 11], [True])):
            with self.assertRaises(audit.AuditError):
                audit.trace_attack_sample(query(), [packet(10), packet(11)], provenance)
        with self.assertRaisesRegex(audit.AuditError, "REQUIRES_OBSERVED_PREFIX"):
            audit.trace_attack_sample(query(), None, tokenizer([], []))

    def test_declared_label_is_bound_to_exact_source_and_target(self):
        for changes in ({"target_frame": 10}, {"owner": "other"}, {"capture_id": "other"},
                        {"source_sha256": "f" * 64}, {"rule_applies_to_target": 1}):
            with self.assertRaises(audit.AuditError):
                audit.trace_attack_sample(query(), [packet(11)], label_evidence=label(**changes))
        result = audit.trace_attack_sample(query(), [packet(11)], label_evidence=label(rule_applies_to_target=False))
        self.assertEqual(result["label_rule_status"], "DECLARED_RULE_DOES_NOT_APPLY")

    def test_saturation_is_separate_from_target_retention(self):
        packets = [packet(i) for i in range(6, 12)]
        result = audit.trace_attack_sample(query(), packets)
        self.assertTrue(result["target_in_prefix"])
        self.assertEqual(result["prefix_saturation"]["status"], "BUDGET_REACHED")
        self.assertEqual(result["causal_attribution"], "NOT_ESTABLISHED")
        with self.assertRaisesRegex(audit.AuditError, "PACKETS_PER_BURST_EXCEEDED"):
            audit.trace_attack_sample(query(), [packet(i) for i in range(5, 12)])

    def test_packet_and_burst_capacity_cannot_be_changed(self):
        q = dict(query(), frame=200, timestamp=2000)
        packets = [packet(i, timestamp=1000 + i, burst_id=i - 1) for i in range(1, 14)]
        with self.assertRaisesRegex(audit.AuditError, "BURSTS_PER_DIRECTION_EXCEEDED"):
            audit.trace_attack_sample(q, packets)
        with self.assertRaisesRegex(audit.AuditError, "PACKET_BUDGET_EXCEEDED"):
            audit.trace_attack_sample(q, packets * 12)

    def test_empty_observed_prefix_differs_from_unobserved_prefix(self):
        result = audit.trace_attack_sample(query(), [], tokenizer([], []))
        self.assertFalse(result["target_in_prefix"])
        self.assertFalse(result["target_survives_tokenizer"])
        self.assertEqual(result["retained_frame_ids"], [])


if __name__ == "__main__":
    unittest.main()
