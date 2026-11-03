"""Boundary and source-role tests against the unchanged V3 lambda selector."""
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import unittest

import numpy as np

import constrained_onboarding_core_v3 as core
import onboarding_budget_v1 as budget


REAL_SOURCE_RESULT = None


def row(uid, label=1, device='D', activity='attack', component=None, reference=False):
    return dict(uid=uid, device=device, activity=activity, capture_id='capture',
                session_id='session-' + uid, component_id=component or uid,
                partition='LEARN', fit_role='FIT' if reference else 'CAL',
                protocol=6, timestamp=1. if reference else 20., frame=1 if reference else 20,
                reference_end=2., use='REFERENCE' if reference else 'QUERY', label=label)


class MatrixBank:
    """Known geometry outputs for numerical decision-boundary unit tests."""
    def __init__(self, support, normal_support=None, eligible=None):
        self.support = np.asarray(support, dtype=np.float64)
        self.eligible = (np.ones_like(self.support, dtype=bool) if eligible is None else eligible)
        self.normal_support = normal_support
        self.rows = [row('ref1', label=0, reference=True), row('ref2', label=0, reference=True)]

    def matrix(self, rows, *args, **kwargs):
        return dict(support=self.support, eligible=self.eligible,
                    roster=[dict(partition='LEARN', device='donor' + str(j), protocol=6,
                                 distinct_components=2) for j in range(self.support.shape[1])],
                    query_uid_sha256=core._uid_hash([r['uid'] for r in rows]))

    def own(self, rows, *args, **kwargs):
        support = np.ones(len(rows)) if self.normal_support is None else self.normal_support
        return dict(support=np.asarray(support))


def fixture(logits, *, weights=None, support=None, normal_logits=None, normal_support=None,
            rows=None, cuts=None, ensemble_cut=0., scales=None):
    if isinstance(logits, dict):
        n = len(next(iter(logits.values())))
    else:
        n = len(logits)
    rows = [row('attack' + str(i)) for i in range(n)] if rows is None else rows
    normals = [row('normal', 0, activity='normal')]
    bank = MatrixBank(np.ones((n, 1)) if support is None else support, normal_support)
    args = (rows, logits, np.zeros(3) if cuts is None else cuts, ensemble_cut,
            np.ones(3) if scales is None else scales, bank, None, None,
            dict(protocols={'6': dict(status='READY', rho_z=1., rho_q=1.),
                            '17': dict(status='READY', rho_z=1., rho_q=1.)}))
    kwargs = dict(cal_normal_rows=normals,
                  normal_logits=np.full((1, 3), .05) if normal_logits is None else normal_logits,
                  normal_e3=None, normal_q14=None,
                  attack_weights=weights,
                  feature_uids=[r['uid'] for r in rows], q_uids=[r['uid'] for r in rows],
                  normal_feature_uids=['normal'], normal_q_uids=['normal'])
    return args, kwargs


