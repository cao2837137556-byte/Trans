"""Meaningful causal/role regressions, with no encoder or test performance."""
import tempfile
from pathlib import Path
import unittest
from decimal import Decimal

import edge_adapter as edge


def packet(frame, seconds, *, sport='12345', dport='1883', outgoing=False, truncated=False):
    return {'frame.number':str(frame),'frame.time_epoch':str(seconds),'frame.len':'60',
        'frame.cap_len':'40' if truncated else '60','eth.src':edge.OWNER if outgoing else 'aa:bb:cc:dd:ee:ff',
        'eth.dst':'aa:bb:cc:dd:ee:ff' if outgoing else edge.OWNER,
        'ip.src':edge.TARGET_IP if outgoing else '192.168.0.170',
        'ip.dst':'192.168.0.170' if outgoing else edge.TARGET_IP,
        'ip.proto':'6','ip.hdr_len':'20','ip.dsfield':'0x00','ip.len':'40','ip.flags':'0x02','ip.ttl':'64',
        'tcp.srcport':sport,'tcp.dstport':dport,'tcp.flags':'0x0010','tcp.window_size_value':'1024',
        'tcp.seq_raw':'10','tcp.ack_raw':'20','tcp.urgent_pointer':'0','tcp.hdr_len':'20','tcp.len':'0',
        'tcp.flags.ack':'1','tcp.flags.syn':'0','tcp.flags.reset':'0','tcp.flags.fin':'0'}


