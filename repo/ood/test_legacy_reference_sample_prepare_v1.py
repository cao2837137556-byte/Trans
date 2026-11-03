"""Leakage/label regressions and a real-decoder synthetic manifest integration."""
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import dpkt
import legacy_reference_sample_prepare_v1 as m

A='02:00:00:00:00:01'
B='02:00:00:00:00:02'
PEER='02:00:00:00:00:03'


def row(frame, ts, src_mac=PEER, dst_mac=A, proto=17, src='10.0.0.3',dst='10.0.0.1',sport=40000,dport=80):
    result={'frame.number':str(frame),'frame.time_epoch':str(ts),'frame.len':'80','frame.cap_len':'80',
        'eth.src':src_mac,'eth.dst':dst_mac,'ip.src':src,'ip.dst':dst,'ip.proto':str(proto),
        'ip.hdr_len':'20','ip.dsfield':'0','ip.len':'66','ip.flags':'0','ip.ttl':'64',
        'udp.srcport':str(sport),'udp.dstport':str(dport),'udp.length':'16','udp.stream':'0'}
    return result


class Samples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api,cls.prefix,_=m.old.legacy_runtime()

    def test_owner_isolation_and_ambiguous_packet(self):
        c=m.ScopedPrefixes('capture',[A,B],self.prefix)
        r1=row(1,1);_,key,ok=c.append(r1,self.api.event_from_tshark(r1));self.assertTrue(ok)
        r2=row(2,2,dst_mac=B);_,key2,ok=c.append(r2,self.api.event_from_tshark(r2));self.assertTrue(ok)
        self.assertNotEqual(key,key2)
        r3=row(3,3,src_mac=A,dst_mac=B);self.assertIsNone(c.append(r3,self.api.event_from_tshark(r3))[1])
        self.assertEqual(c.states[key].latest_timestamp,1)

    def test_dhcp_rejected_before_any_append(self):
        c=m.ScopedPrefixes('capture',[A,B],self.prefix)
        r=row(1,1,src_mac=A,dst_mac='ff:ff:ff:ff:ff:ff',src='0.0.0.0',dst='255.255.255.255',sport=68,dport=67)
        self.assertFalse(c.append(r,self.api.event_from_tshark(r))[2]);self.assertFalse(c.states)

    def test_poison_is_permanent_and_other_session_survives(self):
        c=m.ScopedPrefixes('capture',[A],self.prefix)
        for i,t in enumerate((2,1,3),1):
            r=row(i,t);valid=c.append(r,self.api.event_from_tshark(r))[2]
            self.assertEqual(valid,i==1)
        r=row(4,.5,sport=40001);self.assertTrue(c.append(r,self.api.event_from_tshark(r))[2])

    def test_snapshot_owned_and_metadata_cannot_embed(self):
        c=m.ScopedPrefixes('capture',[A],self.prefix,retain_full_rows=True)
        r=row(1,1);_,key,_=c.append(r,self.api.event_from_tshark(r))
        translator=SimpleNamespace(netfound_flow=lambda rows:{'fixture':[int(x['frame.number']) for x in rows]})
        first=c.snapshot(key,translator)
        r=row(2,2);c.append(r,self.api.event_from_tshark(r))
        self.assertEqual(first['fixture'],[1]);self.assertEqual(c.snapshot(key,translator)['fixture'],[1,2])
        empty=m.ScopedPrefixes('capture',[A],self.prefix)
        with self.assertRaisesRegex(RuntimeError,'Metadata-only'):empty.snapshot(key,translator)

    def test_label_direction_source_and_service(self):
        spec={'provenance':'attack','owner':A,'mode':'UDP'}
        r=row(1,1,src_mac=m.ATTACKER_MAC,src=m.ATTACKER_IP)
        self.assertEqual(m.label(spec,r,self.api.event_from_tshark(r),A)[0],1)
        for change in ({'eth.src':PEER},{'eth.dst':PEER},{'ip.src':'10.0.0.9'},{'udp.dstport':'53'}):
            bad=dict(r,**change);self.assertIsNone(m.label(spec,bad,self.api.event_from_tshark(bad),A)[0])
        spec['mode']='HTTP';self.assertIsNone(m.label(spec,r,self.api.event_from_tshark(r),A)[0])

    def test_selection_covers_endpoints(self):
        for n in (0,1,2,31,32,33,999):
            idx=m.even_indices(n)
            self.assertEqual(len(idx),min(n,32));self.assertEqual(len(idx),len(set(idx)))
            if n:self.assertEqual((idx[0],idx[-1]),(0,n-1))
        self.assertEqual(m.even_indices(900,1),[899])

    def test_real_decoder_to_uid_manifest(self):
        with tempfile.TemporaryDirectory(prefix='reference_manifest_fixture_') as tmp:
            out=Path(tmp);path=out/'fixture.pcap'
            transport=dpkt.udp.UDP(sport=40000,dport=80,data=b'fixture');transport.ulen=15
            ip=dpkt.ip.IP(src=bytes([10,0,0,3]),dst=bytes([10,0,0,1]),p=17,ttl=64,data=transport)
            packet=bytes(dpkt.ethernet.Ethernet(src=bytes.fromhex(PEER.replace(':','')),dst=bytes.fromhex(A.replace(':','')),type=2048,data=ip))
            with path.open('wb') as f:
                writer=dpkt.pcap.Writer(f)
                for t in (1.,2.,.5,3.):writer.writepkt(packet,ts=t)
            spec=dict(capture_id='fixture',path=str(path),bytes=path.stat().st_size,sha256=m.old.sha(path),skip_reason=None,
                mode='ACTIVE_UNANNOTATED',owner=None,provenance='normal',expected_packets=4,use='LATER_NORMAL_QUERY')
            devices=[dict(mac=A,device='fixture',proposed_partition='LEARN',reference_end=0)]
            receipt=m.scan_capture(spec,devices,out)
            self.assertEqual(receipt['selected'],2)
            self.assertEqual(receipt['context_reasons']['NEW_TIMESTAMP_REGRESSION'],1)
            with gzip.open(out/'fixture_targets.jsonl.gz','rt',encoding='utf8') as f:targets=[json.loads(x) for x in f]
            self.assertEqual([t['frame'] for t in targets],[1,2])
            self.assertTrue(all(t['label']==0 and t['packet_sha256'] for t in targets))


if __name__=='__main__':unittest.main(verbosity=2)
