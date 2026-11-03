"""Guards for saved-score analysis; synthetic arrays only."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
import legacy_reference_saved_score_audit_v1 as a


class SavedScoreGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'scores.npz'
        self.rows = [{'uid': 'a'}, {'uid': 'b'}]
        self.seeds = [27, 127, 227]
        names = ['R', 'Q', 'M', 'C'] + [arm+'_'+str(s) for arm in ('Q', 'M', 'C') for s in self.seeds]
        self.values = {k: np.array([-2., 3.], dtype=np.float32) for k in names}
        self.values['uid'] = np.array(['a', 'b'])

    def tearDown(self):
        self.temp.cleanup()

    def load(self):
        np.savez(self.path, **self.values)
        return a.load_scores(self.path, self.rows, self.seeds, True)

    def test_valid(self):
        self.assertEqual(len(self.load()), 13)

    def test_uid_reordering_rejected(self):
        self.values['uid'] = np.array(['b', 'a'])
        with self.assertRaisesRegex(a.c.Stop, 'SCORE_UID_ORDER'): self.load()

    def test_truncation_rejected(self):
        self.values['R'] = np.array([-2.], dtype=np.float32)
        with self.assertRaisesRegex(a.c.Stop, 'SCORE_SHAPE_FINITE'): self.load()

    def test_nonfinite_rejected(self):
        self.values['Q_27'][0] = np.nan
        with self.assertRaisesRegex(a.c.Stop, 'SCORE_SHAPE_FINITE'): self.load()

    def test_changed_ensemble_rejected(self):
        self.values['C'][0] = 0
        with self.assertRaisesRegex(a.c.Stop, 'ENSEMBLE_DRIFT'): self.load()

    def test_missing_seed_rejected(self):
        self.values.pop('M_227')
        with self.assertRaisesRegex(a.c.Stop, 'SCORE_KEYS'): self.load()

    def test_weighted_sum_roundoff_is_recorded(self):
        d = a.compare_saved_report({'weighted_rate': .5}, {'weighted_rate': .5+1e-14})
        self.assertGreater(d, 0)

    def test_material_weighted_difference_rejected(self):
        with self.assertRaisesRegex(a.c.Stop, 'REPORT_WEIGHTED_SUM'):
            a.compare_saved_report({'weighted_rate': .5}, {'weighted_rate': .500001})

    def test_integer_count_difference_never_tolerated(self):
        with self.assertRaisesRegex(a.c.Stop, 'REPORT_EXACT_FIELD'):
            a.compare_saved_report({'positive': 200}, {'positive': 201})

    def test_missing_report_field_rejected(self):
        with self.assertRaisesRegex(a.c.Stop, 'REPORT_KEYS'):
            a.compare_saved_report({'positive': 200}, {})


if __name__ == '__main__':
    unittest.main()
