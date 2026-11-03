"""Synthetic rows through real frozen prefix declarations; no decoder/model."""

import copy
from types import SimpleNamespace
import unittest

import legacy_commissioning_attack_v1 as audit
import legacy_commissioning_trace_bridge_v1 as bridge
import legacy_reference_sample_prepare_v1 as prep


A = "02:00:00:00:00:01"
B = "02:00:00:00:00:02"
PEER = "02:00:00:00:00:03"


def row(frame, timestamp=None, stream="0", **changes):
    data = {
        "frame.number": str(frame), "frame.time_epoch": str(frame if timestamp is None else timestamp),
        "frame.len": "80", "frame.cap_len": "80", "eth.src": PEER, "eth.dst": A,
        "ip.src": "10.0.0.3", "ip.dst": "10.0.0.1", "ip.proto": "6", "ip.hdr_len": "20",
        "ip.dsfield": "0", "ip.len": "66", "ip.flags": "0", "ip.ttl": "64",
        "tcp.srcport": "40000", "tcp.dstport": "80", "tcp.flags": "0x0010",
        "tcp.window_size_value": "4096", "tcp.seq_raw": "101", "tcp.ack_raw": "202",
        "tcp.urgent_pointer": "0", "tcp.hdr_len": "20", "tcp.stream": stream,
    }
    data.update(changes)
    return data


def source(**changes):
    result = dict(capture_id="synthetic-capture", source_sha256="a" * 64,
                  source_read_receipt_sha256="b" * 64, owner=A, device="Synthetic DEV Device",
                  role="DEV", activity="TCP", provenance="attack")
    result.update(changes)
    return result


class Factory:
    def __init__(self, rows, fail_at=None):
        self.rows = rows
        self.calls = 0
        self.max_frame = None
        self.read_frames = []
        self.closed = False
        self.fail_at = fail_at

    def __call__(self, *, max_frame):
        self.calls += 1
        self.max_frame = max_frame

        def iterator():
            try:
                for entry in self.rows:
                    frame = int(entry["frame.number"])
                    self.read_frames.append(frame)
                    if frame == self.fail_at:
                        raise RuntimeError("synthetic decoder failure")
                    yield entry
            finally:
                self.closed = True
        return iterator()


class Translator:
    """Synthetic numerical callback; actual frozen prefix remains in use."""
    def __init__(self):
        self.seen = []
        self.reused_tokens = []

    def netfound_flow(self, rows):
        self.seen.append(copy.deepcopy(rows))
        # Deliberately reuse a mutable field to test snapshot ownership.
        self.reused_tokens[:] = [[int(r["frame.number"])] for r in rows[:12]]
        n = len(self.reused_tokens)
        return dict(flow_duration=0, burst_tokens=self.reused_tokens, directions=[True] * n,
                    bytes=[80] * n, iats=[0] * n, counts=[1] * n, protocol=6)


class Bridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reads only repository Python declarations; no assets or real packets.
        cls.event_api, cls.prefix_api, _ = prep.old.legacy_runtime()

    def target(self, packet, **changes):
        event = self.event_api.event_from_tshark(packet)
        frame = int(packet["frame.number"])
        result = dict(uid=prep.digest(["a" * 64, frame, A]), role="DEV", owner=A,
                      device="Synthetic DEV Device", capture_id="synthetic-capture", source_sha256="a" * 64,
                      component_id=prep.digest([A, prep.old.old_key(event)]), protocol=6, activity="TCP",
                      candidate_rank=frame - 1, timestamp=event.timestamp, frame=frame,
                      observed_transport_streams=1, saved_q_correct=False)
        result.update(changes)
        return result

    def run_bridge(self, factory, targets, src=None, translator=None, **kwargs):
        return bridge.audit_selected_source(factory, targets, source() if src is None else src,
                                            [A, B], self.event_api, self.prefix_api,
                                            Translator() if translator is None else translator, **kwargs)

    def test_one_factory_one_bounded_pass_no_future_request(self):
        rows = [row(1), row(2), row(3)]
        factory = Factory(rows, fail_at=3)
        result = self.run_bridge(factory, [self.target(rows[1])])
        self.assertEqual(factory.calls, 1)
        self.assertEqual(factory.max_frame, 2)
        self.assertEqual(factory.read_frames, [1, 2])
        self.assertTrue(factory.closed)
        self.assertEqual(result["selected_uids"], [self.target(rows[1])["uid"]])
        self.assertEqual(result["encoder_calls"], 0)
        self.assertFalse(result["source_bytes_verified_by_bridge"])
        self.assertFalse(result["upstream_decoder_prefetch_verified"])
        self.assertEqual(result["upstream_decoder_packet_limit_required"], 2)

    def test_actual_prefix_retains_unselected_past_and_never_resets_on_stream(self):
        rows = [row(1, stream="1"), row(2, stream="2")]
        result = self.run_bridge(Factory(rows), [self.target(rows[1], observed_transport_streams=2)])
        trace = result["traces"][0]
        self.assertEqual(trace["retained_frame_ids"], [1, 2])
        self.assertTrue(trace["cross_stream_prefix"])
        self.assertEqual(trace["past_stream_ids"], ["tcp:1", "tcp:2"])
        self.assertIsNone(trace["target_survives_tokenizer"])
        self.assertEqual(trace["status"], "INCONCLUSIVE")
        self.assertEqual(trace["flow_summary"]["target_in_translated_flow_without_callback"], "INCONCLUSIVE")
        self.assertFalse(trace["flow_summary"]["translation_frame_mapping_available"])

    def test_other_owner_stays_out_of_target_prefix(self):
        rows = [row(1), row(2, **{"eth.dst": B}), row(3)]
        result = self.run_bridge(Factory(rows), [self.target(rows[2])])
        self.assertEqual(result["traces"][0]["retained_frame_ids"], [1, 3])

    def test_snapshots_and_callbacks_cannot_mutate_later_prefix(self):
        rows = [row(1), row(2)]
        seen = []
        translator = Translator()

        def callback(flow, packets):
            seen.append(copy.deepcopy(flow))
            frames = [p["frame"] for p in packets]
            flow["burst_tokens"][0].append(999)
            packets[0]["frame"] = 999
            return dict(input_frame_ids=frames, output_source_frame_ids=frames, complete=True,
                        tokenizer_sha256="c" * 64, config_sha256="d" * 64)

        result = self.run_bridge(Factory(rows), [self.target(x) for x in rows], translator=translator,
                                 tokenizer_callback=callback)
        self.assertEqual(seen[0]["burst_tokens"], [[1]])
        self.assertEqual(seen[1]["burst_tokens"], [[1], [2]])
        self.assertEqual(result["traces"][0]["retained_frame_ids"], [1])
        self.assertEqual(result["traces"][1]["retained_frame_ids"], [1, 2])

    def test_actual_prefix_six_packet_saturation_can_omit_current_target(self):
        rows = [row(i, timestamp=1 + i * 0.001) for i in range(1, 8)]
        result = self.run_bridge(Factory(rows), [self.target(rows[-1])])
        trace = result["traces"][0]
        self.assertEqual(trace["retained_frame_ids"], [1, 2, 3, 4, 5, 6])
        self.assertFalse(trace["target_in_prefix"])
        self.assertEqual(trace["prefix_saturation"]["status"], "BUDGET_REACHED")
        self.assertIsNone(trace["target_survives_tokenizer"])
        self.assertEqual(trace["causal_attribution"], "NOT_ESTABLISHED")

    def test_actual_twelve_burst_limit_is_unchanged(self):
        rows = [row(i) for i in range(1, 14)]
        result = self.run_bridge(Factory(rows), [self.target(rows[-1])])
        self.assertEqual(result["traces"][0]["retained_frame_ids"], list(range(1, 13)))
        self.assertFalse(result["traces"][0]["target_in_prefix"])

    def test_actual_translator_can_reduce_retained_prefix_without_inferred_tokenizer_claim(self):
        translator = prep.old.declarations(prep.old.LEGACY_TRANSLATOR,
            {'parse_int', 'parse_float', 'uint_tokens', 'netfound_flow'})
        rows = []
        for frame in range(1, 15):
            packet = row(frame)
            if frame % 2 == 0:
                packet.update({'eth.src': A, 'eth.dst': PEER, 'ip.src': '10.0.0.1',
                               'ip.dst': '10.0.0.3', 'tcp.srcport': '80', 'tcp.dstport': '40000'})
            rows.append(packet)
        result = self.run_bridge(Factory(rows), [self.target(rows[-1])], translator=translator)
        trace = result['traces'][0]
        self.assertTrue(trace['target_in_prefix'])
        self.assertEqual(trace['flow_summary']['retained_prefix_packets'], 14)
        self.assertEqual(trace['flow_summary']['translated_packets'], 12)
        # Aggregate flow_duration can still carry information from all14 retained
        # packets. Fewer packet tokens alone must not become 'target invisible'.
        self.assertEqual(trace['flow_summary']['flow_duration'], 13000000)
        self.assertIsNone(trace['target_survives_tokenizer'])
        self.assertEqual(trace['flow_summary']['target_in_translated_flow_without_callback'], 'INCONCLUSIVE')

    def test_incomplete_source_fails_and_closes_without_retry(self):
        factory = Factory([row(1)])
        with self.assertRaisesRegex(audit.AuditError, "INCOMPLETE_SOURCE_TARGET_COVERAGE"):
            self.run_bridge(factory, [self.target(row(2))])
        self.assertEqual(factory.calls, 1)
        self.assertTrue(factory.closed)

    def test_decoder_failure_fails_and_closes_without_retry(self):
        factory = Factory([row(1), row(2)], fail_at=2)
        with self.assertRaisesRegex(RuntimeError, "synthetic decoder failure"):
            self.run_bridge(factory, [self.target(row(2))])
        self.assertEqual(factory.calls, 1)
        self.assertTrue(factory.closed)

    def test_duplicate_targets_and_bad_uid_rejected_before_factory(self):
        target = self.target(row(1))
        for targets in ([target, target], [dict(target, uid="f" * 64)]):
            factory = Factory([row(1)])
            with self.assertRaises(audit.AuditError):
                self.run_bridge(factory, targets)
            self.assertEqual(factory.calls, 0)

    def test_source_identity_role_and_consumed_names_rejected_before_factory(self):
        for change in ({"role": "DEVICE_HOLDOUT"}, {"source_sha256": "f" * 64},
                       {"device": "Netatmo Camera"}, {"device": "  rING   BASESTATION "},
                       {"device": "Borun Camera"}, {"provenance": "normal"}):
            src = source(**change)
            target = self.target(row(1))
            if "device" in change:
                target["device"] = change["device"]
            factory = Factory([row(1)])
            with self.subTest(change=change), self.assertRaises(audit.AuditError):
                self.run_bridge(factory, [target], src=src)
            self.assertEqual(factory.calls, 0)

    def test_frame_uid_owner_component_protocol_time_are_not_silently_repaired(self):
        for change in ({"component_id": "e" * 64}, {"timestamp": 2}, {"protocol": 17}):
            factory = Factory([row(1)])
            with self.subTest(change=change), self.assertRaises(audit.AuditError):
                self.run_bridge(factory, [self.target(row(1), **change)])
            self.assertTrue(factory.closed)
        for decoded in (row(2), row(1, **{"eth.dst": B}), row(1, **{"frame.cap_len": "1"})):
            factory = Factory([decoded])
            with self.assertRaises(audit.AuditError):
                self.run_bridge(factory, [self.target(row(1))])
            self.assertTrue(factory.closed)

    def test_timestamp_regression_poison_is_not_repaired(self):
        rows = [row(1, timestamp=2), row(2, timestamp=1), row(3, timestamp=3)]
        factory = Factory(rows)
        with self.assertRaisesRegex(audit.AuditError, "NAMESPACE_OR_VALIDITY"):
            self.run_bridge(factory, [self.target(rows[-1])])
        self.assertEqual(factory.calls, 1)
        self.assertTrue(factory.closed)

    def test_callbacks_report_token_truncation_and_legal_label_evidence(self):
        rows = [row(1), row(2)]

        def token_callback(flow, retained):
            return dict(input_frame_ids=[p["frame"] for p in retained], output_source_frame_ids=[1],
                        complete=True, tokenizer_sha256="c" * 64, config_sha256="d" * 64)

        def label_callback(decoded, event, src):
            return dict(owner=src["owner"], capture_id=src["capture_id"], source_sha256=src["source_sha256"],
                        target_frame=event.frame_number, rule_sha256="e" * 64, rule_applies_to_target=True)

        result = self.run_bridge(Factory(rows), [self.target(rows[-1])],
                                 tokenizer_callback=token_callback, label_callback=label_callback)
        trace = result["traces"][0]
        self.assertTrue(trace["target_in_prefix"])
        self.assertFalse(trace["target_survives_tokenizer"])
        self.assertEqual(trace["label_rule_status"], "DECLARED_RULE_APPLIES")

    def test_callback_error_does_not_retry_or_consume_future(self):
        factory = Factory([row(1), row(2)])

        def failed_callback(flow, retained):
            raise RuntimeError("audit callback stopped")

        with self.assertRaisesRegex(RuntimeError, "audit callback stopped"):
            self.run_bridge(factory, [self.target(row(1))], tokenizer_callback=failed_callback)
        self.assertEqual(factory.calls, 1)
        self.assertEqual(factory.read_frames, [1])
        self.assertTrue(factory.closed)

    def test_source_cannot_supply_scores_or_a_raw_path(self):
        for key in ("score", "path", "label"):
            factory = Factory([row(1)])
            src = dict(source(), **{key: "forbidden"})
            with self.assertRaisesRegex(audit.AuditError, "SOURCE_SCHEMA"):
                self.run_bridge(factory, [self.target(row(1))], src=src)
            self.assertEqual(factory.calls, 0)


if __name__ == "__main__":
    unittest.main()
