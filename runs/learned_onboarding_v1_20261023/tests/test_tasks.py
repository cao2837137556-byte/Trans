import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tasks import (dependency_folds, hierarchical_weights, fit_statistics,
                   mine_hard_tasks, build_task_distribution, sample_indices,
                   coverage_precheck, residual_signal)


def row(uid, label, device, component, session, score=0.0, view=0):
    return dict(uid=uid, label=label, device=device, component_id=component,
                source_sha256='source', session_id=session, capture_id=uid,
                activity='activity', partition='LEARN', fit_role='FIT',
                protocol=6, fold='F0', view=view, score=score, t=0.0,
                s=1.0, eligible=True, own_bank=True, banks=[{'d2': .2}])


class TaskTests(unittest.TestCase):
    def test_transitive_closure_and_weight_mass(self):
        rows = [row('a', 0, 'A', 'c1', 's1'), row('b', 0, 'A', 'c1', 's2'),
                row('c', 0, 'B', 'c2', 's2'), row('d', 0, 'B', 'c3', 's3')]
        folds = dependency_folds(rows)
        self.assertEqual({folds[u]['group'] for u in ('a', 'b', 'c')}, {'a'})
        self.assertEqual(folds['d']['group'], 'd')
        np.testing.assert_allclose(hierarchical_weights(rows).sum(), 1.0)

    def test_fit_statistics_are_complementary_and_fit_only(self):
        rows = [row('a', 0, 'A', 'a', 'a'), row('b', 1, 'A', 'b', 'b'),
                row('c', 0, 'B', 'c', 'c'), row('d', 1, 'B', 'd', 'd')]
        folds = {r['uid']: {'group': r['uid'], 'fold': 'F0' if i < 2 else 'F1'}
                 for i, r in enumerate(rows)}
        stats = fit_statistics(rows, np.array([0., 1., 10., 11.]), folds)
        self.assertEqual(stats['F0']['t'], 10.)
        self.assertEqual(stats['F1']['t'], 0.)
        with self.assertRaisesRegex(ValueError, 'FIT_ONLY'):
            fit_statistics(rows + [{**row('x', 0, 'X', 'x', 'x'), 'fit_role': 'CAL'}],
                           np.zeros(5))

    def test_hard_tie_and_sampling_mass(self):
        tasks = []
        for view in (0, 1):
            for label in (0, 1):
                for i in range(3):
                    tasks.append(row(f'{view}{label}{i}', label, 'A', f'c{i}', f's{i}',
                                     score=.1, view=view))
        hard, _ = mine_hard_tasks(tasks)
        self.assertTrue({(v, f'{v}{label}0') for v in (0, 1) for label in (0, 1)} <= hard)
        ordered, p0, ph = build_task_distribution(tasks, hard)
        for view in (0, 1):
            for label in (0, 1):
                ix = [i for i, t in enumerate(ordered) if t['view'] == view and t['label'] == label]
                self.assertTrue(np.isclose(p0[ix].sum(), .25))
                self.assertTrue(np.isclose(ph[ix].sum(), .25))
        np.testing.assert_array_equal(sample_indices(ph, [.0, .5]), sample_indices(ph, [.0, .5]))

    def test_gates_use_own_bank_and_positive_aux_residual(self):
        tasks = [row('a', 0, 'A', 'a', 'a', score=1., view=1),
                 row('b', 0, 'B', 'b', 'b', score=1., view=1),
                 row('c', 1, 'A', 'c', 'c'), row('d', 1, 'B', 'd', 'd')]
        self.assertEqual(coverage_precheck(tasks)['status'], 'READY')
        self.assertEqual(residual_signal(tasks)['status'], 'READY')
        tasks[0]['hard'] = True
        hard_signal = residual_signal(tasks)['views']['auxiliary']['hard']
        self.assertEqual(hard_signal['positive_count'], 1)
        self.assertAlmostEqual(hard_signal['positive_weight_mass_in_full_class'], .5)
        self.assertAlmostEqual(hard_signal['positive_weight_mass_within_hard'], 1.)
        self.assertEqual(hard_signal['devices'], ['A'])
        tasks[1]['own_bank'] = False
        self.assertEqual(residual_signal(tasks)['status'], 'SOURCE_SIGNAL_INSUFFICIENT')


if __name__ == '__main__':
    unittest.main()
