import copy
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('edge_formal_reporting_tested', HERE/'reporting.py')
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


def ratio(n, d=1):
    return dict(numerator=n, denominator=d)


def row(uid, *, role='NORMAL', component='a', seconds=0, capture=None):
    return dict(uid=uid, source_role=role, capture_id=capture or 'EDGE_'+role,
        component_id=component, timestamp_ns=100+seconds*1_000_000_000,
        protocol=17 if role == 'UDP' else 6,
        tcp_flags=0 if role == 'UDP' else 0x10,
        stratum='NORMAL' if role == 'NORMAL' else 'UDP' if role == 'UDP' else 'ACK_ONLY',
        use='QUERY', owner='PINNED_EDGE_TARGET')


def selected(value, expansion=1, component_weight=None):
    result = dict(value, weights=dict(population_expansion_weight=ratio(expansion),
                                     row_inclusion_probability=ratio(1, expansion)))
    if value['source_role'] == 'NORMAL':
        result['weights']['component_metric_weight'] = component_weight or ratio(1)
    return result


def predictions(values):
    return np.asarray([[v]*4 for v in values], dtype=bool)


def census(rows):
    anchors = {(r['source_role'], r['capture_id']): 100 for r in rows}
    return reporting.population_census(rows, anchors)


def run(rows, methods, population):
    return reporting.summarise(rows, methods, population,
        prediction_uids={name:[r['uid'] for r in rows] for name in methods}, repetitions=200)


