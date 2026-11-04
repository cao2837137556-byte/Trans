import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('budget_under_test',Path(__file__).with_name('budget.py'))
budget=importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class BudgetTests(unittest.TestCase):
    def test_singleton_physical_clone_is_not_one_forward_row(self):
        self.assertEqual(budget.physical_rows(1),16)
        self.assertEqual(budget.physical_rows(17),32)
        self.assertEqual(budget.physical_rows(16),16)
        self.assertEqual(budget.physical_rows(18),18)

    def test_rates_use_physical_not_logical_denominator(self):
        rates=budget.measured_rates([dict(shape=[6,13,12],logical_rows=1,physical_rows=16,seconds=16.)])
        self.assertEqual(rates[(6,13,12)],1.)

    def test_unmeasured_dominator_is_explicit_not_exact_measurement(self):
        rate,kind,proxies=budget.estimate_rate((6,25,5),{(6,25,6):.4,(6,73,12):4.})
        self.assertEqual(rate,.4)
        self.assertEqual(proxies,[(6,25,6)])
        self.assertNotIn('EXACT',kind)

    def test_unmeasured_udp_width_extrapolation_is_labelled(self):
        rate,kind,_=budget.estimate_rate((17,25,2),{(17,7,1):1.,(17,7,2):.5})
        self.assertGreater(rate,1.)
        self.assertIn('EXTRAPOLATION',kind)

    def test_exact_shape_counts_preserved(self):
        out=budget.encoding_scenario({'6,13,1':17,'17,7,1':20}, {(6,13,1):1.,(17,7,1):.1})
        self.assertEqual(out['logical_rows'],37)
        self.assertEqual(out['physical_rows'],52)
        self.assertEqual(out['batches'],4)


if __name__=='__main__':
    unittest.main()