class BudgetTests(unittest.TestCase):
    def prepare(self, *args, **kwargs):
        return budget.prepare_budget_calibration(*args, **kwargs)

    def assert_legacy(self, args, kwargs):
        expected = core.choose_lambda(*args, feature_uids=kwargs['feature_uids'], q_uids=kwargs['q_uids'])
        prep = self.prepare(*args, **kwargs)
        # Full legacy receipt equality includes exact withdrawal UIDs/counts,
        # cap margin floats, candidate passes, ordering and lambda tie policy.
        self.assertEqual(prep['legacy_protection'], expected)
        result = budget.select_budget_lambda(prep, 0.)
        self.assertEqual(result['selected_lambda'], expected['selected_lambda'])
        self.assertEqual([x['selection_pass'] for x in result['candidates']],
                         [x['passes'] for x in expected['candidates']])
        for candidate, item in zip(prep['candidates'], expected['candidates']):
            self.assertEqual(candidate['newly_missed_uids'], item['newly_missed_uids'])
        return prep, result

    def test_strict_cut_and_nextafter_float64(self):
        for score, expected in [(.05, 0.), (np.nextafter(.05, np.inf), .05),
                                (np.nextafter(.05, -np.inf), 0.), (0., .25)]:
            with self.subTest(score=score):
                args, kwargs = fixture(np.full((1, 3), score))
                prep, result = self.assert_legacy(args, kwargs)
                self.assertEqual(result['selected_lambda'], expected)
                corrected = core.apply_correction(args[1], np.ones(1), args[4], .05)
                self.assertEqual(bool((corrected > 0.)[0, 0]), score > .05)

    def test_float32_float64_grid_dict_seed_and_scale_paths(self):
        rng = np.random.default_rng(5727)
        for dtype in (np.float32, np.float64):
            for mapping in (False, True):
                with self.subTest(dtype=dtype, mapping=mapping):
                    values = rng.normal(.2, .2, (11, 3)).astype(dtype)
                    values[0] = .05
                    logits = {str(seed): values[:, j] for j, seed in enumerate(core.SEEDS)} if mapping else values
                    args, kwargs = fixture(logits, support=rng.uniform(0., 1., (11, 3)),
                                           cuts={str(s): 0. for s in core.SEEDS},
                                           scales={str(s): v for s, v in zip(core.SEEDS, (0., 1., 2.))})
                    self.assert_legacy(args, kwargs)

    def test_float32_boundary_is_cast_like_original(self):
        args, kwargs = fixture(np.full((1, 3), .05, dtype=np.float32))
        _, result = self.assert_legacy(args, kwargs)
        self.assertEqual(result['selected_lambda'], .05)

    def test_original_ordered_ensemble_boundary(self):
        x = np.array([[2.**53, -(2.**53), 1.], [1., -1., np.nextafter(0., 1.)]])
        for cut in [core.ordered_ensemble(x)[0],
                    np.nextafter(core.ordered_ensemble(x)[0], -np.inf)]:
            args, kwargs = fixture(x, ensemble_cut=cut, scales=[1., 1., 1.])
            self.assert_legacy(args, kwargs)

    def test_zero_weight_attack_is_protected_at_epsilon_zero(self):
        args, kwargs = fixture(np.array([[.05]*3, [1.]*3]), weights=[0., 1.])
        prep, zero = self.assert_legacy(args, kwargs)
        self.assertEqual(zero['selected_lambda'], 0.)
        positive = budget.select_budget_lambda(prep, .1)
        self.assertEqual(positive['selected_lambda'], .25)
        self.assertTrue(positive['selected_budget_acceptance']['passes'])

    def test_no_support_tie_chooses_largest_original_lambda(self):
        args, kwargs = fixture(np.array([[1.]*3]), support=np.zeros((1, 2)), normal_support=[0.])
        prep, zero = self.assert_legacy(args, kwargs)
        self.assertEqual(zero['selected_lambda'], .25)
        self.assertEqual(budget.select_budget_lambda(prep, .1)['selected_lambda'], .25)
        self.assertEqual([c['normal_quality'] for c in prep['candidates']], [0.] * 4)

    def test_epsilon_is_percentage_points_not_fraction(self):
        args, kwargs = fixture(np.array([[.2]*3, [1.]*3]), weights=[.001, .999])
        prep = self.prepare(*args, **kwargs)
        self.assertEqual(budget.select_budget_lambda(prep, .1)['selected_lambda'], .25)
        self.assertEqual(budget.select_budget_lambda(prep, np.nextafter(.1, 0.))['selected_lambda'], .1)
        self.assertEqual(budget.select_budget_lambda(prep, .05)['selected_lambda'], .1)

    def test_union_across_source_donors_not_per_donor_average(self):
        args, kwargs = fixture(np.array([[.2]*3, [.2]*3, [1.]*3]),
                               weights=[.0006, .0006, .9988],
                               support=[[1., 0.], [0., 1.], [0., 0.]])
        prep = self.prepare(*args, **kwargs)
        result = budget.select_budget_lambda(prep, .1)
        self.assertEqual(result['selected_lambda'], .1)
        risk = prep['candidates'][-1]['overall']['suffixes']['ensemble']
        self.assertEqual(risk['added_fn_count'], 2)
        self.assertEqual(risk['recall_loss_pp'], .12)

    def test_weight_scale_does_not_overflow_recall_pp(self):
        for weights in ([.001, .999], [1.e305, 9.99e307], [1.e-303, 9.99e-301]):
            with self.subTest(weights=weights):
                args, kwargs = fixture(np.array([[.2]*3, [1.]*3]), weights=weights)
                prep = self.prepare(*args, **kwargs)
                risk = prep['candidates'][-1]['overall']['suffixes']['ensemble']
                self.assertTrue(np.isfinite(risk['recall_loss_pp']))
                self.assertAlmostEqual(risk['recall_loss_pp'], .1)

    def test_absolute_floor_separated_from_epsilon_zero_compatibility(self):
        args, kwargs = fixture(np.array([[0.]*3, [1.]*3]), support=np.zeros((2, 1)))
        prep, zero = self.assert_legacy(args, kwargs)
        self.assertEqual(zero['selected_lambda'], .25)
        self.assertEqual(zero['status'], 'LEGACY_SELECTION_FAILS_NEW_ACCEPTANCE')
        self.assertFalse(zero['selected_budget_acceptance']['passes'])
        positive = budget.select_budget_lambda(prep, .1)
        self.assertIsNone(positive['selected_lambda'])
        self.assertEqual(positive['status'], 'NO_FEASIBLE_WORKPOINT')

    def test_device_loss_guard_blocks_concentrated_failure(self):
        rows = [row('attack0', device='small'), row('attack1', device='small'), row('attack2', device='large')]
        args, kwargs = fixture(np.array([[.2]*3, [1.]*3, [1.]*3]), rows=rows,
                               weights=[.001, .009, .99])
        prep = self.prepare(*args, **kwargs)
        result = budget.select_budget_lambda(prep, .2)
        self.assertEqual(result['selected_lambda'], .1)
        self.assertTrue(any(x.startswith('DEVICES_LOSS:small:')
                            for x in result['candidates'][-1]['budget_acceptance']['failures']))

    def test_annotation_loss_guard_blocks_concentrated_failure(self):
        rows = [row('attack0', activity='rare'), row('attack1', activity='rare'), row('attack2', activity='common')]
        args, kwargs = fixture(np.array([[.2]*3, [1.]*3, [1.]*3]), rows=rows,
                               weights=[.001, .009, .99])
        prep = self.prepare(*args, **kwargs)
        result = budget.select_budget_lambda(prep, .2)
        self.assertEqual(result['selected_lambda'], .1)
        self.assertTrue(any(x.startswith('ANNOTATIONS_LOSS:rare:')
                            for x in result['candidates'][-1]['budget_acceptance']['failures']))

    def test_each_suffix_constrained_not_only_ensemble(self):
        args, kwargs = fixture(np.array([[.2, 1., 1.], [1., 1., 1.]]), weights=[.002, .998])
        prep = self.prepare(*args, **kwargs)
        result = budget.select_budget_lambda(prep, .1)
        self.assertEqual(result['selected_lambda'], .1)
        last = result['candidates'][-1]['budget_acceptance']['failures']
        self.assertIn('RELATIVE_LOSS:27', last)
        self.assertNotIn('RELATIVE_LOSS:ensemble', last)

    def test_source_only_roles_reference_leakage_and_duplicate_uid(self):
        cases = [('partition', 'DEV', 'ATTACK_SOURCE_CAL_ONLY'),
                 ('fit_role', 'FIT', 'ATTACK_SOURCE_CAL_ONLY'),
                 ('component_id', 'ref1', 'CAL_REFERENCE_COMPONENT_LEAKAGE'),
                 ('activity', '', 'ATTACK_ANNOTATION_REQUIRED')]
        for key, value, error in cases:
            args, kwargs = fixture(np.array([[1.]*3]))
            args[0][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, error):
                self.prepare(*args, **kwargs)
        args, kwargs = fixture(np.array([[1.]*3, [1.]*3]))
        args[0][1]['uid'] = args[0][0]['uid']
        with self.assertRaisesRegex(ValueError, 'EMPTY_OR_DUPLICATE_UID'):
            self.prepare(*args, **kwargs)

    def test_input_validation_weights_epsilon_seed_grid_support(self):
        for bad in ([0., 0.], [-1., 2.], [np.nan, 1.], [np.inf, 1.], [1.], ['1', '1']):
            args, kwargs = fixture(np.array([[1.]*3, [1.]*3]), weights=bad)
            with self.subTest(weights=bad), self.assertRaises(ValueError):
                self.prepare(*args, **kwargs)
        args, kwargs = fixture(np.array([[1.]*3]))
        prep = self.prepare(*args, **kwargs)
        for bad in (-.1, 101., np.nan, np.inf, True, '0.1'):
            with self.subTest(eps=bad), self.assertRaisesRegex(ValueError, 'EPSILON_PP_RANGE'):
                budget.select_budget_lambda(prep, bad)
        kwargs['seed_order'] = (127, 27, 227)
        with self.assertRaisesRegex(ValueError, 'FIXED_SEED_ORDER'):
            self.prepare(*args, **kwargs)
        args, kwargs = fixture(np.array([[1.]*3]), support=[[1.1]])
        with self.assertRaisesRegex(ValueError, 'ATTACK_SUPPORT_MATRIX'):
            self.prepare(*args, **kwargs)
        args, kwargs = fixture(np.array([[1.]*3]))
        args[5].eligible[:] = False
        with self.assertRaisesRegex(ValueError, 'INELIGIBLE_POSITIVE_SUPPORT'):
            self.prepare(*args, **kwargs)
        bad = copy.deepcopy(prep)
        bad['lambda_grid'] = [.0, .1]
        with self.assertRaisesRegex(ValueError, 'PREPARATION_SCHEMA_GRID'):
            budget.select_budget_lambda(bad, .1)

    def test_real_reference_bank_geometry_and_uid_join(self):
        refs = [row('ref1', 0, reference=True), row('ref2', 0, reference=True)]
        z = np.zeros((2, 768)); z[:, 0] = 1.
        q = np.zeros((2, 14))
        bank = core.ReferenceBank(refs, z, q, (np.zeros(768), np.ones(768)),
                                  feature_uids=['ref1', 'ref2'], q_uids=['ref1', 'ref2'])
        args, kwargs = fixture(np.array([[.05]*3]))
        args = list(args); args[5] = bank; args[6] = z[:1]; args[7] = q[:1]
        kwargs.update(normal_e3=z[:1], normal_q14=q[:1])
        prep, result = self.assert_legacy(tuple(args), kwargs)
        self.assertEqual(result['selected_lambda'], 0.)
        self.assertEqual(prep['candidates'][1]['overall']['suffixes']['ensemble']['added_fn_count'], 1)
        kwargs['q_uids'] = ['wrong']
        with self.assertRaisesRegex(ValueError, 'BROKEN_FEATURE_UID_JOIN'):
            self.prepare(*args, **kwargs)


