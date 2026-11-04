import copy
import unittest
from real_slice_preflight import validate_candidate, SLICE_SHA, STAGES


class PreflightContractTests(unittest.TestCase):
    def candidate(self):
        return dict(status='CANDIDATE_SUCCESS', card_sha256='bound', kind='V3_REAL_SLICE_E2E',
            runtime_identity={'runtime': 'frozen'}, slice_sha256=SLICE_SHA, logical_rows=78,
            external_quality_retained=False, actual_v3_packed_backend=True,
            stages=[dict(name=s, status='PASS', seconds=1) for s in STAGES])

    def test_requires_all_real_stages(self):
        value = self.candidate()
        validate_candidate(value, 'bound', {'runtime': 'frozen'})
        for stage in range(len(STAGES)):
            broken = copy.deepcopy(value); broken['stages'][stage]['status'] = 'PENDING'
            with self.assertRaisesRegex(ValueError, 'ALL_REAL_STAGES'):
                validate_candidate(broken, 'bound', {'runtime': 'frozen'})

    def test_wrong_runtime_card_slice_or_old_backend_cannot_promote(self):
        for field, wrong in [('runtime_identity', {}), ('card_sha256', 'old'), ('slice_sha256', 'other'),
                ('logical_rows', 77), ('actual_v3_packed_backend', False), ('external_quality_retained', True)]:
            broken = self.candidate(); broken[field] = wrong
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_FIELDS'):
                validate_candidate(broken, 'bound', {'runtime': 'frozen'})
