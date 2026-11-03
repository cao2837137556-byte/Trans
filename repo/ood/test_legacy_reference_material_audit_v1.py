"""Small integration checks for raw-audit semantics, not scientific results."""
import json
from pathlib import Path

import dpkt
import legacy_reference_material_audit_v1 as audit


def ethernet(payload, src='020000000001', dst='020000000002', typ=dpkt.ethernet.ETH_TYPE_IP):
    return bytes(dpkt.ethernet.Ethernet(src=bytes.fromhex(src), dst=bytes.fromhex(dst), type=typ, data=payload))


def udp(reverse=False):
    transport = dpkt.udp.UDP(sport=40000 if not reverse else 5000, dport=5000 if not reverse else 40000, data=b'fixture')
    transport.ulen = 8 + len(transport.data)
    return dpkt.ip.IP(src=bytes([10,0,0,1 if not reverse else 2]), dst=bytes([10,0,0,2 if not reverse else 1]), p=17, ttl=64, data=transport)


def tcp(seq, flags, data=b''):
    segment = dpkt.tcp.TCP(sport=40000, dport=80, seq=seq, ack=1, flags=flags, win=1024, data=data)
    segment.off = 5
    return dpkt.ip.IP(src=bytes([10,0,0,1]), dst=bytes([10,0,0,2]), p=6, ttl=64, data=segment)


def write_capture(path, packets):
    with path.open('wb') as f:
        writer = dpkt.pcap.Writer(f)
        for timestamp, packet in packets:
            writer.writepkt(packet, ts=timestamp)


def main():
    output = audit.ROOT / 'runs/legacy_reference_material_audit_v1_20260916_synthetic'
    output.mkdir(exist_ok=False)
    runtime = audit.old.legacy_runtime()
    tshark = Path('C:/Program Files/Wireshark/tshark.exe')
    expected = '02:00:00:00:00:02'
    packet = ethernet(udp())
    normal = output / 'normal.pcap'
    write_capture(normal, [(1,packet),(1,packet),(2,ethernet(udp(True),src='020000000002',dst='020000000001')),
        (3,ethernet(udp(),src='020000000003',dst='020000000004')),
        (4,ethernet(dpkt.arp.ARP(sha=bytes.fromhex('020000000001'), spa=bytes([10,0,0,1]), tpa=bytes([10,0,0,2])), typ=dpkt.ethernet.ETH_TYPE_ARP))])
    common={'device_label':'fixture','proposed_device_partition':'SYNTHETIC','member_sha256':audit.source_hash(normal)}
    spec=dict(common,file_id=1,provenance='normal',member_path='3-Interactions/Fixture/A/normal.pcap')
    audit.analyze(spec,expected,normal,output,tshark,runtime)
    summary=json.loads((output/'001_summary.json').read_text(encoding='utf-8'))
    assert summary['counts']['packets']==5
    assert summary['counts']['legacy_valid']==4
    assert summary['counts']['candidate_targets']==3
    assert summary['independent']['counts']['byte_repeat_packets']==1
    spec=dict(common,file_id=2,provenance='attack',member_path='6-Attacks/1-Flood/Fixture/UDP/a.pcap')
    audit.analyze(spec,expected,normal,output,tshark,runtime)
    summary=json.loads((output/'002_summary.json').read_text(encoding='utf-8'))
    assert summary['counts']['candidate_targets']==2
    assert summary['counts'].get('normal_provenance_candidate',0)==0
    trace=output/'regression.pcap'
    write_capture(trace,[(1,ethernet(tcp(0,dpkt.tcp.TH_SYN))),
        (2,ethernet(tcp(1,dpkt.tcp.TH_ACK|dpkt.tcp.TH_PUSH,b'GET / HTTP/1.0\r\nHost: test.invalid\r\n\r\n'))),
        (3,ethernet(tcp(50,dpkt.tcp.TH_ACK))),
        (.5,ethernet(tcp(50,dpkt.tcp.TH_ACK))),
        (4,ethernet(tcp(50,dpkt.tcp.TH_ACK|dpkt.tcp.TH_PUSH,b'next')))])
    spec=dict(common,file_id=3,provenance='attack',member_path='6-Attacks/1-Flood/Fixture/TCP/a.pcap',member_sha256=audit.source_hash(trace))
    audit.analyze(spec,expected,trace,output,tshark,runtime)
    summary=json.loads((output/'003_summary.json').read_text(encoding='utf-8'))
    assert summary['counts']['candidate_targets']==2
    assert summary['counts']['session_regressions']==1
    assert summary['counts']['legacy_valid']==3
    spec=dict(spec,file_id=4,member_path='6-Attacks/1-Flood/Fixture/HTTP/a.pcap')
    audit.analyze(spec,expected,trace,output,tshark,runtime)
    summary=json.loads((output/'004_summary.json').read_text(encoding='utf-8'))
    assert summary['counts']['candidate_targets']==1
    audit.dump(output/'acceptance.json',{'status':'PASS','integration_cases':4,'behaviors':['Device-bound normal provenance excludes unrelated MAC and unsupported ARP','Independent record/byte and exact-byte repeat accounting','Flood direction excludes victim response/unrelated traffic','Past-valid targets survive later timestamp regression; current and future poisoned','HTTP request evidence excludes SYN/ACK; no blanket attack labels'],'script_sha256':audit.source_hash(Path(audit.__file__)),'training_calls':0})
    print('PASS: 4 integration cases; direction, identity, accounting, HTTP and causal regression semantics')


if __name__=='__main__':
    main()
