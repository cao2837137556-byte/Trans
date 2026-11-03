"""Generated-data checks for fixed calibration, all-family gates and module IO."""
import copy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import continuous_common_v3 as c
import modern_head_evaluate_v1 as evaluation
import modern_head_onboarding_v1 as adapter
import query_tail_evaluate_v2 as official
import constrained_onboarding_query_tail_adapter_v2 as prior
import constrained_onboarding_core_v2 as core
import constrained_onboarding_runner_v2 as onboarding
from test_constrained_onboarding_integration_v1 import fixture, row, data


ROOT = Path(os.environ.get('MODERN_TEST_ROOT', Path(__file__).resolve().parents[2]))
DESIGN = ROOT/'query_tail_design.json'
if not DESIGN.exists():
    DESIGN = ROOT/'runs/query_tail_configured_v2r3_20261017/bundle/design_contract.json'
PROTOCOL = ROOT/'protocol.json'
if not PROTOCOL.exists():
    PROTOCOL = ROOT/'runs/onboarding_materials_and_protocol_20261015/protocol.json'


def config():
    return dict(schema='modern-head-comparison-v1', families=list(evaluation.FAMILIES), seeds=list(c.SEEDS),
                onboarding_families=list(evaluation.ONBOARDING_FAMILIES), synthetic_only=True,
                gates=evaluation.modern_gates(c.read(DESIGN)))


def source_rows():
    return [row('n0', role='CAL'), row('n1', role='CAL')] + [
        dict(row('a'+str(i), 1, role='CAL'), activity=activity, protocol=17 if activity == 'UDP' else 6)
        for i, activity in enumerate(('TCP', 'UDP', 'Hydra'))]


def scores_for(values, family):
    return {family+'_'+suffix: np.asarray(values).copy() for suffix in evaluation.SUFFIXES}


def saved_pool(folder, rows, logits, family='TabM'):
    folder = Path(folder); folder.mkdir()
    recent = {s: np.asarray([-1., 2.], dtype=np.float32) for s in evaluation.SUFFIXES[:3]}
    recent['ensemble'] = evaluation.ensemble([recent[s] for s in evaluation.SUFFIXES[:3]])
    recent['cuts'] = {s: 0. for s in evaluation.SUFFIXES}
    scores = {family+'_'+s: logits[:, j] for j, s in enumerate(evaluation.SUFFIXES[:3])}
    scores[family+'_ensemble'] = evaluation.ensemble([logits[:, j] for j in range(3)])
    scores.update({'RECENT_'+s: recent[s] for s in evaluation.SUFFIXES})
    c.save_arrays(folder/'scores.npz', uid=np.asarray([r['uid'] for r in rows]), **scores)
    c.save_arrays(folder/'decisions.npz', uid=np.asarray([r['uid'] for r in rows]),
                  **{name: value > 0 for name, value in scores.items()})
    return recent


