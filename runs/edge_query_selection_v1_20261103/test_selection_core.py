"""Selection regressions verify budget, inclusion and ordering contracts."""
import hashlib
import importlib.util
import itertools
import random
from fractions import Fraction
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('edge_selection_core', HERE/'selection_core.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def frac(x):
    return Fraction(x['numerator'], x['denominator'])


class SelectionContracts(unittest.TestCase):
    def test_b_matches_frozen_algorithm_over_varied_populations(self):
        # Independent direct transcription of the frozen B integer contract.
        rng = random.Random(28430)
        for _ in range(120):
            counts = {str(i): rng.randint(1, 1500) for i in range(rng.randint(1, 35))}
            total, c = sum(counts.values()), len(counts)
            k = rng.randint(c, total)
            expected = dict(counts)
            if total != c:
                r, d = k-c, total-c
                expected = {g: 1+r*(n-1)//d for g, n in counts.items()}
                order = sorted(counts, key=lambda g: (-(r*(counts[g]-1)%d), g))
                for g in order[:k-sum(expected.values())]:
                    expected[g] += 1
            self.assertEqual(s.normal_plan(counts, k)['quotas'], expected)

    def test_normal_fallback_is_component_hash_not_packet_population(self):
        counts = {'large': 100000, 'tiny1': 1, 'tiny2': 1, 'tiny3': 2}
        p = s.normal_plan(counts, 2)
        expected = sorted(counts, key=lambda g: (
            hashlib.sha256((s.NORMAL_SALT+'|'+g).encode()).hexdigest(), g))[:2]
        self.assertEqual(set(p['quotas']), set(expected))
        self.assertEqual(set(p['quotas'].values()), {1})
        self.assertEqual(p['branch'], s.FALLBACK_BRANCH)
        self.assertEqual(p, s.normal_plan(dict(reversed(list(counts.items()))), 2))

    def test_fallback_inclusion_and_ht_factor(self):
        w = s.normal_weights(50, 1, 30000, 20000, s.FALLBACK_BRANCH)
        self.assertEqual(frac(w['row_inclusion_probability']), Fraction(1, 75))
        self.assertEqual(frac(w['population_expansion_weight']), Fraction(75))
        self.assertEqual(frac(w['component_metric_weight']), Fraction(1, 20000))
        # Omitting C/K would yield 50 and is explicitly rejected by this test.
        self.assertNotEqual(frac(w['population_expansion_weight']), Fraction(50))

    def test_b_weights_and_attack_weights(self):
        w = s.normal_weights(100, 4, 10, 10, s.B_QUOTA_BRANCH)
        self.assertEqual(frac(w['population_expansion_weight']), 25)
        self.assertEqual(frac(w['component_metric_weight']), Fraction(1, 40))
        self.assertEqual(frac(s.attack_weights(2000, 1000)['population_expansion_weight']), 2)

    def test_fallback_ht_total_exact_expectation_over_two_stage_samples(self):
        # Enumerate every component subset and every within-component row draw.
        # The two-stage HT error-total expectation must equal the full total,
        # while the missing-C/K coefficient would undercount by K/C.
        groups = {'a': (1, 0), 'b': (0, 1, 1), 'c': (0,)}
        c, k = len(groups), 2
        component_sets = list(itertools.combinations(groups, k))
        expectation = Fraction(0)
        wrong_expectation = Fraction(0)
        for chosen in component_sets:
            probability_component = Fraction(1, len(component_sets))
            for values in itertools.product(*(range(len(groups[g])) for g in chosen)):
                probability_rows = probability_component
                estimated = Fraction(0)
                wrong = Fraction(0)
                for g, i in zip(chosen, values):
                    n = len(groups[g])
                    probability_rows /= n
                    expansion = frac(s.normal_weights(n, 1, c, k, s.FALLBACK_BRANCH)
                                     ['population_expansion_weight'])
                    estimated += expansion * groups[g][i]
                    wrong += n * groups[g][i]
                expectation += probability_rows * estimated
                wrong_expectation += probability_rows * wrong
        true_total = sum(sum(x) for x in groups.values())
        self.assertEqual(expectation, true_total)
        self.assertEqual(wrong_expectation, Fraction(k, c) * true_total)
        self.assertNotEqual(wrong_expectation, true_total)

    def test_http_flags_exclusive_and_unknown_retained(self):
        observed = {2: 'SYN_NO_ACK', 24: 'PSH_ACK', 16: 'ACK_ONLY',
                    17: 'FIN', 25: 'FIN', 4: 'RST'}
        self.assertEqual({f: s.http_stratum(f) for f in observed}, observed)
        self.assertEqual(s.http_stratum(0x14), 'OTHER')
        self.assertEqual(s.http_stratum(0x12), 'OTHER')
        self.assertEqual(s.http_stratum(0x03), 'SYN_NO_ACK')

    def test_actual_http_population_floor_and_conservation(self):
        counts = dict(SYN_NO_ACK=61641, PSH_ACK=77043, ACK_ONLY=7817,
                      FIN=3003+399, RST=2449, OTHER=0)
        p = s.attack_plan(counts)
        self.assertEqual(p['population_count'], 152352)
        self.assertEqual(sum(p['quotas'].values()), 20000)
        self.assertEqual(p['quotas']['FIN'], 1000)
        self.assertEqual(p['quotas']['RST'], 1000)
        self.assertGreaterEqual(p['quotas']['ACK_ONLY'], 1000)
        self.assertEqual(p['quotas']['OTHER'], 0)
        self.assertEqual(p, s.attack_plan(dict(reversed(list(counts.items())))))

    def test_udp_single_stratum(self):
        self.assertEqual(s.attack_plan({'UDP': 2898830}, order=('UDP',))['quotas'],
                         {'UDP': 20000})

    def test_small_population_and_budget_floor_failures(self):
        self.assertEqual(s.attack_plan({'UDP': 25}, order=('UDP',))['quotas'], {'UDP': 25})
        with self.assertRaisesRegex(ValueError, 'FLOORS_EXCEED_BUDGET'):
            s.attack_plan({'a': 1000, 'b': 1000}, 1500, ('a', 'b'))
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_OR_DUPLICATE_STRATUM'):
            s.attack_plan({'unregistered': 10})

    def test_ties_use_pinned_order_and_never_zero_nonempty_floor(self):
        p = s.attack_plan({'a': 30000, 'b': 30000, 'c': 30}, 10001, ('a', 'b', 'c'))
        self.assertEqual(sum(p['quotas'].values()), 10001)
        self.assertEqual(p['quotas']['c'], 30)
        self.assertGreaterEqual(p['quotas']['b'], p['quotas']['a'])

    def test_invalid_or_inconsistent_weights_rejected(self):
        with self.assertRaises(ValueError):
            s.normal_weights(5, 2, 3, 2, s.FALLBACK_BRANCH)
        with self.assertRaises(ValueError):
            s.normal_weights(5, 2, 3, 2, s.B_QUOTA_BRANCH)
        with self.assertRaises(ValueError):
            s.normal_plan({'a': True})
        with self.assertRaises(ValueError):
            s.http_stratum(-1)


if __name__ == '__main__':
    unittest.main()
