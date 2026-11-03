"""Meaningful invariants for balancing, duplication and reference controls."""
import copy
import math
import unittest

import legacy_reference_sample_finalize_v1 as m


def target(uid,device='A',label=0,activity='normal',capture='c1',session='s1',timestamp=20,packet=None,partition='LEARN'):
    return dict(uid=uid,device=device,owner=device,label=label,activity=activity,capture_id=capture,
        session_id=session,timestamp=timestamp,packet_sha256=packet or uid,partition=partition,
        frame=1,use='LATER_NORMAL_QUERY',component_id=session,protocol=17)


class Finalizer(unittest.TestCase):
    def test_balancing_does_not_reward_packet_burst(self):
        rows=[]
        for d in ('A','B'):
            for y in (0,1):
                for i in range(100 if d=='A' and y else 1):rows.append(target('%s-%s-%s'%(d,y,i),device=d,label=y))
        m.weight_rows(rows)
        self.assertTrue(math.isclose(sum(1/r['balanced_bce_weight_denominator'] for r in rows),1))
        for d in ('A','B'):
            for y in (0,1):
                mass=sum(1/r['balanced_bce_weight_denominator'] for r in rows if r['device']==d and r['label']==y)
                self.assertAlmostEqual(mass,.25)

    def test_unpaired_device_is_error(self):
        with self.assertRaisesRegex(RuntimeError,'Unpaired'):m.weight_rows([target('a')])

    def test_exact_duplicate_excluded_but_later_equal_bytes_retained(self):
        a=target('a',packet='same');b=target('b',packet='same');c=target('c',timestamp=21,packet='same')
        selected,excluded=m.deduplicate([a,b,c],{'A':[]})
        self.assertEqual([x['uid'] for x in selected],['a','c']);self.assertEqual(len(excluded),1)

    def test_cross_partition_or_label_duplicate_stops(self):
        a=target('a',packet='same');b=target('b',packet='same',partition='DEV')
        with self.assertRaisesRegex(RuntimeError,'Cross-role'):m.deduplicate([a,b],{'A':[]})
        b['partition']='LEARN';b['label']=1
        with self.assertRaisesRegex(RuntimeError,'Cross-role'):m.deduplicate([a,b],{'A':[]})

    def test_reference_query_duplicate_removed(self):
        a=target('a',packet='same');b=target('b',packet='same')
        selected,excluded=m.deduplicate([b],{'A':[a]})
        self.assertFalse(selected);self.assertEqual(excluded[0]['reason'],'SAME_PACKET_TIME_AS_REFERENCE')

    def test_reference_components_not_repeated_to_pad_budget(self):
        a=target('a',timestamp=1);a['use']='REFERENCE'
        b=target('b',timestamp=2);b['use']='REFERENCE'
        devices=[dict(device='A',proposed_partition='LEARN',reference_end=5)]
        pools,cost=m.collapse_references([a,b],devices)
        self.assertEqual([r['uid'] for r in pools['A']],['b']);self.assertEqual(cost[0]['selected'],1)

    def test_control_equal_budget_partition_and_time(self):
        devices=[dict(device=d,proposed_partition='DEV',reference_end=end) for d,end in [('A',5),('B',10)]]
        pools={'A':[target('a',timestamp=2)],'B':[target('b',device='B',timestamp=8),target('c',device='B',timestamp=9)]}
        result=m.reference_interventions(pools,devices,[target('early',timestamp=7),target('later',timestamp=12)])
        self.assertEqual(result[0]['equal_count'],1);self.assertEqual(result[0]['applicable_query_count'],1)
        self.assertEqual(len(result[0]['correct_reference_uids']),len(result[0]['wrong_reference_uids']))
        # Counts within each protocol must match, even when the first-k order
        # would have produced a different TCP/UDP composition.
        pools={'A':[target('a'),target('a2'),target('a3')],
               'B':[target('b',device='B'),target('b2',device='B'),target('b3',device='B')]}
        pools['A'][-1]['protocol']=6
        pools['B'][0]['protocol']=6;pools['B'][1]['protocol']=6
        matched=m.reference_interventions(pools,devices,[])[0]
        self.assertEqual(matched['equal_count'],2);self.assertEqual(matched['protocol_multiset'],{6:1,17:1})
        pools={'A':[target('a')],'B':[target('b',device='B'),target('c',device='B')]}
        pools['B'][0]['protocol']=6
        self.assertEqual(m.reference_interventions(pools,devices,[])[0]['status'],'UNAVAILABLE_NO_EQUAL_PROTOCOL_DONOR')


if __name__=='__main__':unittest.main(verbosity=2)