class AdapterContracts(unittest.TestCase):
    def setUp(self):
        self.api=edge.prep.old.legacy_runtime()[0]

    def assert_same(self, a, b, row):
        ar=a.append(row);br=b.append(row)
        self.assertEqual(ar[:2],br[:2])
        self.assertEqual(a.query_allowed,b.query_allowed)
        self.assertEqual(a.query_reason,b.query_reason)
        self.assertEqual(a.events,b.events)
        self.assertEqual(a.reasons,b.reasons)
        self.assertEqual(a.last_seen,b.last_seen)
        self.assertEqual(a.poisoned,b.poisoned)
        self.assertEqual(a.tainted,b.tainted)

    def test_population_eligibility_equals_complete_numerical_core(self):
        numerical=edge.frozen.Contexts('test',{edge.OWNER},self.api)
        census=edge.eligibility_context('test',self.api)
        data=[packet(1,100),packet(2,101,sport='9999'),
              packet(3,'99.5'),packet(4,102),packet(5,103,sport='9999'),
              packet(6,104,sport='9999',truncated=True),packet(7,105,sport='9999')]
        # A same-key regression permanently poisons only its own namespace;
        # truncation leaves context but cannot become a query.
        for row in data:self.assert_same(numerical,census,row)
        self.assertEqual(len(census.poisoned),1)
        self.assertFalse(census.query_reason=='POISONED_PREFIX')

    def test_missing_header_taint_and_genuine_idle_reset_parity(self):
        numerical=edge.frozen.Contexts('test',{edge.OWNER},self.api)
        census=edge.eligibility_context('test',self.api)
        damaged=packet(2,101);del damaged['tcp.window_size_value']
        for row in [packet(1,100),damaged,packet(3,102),packet(4,200)]:
            self.assert_same(numerical,census,row)
        self.assertTrue(census.query_allowed)
        self.assertEqual(census.reasons['MISSING_HEADER_TAINT_RESET'],1)

    def test_missing_namespace_is_hard_failure_not_port_zero(self):
        bad=packet(1,100);del bad['tcp.dstport']
        for cls in [edge.frozen.Contexts('t',{edge.OWNER},self.api),edge.eligibility_context('t',self.api)]:
            with self.assertRaisesRegex(RuntimeError,'MISSING_NAMESPACE_HEADERS'):cls.append(bad)

    def test_cross_key_capture_regression_does_not_poison(self):
        a=edge.frozen.Contexts('t',{edge.OWNER},self.api)
        b=edge.eligibility_context('t',self.api)
        for row in [packet(1,102),packet(2,101,sport='54321'),packet(3,103)]:
            self.assert_same(a,b,row)
        self.assertFalse(a.poisoned)
        self.assertEqual(a.reasons['CAPTURE_REGRESSION_CROSS_KEY'],1)

    def test_offset_physical_frames_preserve_numerical_values(self):
        left=edge.frozen.Contexts('t',{edge.OWNER},self.api)
        right=edge.frozen.Contexts('t',{edge.OWNER},self.api);right.frame=99
        for n in range(1,5):
            _,lns,_=left.append(packet(n,100+n))
            _,rns,_=right.append(packet(n+99,100+n))
        lf,ls,lp=left.states[lns].snapshot();rf,rs,rp=right.states[rns].snapshot()
        self.assertEqual(lf,rf);self.assertEqual(ls,rs)
        self.assertEqual(lp['query_time_ns'],rp['query_time_ns'])
        self.assertEqual(rp['query_frame'],lp['query_frame']+99)
        self.assertEqual([f+99 for b in lp['bursts'] for f in b['frames']],
                         [f for b in rp['bursts'] for f in b['frames']])

    def test_segment_boundary_clears_poison_without_reordering(self):
        old=edge.eligibility_context('seg1',self.api)
        old.append(packet(1,102));old.append(packet(2,101))
        self.assertTrue(old.poisoned)
        new=edge.eligibility_context('seg2',self.api,first_frame=3)
        new.append(packet(3,1000))
        self.assertTrue(new.query_allowed);self.assertFalse(new.poisoned)
        self.assertEqual(new.frame,3)

    def test_attack_direction_and_real_udp_port_zero(self):
        value=edge.card()
        ts=value['labels']['HTTP']['captured_interval_ns'][0]
        row=packet(1,ts/1e9,dport='80')
        self.assertEqual(edge.label_role('HTTP',row,ts,value),(3,1))
        row['ip.src']='216.58.198.74';row['tcp.dstport']='42162'
        self.assertEqual(edge.label_role('HTTP',row,ts,value),(0,None))
        uts=value['labels']['UDP']['captured_interval_ns'][0]
        row.update({'ip.proto':'17','udp.dstport':'0','ip.src':'10.200.3.4'})
        self.assertEqual(edge.label_role('UDP',row,uts,value),(4,1))

    def test_eligibility_sink_cannot_generate_feature(self):
        with self.assertRaisesRegex(RuntimeError,'CANNOT_EMIT'):
            edge.EligibilityOnlyStore()['anything'].snapshot()

    def test_reference_physical_uid_remains_full_view_prebank_query(self):
        from constrained_onboarding_reference_v2 import reference_descriptor
        value=edge.card();ctx=edge.frozen.Contexts('EDGE_NORMAL_SEGMENT_1',{edge.OWNER},self.api)
        now=str(Decimal(value['reference']['t0_ns'])/Decimal(edge.frozen.NS))
        raw=packet(1,now);owner,ns,event=ctx.append(raw)
        row=edge.reference_row(edge.metadata('NORMAL',raw,ctx,ns,event,0,value),value)
        flow,state,provenance=ctx.states[ns].snapshot()
        body=dict(flow=flow,state=state,provenance=provenance,source_sha256=row['source_sha256'])
        q14,_=reference_descriptor(body,row)
        query=edge.prebank_query_for_reference(dict(uid=row['uid'],row=row,body=body))
        self.assertEqual(query['uid'],row['uid'])
        self.assertEqual(query['q14'],q14.tolist())
        self.assertEqual(query['row']['use'],'QUERY')
        self.assertEqual(query['required_support'],0.0)
        self.assertIs(query['body'],body)

    def test_selected_replay_rejects_tampered_raw_before_decoding(self):
        value=edge.card()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'modified.pcap';path.write_bytes(b'altered source')
            value['raw_inputs']['NORMAL']=dict(path=str(path),bytes=path.stat().st_size,sha256='0'*64)
            with self.assertRaisesRegex(RuntimeError,'RAW_SNAPSHOT_REPLAY_INPUT_PIN'):
                list(edge.selected_snapshots('NORMAL',[1],Path(folder)/'new',value=value))
            self.assertFalse((Path(folder)/'new').exists())


if __name__=='__main__':unittest.main()
