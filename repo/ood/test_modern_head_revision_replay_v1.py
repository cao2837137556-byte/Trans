"""Generated-data regression coverage for review P3 evidence and P4 data scope."""
import copy
import hashlib
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import continuous_common_v3 as c
import constrained_onboarding_query_tail_adapter_v2 as prior
import modern_head_onboarding_v1 as adapter
from test_constrained_onboarding_integration_v1 import row
from test_modern_head_evaluate_v1 import saved_pool


class ReplayEvidenceTests(unittest.TestCase):
    def test_each_seed_and_ensemble_has_measured_file_and_array_digests(self):
        rows = [row('n'), row('a', 1)]
        logits = np.asarray([[-0., -1., -2.], [2., 3., 4.]], dtype=np.float32)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'CAL'; recent = saved_pool(folder, rows, logits, 'QUERY_BCE')
            proof = {}
            actual = prior._verify_saved_pool(folder, rows, logits, 'QUERY_BCE', np.zeros(3), 0.,
                                               recent, recorder=proof)
            self.assertEqual(actual.dtype, np.bool_)
            self.assertEqual(actual.shape, (2, 4))
            self.assertEqual(proof['status'], 'VERIFIED')
            self.assertEqual(set(proof['heads']), set(prior.SUFFIXES))
            self.assertEqual(proof['verification_source']['source_sha256'], c.sha(prior.__file__))
            self.assertEqual(proof['uid']['expected_ordered_uid_sha256'], hashlib.sha256(b'n\na\n').hexdigest())
            for name in ('scores', 'decisions'):
                self.assertEqual(proof['files'][name]['sha256'], c.sha(folder/(name+'.npz')))
                self.assertTrue(proof['uid'][name]['matches_expected_order'])
                with np.load(folder/(name+'.npz'), allow_pickle=False) as saved:
                    for suffix in prior.SUFFIXES:
                        item = proof['heads'][suffix]['score' if name == 'scores' else 'decision']
                        values = saved['QUERY_BCE_'+suffix]
                        self.assertEqual(item['saved']['dtype'], values.dtype.str)
                        self.assertEqual(item['saved']['shape'], list(values.shape))
                        self.assertEqual(item['saved']['bytes_sha256'], hashlib.sha256(values.tobytes()).hexdigest())
                        self.assertEqual(item['saved'], item['replay'])
                        self.assertTrue(item['bitwise_equal'])
            self.assertEqual(proof['heads']['ensemble']['score']['replay']['dtype'], np.dtype(np.float64).str)
            self.assertTrue(proof['score_and_decision_bitwise'])

    def test_legacy_call_without_recorder_still_returns_recent_decisions(self):
        rows = [row('n'), row('a', 1)]; logits = np.asarray([[-1.]*3, [2.]*3])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'CAL'; recent = saved_pool(folder, rows, logits)
            actual = prior._verify_saved_pool(folder, rows, logits, 'TabM', np.zeros(3), 0., recent)
            np.testing.assert_array_equal(actual, np.asarray([[False]*4, [True]*4]))

    def test_signed_zero_drift_records_false_before_rejecting(self):
        rows = [row('n'), row('a', 1)]; logits = np.asarray([[-0.]*3, [2.]*3])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'CAL'; recent = saved_pool(folder, rows, logits)
            changed = logits.copy(); changed[0, 0] = 0.
            proof = {}
            with self.assertRaisesRegex(RuntimeError, 'SCORE_NOT_BITWISE:27'):
                prior._verify_saved_pool(folder, rows, changed, 'TabM', np.zeros(3), 0., recent, proof)
            self.assertFalse(proof['heads']['27']['score']['bitwise_equal'])
            self.assertNotEqual(proof['heads']['27']['score']['saved']['bytes_sha256'],
                                proof['heads']['27']['score']['replay']['bytes_sha256'])
            self.assertTrue(proof['heads']['27']['decision']['bitwise_equal'])
            self.assertFalse(proof['score_and_decision_bitwise'])
            self.assertEqual(proof['status'], 'MISMATCH')

    def test_score_dtype_change_is_visible_and_rejected(self):
        rows = [row('n'), row('a', 1)]; logits = np.asarray([[-1.]*3, [2.]*3], dtype=np.float64)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'CAL'; recent = saved_pool(folder, rows, logits); proof = {}
            with self.assertRaisesRegex(RuntimeError, 'SCORE_NOT_BITWISE'):
                prior._verify_saved_pool(folder, rows, logits.astype(np.float32), 'TabM', np.zeros(3), 0., recent, proof)
            evidence = proof['heads']['27']['score']
            self.assertNotEqual(evidence['saved']['dtype'], evidence['replay']['dtype'])
            self.assertFalse(evidence['bitwise_equal'])

    def test_saved_decision_drift_records_false_and_its_new_file_hash(self):
        rows = [row('n'), row('a', 1)]; logits = np.asarray([[-1.]*3, [2.]*3])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'CAL'; recent = saved_pool(folder, rows, logits); proof = {}
            with np.load(folder/'decisions.npz', allow_pickle=False) as saved:
                arrays = {name: saved[name].copy() for name in saved.files}
            arrays['TabM_127'][0] = True
            np.savez(folder/'decisions.npz', **arrays)
            with self.assertRaisesRegex(RuntimeError, 'HEAD_DECISION_DRIFT'):
                prior._verify_saved_pool(folder, rows, logits, 'TabM', np.zeros(3), 0., recent, proof)
            self.assertTrue(proof['heads']['127']['score']['bitwise_equal'])
            self.assertFalse(proof['heads']['127']['decision']['bitwise_equal'])
            self.assertFalse(proof['score_and_decision_bitwise'])
            self.assertEqual(proof['files']['decisions']['sha256'], c.sha(folder/'decisions.npz'))

    def test_uid_order_drift_cannot_be_hidden_by_matching_numeric_arrays(self):
        rows = [row('n'), row('a', 1)]; logits = np.asarray([[-1.]*3, [2.]*3])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'CAL'; recent = saved_pool(folder, rows, logits); proof = {}
            with self.assertRaisesRegex(RuntimeError, 'SCORED_UID_ORDER'):
                prior._verify_saved_pool(folder, rows[::-1], logits, 'TabM', np.zeros(3), 0., recent, proof)
            self.assertFalse(proof['uid']['scores']['matches_expected_order'])
            self.assertNotEqual(proof['uid']['expected_ordered_uid_sha256'],
                                proof['uid']['scores']['ordered_uid_sha256'])
            self.assertEqual(proof['status'], 'MISMATCH')

    def test_prepare_returns_actual_three_pool_evidence(self):
        """Exercise real pool verification while replacing remote inputs with tiny fixtures."""
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp); parent = root/'parent'; parent.mkdir()
            head = root/'head'; head.mkdir(); design_path = root/'design.json'
            fit = [row('fit-n'), row('fit-a', 1)]
            cal = [row('cal-n', role='CAL'), row('cal-a', 1, role='CAL')]
            metadata = {'LEARN': fit+cal, 'CIC_DEV': [row('cic-n'), row('cic-a', 1)],
                        'UNSW_DEV': [row('unsw-n'), row('unsw-a', 1)]}
            indices = {'FIT': np.arange(2), 'CAL': np.arange(2, 4)}
            values = {role: np.zeros((len(rows), 794), dtype=np.float32) for role, rows in metadata.items()}
            for role in values: values[role][:, 0] = np.tile([-1., 2.], len(values[role])//2)
            norm = (np.zeros(768), np.ones(768))
            q = {role: np.zeros((len(rows), 14), dtype=np.float32) for role, rows in metadata.items()}
            recent_by_pool = {}
            for pool, rows in [('CAL', cal), ('CIC_DEV', metadata['CIC_DEV']), ('UNSW_DEV', metadata['UNSW_DEV'])]:
                recent_by_pool[pool] = saved_pool(head/pool, rows, np.asarray([[-1.]*3, [2.]*3], dtype=np.float32), 'QUERY_BCE')
            design = {'provenance': {'feature_manifest_sha256': 'feature-hash', 'spool_sha256': 'spool-hash'}}
            c.write(design_path, design)
            c.write(parent/'P_COMPLETE.json', dict(status='COMPLETE', rows=1095200, feature_seal='feature-hash'))
            c.write(head/'K_COMPLETE.json', dict(status='COMPLETE', decision_sha256='decision-hash'))
            endpoint = {'fixture': 'verified endpoint'}
            c.write(head/'T_COMPLETE.json', dict(status='COMPLETE', total_updates=869040, endpoints=[endpoint]))
            cuts = {arm+'_'+suffix: 0. for arm in ('QUERY_BCE', 'RECENT') for suffix in prior.SUFFIXES}
            c.write(head/'thresholds.json', dict(source='ORIGINAL_SOURCE_CAL_NORMAL_ONLY', comparator='strict >',
                budget=.01, normal_rows=33147, normal_uid_sha256=c.uid_sha([cal[0]['uid']]), cuts=cuts))
            real_sha = c.sha
            stack.enter_context(patch.object(prior, '_required_files'))
            stack.enter_context(patch.object(c, 'pin', side_effect=lambda path, digest: Path(path)))
            stack.enter_context(patch.object(c, 'verify'))
            stack.enter_context(patch.object(c, 'sha', side_effect=lambda path: real_sha(path) if Path(path).is_file() else 'fixture-unread-input'))
            stack.enter_context(patch.dict(prior.EXPECTED_COUNTS, LEARN=4, FIT=2, CAL=2, CIC_DEV=2, UNSW_DEV=2))
            stack.enter_context(patch.object(prior.p, 'load_metadata', return_value=(metadata, indices)))
            stack.enter_context(patch.object(prior.p, 'arrays', return_value=(values, norm)))
            stack.enter_context(patch.object(prior, '_prepared_inputs', return_value=q))
            stack.enter_context(patch.object(prior, '_endpoint', return_value=endpoint))
            stack.enter_context(patch.object(prior.t, 'load', return_value=object()))
            stack.enter_context(patch.object(prior.k, 'scores', side_effect=lambda model, value, descriptors, ix, *rest: value[ix, 0]))
            stack.enter_context(patch.object(prior, '_recent', side_effect=lambda parent, pool, rows: recent_by_pool[pool]))
            stack.enter_context(patch.object(prior, '_references', return_value={'LEARN': {}, 'DEV': {}, 'EXTERNAL_ARCHIVAL_EVALUATION': {}}))
            bundle = prior.prepare_query_tail(parent, head, design_path, arm='QUERY_BCE')
            evidence = bundle['replay_evidence']
            self.assertEqual(evidence['arm'], 'QUERY_BCE')
            self.assertEqual(set(evidence['pools']), {'CAL', 'CIC_DEV', 'UNSW_DEV'})
            for pool, proof in evidence['pools'].items():
                self.assertEqual(proof['status'], 'VERIFIED')
                self.assertEqual(proof['files']['scores']['sha256'], real_sha(head/pool/'scores.npz'))
                self.assertEqual(proof['heads']['27']['score']['replay']['shape'], [2])


class EndpointCalScopeTests(unittest.TestCase):
    def test_cal_false_is_accepted_and_true_or_missing_is_rejected(self):
        rows = [row('fit-n'), row('fit-a', 1)]
        config = {'fixture': 'same config'}; norm = (np.zeros(768), np.ones(768))
        design = {'data': {'fit_cal_identity': {'FIT': {'uid_sha256': c.uid_sha(r['uid'] for r in rows)}}}}
        receipt = dict(status='COMPLETE', family='TabM', seed=27, dimension=782, rows=2,
                       synthetic_only=False, reference_used=False, DEV_used=False, CAL_used=False,
                       uid_sha256=design['data']['fit_cal_identity']['FIT']['uid_sha256'],
                       normalizer_digest=c.digest([v.tolist() for v in norm]), config_digest=c.digest(config),
                       **adapter.fit_identity(rows))
        with tempfile.TemporaryDirectory() as temp, patch.dict(prior.EXPECTED_COUNTS, FIT=2):
            for mode in ('false', 'true', 'missing'):
                changed = copy.deepcopy(receipt)
                if mode == 'true': changed['CAL_used'] = True
                if mode == 'missing': del changed['CAL_used']
                folder = Path(temp)/mode; folder.mkdir(); c.write(folder/'endpoint.json', changed); c.seal(folder)
                with self.subTest(mode=mode):
                    if mode == 'false':
                        self.assertEqual(adapter.verify_endpoint(folder, 'TabM', 27, config, design, norm, rows,
                                                                  {'endpoints': [changed]}), changed)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'ENDPOINT_SCOPE'):
                            adapter.verify_endpoint(folder, 'TabM', 27, config, design, norm, rows,
                                                    {'endpoints': [changed]})


if __name__ == '__main__':
    unittest.main()