class CalibrationTests(unittest.TestCase):
    def test_normal_only_attack_scores_cannot_move_cut(self):
        rows = source_rows(); scores = scores_for([0., 1., 2., 3., 4.], 'TabM')
        before = evaluation.calibrate(rows, scores)
        for value in scores.values(): value[2:] = [-1e8, 1e8, -99]
        self.assertEqual(before, evaluation.calibrate(rows, scores))

    def test_target_rows_rejected_at_calibration(self):
        rows = source_rows(); rows[0]['partition'] = 'DEV'
        with self.assertRaisesRegex(RuntimeError, 'CAL_ROLE'):
            evaluation.calibrate(rows, scores_for(np.arange(5.), 'TabM'))

    def test_tied_maximum_is_never_split_by_order(self):
        rows = [row(str(i), role='CAL') for i in range(200)]
        values = np.zeros(200); values[-3:] = 10
        cut = evaluation.calibrate(rows, {'TabM_27': values})['TabM_27']
        self.assertEqual(cut, 10.)
        self.assertEqual(int((values > cut).sum()), 0)
        self.assertEqual(cut, evaluation.calibrate(rows[::-1], {'TabM_27': values[::-1]})['TabM_27'])

    def test_hierarchy_weights_not_query_fraction(self):
        rows = [row(str(i), role='CAL', device='many') for i in range(100)] + [row('rare', role='CAL', device='rare')]
        values = np.zeros(101); values[-1] = 10.
        self.assertLess((values > 0).mean(), .01)
        self.assertEqual(evaluation.calibrate(rows, {'LightGBM_27': values})['LightGBM_27'], 10.)

    def test_seed_and_family_cuts_are_separate(self):
        rows = source_rows(); score = {'TabM_27': np.arange(5.), 'LightGBM_127': 10+np.arange(5.)}
        result = evaluation.calibrate(rows, score)
        self.assertEqual(result, {'TabM_27': 1., 'LightGBM_127': 11.})

    def test_ensemble_preserves_order_and_float64(self):
        columns = [np.asarray([1e20, 1.], dtype=np.float64), np.asarray([-1e20, 2.]), np.asarray([3., 9.])]
        actual = evaluation.ensemble(columns)
        self.assertTrue(prior._exact_equal(actual, np.stack(columns).mean(0, dtype=np.float64)))
        self.assertEqual(actual[0], 1.)

    def test_scope_and_gates_cannot_be_silently_reduced(self):
        cfg = config(); evaluation.validate_config(cfg, c.read(DESIGN))
        for key, value in [('families', ['TabM']), ('onboarding_families', ['TabM']), ('seeds', [27])]:
            altered = copy.deepcopy(cfg); altered[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'SCOPE'):
                evaluation.validate_config(altered)
        cfg['gates'] = {}
        with self.assertRaisesRegex(RuntimeError, 'INHERITED_GATES'):
            evaluation.validate_config(cfg, c.read(DESIGN))


class OfficialMetricTests(unittest.TestCase):
    def test_each_family_uses_identical_official_regression_weights(self):
        rows = source_rows(); decisions = scores_for(np.ones(5, dtype=bool), 'RECENT')
        for family in evaluation.FAMILIES:
            decisions.update(scores_for(np.asarray([True, True, True, False, True]), family))
            result = evaluation.regressions(rows, decisions, 'CAL', family)
            mapped = {name: value for name, value in decisions.items() if name.startswith('RECENT_')}
            mapped.update({'QUERY_TAIL_'+s: decisions[family+'_'+s] for s in evaluation.SUFFIXES})
            expected = official.regressions(rows, mapped, 'CAL')
            self.assertEqual([{k: v for k, v in item.items() if k != 'family'} for item in result], expected)
            self.assertFalse(all(item['passed'] for item in result))

    def test_each_family_carries_historical_q_and_seed_guards(self):
        cfg = config(); base = dict(overall=dict(attack=dict(weighted_rate=1., rate=1.),
                    normal=dict(weighted_rate=0.)), groups={'device': []})
        for family in evaluation.FAMILIES:
            reports = {family+'_'+s: copy.deepcopy(base) for s in evaluation.SUFFIXES}
            reports[family+'_ensemble']['overall']['attack']['rate'] = .99
            reports[family+'_27']['overall']['attack']['weighted_rate'] = .96
            result = evaluation.gate(cfg, reports, 'CIC_DEV', family)
            self.assertFalse(result['passed'])
            self.assertIn('HISTORICAL_Q_REGRESSION', result['reasons'])
            self.assertIn('SEED_ATTACK_27', result['reasons'])

    def test_cic_regression_uses_supplied_denominators(self):
        rows = [row('a', 1, partition='DEV'), row('b', 1, partition='DEV')]
        rows[0]['label_metric_weight_denominator'] = 1000
        rows[1]['label_metric_weight_denominator'] = 1
        decisions = scores_for(np.asarray([True, True]), 'RECENT')
        decisions.update(scores_for(np.asarray([False, True]), 'LightGBM'))
        result = evaluation.regressions(rows, decisions, 'CIC_DEV', 'LightGBM')
        self.assertTrue(all(item['passed'] for item in result))
        self.assertAlmostEqual(result[0]['drop'], 1/1001)