class ReportingTests(unittest.TestCase):
    def test_sample_component_and_known_N_population_rates_are_distinct(self):
        full = [row('a0', seconds=0), row('a1', seconds=60), row('a2', seconds=120),
                row('a3', seconds=121), row('b', component='b', seconds=120)]
        rows = [selected(full[0], 4, ratio(1,2)), selected(full[-1], 1, ratio(1,2))]
        result = run(rows, dict(RAW=predictions([True,True]), C5_P3=predictions([False,True])), census(full))
        normal = result['methods']['C5_P3']['heads']['ensemble']['roles']['NORMAL']
        self.assertEqual(normal['exact_selected_sample_alarm_rate'], .5)
        self.assertEqual(normal['normal_component_equal_alarm_rate'], .5)
        self.assertEqual(normal['ht_population_alarm_estimate'], .2)
        self.assertEqual(normal['unsampled_population_rows'], 3)
        self.assertFalse(result['ht_renormalized'])
        self.assertEqual(result['references_in_query_denominator'], 0)
        self.assertEqual(result['views']['full']['normal'], 'NOT_EVALUABLE_POSTWINDOW_ONLY_SELECTION')

    def test_fallback_HT_can_exceed_one_and_is_not_clamped_or_renormalized(self):
        full = [row('a'+str(i), seconds=i) for i in range(10)]+[row('b', component='b')]
        rows = [selected(full[0], expansion=20)]
        result = run(rows, dict(RAW=predictions([True])), census(full))
        rate = result['methods']['RAW']['heads']['27']['roles']['NORMAL']
        self.assertAlmostEqual(rate['ht_population_alarm_estimate'], 20/11)
        self.assertEqual(rate['ht_expanded_sample_count'], 20)
        self.assertFalse(result['ht_clamped'])

    def test_three_distinct_rates_and_head_identity(self):
        full = [row('a'+str(i), seconds=i) for i in range(4)]+[row('b',component='b')]
        rows = [selected(full[0],2,ratio(1,4)), selected(full[1],2,ratio(1,4)),
                selected(full[-1],1,ratio(1,2))]
        raw = np.ones((3,4),dtype=bool)
        c5 = np.asarray([[True,False,True,False],[False,True,True,False],
                         [False,False,False,True]],dtype=bool)
        result = run(rows,dict(RAW=raw,C5_P3=c5),census(full))
        heads = result['methods']['C5_P3']['heads']
        first = heads['27']['roles']['NORMAL']
        self.assertAlmostEqual(first['exact_selected_sample_alarm_rate'],1/3)
        self.assertEqual(first['normal_component_equal_alarm_rate'],.25)
        self.assertEqual(first['ht_population_alarm_estimate'],.4)
        self.assertEqual(heads['227']['roles']['NORMAL']['ht_population_alarm_estimate'],.8)
        self.assertEqual(heads['ensemble']['roles']['NORMAL']['ht_population_alarm_estimate'],.2)

    def test_complete_time_span_includes_zero_eligible_and_zero_selected_blocks(self):
        full = [row('a', seconds=0), row('b', seconds=120)]
        population = census(full)
        group = population['groups'][0]
        self.assertEqual(group['block_population_counts'], {'0':1,'1':0,'2':1})
        selected_rows = [selected(full[0])]
        result = reporting.temporal_sensitivity(selected_rows, np.array([True]), np.array([1.]),
            reporting._population(population), 'NORMAL', repetitions=2000, seed=20261103)
        fact = result['capture_scenario_groups'][0]
        self.assertEqual(fact['eligible_population_blocks'], 3)
        self.assertEqual(fact['zero_eligible_population_blocks'], 1)
        self.assertEqual(fact['zero_selected_population_blocks'], 2)
        self.assertLess(result['valid_repetitions'], 2000)
        self.assertGreater(result['zero_denominator_repetitions'],0)
        self.assertEqual(result['valid_repetitions']+result['zero_denominator_repetitions'],2000)
        self.assertEqual(result['positive_denominator_repetitions'],result['valid_repetitions'])
        again = reporting.temporal_sensitivity(selected_rows, np.array([True]), np.array([1.]),
            reporting._population(population), 'NORMAL', repetitions=2000, seed=20261103)
        self.assertEqual(result, again)

    def test_original_anchor_and_exact_integer_boundary(self):
        full = [row('before', seconds=59), row('at', seconds=60)]
        population = census(full)
        self.assertEqual(population['groups'][0]['anchor_ns'], 100)
        self.assertEqual(population['groups'][0]['block_population_counts'], {'0':1,'1':1})
        with self.assertRaisesRegex(ValueError, 'RAW_CAPTURE_ANCHOR_REQUIRED'):
            reporting.population_census(full, {})
        with self.assertRaisesRegex(ValueError, 'CANDIDATE_BEFORE_RAW_CAPTURE_ANCHOR'):
            reporting.population_census(full, {('NORMAL','EDGE_NORMAL'):full[-1]['timestamp_ns']})

    def test_capture_and_scenario_groups_never_merge(self):
        full = [row('n1', capture='n1'), row('n2', capture='n2', seconds=60),
                row('h', role='HTTP'), row('u', role='UDP')]
        population = census(full)
        self.assertEqual(len(population['groups']), 4)
        rows = [selected(r) for r in full]
        result = run(rows, dict(RAW=predictions([True]*4)), population)
        normal_time = result['methods']['RAW']['heads']['27']['roles']['NORMAL']['conditional_time_sensitivity']
        self.assertEqual(len(normal_time['capture_scenario_groups']), 2)
        self.assertTrue(all(g['source_role']=='NORMAL' for g in normal_time['capture_scenario_groups']))
        self.assertNotIn('EDGE_HTTP', [g['capture_id'] for g in normal_time['capture_scenario_groups']])

    def test_attack_strata_and_low_RAW_recall_withdrawal_gate(self):
        full = [row('h0', role='HTTP'), row('h1', role='HTTP',seconds=60)]
        full[0]['stratum'] = 'SYN_NO_ACK'
        full[0]['tcp_flags'] = 0x02
        rows = [selected(r) for r in full]
        result = run(rows, dict(RAW=predictions([True,False]), C5_P3=predictions([False,False])), census(full))
        head = result['methods']['C5_P3']['heads']['ensemble']
        self.assertEqual(set(head['roles']['HTTP']['strata']), set(reporting.HTTP_STRATA))
        self.assertEqual(head['raw_cumulative_safety']['status'], 'FAIL')
        self.assertIn('LOW_RAW_RECALL_ANY_WITHDRAWAL',
            head['raw_cumulative_safety']['groups']['scenario:HTTP']['failures'])
        self.assertEqual(head['roles']['HTTP']['strata']['OTHER']['population_count'], 0)

    def test_overlapping_HTTP_flag_subsets_are_explicit_and_payload_not_inferred(self):
        full = [row('h'+str(i),role='HTTP') for i in range(6)]
        for value, flags, stratum in zip(full,(2,24,16,17,25,4),
                ('SYN_NO_ACK','PSH_ACK','ACK_ONLY','FIN','FIN','RST')):
            value.update(tcp_flags=flags,stratum=stratum)
        rows = [selected(r) for r in full]
        result = run(rows,dict(RAW=predictions([True]*6)),census(full))
        audit = result['methods']['RAW']['heads']['27']['roles']['HTTP']['header_audit_subsets']
        self.assertEqual(audit['SYN_NO_ACK']['population_count'],1)
        self.assertEqual(audit['ACK_NO_SYN']['population_count'],4)
        self.assertEqual(audit['ACK_ONLY']['selected_rows'],1)
        self.assertEqual(audit['PSH_ACK']['population_count'],1)
        self.assertEqual(audit['OUTSIDE_SYN_GUARD']['population_count'],5)
        self.assertEqual(audit['HTTP_PAYLOAD']['status'],'NOT_EVALUABLE')
        self.assertEqual(audit['HTTP_GET']['status'],'NOT_EVALUABLE')

    def test_reference_query_overlap_is_rejected_in_denominator(self):
        value = selected(row('r'))
        value['use'] = 'REFERENCE'
        with self.assertRaisesRegex(ValueError, 'REFERENCE_OR_UNSELECTED_ROW'):
            run([value], dict(RAW=predictions([False])), census([value]))

    def test_ordered_UID_join_and_duplicates_fail(self):
        rows = [selected(row('a')), selected(row('b'))]
        with self.assertRaisesRegex(ValueError, 'ORDERED_QUERY_UID_JOIN'):
            reporting.summarise(rows, dict(RAW=predictions([False,False])), census(rows),
                prediction_uids={'RAW':['b','a']},repetitions=1)
        rows[1]['uid']='a'
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_QUERY_UID'):
            run(rows, dict(RAW=predictions([False,False])), census(rows))

    def test_inverse_weight_mismatch_is_rejected(self):
        rows = [selected(row('a'))]
        rows[0]['weights']['population_expansion_weight']=ratio(2)
        with self.assertRaisesRegex(ValueError, 'INVERSE_INCLUSION_WEIGHT_MISMATCH'):
            run(rows, dict(RAW=predictions([False])), census(rows))

    def test_independent_detector_may_add_RAW_negative_alarm(self):
        rows = [selected(row('a'))]
        with self.assertRaisesRegex(ValueError, 'SUPPRESSION_METHOD_ADDS_RAW_ALARM'):
            run(rows, dict(RAW=predictions([False]), C5_P3=predictions([True])), census(rows))
        result = run(rows, dict(RAW=predictions([False]), STANDARD_KNN5=predictions([True])), census(rows))
        self.assertEqual(result['methods']['STANDARD_KNN5']['heads']['27']['raw_cumulative_safety']['status'],
                         'DESCRIPTIVE_INDEPENDENT_DETECTOR')

    def test_unobserved_roles_are_not_reported_as_perfect_detection(self):
        rows = [selected(row('a'))]
        result = run(rows, dict(RAW=predictions([False])), census(rows))
        attack = result['methods']['RAW']['heads']['27']['roles']['UDP']
        self.assertIsNone(attack['exact_selected_sample_alarm_rate'])
        self.assertIsNone(attack['ht_population_alarm_estimate'])
        self.assertEqual(attack['sampling_status'], 'NOT_SAMPLED')

    def test_nonempty_unselected_population_is_not_zero_error_estimate(self):
        full = [row('n'),row('h',role='HTTP')]
        rows = [selected(full[0])]
        result = run(rows,dict(RAW=predictions([False])),census(full))
        attack = result['methods']['RAW']['heads']['27']['roles']['HTTP']
        self.assertEqual(attack['population_count'],1)
        self.assertIsNone(attack['ht_population_alarm_estimate'])
        self.assertIsNone(attack['ht_expanded_alarm_count'])
        self.assertIsNone(attack['conditional_time_sensitivity']['interval_2_5_97_5'])
        self.assertEqual(attack['conditional_time_sensitivity']['status'],'NOT_SAMPLED')
        self.assertEqual(attack['conditional_time_sensitivity']['valid_repetitions'],0)
        self.assertEqual(attack['conditional_time_sensitivity']['positive_denominator_repetitions'],200)
        self.assertEqual(attack['conditional_time_sensitivity']['zero_denominator_repetitions'],0)

    def test_attack_spoofed_components_not_materialized_as_population_component_metric(self):
        full = [row('u'+str(i),role='UDP',component='component'+str(i)) for i in range(40)]
        population = census(full)
        self.assertEqual(population['groups'][0]['component_counts'],{})
        self.assertEqual(population['roles']['UDP']['population_count'],40)

    def test_UTC_parser_keeps_all_nine_fractional_digits(self):
        spec = importlib.util.spec_from_file_location('edge_temporal_census_builder_tested', HERE/'build_population_census.py')
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0,str(HERE))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        self.assertEqual(module.utc_ns('1970-01-01T00:00:01.123456789Z'),1123456789)
        self.assertEqual(module.utc_ns('1970-01-02T01:02:03.000000001Z'),90123000000001)


if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ReportingTests)
    cases=[item.id() for item in suite]
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    pins={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
          for name in ('reporting.py','build_population_census.py','test_reporting.py')}
    receipt=dict(status='PASS' if result.wasSuccessful() else 'FAIL',
        scope='SYNTHETIC_STATISTICS_ONLY_NO_REAL_PREDICTIONS',tests_run=result.testsRun,
        test_cases=cases,failures=len(result.failures),errors=len(result.errors),input_pins=pins,
        model_calls=0,external_quality_evaluations=0,cloud_jobs_submitted=0)
    (HERE/'STATISTICS_TEST_RECEIPT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
