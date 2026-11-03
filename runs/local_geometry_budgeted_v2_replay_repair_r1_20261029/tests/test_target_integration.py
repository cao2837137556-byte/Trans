"""Target stage wiring with tiny fake assets; no real forward or distances."""
import json
import gzip
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lg import metrics, target
from lg.common import SPEC_SHA, array_sha, sha, uid_sha, write_json


class FakeRuntime:
    def __init__(self, output):
        self.output = output
        self.pairs = 0

    def checkpoint(self, *args, **kwargs):
        pass

    def add_pairs(self, count):
        self.pairs += count

    def write_json(self, name, value):
        write_json(self.output / name, value)


def params():
    return dict(cuts=np.repeat(.5, 4), geometry={}, scales=np.ones(3),
                normalizer=(np.zeros(768), np.ones(768)))


class TargetIntegrationTests(unittest.TestCase):
    @contextmanager
    def _real_cal_fixture(self, root, *, exposed_logit=.6, bad_anchor=False):
        """Four synthetic CAL rows through the real main_calibration body.

        Only the two production cardinality assertions are replaced for this
        tiny fixture.  Roles, UID order, component isolation, original decisions,
        D0 hashes, correction arithmetic, new eligibility and safety checks remain
        real.  Geometry itself is mocked, so no pair or head is evaluated.
        """
        output = root / 'output'
        output.mkdir()
        for name in ('dense', 'oldrefs', 'prep', 'calibration'):
            (root / name).mkdir()
        rr = [dict(uid='q0', device='A', label=0), dict(uid='q1', device='B', label=0),
              dict(uid='q2', device='A', label=1), dict(uid='q3', device='C', label=1)]
        for i, row in enumerate(rr):
            row.update(source_index=i, fit_role='CAL', partition='LEARN', protocol=6,
                       component_id='query-component-' + str(i))
        references = [dict(uid='r0', device='A', component_id='reference-A'),
                      dict(uid='r1', device='B', component_id='reference-B')]
        reference_arrays = dict(uid=np.array(['r0', 'r1']), e3=np.ones((2, 768)),
                                q14=np.zeros((2, 14)))
        np.savez(root / 'dense' / 'bank.npz', **reference_arrays)
        np.savez(root / 'oldrefs' / 'SOURCE_REFS.npz', **reference_arrays)
        np.savez(root / 'prep' / 'CAL.npz', indices=np.arange(4, dtype=np.int64))
        with gzip.open(root / 'prep' / 'LEARN.jsonl.gz', 'wt', encoding='utf-8') as stream:
            for row in rr:
                stream.write(json.dumps(row) + '\n')
        raw3 = np.repeat(np.array([.6, .6, .9, exposed_logit])[:, None], 3, axis=1)
        raw4 = np.column_stack((raw3, metrics.ensemble(raw3, mode='target')))
        np.savez(root / 'trace.npz', uid=np.array([r['uid'] for r in rr]),
                 original_logits=raw3, original_decisions=raw4 > .5)
        write_json(root / 'calibration' / 'cuts.json', dict(cuts=[.5, .5, .5],
                   ensemble_cut=.5, seeds=[27, 127, 227], moved=False))
        write_json(root / 'calibration' / 'geometry.json', {'synthetic': True})
        write_json(root / 'calibration' / 'scales.json', {'scales': [1., 1., 1.]})
        write_json(root / 'plan.json', {'synthetic': True})
        np.savez(root / 'prep' / 'normalizer.npz', mean=np.zeros(768), scale=np.ones(768))
        np.save(root / 'features.npy', np.zeros((4, 768)))
        np.save(root / 'prep' / 'LEARN_q.npy', np.zeros((4, 14)))
        (root / 'sealed-input.txt').write_text('synthetic input', encoding='utf-8')
        own_d0 = metrics.apply_correction(raw3, np.array([.2, .2, .2, 0.]),
                                          np.ones(3), .25, mode='target')
        old_mask = np.array([[True, False], [False, False]])
        anchors = dict(own_corrected_logits_sha256=array_sha(own_d0[:, :3]),
                       own_decisions_sha256=array_sha(own_d0 > .5),
                       eligible_matrix_sha256=array_sha(old_mask))
        if bad_anchor:
            anchors['own_corrected_logits_sha256'] = '0' * 64
        dense = SimpleNamespace(
            DENSE=Path('dense'), OLD_REFS=Path('oldrefs'), PREP=Path('prep'),
            SOURCE_PLAN=Path('plan.json'), TRACE=Path('trace.npz'),
            CALIBRATION=Path('calibration'), FEATURES=Path('features.npy'), ANCHORS=anchors,
            source_identity_preflight=lambda root: {'sealed-input.txt': sha(root / 'sealed-input.txt')},
            load_rows=lambda path: references, validate_bank=Mock())
        target_data = SimpleNamespace(_verify_assets=Mock(), load_pool=Mock())
        legacy = dict(dense_source=dense, source_data=SimpleNamespace(), core=object(),
                      target_data=target_data, indexed=SimpleNamespace(
                          IndexedMatrix=lambda a, ix, columns=None: a[ix] if columns is None else a[ix, columns]))
        testcase = self

        class FakeBank:
            def __init__(self, *args, **kwargs):
                testcase.assertFalse(kwargs['allow_prebank_history'])

            def scale_arrays(self):
                return dict(uid=np.array(['r0', 'r1']), ready=np.zeros(2, bool),
                            rho_z=np.full(2, np.nan), rho_q=np.full(2, np.nan),
                            neighbor_uids=np.full((2, 5), '', dtype='<U2'))

            def own(self, rows, *args, **kwargs):
                testcase.assertEqual([r['uid'] for r in rows], ['q0', 'q1'])
                return dict(d0=np.array([.2, .2]), local=np.array([.8, .8]),
                            eligible_d0=np.ones(2, bool), eligible_local=np.ones(2, bool))

            def matrix(self, rows, *args, **kwargs):
                testcase.assertEqual([r['uid'] for r in rows], ['q2', 'q3'])
                # q3 has no own donor.  A newly legal foreign 1C donor must
                # still veto CAL even though q3's own score stays at RAW.
                return dict(d0=np.array([[.2, 0.], [0., 0.]]),
                            local=np.array([[.2, 0.], [0., 1.]]),
                            eligible_d0=old_mask.copy(),
                            eligible_local=np.array([[True, False], [False, True]]),
                            roster=[dict(partition='LEARN', device='A', protocol=6),
                                    dict(partition='LEARN', device='B', protocol=6)])

        original_require = target.require
        def fixture_require(condition, message):
            if message == 'MAIN_CAL_INDICES':
                testcase.assertEqual(len(rr), 4)
                return
            if message == 'MAIN_CAL_COUNTS':
                testcase.assertEqual([r['label'] for r in rr], [0, 0, 1, 1])
                return
            return original_require(condition, message)
        source_result = root / 'source.json'
        source_result.write_text('{}', encoding='utf-8')
        runtime = FakeRuntime(output)
        with patch('lg.geometry.DualBank', FakeBank), \
             patch('lg.target.require', side_effect=fixture_require), \
             patch('lg.target.load_legacy', return_value=legacy), \
             patch('lg.target.verify_predecessor', return_value=(
                 {'scientific_status': 'SOURCE_SIGNAL_PASS'}, {'elapsed_seconds': 1.})):
            yield SimpleNamespace(root=root, output=output, runtime=runtime, legacy=legacy,
                                  target_data=target_data, source_result=source_result, raw4=raw4)

    def test_real_main_cal_path_new_foreign_one_component_donor_blocks_ab(self):
        with tempfile.TemporaryDirectory() as td:
            with self._real_cal_fixture(Path(td), exposed_logit=.6) as fixture:
                result = target.run_target(fixture.root, fixture.output, fixture.runtime,
                                           fixture.source_result)
                self.assertEqual(result['scientific_status'], 'MAIN_CAL_SAFETY_FAIL')
                self.assertEqual(result['target_evaluations'], 0)
                fixture.target_data._verify_assets.assert_not_called()
                fixture.target_data.load_pool.assert_not_called()
                checks = json.loads((fixture.output / 'MAIN_CAL_CHECK.json').read_text(encoding='utf-8'))
                self.assertTrue(checks['d0']['pass'])
                self.assertFalse(checks['local']['pass'])
                self.assertEqual(checks['local']['withdrawals']['ensemble'], 1)
                parity = json.loads((fixture.output / 'MAIN_D0_PARITY.json').read_text(encoding='utf-8'))
                self.assertEqual(parity['measured'], parity['expected'])
                with np.load(fixture.output / 'MAIN_CAL_LOCAL_ATTACK_SCENARIOS.npz', allow_pickle=False) as saved:
                    self.assertTrue(saved['eligible'][1, 1])
                    self.assertLess(saved['safety'][1, 3], .5)
                with np.load(fixture.output / 'MAIN_CAL_D0_ATTACK_SCENARIOS.npz', allow_pickle=False) as saved:
                    self.assertFalse(saved['eligible'][1, 1])
                    self.assertGreater(saved['safety'][1, 3], .5)
                with np.load(fixture.output / 'MAIN_CAL_SCORES.npz', allow_pickle=False) as saved:
                    # Own C is head-only; failure came from the foreign donor.
                    self.assertEqual(saved['local'][3, 3], .6)
                    self.assertFalse(saved['eligible_local'][3])
                self.assertEqual(fixture.runtime.pairs, 0)

    def test_real_main_cal_path_rejects_d0_numeric_anchor_before_ab(self):
        with tempfile.TemporaryDirectory() as td:
            with self._real_cal_fixture(Path(td), bad_anchor=True) as fixture:
                with self.assertRaisesRegex(ValueError, 'MAIN_D0_NUMERIC_ANCHOR'):
                    target.run_target(fixture.root, fixture.output, fixture.runtime,
                                      fixture.source_result)
                fixture.target_data._verify_assets.assert_not_called()
                fixture.target_data.load_pool.assert_not_called()
                self.assertFalse((fixture.output / 'MAIN_CAL_CHECK.json').exists())

    def test_real_main_cal_path_safe_new_donor_preserves_all_four_suffixes(self):
        with tempfile.TemporaryDirectory() as td:
            with self._real_cal_fixture(Path(td), exposed_logit=.9) as fixture:
                result = target.main_calibration(fixture.root, fixture.output,
                                                  fixture.runtime, fixture.legacy)
                self.assertTrue(all(check['pass'] for check in result['checks'].values()))
                self.assertEqual(result['checks']['local']['withdrawals'],
                                 {str(seed): 0 for seed in (27, 127, 227, 'ensemble')})
                self.assertEqual(fixture.runtime.pairs, 0)

    def test_source_failure_stops_before_any_legacy_or_target_loader(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result_path = root / 'RESULT.json'
            write_json(result_path, {'scientific_status': 'SAFETY_FAIL'})
            write_json(root / 'STAGE_RECEIPT.json', dict(
                stage='source', technical_status='COMPLETED', spec_sha256=SPEC_SHA,
                code_sha256={'synthetic': 'code'}, result_sha256=sha(result_path),
                outputs={'RESULT.json': sha(result_path)}, elapsed_seconds=1.,
                peak_process_tree_rss_bytes=1, output_bytes=1, pairs=0, head_forward_rows=0))
            write_json(root / 'STATUS.json', {'technical_status': 'COMPLETED'})
            with patch('lg.runtime.code_seal', return_value={'synthetic': 'code'}), \
                 patch('lg.target.load_legacy') as loader:
                with self.assertRaisesRegex(ValueError, 'SOURCE_GATE_NOT_PASS'):
                    target.run_target(root, root / 'never_created', None, result_path)
                loader.assert_not_called()

    def test_main_cal_failure_stops_before_ab_asset_verification_or_load(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / 'output'
            output.mkdir()
            result_path = root / 'source.json'
            result_path.write_text('{}', encoding='utf-8')
            target_data = SimpleNamespace(_verify_assets=Mock(), load_pool=Mock())
            cal = dict(checks={'d0': {'pass': True}, 'local': {'pass': False}}, parameters=params())
            with patch('lg.target.verify_predecessor', return_value=(
                    {'scientific_status': 'SOURCE_SIGNAL_PASS'}, {'elapsed_seconds': 1.})), \
                 patch('lg.target.load_legacy', return_value={'target_data': target_data}), \
                 patch('lg.target.main_calibration', return_value=cal):
                result = target.run_target(root, output, FakeRuntime(output), result_path)
            self.assertEqual(result['scientific_status'], 'MAIN_CAL_SAFETY_FAIL')
            self.assertEqual(result['target_evaluations'], 0)
            target_data._verify_assets.assert_not_called()
            target_data.load_pool.assert_not_called()

    def test_two_target_pools_call_real_metrics_and_write_pickle_free_arrays(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / 'output'
            output.mkdir()
            source_result = root / 'source.json'
            source_result.write_text('{}', encoding='utf-8')
            population = {}
            manifest = {'pools': []}
            historical = {'pools': {}}
            refs = [dict(uid='r0'), dict(uid='r1')]
            for pool in ('CIC_DEV', 'UNSW_DEV'):
                folder = root / pool
                folder.mkdir()
                rr = [dict(uid=pool + str(i), label=0 if i < 2 else 1, device='device',
                           partition='DEV', protocol=6, activity='normal' if i < 2 else 'attack',
                           annotation='normal' if i < 2 else 'attack', component_id='c' + str(i))
                      for i in range(4)]
                raw3 = np.repeat(np.array([.6, .6, .9, .9])[:, None], 3, axis=1)
                a0 = np.array([.2, .2, 0., 0.])
                d0 = metrics.apply_correction(raw3, a0, np.ones(3), .25, mode='target')
                own = dict(uid=np.asarray([r['uid'] for r in rr]), cuts=np.repeat(.5, 3),
                           ensemble_cut=.5, raw_logits=raw3,
                           raw_ensemble_logits=metrics.ensemble(raw3, mode='target'),
                           corrected_logits=d0[:, :3], corrected_ensemble_logits=d0[:, 3],
                           corrected=d0 > .5, support=a0, eligible=np.ones(4, bool))
                population[pool] = (rr, np.repeat('TCP_OTHER', 4), {'own': own},
                                    np.ones(4, dtype=np.int64), np.array([False, True, True, True]))
                np.save(folder / 'query.npy', np.zeros((4, 768), dtype=np.float64))
                np.save(folder / 'q.npy', np.zeros((4, 14), dtype=np.float64))
                np.savez(folder / 'bank.npz', uid=np.array(['r0', 'r1']),
                         e3=np.ones((2, 768)), q14=np.zeros((2, 14)))
                (folder / 'rows.json').write_text('[]', encoding='utf-8')
                def asset(name):
                    return dict(path=pool + '/' + name, sha256=sha(folder / name))
                spec = dict(pool_id=pool, dense_rows=2,
                            query=dict(e3=asset('query.npy'), q14=asset('q.npy'),
                                       feature_uid_sha256=uid_sha(r['uid'] for r in rr),
                                       q_uid_sha256=uid_sha(r['uid'] for r in rr)),
                            dense_bank=dict(rows=asset('rows.json'), e3=asset('bank.npz'),
                                            expected_ordered_uid_sha256=uid_sha(['r0', 'r1'])))
                manifest['pools'].append(spec)
                historical['pools'][pool] = {'arms': {'R-DENSE': {'0.1': {'views': {
                    'full': {}, 'post_window_primary': {}}}}}}
            write_json(root / 'manifest.json', manifest)
            write_json(root / 'matrix' / 'RESULT.json', historical)
            pool_loader = Mock(side_effect=lambda root, pool, spec: population[pool])
            parity = Mock(return_value={'status': 'SYNTHETIC_PARITY'})
            target_data = SimpleNamespace(
                _verify_assets=Mock(return_value={'target_inputs': {}}),
                MANIFEST='manifest.json', MATRIX=Path('matrix'), load_pool=pool_loader,
                target_denominators=lambda rows, pool: np.ones(len(rows), dtype=np.int64),
                verify_d0_view=parity)
            legacy = dict(target_data=target_data,
                          dense_source=SimpleNamespace(load_rows=lambda path: refs),
                          core=object(), indexed=SimpleNamespace(
                              IndexedMatrix=lambda a, ix, columns=None: a[ix] if columns is None else a[ix, columns]))

            class FakeBank:
                def __init__(self, *args, **kwargs):
                    pass

                def own(self, rows, *args, **kwargs):
                    return dict(d0=np.array([.2, .2, 0., 0.]),
                                local=np.array([.6, .6, 0., 0.]),
                                eligible_d0=np.ones(4, bool), eligible_local=np.ones(4, bool),
                                branch=np.array(['1C', '2C_ZERO', '2C_POS', 'OTHER'], dtype=object))

                def scale_arrays(self):
                    return dict(uid=np.array(['r0', 'r1']), ready=np.ones(2, bool),
                                rho_z=np.ones(2), rho_q=np.ones(2),
                                neighbor_uids=np.full((2, 5), '', dtype='<U2'))

            cal = dict(checks={'d0': {'pass': True}, 'local': {'pass': True}}, parameters=params())
            runtime = FakeRuntime(output)
            # Only geometry and saved-input loaders are mocked.  The real
            # evaluate_population/target_gate APIs and arithmetic must execute.
            with patch('lg.target.verify_predecessor', return_value=(
                    {'scientific_status': 'SOURCE_SIGNAL_PASS'}, {'elapsed_seconds': 1.})), \
                 patch('lg.target.load_legacy', return_value=legacy), \
                 patch('lg.target.main_calibration', return_value=cal), \
                 patch('lg.geometry.DualBank', FakeBank), \
                 patch('lg.metrics.evaluate_population', wraps=metrics.evaluate_population) as evaluate:
                result = target.run_target(root, output, runtime, source_result)
            self.assertEqual(result['scientific_status'], 'TARGET_GOAL_PASS')
            self.assertEqual(result['target_evaluations'], 2)
            self.assertEqual(pool_loader.call_count, 2)
            self.assertEqual(evaluate.call_count, 4)  # two views for each pool
            self.assertEqual(runtime.pairs, 0)
            self.assertEqual({c.kwargs['name'] for c in evaluate.call_args_list}, {'CIC_DEV', 'UNSW_DEV'})
            for pool in ('CIC_DEV', 'UNSW_DEV'):
                with np.load(output / (pool + '_SCORES.npz'), allow_pickle=False) as saved:
                    for name in saved.files:
                        self.assertNotEqual(saved[name].dtype.kind, 'O')
                report = json.loads((output / (pool + '_REPORT.json')).read_text(encoding='utf-8'))
                self.assertEqual(report['views']['post_window_primary']['metrics']['L']['ensemble']['fpr'], 0.)


if __name__ == '__main__':
    unittest.main()
