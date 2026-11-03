"""Independent minimal IPv4 transport header count, raw qualification only."""
from pathlib import Path
from collections import Counter
import importlib.util
import json
import socket
import struct
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'runs/edge_iiotset_raw_qualification_v1_20261102'
spec = importlib.util.spec_from_file_location('edge_raw_reader', OLD / 'scan_raw.py')
raw = importlib.util.module_from_spec(spec); spec.loader.exec_module(raw)
TARGET = socket.inet_aton('192.168.0.128')
HTTP_SOURCE = socket.inet_aton('192.168.0.170')


def run(role):
    start = time.monotonic()
    old = json.loads((OLD / (role+'_AUDIT.json')).read_text(encoding='utf-8-sig'))
    path = Path(old['input']); stat = path.stat(); before = raw.sha(path)
    assert before == old['input_sha256']
    counts = Counter(); flags = Counter(); ports = Counter(); direct_strata = Counter()
    first = last = None
    for frame, (ns, p, caplen, wirelen, link, iface, snaplen) in enumerate(raw.RawRecords(path), 1):
        counts['all_capture_records'] += 1
        if link != 1: raise ValueError('expected qualified Ethernet linktype')
        if len(p)<14:raise ValueError('short Ethernet')
        if p[12:14] != b'\x08\x00':
            counts['non_IPv4'] += 1;continue
        off=14; ihl=(p[off]&15)*4
        if p[off]>>4 != 4 or ihl<20 or len(p)<off+ihl:raise ValueError('invalid IPv4')
        proto=p[off+9];src=p[off+12:off+16];dst=p[off+16:off+20]
        if dst!=TARGET:
            if src==TARGET:counts['outbound_from_target']+=1
            else:counts['neither_target']+=1
            continue
        counts['inbound_to_target']+=1
        fragment=struct.unpack('!H',p[off+6:off+8])[0]
        if fragment & 0x1fff:raise ValueError('unexpected noninitial fragment')
        trans=off+ihl
        if proto not in (6,17):
            counts['inbound_other_protocol']+=1;continue
        if len(p)<trans+(20 if proto==6 else 8):raise ValueError('short transport header')
        sport,dport=struct.unpack('!HH',p[trans:trans+4])
        ports[str(proto)+'|'+str(dport)]+=1
        if role=='UDP' and proto==17 and dport==0:
            counts['direct_rule_UDP_dst_target_dport0']+=1
        if role=='HTTP' and proto==6 and src==HTTP_SOURCE and dport==80:
            counts['direct_rule_HTTP_source_target_dport80']+=1
            f=p[trans+13];flags[str(f)]+=1
            if f&2 and not f&16:direct_strata['TCP_SYN_NO_ACK']+=1
            elif f&16 and not f&2:direct_strata['TCP_ACK_NO_SYN']+=1
            else:direct_strata['TCP_OTHER']+=1
            if f==16:counts['direct_HTTP_ACK_ONLY']+=1
            if f==24:counts['direct_HTTP_PSH_ACK']+=1
            if f&16 and not f&2:counts['direct_HTTP_ACK_NO_SYN']+=1
            first=ns if first is None else min(first,ns);last=ns if last is None else max(last,ns)
        if frame%100_000==0 and time.monotonic()-start>120:raise TimeoutError('120s raw attack header bound')
    assert counts['all_capture_records']==old['counts']['records']
    if role=='UDP':assert counts['direct_rule_UDP_dst_target_dport0']==2898830
    if role=='HTTP':assert counts['direct_HTTP_ACK_NO_SYN']==88262
    assert raw.sha(path)==before and path.stat().st_mtime_ns==stat.st_mtime_ns
    return {'input_sha256':before,'input_unchanged':True,'counts':dict(counts),'inbound_target_protocol_dport':dict(ports),
            'HTTP_direct_flags':dict(flags),'HTTP_direct_strata':dict(direct_strata),'HTTP_direct_first_ns':first,
            'HTTP_direct_last_ns':last,'elapsed_seconds':time.monotonic()-start,
            'limit':'Header/direction population is not certified per-packet malicious truth'}


if __name__=='__main__':
    out={role:run(role) for role in ('HTTP','UDP')}
    (OUT/'ATTACK_PORT_RESULT.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v['counts'] for k,v in out.items()}))
