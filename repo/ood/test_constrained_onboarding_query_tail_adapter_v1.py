"""Generated-file and mocked-loader checks; no real data/cache/model reads."""
import gzip
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import constrained_onboarding_query_tail_adapter_v1 as adapter


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def pool_fixture(self):
        rows = [{'uid': 'u0'}, {'uid': 'u1'}, {'uid': 'u2'}]
        logits = np.asarray([[0, 1, 2], [3, 4, 5], [-1, -2, -3]], dtype=np.float32)
        cuts = np.asarray([.5, 2, 4], dtype=np.float64)
        cut = 2.
        ensemble = np.stack([logits[:, i] for i in range(3)]).mean(0, dtype=np.float64)
        recent = {s: np.asarray([0., 1., -1.], dtype=np.float32) for s in adapter.SUFFIXES[:3]}
        recent['ensemble'] = np.stack([recent[s] for s in adapter.SUFFIXES[:3]]).mean(0, dtype=np.float64)
        recent['cuts'] = {s: 0. for s in adapter.SUFFIXES}
        scores = {'uid': np.asarray([r['uid'] for r in rows])}
        decisions = {'uid': scores['uid']}
        for i, s in enumerate(adapter.SUFFIXES):
            scores['QUERY_TAIL_'+s] = logits[:, i] if i < 3 else ensemble
            scores['RECENT_'+s] = recent[s]
            decisions['QUERY_TAIL_'+s] = scores['QUERY_TAIL_'+s] > (cuts[i] if i < 3 else cut)
            decisions['RECENT_'+s] = recent[s] > recent['cuts'][s]
        np.savez(self.root/'scores.npz', **scores)
        np.savez(self.root/'decisions.npz', **decisions)
        return rows, logits, cuts, cut, recent, scores, decisions

    def verify_pool(self, fixture):
        rows, logits, cuts, cut, recent, _, _ = fixture
        return adapter._verify_saved_pool(self.root, rows, logits, 'QUERY_TAIL', cuts, cut, recent)

    def test_saved_head_scores_cuts_and_uid_exactly_reproduce(self):
        fixture = self.pool_fixture()
        result = self.verify_pool(fixture)
        np.testing.assert_array_equal(result, np.asarray([[False]*4, [True]*4, [False]*4]))

    def test_one_ulp_score_drift_rejected_even_same_decisions(self):
        fixture = self.pool_fixture()
        fixture[1][1, 0] = np.nextafter(fixture[1][1, 0], np.float32(np.inf))
        with self.assertRaisesRegex(RuntimeError, 'SCORE_NOT_BITWISE'):
            self.verify_pool(fixture)

    def test_signed_zero_and_dtype_drift_are_not_bitwise(self):
        self.assertFalse(adapter._exact_equal(np.asarray([0.], dtype=np.float32), np.asarray([-0.], dtype=np.float32)))
        self.assertFalse(adapter._exact_equal(np.asarray([1.], dtype=np.float32), np.asarray([1.], dtype=np.float64)))

    def test_decision_drift_rejected(self):
        fixture = self.pool_fixture()
        fixture[-1]['QUERY_TAIL_ensemble'][0] = True
        np.savez(self.root/'decisions.npz', **fixture[-1])
        with self.assertRaisesRegex(RuntimeError, 'HEAD_DECISION_DRIFT'):
            self.verify_pool(fixture)

    def test_uid_permutation_rejected(self):
        fixture = self.pool_fixture()
        fixture[-2]['uid'] = fixture[-2]['uid'][::-1]
        np.savez(self.root/'scores.npz', **fixture[-2])
        with self.assertRaisesRegex(RuntimeError, 'SCORED_UID_ORDER'):
            self.verify_pool(fixture)

    def test_recent_baseline_drift_rejected(self):
        fixture = self.pool_fixture()
        fixture[-2]['RECENT_127'][0] = .25
        np.savez(self.root/'scores.npz', **fixture[-2])
        # Undo the mutation of the dictionary sharing this generated array.
        fixture[4]['127'] = np.asarray([0., 1., -1.], dtype=np.float32)
        with self.assertRaisesRegex(RuntimeError, 'RECENT_SCORE_DRIFT'):
            self.verify_pool(fixture)

    def test_missing_material_fails_before_model_or_metadata_loading(self):
        with patch.object(adapter.p, 'load_metadata') as metadata, patch.object(adapter.t, 'load') as model:
            with self.assertRaisesRegex(RuntimeError, 'PREPARATION_REQUIRED'):
                adapter.prepare_query_tail(self.root/'parent', self.root/'run', self.root/'design.json')
            metadata.assert_not_called()
            model.assert_not_called()

    def test_invalid_arm_fails_before_loading(self):
        with self.assertRaisesRegex(RuntimeError, 'ADAPTER_ARM'):
            adapter.prepare_query_tail('missing', 'missing', 'missing', arm='OLD_MATCHED')

    def test_q14_shape_range_and_nonfinite_guards(self):
        good = np.zeros((2, 14), dtype=np.float32)
        adapter._q_schema(good, 2)
        for bad in (good.astype(np.float64), good[:, :13]):
            with self.assertRaisesRegex(RuntimeError, 'Q_SCHEMA'):
                adapter._q_schema(bad, 2)
        for value in (-.01, 1.01, np.nan, np.inf):
            bad = good.copy(); bad[0, 0] = value
            with self.assertRaisesRegex(RuntimeError, 'Q_RANGE'):
                adapter._q_schema(bad, 2)

    def endpoint_fixture(self):
        design = {'training': {'updates_per_head': 96560},
                  'data': {'fit_cal_identity': {'FIT': {'uid_sha256': 'f'*64}}}}
        norm = (np.zeros(768), np.ones(768))
        np.savez(self.root/'head.npz', placeholder=np.asarray([1.]))
        receipt = dict(status='COMPLETE', arm='QUERY_TAIL', seed=27, dimension=782,
                       synthetic_only=False, reference_used=False, DEV_used=False,
                       rows=617908, epochs=40, updates=96560, uid_sha256='f'*64,
                       normalizer_digest=adapter.c.digest([v.tolist() for v in norm]),
                       design_digest=adapter.c.digest(design), objective='BCE+TAIL',
                       diagnostics_enabled=True, head_sha256=adapter.c.sha(self.root/'head.npz'))
        return design, norm, receipt

    def test_endpoint_scope_and_original_objective_required(self):
        design, norm, receipt = self.endpoint_fixture()
        (self.root/'endpoint.json').write_text(json.dumps(receipt), encoding='utf-8')
        adapter._endpoint(self.root, 'QUERY_TAIL', 27, design, norm)
        for field, value, message in (
                ('synthetic_only', True, 'DATA_SCOPE'), ('DEV_used', True, 'DATA_SCOPE'),
                ('rows', 4, 'ENDPOINT_FIT'), ('objective', '(BCE+TAIL)/2', 'OBJECTIVE'),
                ('normalizer_digest', 'wrong', 'PROVENANCE'), ('seed', 127, 'IDENTITY')):
            bad = dict(receipt, **{field: value})
            (self.root/'endpoint.json').write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, message):
                adapter._endpoint(self.root, 'QUERY_TAIL', 27, design, norm)

    def reference_fixture(self):
        inputs = self.root/'inputs'; inputs.mkdir()
        features = self.root/'features'; features.mkdir()
        pins = {}; feature_pins = {}
        for role, count in [('SOURCE_REFS', 179), ('UNSW_REFS', 92)]:
            rows = [dict(uid=role+str(i), use='REFERENCE', label=0,
                         partition=('LEARN' if i % 2 == 0 or i >= 150 else 'DEV')
                                   if role == 'SOURCE_REFS' else 'EXTERNAL_ARCHIVAL_EVALUATION')
                    for i in range(count)]
            # 75 DEV rows interleaved among 104 source rows detects slice/order assumptions.
            with gzip.open(inputs/(role+'.jsonl.gz'), 'wt', encoding='utf-8') as stream:
                for row in rows:
                    stream.write(json.dumps(row)+'\n')
            pins[role+'.jsonl.gz'] = adapter.c.sha(inputs/(role+'.jsonl.gz'))
            values = np.broadcast_to(np.arange(count, dtype=np.float32)[:, None], (count, 794)).copy()
            np.save(features/(role+'.npy'), values)
            feature_pins[role+'.npy'] = adapter.c.sha(features/(role+'.npy'))
        design = {'provenance': {'input_manifest_sha256': 'inputs', 'feature_manifest_sha256': 'features',
                                 'spool_sha256': 's'*64}}
        return design, pins, feature_pins

    def test_old_bank_reference_subsets_keep_original_slots_and_recent_columns(self):
        design, pins, feature_pins = self.reference_fixture()
        def fake_q(path, rows, digest):
            self.assertEqual(digest, 's'*64)
            self.assertEqual([r['parent_slot'] for r in rows], list(range(len(rows))))
            return np.broadcast_to(np.arange(len(rows), dtype=np.float32)[:, None]/200, (len(rows), 14)).copy()
        with patch.object(adapter.p, 'manifest', side_effect=lambda path, digest: pins if digest == 'inputs' else feature_pins), \
                patch.object(adapter.reference, 'extract_old_bank_q14', side_effect=fake_q) as extract:
            refs = adapter._references(self.root, design)
        self.assertEqual(extract.call_count, 2)
        for key, count in [('LEARN', 104), ('DEV', 75), ('EXTERNAL_ARCHIVAL_EVALUATION', 92)]:
            bank = refs[key]
            self.assertEqual(bank['e3'].shape, (count, 768))
            self.assertEqual(bank['feature_uids'], [r['uid'] for r in bank['rows']])
            np.testing.assert_array_equal(bank['e3'][:, 0], [r['parent_slot'] for r in bank['rows']])
            np.testing.assert_array_equal(bank['q14'][:, 0], np.asarray([r['parent_slot'] for r in bank['rows']], dtype=np.float32)/200)

    def test_old_768_column_prefix_cache_cannot_replace_recent_cache(self):
        design, pins, feature_pins = self.reference_fixture()
        path = self.root/'features/SOURCE_REFS.npy'
        np.save(path, np.zeros((179, 768), dtype=np.float32))
        feature_pins[path.name] = adapter.c.sha(path)
        with patch.object(adapter.p, 'manifest', side_effect=lambda path, digest: pins if digest == 'inputs' else feature_pins), \
                patch.object(adapter.reference, 'extract_old_bank_q14') as extract:
            with self.assertRaisesRegex(RuntimeError, 'REFERENCE_RECENT_FEATURES'):
                adapter._references(self.root, design)
            extract.assert_not_called()

    def test_completed_mock_production_adapter_supplies_runner_provenance(self):
        """Exercise the real return path after generated/mock verification inputs.

        Every expensive loader is replaced; this does not claim real data passed.
        The CLI/runner contract must still be emitted by the adapter itself.
        """
        parent, run, design_path = self.root/'parent', self.root/'run', self.root/'design.json'
        counts = {'LEARN': 4, 'FIT': 2, 'CAL': 2, 'CIC_DEV': 2, 'UNSW_DEV': 2}
        metadata = {role: [dict(uid=role+str(i), label=i % 2) for i in range(counts[role])]
                    for role in adapter.k.ROLES}
        indices = {'FIT': np.asarray([0, 1]), 'CAL': np.asarray([2, 3])}
        values = {role: np.ones((counts[role], 794), dtype=np.float32) for role in adapter.k.ROLES}
        q = {role: np.zeros((counts[role], 14), dtype=np.float32) for role in adapter.k.ROLES}
        norm = (np.zeros(768), np.ones(768))
        design = {'provenance': {'feature_manifest_sha256': 'features', 'spool_sha256': 'spool'}}
        cuts = {arm+'_'+suffix: 0. for arm in ('QUERY_TAIL', 'RECENT') for suffix in adapter.SUFFIXES}
        threshold = dict(source='ORIGINAL_SOURCE_CAL_NORMAL_ONLY', comparator='strict >', budget=.01,
                         normal_rows=33147, cuts=cuts,
                         normal_uid_sha256=adapter.c.uid_sha([metadata['LEARN'][2]['uid']]))
        endpoint = {'verified_fixture': True}
        documents = {str(design_path): design,
                     str(parent/'P_COMPLETE.json'): dict(status='COMPLETE', rows=1095200, feature_seal='features'),
                     str(run/'K_COMPLETE.json'): dict(status='COMPLETE', decision_sha256='decision'),
                     str(run/'T_COMPLETE.json'): dict(status='COMPLETE', total_updates=869040, endpoints=[endpoint]),
                     str(run/'thresholds.json'): threshold}
        refs = {key: {'rows': []} for key in ('LEARN', 'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION')}
        with ExitStack() as stack:
            stack.enter_context(patch.object(adapter, 'EXPECTED_COUNTS', counts))
            stack.enter_context(patch.object(adapter, '_required_files'))
            stack.enter_context(patch.object(adapter.c, 'pin', side_effect=lambda path, digest: Path(path)))
            stack.enter_context(patch.object(adapter.c, 'verify'))
            stack.enter_context(patch.object(adapter.c, 'sha', return_value='a'*64))
            stack.enter_context(patch.object(adapter.c, 'read', side_effect=lambda path: documents[str(path)]))
            stack.enter_context(patch.object(adapter.p, 'load_metadata', return_value=(metadata, indices)))
            stack.enter_context(patch.object(adapter.p, 'arrays', return_value=(values, norm)))
            stack.enter_context(patch.object(adapter, '_prepared_inputs', return_value=q))
            stack.enter_context(patch.object(adapter, '_endpoint', return_value=endpoint))
            stack.enter_context(patch.object(adapter.t, 'load', return_value=object()))
            stack.enter_context(patch.object(adapter.k, 'scores', side_effect=lambda model, vals, qq, ix, *rest: np.zeros(len(ix), dtype=np.float32)))
            stack.enter_context(patch.object(adapter, '_recent', return_value={'cuts': {s: 0. for s in adapter.SUFFIXES}}))
            stack.enter_context(patch.object(adapter, '_verify_saved_pool', return_value=np.zeros((2, 4), dtype=bool)))
            stack.enter_context(patch.object(adapter, '_references', return_value=refs))
            bundle = adapter.prepare_query_tail(parent, run, design_path)
        self.assertIs(bundle['synthetic_only'], False)
        self.assertIs(bundle['provenance']['verified_current_parent'], True)
        self.assertEqual(bundle['provenance']['protected_paths'],
                         [str(path.resolve()) for path in (parent, run, design_path)])
        self.assertEqual(bundle['provenance']['normalizer_sha256'], 'a'*64)

    def test_cli_attaches_banks_and_preserves_verified_provenance(self):
        import constrained_onboarding_runner_v1 as runner
        parent, run, design = self.root/'parent', self.root/'run', self.root/'design.json'
        protocol, banks, output = self.root/'protocol.json', self.root/'banks.json', self.root/'output'
        bundle = {'synthetic_only': False, 'provenance': {'verified_current_parent': True,
                  'protected_paths': [str(p.resolve()) for p in (parent, run, design)]}}
        def attach(value, path):
            self.assertIs(value, bundle)
            self.assertEqual(path, str(banks))
            value['attached_test_banks'] = True
        with patch.object(adapter.c, 'pin'), patch.object(adapter, 'prepare_query_tail', return_value=bundle), \
                patch.object(runner, 'attach_reference_banks', side_effect=attach), \
                patch.object(runner, 'run_development', return_value='fixture-complete') as execute:
            result = adapter.main(['--parent', str(parent), '--head-run', str(run), '--design', str(design),
                                   '--protocol', str(protocol), '--banks-manifest', str(banks), '--output', str(output)])
        self.assertEqual(result, 'fixture-complete')
        execute.assert_called_once_with(bundle, output.resolve(), str(protocol))
        self.assertIs(bundle['provenance']['verified_current_parent'], True)
        self.assertTrue(bundle['attached_test_banks'])
        self.assertTrue({str(p.resolve()) for p in (parent, run, design, protocol, banks)} <=
                        set(bundle['provenance']['protected_paths']))

    def test_runner_honors_adapter_protected_paths_before_creating_output(self):
        import constrained_onboarding_runner_v1 as runner
        parent = self.root/'protected-parent'
        output = parent/'new-run'
        bundle = {'provenance': {'verified_current_parent': True, 'protected_paths': [str(parent.resolve())]}}
        with patch.object(runner.c, 'pin', return_value=self.root/'protocol.json'), \
                patch.object(runner.c, 'read', return_value={}), patch.object(runner, '_validate_bundle'):
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_INSIDE_INPUT'):
                runner.run_development(bundle, output, self.root/'protocol.json')
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
