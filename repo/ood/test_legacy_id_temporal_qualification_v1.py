"""Synthetic identity, chronology and literal decoder checks; no real assets."""
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import dpkt

import legacy_id_temporal_qualification_v1 as q


def packet(frame, timestamp, key, first=None, eligible=True):
    return {'frame_number_1based':frame, 'position_zero_based':frame-1,
            'timestamp':timestamp,'old_key':key,
            'session_key_sha256':None if key is None else q.digest(repr(key).encode()),
            'legacy_prefix_regressed':False,'legacy_input_eligible':eligible,
            'session_first_frame':first if first is not None else frame}


class QualificationTests(unittest.TestCase):
    def test_semantic_time_and_actual_cache_are_separate_exposures(self):
        a=(6,('a',1),('b',2)); b=(6,('a',3),('b',2)); c=(6,('a',4),('b',2))
        packets=[packet(1,10.0,a),packet(2,11.0,b),packet(3,12.0,a,1),packet(4,13.0,c)]
        rows=[{'uid':'u','role':'aux_fit','plan_scope':'FIT_PROBE_ONLY','source_group':'source',
               'target_event_position_within_capture':'0.0','feature_available_time_epoch':'11.0','recorded_index':'9999'}]
        cache={'u':{'event_position':'0','timestamp_epoch':'10.0',
                    'session_id':q.digest(repr(('source','member',a)).encode())}}
        mapped,exposed,cut,time=q.map_exposure(rows,cache,packets,'member')
        self.assertFalse(mapped[0]['same_actual_and_semantic_frame'])
        self.assertEqual((cut,time),(2,11.0))
        selected,reasons=q.qualify(packets,exposed,cut,time)
        self.assertEqual([r['frame_number_1based'] for r in selected],[4])
        self.assertEqual(reasons['later_session_shared_with_fit_select'],1)
        cache['u']['timestamp_epoch']='9.0'
        with self.assertRaisesRegex(RuntimeError,'CACHED_TIME_RAW_MISMATCH'):
            q.map_exposure(rows,cache,packets,'member')

    def test_later_target_in_existing_unseen_session_is_not_new_session(self):
        key=(17,('a',1),('b',2))
        rows=[packet(1,10,key),packet(2,20,key,1),packet(3,30,(17,('a',3),('b',2)),eligible=False)]
        selected,reasons=q.qualify(rows,set(),1,10)
        self.assertEqual(selected,[])
        self.assertEqual(reasons,{'not_after_all_source_fit_select':1,'later_session_began_before_cutoff':1,'later_legacy_input_ineligible':1})

    def test_no_ipv6_protocol_fallback_is_added(self):
        api,_=q.runtime()
        event=api.event_from_tshark({'frame.number':'1','frame.time_epoch':'1.0','ipv6.src':'::1',
                                    'ipv6.dst':'::2','ipv6.nxt':'6','tcp.srcport':'1','tcp.dstport':'2'})
        self.assertIsNone(q.canonical(event))
        with self.assertRaisesRegex(RuntimeError,'NONINTEGER_POSITION'):
            q.integer('1.5')

    def test_real_decoder_synthetic_capture_and_timestamp_regression(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'synthetic.pcap'
            with path.open('wb') as f:
                writer=dpkt.pcap.Writer(f)
                for ts in [10.0,11.0,10.5]:
                    tcp=dpkt.tcp.TCP(sport=1234,dport=443,seq=1,ack=0,flags=dpkt.tcp.TH_SYN,win=8192)
                    tcp.off=5
                    ip=dpkt.ip.IP(src=b'\x0a\x00\x00\x01',dst=b'\x0a\x00\x00\x02',p=6,ttl=64,data=tcp)
                    ip.len=len(ip)
                    eth=dpkt.ethernet.Ethernet(src=b'\x01'*6,dst=b'\x02'*6,type=dpkt.ethernet.ETH_TYPE_IP,data=ip)
                    writer.writepkt(bytes(eth),ts=ts)
            records,link=q.record_inventory(path.read_bytes())
            api,fields=q.runtime()
            decoded=q.decode(path,api,fields,Path('C:/Program Files/Wireshark/tshark.exe'),Path(temp)/'stderr.log')
            self.assertEqual(len(records),len(decoded))
            self.assertEqual([r['timestamp'] for r in records],[r['timestamp'] for r in decoded])
            self.assertEqual([r['legacy_input_eligible'] for r in decoded],[True,True,False])
            self.assertTrue(decoded[-1]['legacy_prefix_regressed'])


if __name__=='__main__':
    unittest.main()