class ReplayAndOnboardingTests(unittest.TestCase):
    def test_endpoint_provenance_rejects_wrong_order_weights_and_training_join(self):
        rows = [row('fit-n'), row('fit-a', 1)]; cfg = config(); cfg['synthetic_only'] = False
        norm = (np.zeros(768), np.ones(768)); identity = adapter.fit_identity(rows)
        design = {'data': {'fit_cal_identity': {'FIT': {'uid_sha256': c.uid_sha(r['uid'] for r in rows)}}}}
        receipt = dict(status='COMPLETE', family='TabM', seed=27, dimension=782, rows=2,
            synthetic_only=False, reference_used=False, DEV_used=False, CAL_used=False,
            uid_sha256=design['data']['fit_cal_identity']['FIT']['uid_sha256'],
            normalizer_digest=c.digest([v.tolist() for v in norm]), config_digest=c.digest(cfg), **identity)
        with tempfile.TemporaryDirectory() as temp, patch.dict(prior.EXPECTED_COUNTS, FIT=2):
            folder = Path(temp)/'valid'; folder.mkdir(); c.write(folder/'endpoint.json', receipt); c.seal(folder)
            training = {'endpoints': [receipt]}
            self.assertEqual(adapter.verify_endpoint(folder, 'TabM', 27, cfg, design, norm, rows, training), receipt)
            with self.assertRaisesRegex(RuntimeError, 'FIT_ORDER_WEIGHT'):
                adapter.verify_endpoint(folder, 'TabM', 27, cfg, design, norm, rows[::-1], training)
            with self.assertRaisesRegex(RuntimeError, 'T_ENDPOINT_JOIN'):
                adapter.verify_endpoint(folder, 'TabM', 27, cfg, design, norm, rows, {'endpoints': []})
            for key, value in [('weight_sha256', 'bad'), ('normalizer_digest', 'bad'),
                               ('reference_used', True), ('config_digest', 'bad')]:
                altered = dict(receipt); altered[key] = value
                other = Path(temp)/key; other.mkdir(); c.write(other/'endpoint.json', altered); c.seal(other)
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    adapter.verify_endpoint(other, 'TabM', 27, cfg, design, norm, rows, {'endpoints': [altered]})

    def test_float32_mlp_and_float64_modern_heads_replay_exactly(self):
        rows = [row('n'), row('a', 1)]
        for family, dtype in [('MLP_QUERY_BCE', np.float32), ('TabM', np.float64), ('LightGBM', np.float64)]:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)/'CAL'; logits = np.asarray([[-1]*3, [2]*3], dtype=dtype)
                recent = saved_pool(folder, rows, logits, family)
                got = prior._verify_saved_pool(folder, rows, logits, family, np.zeros(3), 0., recent)
                self.assertEqual(got.shape, (2, 4))
                adapter.verify_fit_scores(folder, rows, logits, family)

    def test_score_dtype_signed_zero_and_uid_drift_rejected(self):
        rows = [row('n'), row('a', 1)]; logits = np.asarray([[-0.]*3, [2.]*3])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'CAL'; recent = saved_pool(folder, rows, logits)
            changed = logits.copy(); changed[0] = 0.
            for rr, xx, reason in [(rows, changed, 'BITWISE'), (rows, logits.astype(np.float32), 'BITWISE'),
                                    (rows[::-1], logits, 'UID_ORDER')]:
                with self.subTest(reason=reason), self.assertRaisesRegex(RuntimeError, reason):
                    prior._verify_saved_pool(folder, rr, xx, 'TabM', np.zeros(3), 0., recent)

    def test_empty_reference_preserves_same_head_for_both_candidates(self):
        for family in evaluation.ONBOARDING_FAMILIES:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as temp:
                b = fixture(); b['head_family'] = family
                for target in b['targets'].values(): target['banks'] = {'OLD_BANK': data([])}
                result = onboarding.run_development(b, Path(temp)/'run', PROTOCOL)
                for pool, target in b['targets'].items():
                    with np.load(Path(temp)/'run'/pool/'OLD_BANK/scores.npz', allow_pickle=False) as saved:
                        self.assertTrue(np.array_equal(saved['head'], saved['corrected']))
                for decision in result['scientific_decisions'].values():
                    self.assertNotEqual(decision['status'], 'PASS')
                    self.assertIn('CIC_THREE_DEVICE_REGRESSION_CONSUMED', decision['missing_evidence'])


