"""Scientific boundary checks for the source-only structural audit."""
import unittest
from source_task_audit import audit, legal_components, validate


def sample(**overrides):
    row = dict(uid='q', device='device', source_sha256='capture-q',
        capture_id='cq', session_id='sq', component_id='component-q',
        timestamp=20., reference_end=10., protocol=6, partition='LEARN',
        use='LATER_NORMAL_QUERY', label=0, fit_role='FIT', activity='normal')
    row.update(overrides)
    return row


def reference(**overrides):
    row = sample(uid='r', source_sha256='capture-r', session_id='sr',
        component_id='component-r', timestamp=5., use='REFERENCE')
    row.pop('fit_role')
    row.update(overrides)
    return row


class SourceAuditTests(unittest.TestCase):
    def test_target_query_and_reference_rejected(self):
        for row, is_ref in ((sample(partition='DEV'), False),
                            (reference(partition='DEV'), True)):
            with self.assertRaisesRegex(ValueError, 'TARGET_ROLE'):
                validate(row, reference=is_ref)

    def test_future_and_boundary_references_have_no_support(self):
        for end in (20., 21.):
            self.assertEqual(legal_components(sample(), [reference(reference_end=end)]),
                             (set(), set(), set()))

    def test_copied_component_not_extra_component_evidence(self):
        refs = [reference(uid='r1'), reference(uid='r2')]
        all_c, different_dependency, _ = legal_components(sample(), refs)
        self.assertEqual(len(all_c), 1)
        self.assertEqual(len(different_dependency), 1)

    def test_same_component_history_separated_from_other_dependencies(self):
        all_c, different_dependency, _ = legal_components(sample(),
            [reference(component_id='component-q')])
        self.assertEqual(all_c, {'component-q'})
        self.assertFalse(different_dependency)

    def test_same_dependency_not_different_dependency(self):
        _, different_dependency, _ = legal_components(sample(),
            [reference(source_sha256='capture-q', session_id='sq')])
        self.assertFalse(different_dependency)

    def test_other_device_and_protocol_not_support(self):
        for r in (reference(device='other'), reference(protocol=17)):
            self.assertFalse(legal_components(sample(), [r])[0])

    def test_pre_reference_query_retained(self):
        result, roles = audit([sample(timestamp=1.)], [reference()])
        self.assertEqual(result['query_rows'], 1)
        self.assertEqual(roles, ['FIT'])
        self.assertEqual(result['groups'][0]['support_rows']['no_timestamp_prior_component'], 1)

    def test_attack_reference_and_unknown_fit_role_rejected(self):
        with self.assertRaisesRegex(ValueError, 'NORMAL_REFERENCE_ONLY'):
            validate(reference(label=1), reference=True)
        with self.assertRaisesRegex(ValueError, 'FIT_CAL_ROLE'):
            validate(sample(fit_role='TARGET'))

    def test_cross_role_component_reported(self):
        result, _ = audit([sample(), sample(uid='q2', session_id='s2', fit_role='CAL')], [])
        self.assertEqual(result['fit_cal_dependency_overlap'], 0)
        self.assertEqual(result['fit_cal_component_overlap'], 1)

    def test_device_bank_cutoff_must_be_consistent_across_protocols(self):
        with self.assertRaisesRegex(ValueError, 'COMPLETE_DEVICE_BANK_END'):
            audit([sample()], [reference(uid='r1'),
                reference(uid='r2', protocol=17, reference_end=21.)])

    def test_source_reference_query_uid_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_REFERENCE_QUERY_UID_OVERLAP'):
            audit([sample(uid='r', timestamp=1.)], [reference()])

    def test_two_timestamp_prior_components_counted_separately_from_different_dependencies(self):
        report, _ = audit([sample()], [reference(uid='r1'),
            reference(uid='r2', component_id='component-q')])
        support = report['groups'][0]['support_rows']
        self.assertEqual(support['with_at_least_two_timestamp_prior_components'], 1)
        self.assertNotIn('with_at_least_two_different_dependency_components', support)


if __name__ == '__main__':
    unittest.main()
