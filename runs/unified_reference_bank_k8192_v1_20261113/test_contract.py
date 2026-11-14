"""Check frozen selection and stop conditions without accessing experiment queries."""
import json
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
import random
import unittest

import numpy as np

from frozen_selector import CAP, rank, select, verify_snapshot_row
from zero_degradation import paired_cell

ORIGIN=('e1a9de0a5eb30c72c26309edbb1345b9b1116bee3ab2937de2f88b549e8aaa1b',
        1,'ec:1a:59:83:28:11')
SHA,_,OWNER=ORIGIN


def row(i, *, capture='a', proto=6, raw=SHA):
    return dict(uid=f'{i:064x}', origin_raw_sha256=raw, origin_packet_ordinal=i,
                owner=OWNER, device='motion', capture_id=capture, partition='archive',
                protocol=proto, use='REFERENCE',label=0,history_role='HIST_REF',
                timestamp_us=10, frame=i, reference_end_us=15, bank_end_frame=10000,
                component_id=f'{1:064x}')


class Contract(unittest.TestCase):
    def test_c4_vector(self):
        self.assertEqual(f'{rank(ORIGIN):064x}',
                         '251b9159e42445142679b4592cca45ceeeaaa61e1ccb1dccd106fe9da99bd57f')

    def test_pool_complete_top_k_across_sources(self):
        other='b'*64
        meta=dict(partition='archive',reference_end_us=15,bank_end_frame=10000,raw_packet_count=10000)
        sources={('motion',SHA,OWNER,'a'):meta,('motion',other,OWNER,'b'):meta}
        rows=[row(i) for i in range(1,8195)]+[row(8195,capture='b',raw=other)]
        expect=sorted(rows,key=lambda x:rank((x['origin_raw_sha256'],x['origin_packet_ordinal'],x['owner'])))[:CAP]
        random.Random(42).shuffle(rows)
        with TemporaryDirectory() as tmp:
            chosen, totals=select(iter(rows+[rows[0]]),sources,Path(tmp)/'origins.sqlite')
            self.assertEqual(totals,{('motion',6):len(rows)})
            self.assertEqual(chosen,sorted(expect,key=lambda x:x['uid']))
            with self.assertRaisesRegex(ValueError,'TARGET_FEEDBACK_FIELD'):
                select(iter([dict(rows[0],score=1)]),sources,Path(tmp)/'bad.sqlite')

    def test_no_offsetting_attack_loss(self):
        old=np.array([True,False]); new=np.array([False,True]); w=np.array([.5,.5])
        self.assertEqual(paired_cell(old,new,w,attack=False)['status'],'PASS')
        self.assertEqual(paired_cell(old,new,w,attack=True)['status'],'FAIL')

    def test_census_json_and_decoded_snapshot_share_exact_row_identity(self):
        decoded = dict(row(1), canonical_key=(6, ('10.0.0.1', 80), ('10.0.0.2', 1234)))
        sealed = json.loads(json.dumps(decoded))
        self.assertNotEqual(sealed, decoded)
        verify_snapshot_row(sealed, dict(uid=decoded['uid'], row=decoded))
        with self.assertRaisesRegex(ValueError, 'SEALED_SNAPSHOT_ROW_JOIN'):
            verify_snapshot_row(dict(sealed, timestamp_us=11), dict(uid=decoded['uid'], row=decoded))
        with self.assertRaisesRegex(ValueError, 'SEALED_SNAPSHOT_ROW_JOIN'):
            verify_snapshot_row(dict(sealed, label=False), dict(uid=decoded['uid'], row=decoded))

    def test_no_positive_weight_tolerance(self):
        old=np.array([True,False]); new=np.array([False,True])
        w=np.array([.5,np.nextafter(.5,np.inf)])
        result=paired_cell(old,new,w,attack=False)
        self.assertEqual(result['n10'],result['n01'])
        self.assertEqual(result['status'],'FAIL')
        self.assertGreater(result['weighted_delta_numerator'],0)

    def test_packaged_metrics_support_device_protocol_groups(self):
        if not (Path(__file__).parent/'PACKAGE_MANIFEST.json').is_file() or not (
                Path(__file__).parent/'analysis_core.py').is_file():
            self.skipTest('run from the extracted HPC package')
        import prepare_reference  # Initialize vendor first, as the worker does.
        import paired_replay
        for func in (paired_replay.metrics_core.metrics, paired_replay.metrics_core.paired):
            self.assertIn('group_masks', inspect.signature(func).parameters)


if __name__=='__main__':
    unittest.main()