@unittest.skipUnless(os.environ.get('PAPER04_BUDGET_REAL_SOURCE') == '1',
                     'set PAPER04_BUDGET_REAL_SOURCE=1 for pinned saved-source parity')
class SavedSourceTests(unittest.TestCase):
    def test_saved_source_subset_legacy_receipt_and_score_bits(self):
        """Use real saved CAL logits/E3/q14 and all original source references.

        This deliberately uses a small deterministic source subset; the full-CAL
        dry-run is separate. No model forward or target asset is accessed.
        """
        global REAL_SOURCE_RESULT
        root = Path(__file__).resolve().parents[2]
        prior = root / 'runs/diagnostics_d1_d2_v1_20261022'
        prepared = prior / 'assets/heads/run/prepared'
        cal_root = prior / 'assets/onboarding/run/evaluation/calibration'
        feature_path = root / 'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy'

        def sha(path):
            h = hashlib.sha256()
            with path.open('rb') as f:
                for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
                    h.update(block)
            return h.hexdigest()

        binding = json.loads((prior / 'assets/heads/run/cache_binding.json').read_text())
        self.assertEqual(sha(feature_path), binding['feature_files']['LEARN.npy'])
        indices = np.load(prepared / 'CAL.npz', allow_pickle=False)['indices']
        cal_slots = {int(index): pos for pos, index in enumerate(indices)}
        chosen, counts = [], {}
        with gzip.open(prepared / 'LEARN.jsonl.gz', 'rt', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i not in cal_slots:
                    continue
                r = json.loads(line)
                self.assertEqual(r['fit_role'], 'CAL')
                key = (r['label'], r['device'], r['protocol'])
                if counts.get(key, 0) < 2:
                    chosen.append((i, cal_slots[i], r))
                    counts[key] = counts.get(key, 0) + 1
        self.assertTrue(chosen)
        trace_path = prior / 'output/d1/r2/source_actual_trace.npz'
        with np.load(trace_path, allow_pickle=False) as trace:
            saved_uids, saved_logits = trace['uid'], trace['original_logits']
            for _, pos, r in chosen:
                self.assertEqual(str(saved_uids[pos]), r['uid'])
            logits = saved_logits[[pos for _, pos, _ in chosen]]
        refs_path = prior / 'assets/reference_scores/SOURCE_REFS.npz'
        with gzip.open(refs_path.with_suffix('.jsonl.gz'), 'rt', encoding='utf-8') as f:
            refs = [json.loads(line) for line in f]
        with np.load(refs_path, allow_pickle=False) as data:
            self.assertEqual(list(data['uid']), [r['uid'] for r in refs])
            ref_z, ref_q = data['e3'], data['q14']
        with np.load(prepared / 'normalizer.npz', allow_pickle=False) as norm:
            normalizer = (norm['mean'], norm['scale'])
        bank = core.ReferenceBank(refs, ref_z, ref_q, normalizer,
                                  feature_uids=[r['uid'] for r in refs], q_uids=[r['uid'] for r in refs])
        e3 = np.load(feature_path, mmap_mode='r', allow_pickle=False)[[i for i, _, _ in chosen], :768]
        q14 = np.load(prepared / 'LEARN_q.npy', mmap_mode='r', allow_pickle=False)[[i for i, _, _ in chosen]]
        rows = [r for _, _, r in chosen]
        ai = [i for i, r in enumerate(rows) if r['label'] == 1]
        ni = [i for i, r in enumerate(rows) if r['label'] == 0]
        attacks, normals = [rows[i] for i in ai], [rows[i] for i in ni]
        settings = {name: json.loads((cal_root / (name + '.json')).read_text())
                    for name in ('cuts', 'scales', 'geometry')}
        cut, ensemble_cut = settings['cuts']['cuts'], settings['cuts']['ensemble_cut']
        args = (attacks, logits[ai], cut, ensemble_cut, settings['scales'],
                bank, e3[ai], q14[ai], settings['geometry'])
        kwargs = dict(feature_uids=[r['uid'] for r in attacks], q_uids=[r['uid'] for r in attacks],
                      cal_normal_rows=normals, normal_logits=logits[ni], normal_e3=e3[ni], normal_q14=q14[ni],
                      normal_feature_uids=[r['uid'] for r in normals], normal_q_uids=[r['uid'] for r in normals])
        expected = core.choose_lambda(*args, feature_uids=kwargs['feature_uids'], q_uids=kwargs['q_uids'])
        prep = budget.prepare_budget_calibration(*args, **kwargs)
        self.assertEqual(prep['legacy_protection'], expected)
        result = budget.select_budget_lambda(prep, 0.)
        self.assertEqual(result['selected_lambda'], expected['selected_lambda'])
        own = bank.own(attacks, e3[ai], q14[ai], settings['geometry'],
                       feature_uids=kwargs['feature_uids'], q_uids=kwargs['q_uids'])
        legacy_scores = core.apply_correction(logits[ai], own['support'], settings['scales'], expected['selected_lambda'])
        new_scores = core.apply_correction(logits[ai], own['support'], settings['scales'], result['selected_lambda'])
        self.assertEqual(legacy_scores.tobytes(), new_scores.tobytes())
        self.assertTrue(np.array_equal(legacy_scores > cut, new_scores > cut))
        self.assertEqual(core.ordered_ensemble(legacy_scores).tobytes(), core.ordered_ensemble(new_scores).tobytes())
        REAL_SOURCE_RESULT = dict(status='PASS', scope='deterministic first two CAL rows per label/device/protocol',
                                  attacks=len(ai), normals=len(ni), references=len(refs),
                                  complete_source_cal_evaluated=False, target_assets_read=False,
                                  selected_lambda=result['selected_lambda'], source_feature_sha256=binding['feature_files']['LEARN.npy'],
                                  source_uid_sha256=core._uid_hash([r['uid'] for r in rows]),
                                  original_score_bits_equal=True, original_receipt_equal=True,
                                  inputs={str(p.relative_to(root)).replace('\\', '/'): sha(p) for p in
                                          [trace_path, refs_path, refs_path.with_suffix('.jsonl.gz'),
                                           prepared/'CAL.npz', prepared/'LEARN.jsonl.gz', prepared/'LEARN_q.npy',
                                           prepared/'normalizer.npz', cal_root/'geometry.json', cal_root/'scales.json',
                                           cal_root/'cuts.json']})


if __name__ == '__main__':
    unittest.main()
