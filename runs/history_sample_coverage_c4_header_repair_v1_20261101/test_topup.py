"""Scientific input-boundary and density-allocation checks; synthetic only."""
import copy
import hashlib
import random
import unittest
from topup_selector import select


def digest(value):return hashlib.sha256(str(value).encode()).hexdigest()
SPEC={'camera':dict(raw_sha256='a'*64,owner='aa:bb:cc:dd:ee:ff',reference_end_us=100000,bank_end_frame=100000)}
def row(i,component='large'):
    return dict(uid=digest(i),device='camera',owner=SPEC['camera']['owner'],protocol=6,component_id=digest(component),
        origin_raw_sha256='a'*64,origin_packet_ordinal=i,history_role='HIST_REF',use='REFERENCE',label=0,
        timestamp_us=i,frame=i,reference_end_us=100000,bank_end_frame=100000)


class SelectionChecks(unittest.TestCase):
    def test_does_not_balance_large_and_small_components(self):
        rr=[row(i,'large' if i<=9000 else 'small') for i in range(1,10001)]
        chosen,_=select(rr,[],SPEC)
        self.assertEqual(len(chosen),4096)
        fraction=sum(r['component_id']==digest('large') for r in chosen)/len(chosen)
        self.assertGreater(fraction,.86);self.assertLess(fraction,.94)

    def test_traversal_order_invariance(self):
        rr=[row(i) for i in range(1,6001)];expected=select(rr,[],SPEC)
        random.Random(9).shuffle(rr)
        self.assertEqual(expected,select(rr,[],SPEC))

    def test_prior_physical_endpoint_excluded_even_if_uid_alias_changes(self):
        old=row(1);candidate=row(1);candidate['uid']=digest('alias')
        chosen,_=select([candidate,row(2)],[old],SPEC)
        self.assertEqual([r['origin_packet_ordinal'] for r in chosen],[2])

    def test_all_small_pool_rows_preserved(self):
        rr=[row(i) for i in range(1,6)]
        chosen,_=select(rr,[],SPEC)
        self.assertEqual({r['uid'] for r in chosen},{r['uid'] for r in rr})

    def test_dev_attack_future_or_unadmitted_inputs_rejected(self):
        bad=[dict(history_role='HIST_DEV',use='QUERY'),dict(label=1),dict(timestamp_us=100001),
             dict(frame=100001),dict(origin_raw_sha256='b'*64),dict(device='other'),
             dict(reference_end_us=100001),dict(is_fp=True)]
        for change in bad:
            with self.subTest(change=change),self.assertRaises(ValueError):
                select([dict(row(1),**change)],[],SPEC)

    def test_duplicate_physical_origin_rejected(self):
        other=dict(row(1),uid=digest('duplicate'))
        with self.assertRaises(ValueError):select([row(1),other],[],SPEC)
        with self.assertRaises(ValueError):select([row(1),row(1)],[],SPEC)

    def test_protocol_budgets_are_separate(self):
        tcp=[row(i) for i in range(1,5001)]
        udp=[dict(row(i),protocol=17) for i in range(5001,10001)]
        chosen,_=select(tcp+udp,[],SPEC)
        self.assertEqual(len(chosen),8192)

    def test_fixed_capacity_and_no_input_mutation(self):
        rr=[row(i) for i in range(1,6)];before=copy.deepcopy(rr)
        select(rr,[],SPEC);self.assertEqual(rr,before)
        with self.assertRaises(ValueError):select(rr,[],SPEC,cap=2048)


if __name__=='__main__':unittest.main(verbosity=2)
