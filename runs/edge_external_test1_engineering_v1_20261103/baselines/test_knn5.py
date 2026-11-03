import unittest
import numpy as np

from knn5 import KNN5Bank, decisions, source_cuts


def row(i, **changes):
    x = dict(uid=str(i), partition='LEARN', device='d', protocol=6,
             component_id='one-component', capture_id='r', frame=i+1,
             timestamp=float(i), reference_end=10., label=0, use='REFERENCE')
    x.update(changes)
    return x


class KNNTests(unittest.TestCase):
    def test_standard_fifth_distance_and_raw_fallback(self):
        e = np.zeros((6, 768)); e[:,0] = 1
        e[:,1] = np.arange(6)
        refs = [row(i) for i in range(6)]
        bank = KNN5Bank(refs, e, (np.zeros(768), np.ones(768)),
                        feature_uids=[r['uid'] for r in refs])
        query = [row(100, timestamp=20., capture_id='later', use='QUERY')]
        result = bank.distances(query, e[:1], feature_uids=['100'])
        normalized = e/np.linalg.norm(e, axis=1)[:,None]
        expected = np.sort(np.linalg.norm(normalized-normalized[:1], axis=1))[4]
        self.assertAlmostEqual(result['distance'][0], expected, places=14)
        # kNN is point-based; no accidental two-component C5 requirement.
        self.assertEqual(result['reason'][0], 'KNN5_SCORED')
        query[0]['timestamp'] = 10.
        early = bank.distances(query, e[:1], feature_uids=['100'])
        self.assertTrue(np.isnan(early['distance'][0]))
        self.assertEqual(early['reason'][0], 'BANK_NOT_YET_AVAILABLE')

    def test_replay_and_uid_misalignment(self):
        e = np.ones((5,768)); refs = [row(i) for i in range(5)]
        bank = KNN5Bank(refs,e,(np.zeros(768),np.ones(768)),feature_uids=list('01234'))
        q = [row(0, use='QUERY',timestamp=20.,capture_id='later')]
        result = bank.distances(q,e[:1],feature_uids=['0'])
        self.assertTrue(np.isnan(result['distance'][0]))
        with self.assertRaisesRegex(ValueError,'QUERY_UID_JOIN'):
            bank.distances(q,e[:1],feature_uids=['x'])

    def test_threshold_ties_and_fallback_mass(self):
        distance = np.array([0.,1.,1.,2.,np.nan])
        weights = np.array([.1,.2,.3,.15,.25])
        raw = np.zeros((5,4),bool)
        raw[[1,4],:] = True
        calibrated = source_cuts(distance,raw,weights)
        self.assertEqual(calibrated['cuts'],[1.]*4)
        got = decisions(distance,raw,calibrated['cuts'])
        self.assertTrue(got[4].all())
        self.assertTrue(got[3].all())
        self.assertFalse(got[1].any())
        for wp in calibrated['working_points']:
            self.assertLessEqual(wp['achieved_weighted_fpr'],wp['target_weighted_fpr'])

    def test_same_capture_frame_boundary(self):
        e=np.ones((5,768)); refs=[row(i,bank_end_frame=10) for i in range(5)]
        bank=KNN5Bank(refs,e,(np.zeros(768),np.ones(768)),feature_uids=list('01234'))
        q=[row(100,use='QUERY',timestamp=20.,frame=10)]
        result=bank.distances(q,e[:1],feature_uids=['100'])
        self.assertEqual(result['reason'][0],'BANK_FRAME_NOT_YET_AVAILABLE')

    def test_source_only_override(self):
        e=np.ones((5,768)); refs=[row(i) for i in range(5)]
        bank=KNN5Bank(refs,e,(np.zeros(768),np.ones(768)),feature_uids=list('01234'))
        q=[row(100,use='QUERY',timestamp=20.,partition='EXTERNAL_ARCHIVAL_EVALUATION')]
        with self.assertRaisesRegex(ValueError,'SOURCE_DONOR_ONLY'):
            bank.distances(q,e[:1],feature_uids=['100'],donor=('LEARN','d',6))


if __name__ == '__main__':
    unittest.main()