class EndToEndEvaluationTests(unittest.TestCase):
    def test_all_families_all_pools_and_source_seal_before_targets(self):
        import modern_head_models_v1 as models
        import modern_head_train_v1 as training
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); shutil.copyfile(DESIGN, root/'query_tail_design.json')
            parent = root/'parent'; (parent/'calibration').mkdir(parents=True)
            cal = source_rows(); fit = [row('fit-n'), row('fit-a', 1)]
            metadata = {'LEARN': fit+cal}; indices = {'FIT': np.arange(2), 'CAL': np.arange(2, 7)}
            arrays = {'LEARN': np.asarray([-1., 3., 0., 1., 3., 3., 3.])[:, None]}
            baseline = scores_for(arrays['LEARN'][indices['CAL'], 0], 'RECENT')
            c.save_arrays(parent/'calibration/base_logits.npz', **baseline)
            tau = evaluation.calibrate(cal, baseline)
            c.write(parent/'calibration/thresholds.json', {'tau': {'RECENT': {s: tau['RECENT_'+s] for s in evaluation.SUFFIXES}}})
            for pool, partition in [('CIC_DEV', 'DEV'), ('UNSW_DEV', 'EXTERNAL_ARCHIVAL_EVALUATION')]:
                metadata[pool] = [row(pool+'-n', partition=partition), row(pool+'-a', 1, partition=partition)]
                arrays[pool] = np.asarray([-2., 3.])[:, None]
                folder = parent/pool; folder.mkdir()
                values = scores_for(arrays[pool][:, 0], 'RECENT')
                c.save_arrays(folder/'scores.npz', **values)
                c.save_arrays(folder/'decisions.npz', uid=np.asarray([r['uid'] for r in metadata[pool]]),
                              **{name: value > 1 for name, value in values.items()})
            q = {role: np.zeros((len(rr), 14), dtype=np.float32) for role, rr in metadata.items()}
            cfg = config(); outputs = []
            for revision in range(2):
                run = root/('run'+str(revision)); run.mkdir()
                if revision: arrays['UNSW_DEV'][:] = 1e6
                def score(model, family, values, descriptors, ix, norm, progress=None):
                    if values is not arrays['LEARN']:
                        self.assertTrue((run/'thresholds.json').is_file())
                    return values[ix, 0].astype(np.float32 if family == 'MLP_QUERY_BCE' else np.float64)
                with patch.object(training, 'load', return_value=object()), patch.object(models, 'scores', side_effect=score):
                    decision = evaluation.evaluate(root, parent, run, cfg, metadata, indices, arrays, q,
                                                   (np.zeros(768), np.ones(768)))
                self.assertEqual(set(decision['families']), set(evaluation.FAMILIES))
                self.assertEqual(decision['onboarding_families'], ['TabM', 'LightGBM'])
                self.assertIsNone(decision['selected_family']); self.assertFalse(decision['automatic_promotion'])
                for pool in ('CAL', 'CIC_DEV', 'UNSW_DEV', 'FIT'): c.verify(run/pool)
                with np.load(run/'FIT/scores.npz', allow_pickle=False) as saved:
                    self.assertEqual(len(saved.files), 13)
                outputs.append((run/'thresholds.json').read_bytes())
            self.assertEqual(outputs[0], outputs[1])


if __name__ == '__main__':
    unittest.main()
