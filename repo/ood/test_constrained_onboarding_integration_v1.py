"""Generated-data scientific-boundary and end-to-end checks; no real assets."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

import continuous_common_v3 as c
import constrained_onboarding_core_v1 as core
import constrained_onboarding_evaluate_v1 as ev
import constrained_onboarding_runner_v1 as runner
from legacy_qref_evaluate_v1 import measure as official_measure

PROTOCOL = Path(__file__).resolve().parents[2]/'runs/onboarding_materials_and_protocol_20261015/protocol.json'


def row(uid, label=0, device='source', partition='LEARN', role='FIT', reference=False, timestamp=20.):
    return dict(uid=uid, label=label, device=device, partition=partition, fit_role=role,
                use='REFERENCE' if reference else 'QUERY', protocol=6, timestamp=timestamp,
                frame=30, capture_id='capture-'+device, source_sha256='s', owner=device,
                component_id=uid, session_id=uid, activity='TCP' if label else 'normal',
                reference_end=10., label_metric_weight_denominator=2)


def data(rows, logits=None):
    e3 = np.zeros((len(rows), 768), dtype=np.float32); e3[:, 0] = 1
    result = dict(rows=rows, e3=e3, q14=np.zeros((len(rows), 14), dtype=np.float32),
                  feature_uids=[r['uid'] for r in rows], q_uids=[r['uid'] for r in rows])
    if logits is not None:
        result['logits'] = np.tile(np.asarray(logits, dtype=np.float32)[:, None], (1, 3))
    return result


def fixture():
    fit = data([row('fit-n1'), row('fit-n2'), row('fit-a1', 1), row('fit-a2', 1)], [-2, -2, 2, 2])
    cal = data([row('cal-n', role='CAL'), row('cal-a', 1, role='CAL')], [-2, 10])
    refs = [row('source-r1', reference=True, timestamp=2.), row('source-r2', reference=True, timestamp=3.)]
    for r in refs:
        r['frame'] = 2
    bundle = dict(schema=runner.SCHEMA, synthetic_only=True, head_family='QUERY_TAIL',
                  protocol_sha256=runner.PROTOCOL_SHA, input_version=runner.INPUT_VERSION,
                  normalizer=(np.zeros(768), np.ones(768)), source_fit=fit, source_cal=cal,
                  source_references=data(refs), cuts=[0., 0., 0.], ensemble_cut=0., targets={}, provenance={})
    for pool, partition, t0 in [('CIC_DEV', 'DEV', 1635851700.06933),
                                ('UNSW_DEV', 'EXTERNAL_ARCHIVAL_EVALUATION', 1527465601.09039)]:
        rr = [row(pool+'-normal', device=pool, partition=partition, timestamp=t0+7201),
              row(pool+'-attack', 1, device=pool, partition=partition, timestamp=t0+7202)]
        target = data(rr, [.5, 10.])
        banks = [row(pool+'-r1', device=pool, partition=partition, reference=True, timestamp=t0+1),
                 row(pool+'-r2', device=pool, partition=partition, reference=True, timestamp=t0+2)]
        for r in banks:
            r.update(reference_end=t0+3600, frame=2, observation_t0=t0)
        target['banks'] = {'OLD_BANK': data(banks)}
        for policy in ('B0', 'B1'):
            b = data(copy.deepcopy(banks))
            b['preparation_receipt'] = dict(policy=policy, input_version=runner.INPUT_VERSION,
                                           real_recent_features=False, synthetic_only=True,
                                           status='SYNTHETIC_COMPLETE', complete_candidate_census=True)
            target['banks'][policy] = b
        bundle['targets'][pool] = target
    return bundle


def trace(n, support=None, eligible=None):
    return dict(support=np.asarray([1.]*n if support is None else support),
                eligible=np.asarray([True]*n if eligible is None else eligible),
                same_component=np.zeros(n, dtype=bool), reason=np.asarray(['ELIGIBLE']*n))


class EvaluationTests(unittest.TestCase):
    def test_official_weighted_metric_exact_not_packet_rate(self):
        rr = [row(str(i), label=i//3) for i in range(6)]
        for r, den in zip(rr, (2, 7, 19, 2, 5, 101)):
            r['label_metric_weight_denominator'] = den
        pred = np.asarray([True, False, False, False, True, True])
        self.assertEqual(ev.measure(rr, pred), official_measure(rr, pred))
        self.assertNotEqual(ev.measure(rr, pred)['normal']['weighted_rate'], 1/3)

    def test_new_miss_cannot_be_offset_by_recovered_attack(self):
        rr = [row('a', 1), row('b', 1)]
        paired = ev.paired(rr, np.asarray([True, False]), np.asarray([False, True]))
        self.assertEqual(paired['new_attack_misses'], 1)
        self.assertEqual(paired['recovered_attacks'], 1)
        self.assertEqual(paired['new_attack_miss_uids'], ['a'])

    def test_primary_keeps_early_rows_and_late_missing_attack_is_not_pass(self):
        rr = [row('early', 1, timestamp=1.), row('late', timestamp=20.)]
        h = np.asarray([[10., 10., 10.], [.5, .5, .5]])
        f = np.asarray([[10., 10., 10.], [-.5, -.5, -.5]])
        result, before, after = ev.paired_report(rr, h, f, [0.]*3, 0., trace(2, [0., 1.], [False, True]), 'CIC_DEV', late_cutoff=10.)
        self.assertEqual(result['query_rows'], 2)
        self.assertEqual(result['reports']['ensemble']['full']['attack']['rows'], 1)
        self.assertEqual(result['reports']['ensemble']['after_2h_secondary']['attack_evidence'], 'NOT_EVALUABLE')
        self.assertEqual(before.shape, (2, 4)); self.assertEqual(after.shape, (2, 4))

    def test_seed_and_ensemble_misses_all_checked(self):
        rr = [row('normal'), row('attack', 1)]
        h = np.asarray([[-1.]*3, [1.]*3]); f = np.asarray([[-1.]*3, [-.1, 1., 1.]])
        result = ev.paired_report(rr, h, f, [0.]*3, 0., trace(2), 'UNSW_DEV')[0]
        gate = ev.pool_gate(result)
        self.assertEqual(gate['status'], 'FAIL')
        self.assertIn('ADDED_ATTACK_MISSES:27', gate['reasons'])

    def test_device_without_attack_must_remain_pending(self):
        rr = [row('normal', device='a'), row('attack', 1, device='b')]
        h = np.asarray([[-1.]*3, [1.]*3])
        result = ev.paired_report(rr, h, h, [0.]*3, 0., trace(2, [0., 0.]), 'UNSW_DEV')[0]
        self.assertEqual(ev.pool_gate(result)['status'], 'PENDING')
        self.assertFalse(ev.pool_gate(result)['module_benefit'])

    def test_fallback_score_change_rejected(self):
        rr = [row('n'), row('a', 1)]; h = np.ones((2, 3)); f = h.copy(); f[0, 0] -= .1
        with self.assertRaisesRegex(ValueError, 'NO_SUPPORT_MUST_BE_EXACT_NOOP'):
            ev.paired_report(rr, h, f, [0.]*3, 0., trace(2, [0., 1.]), 'UNSW_DEV')

    def test_coverage_fp_share_not_all_normal_share(self):
        rr = [row('n1'), row('n2'), row('a', 1)]
        cov = ev.coverage(rr, np.asarray([False, True, True]), np.asarray([True, False, True]), np.asarray([1., 0., 1.]))
        self.assertEqual(cov['normal']['weighted_eligible_fraction'], .5)
        self.assertEqual(cov['head_false_positives']['weighted_eligible_fraction'], 0.)
        self.assertEqual(cov['head_true_positives']['weighted_eligible_fraction'], 1.)


class IntegrationTests(unittest.TestCase):
    def test_source_fit_then_sealed_target_pairing_and_equivalence(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'run'; b = fixture()
            result = runner.run_development(b, out, PROTOCOL)
            self.assertEqual(result['status'], 'COMPLETE')
            self.assertEqual(result['selected_lambda'], .25)
            for decision in result['scientific_decisions'].values():
                self.assertEqual(decision['status'], 'PENDING')
                self.assertIn('CIC_THREE_DEVICE_REGRESSION_CONSUMED', decision['missing_evidence'])
            reports = c.read(out/'CIC_DEV/OLD_BANK/reports.json')['reports']
            self.assertEqual(reports['ensemble']['full']['normal']['weighted_rate'], 0.)
            self.assertEqual(reports['ensemble']['paired']['new_attack_misses'], 0)
            self.assertTrue((out/'CIC_DEV/B1/equivalence.json').exists())
            with np.load(out/'CIC_DEV/OLD_BANK/decisions.npz', allow_pickle=False) as f:
                self.assertEqual(f['uid'].tolist(), runner._uids(b['targets']['CIC_DEV']))
            c.verify(out)
            with self.assertRaises(FileExistsError):
                runner.run_development(b, out, PROTOCOL)

    def test_target_labels_cannot_change_source_selection(self):
        b = fixture(); changed = copy.deepcopy(b)
        changed['targets']['CIC_DEV']['rows'][0]['label'] = 1
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner.run_development(b, root/'a', PROTOCOL)
            runner.run_development(changed, root/'b', PROTOCOL)
            for name in ('geometry.json', 'scales.json', 'protection.json', 'cuts.json'):
                self.assertEqual((root/'a/calibration'/name).read_bytes(), (root/'b/calibration'/name).read_bytes())

    def test_malformed_identity_source_roles_and_full_counts_rejected(self):
        cases = []
        b = fixture(); b['source_fit']['rows'][0]['fit_role'] = 'CAL'; cases.append(b)
        b = fixture(); b['targets']['CIC_DEV']['q_uids'].reverse(); cases.append(b)
        b = fixture(); b['source_cal']['rows'][0]['component_id'] = b['source_fit']['rows'][0]['component_id']; cases.append(b)
        b = fixture(); b['synthetic_only'] = False; cases.append(b)
        with tempfile.TemporaryDirectory() as temp:
            for i, b in enumerate(cases):
                with self.subTest(i=i), self.assertRaises(RuntimeError):
                    runner.run_development(b, Path(temp)/str(i), PROTOCOL)

    def test_unprepared_new_bank_and_output_inside_input_rejected(self):
        b = fixture(); b['targets']['CIC_DEV']['banks']['B0']['preparation_receipt']['status'] = 'PREPARATION_REQUIRED'
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, 'UNIFIED_BANK_PREPARATION_REQUIRED'):
                runner.run_development(b, Path(temp)/'bad', PROTOCOL)
            b = fixture(); b['provenance']['protected_paths'] = [temp]
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_INPUT'):
                runner.run_development(b, Path(temp)/'nested', PROTOCOL)

    def test_stop_receipt_no_automatic_retry(self):
        b = fixture(); b['source_fit']['e3'][0] = 0
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'fail'
            with self.assertRaises(ValueError):
                runner.run_development(b, out, PROTOCOL)
            self.assertEqual(c.read(out/'status.json')['status'], 'STOPPED_NO_RETRY')
            self.assertFalse((out/'result.json').exists())

    def test_portable_manifest_cannot_self_assert_production_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'bundle.json'
            c.write(path, dict(synthetic_only=False, provenance=dict(verified_current_parent=True)))
            with self.assertRaisesRegex(RuntimeError, 'PORTABLE_PRODUCTION_NOT_SUPPORTED'):
                runner.load_bundle(path)

    def test_generated_reference_encoder_attach_and_paired_evaluation(self):
        import constrained_onboarding_reference_v1 as reference
        from test_constrained_onboarding_reference_v1 import SPEC, REGISTRY, DECODER, stream_packet, fake_runtime
        packets = [stream_packet(1, 0), stream_packet(2, 100, port=5678), stream_packet(3, 7201)]
        prepared = reference.prepare_decoded_capture(packets, SPEC, REGISTRY, t0=0., decoder_identity=DECODER)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); reference.save_prepared(root/'prepared', prepared)
            norm = root/'normalizer.npz'; np.savez(norm, mean=np.zeros(768), scale=np.ones(768))
            config = dict(synthetic_only=True, runtime_root='generated-test-only', normalizer=str(norm),
                          normalizer_sha256=c.sha(norm), prepared_receipt_sha256=c.sha(root/'prepared/B0/receipt.json'))
            reference.encode_selected(root/'prepared/B0', root/'encoded', config, runtime_factory=fake_runtime)
            manifest = root/'banks.json'
            c.write(manifest, dict(pools={'CIC_DEV': {'B0': dict(path='encoded', receipt_sha256=c.sha(root/'encoded/receipt.json'))}}))
            b = fixture(); del b['targets']['CIC_DEV']['banks']['B0']
            runner.attach_reference_banks(b, manifest)
            self.assertIn(str(root/'encoded'), b['provenance']['protected_paths'])
            self.assertFalse(b['targets']['CIC_DEV']['banks']['B0']['preparation_receipt']['real_recent_features'])
            receipt = runner.run_development(b, root/'paired', PROTOCOL)
            self.assertEqual(receipt['status'], 'COMPLETE')
            self.assertEqual(c.read(root/'paired/CIC_DEV/B0/reports.json')['reports']['ensemble']['full']['normal']['weighted_rate'], 1.)
            # A pinned artifact must not silently change after encoding.
            with (root/'encoded/bank.npz').open('ab') as stream:
                stream.write(b'tampered')
            other = fixture(); del other['targets']['CIC_DEV']['banks']['B0']
            with self.assertRaises(RuntimeError):
                runner.attach_reference_banks(other, manifest)

    def test_wrong_reference_plans_are_policy_specific_even_when_scores_reused(self):
        b = fixture(); target = b['targets']['CIC_DEV']; owner = 'CIC_DEV'
        for policy in ('B0', 'B1', 'B2'):
            refs = copy.deepcopy(target['banks']['OLD_BANK']['rows'])
            if policy == 'B2':
                for r in refs:
                    r['uid'] += '-B2'; r['component_id'] = r['uid']
            donors = copy.deepcopy(refs)
            for r in donors:
                r.update(uid=r['uid']+'-donor', component_id=r['component_id']+'-donor',
                         device='donor', owner='donor', capture_id='capture-donor')
            bank = data(refs+donors)
            bank['preparation_receipt'] = dict(policy=policy, input_version=runner.INPUT_VERSION,
                synthetic_only=True, real_recent_features=False, status='SYNTHETIC_COMPLETE', complete_candidate_census=True)
            if policy != 'B0':
                bank['wrong_reference_controls'] = [dict(protocol=6, device=owner, donor_device='donor',
                    selection_basis='METADATA_ONLY_BEFORE_TARGET_SCORES', correct_reference_uids=[r['uid'] for r in refs],
                    wrong_reference_uids=[r['uid'] for r in donors])]
            target['banks'][policy] = bank
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'run'; runner.run_development(b, out, PROTOCOL)
            self.assertTrue((out/'CIC_DEV/B1/equivalence.json').exists())
            self.assertEqual(c.read(out/'CIC_DEV/B0/wrong_reference_controls.json')[0]['status'], 'NOT_AVAILABLE')
            for policy in ('B1', 'B2'):
                result = c.read(out/('CIC_DEV/'+policy+'/wrong_reference_controls.json'))[0]
                self.assertEqual(result['status'], 'MATCHED_METADATA_PLAN')
                self.assertEqual(result['correct']['query_rows'], 2)
                self.assertEqual(result['wrong']['query_rows'], 2)


if __name__ == '__main__':
    unittest.main()
