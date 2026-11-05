"""Independent stdlib PCAP/Ethernet/IPv4/UDP audit, no production decoder import."""
import collections,gzip,hashlib,json,os,struct,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(name,v):
    p=HERE/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def packets(path):
    with Path(path).open('rb') as f:
        head=f.read(24);assert head[:4]==bytes.fromhex('d4c3b2a1')
        assert struct.unpack_from('<I',head,20)[0]==1,'ETHERNET_LINKTYPE'
        n=0
        while h:=f.read(16):
            assert len(h)==16
            sec,usec,cap,wire=struct.unpack('<IIII',h);b=f.read(cap);assert len(b)==cap;n+=1
            out=None
            if len(b)>=34 and b[12:14]==b'\x08\x00':
                off=14;ihl=(b[off]&15)*4;assert b[off]>>4==4 and ihl>=20
                total=struct.unpack_from('!H',b,off+2)[0];frag=struct.unpack_from('!H',b,off+6)[0]
                if b[off+9]==17 and not frag&0x1fff and len(b)>=off+ihl+8:
                    src,dst=b[off+12:off+16],b[off+16:off+20]
                    sport,dport,length=struct.unpack_from('!HHH',b,off+ihl)
                    key=tuple(sorted(((src.hex(),sport),(dst.hex(),dport))))
                    out=dict(key=key,src=src.hex(),dst=dst.hex(),sport=sport,dport=dport,
                             time_ns=(sec*1000000+usec)*1000,mac_dst=b[:6].hex(),mac_src=b[6:12].hex(),
                             header=[ihl,b[off+1],total,frag>>13,b[off+8],length],fragmented=bool(frag&0x3fff),
                             truncated=cap<wire or len(b)<off+total,payload_bytes=max(0,length-8))
            yield n,out
def main():
    started=time.monotonic()
    import psutil
    proc=psutil.Process();proc.cpu_affinity([proc.cpu_affinity()[0]])
    card=read(ROOT/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json');spec=card['raw_inputs']['UDP'];path=Path(spec['path'])
    assert path.stat().st_size==spec['bytes'] and sha(path)==spec['sha256']
    sealbase=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=read(sealbase/'QUERY_SELECTION_SEAL.json')['roles']['UDP']
    selected_path=sealbase/seal['selected_file'];assert sha(selected_path)==seal['selected_sha256']
    with gzip.open(selected_path,'rt') as f:rows=[json.loads(x) for x in f]
    targets={r['frame']:r for r in rows};actual={}
    for frame,packet in packets(path):
        if frame in targets:
            assert packet is not None
            row=targets[frame];assert packet['time_ns']==row['timestamp_ns']
            assert packet['dst']=='c0a80080' and packet['dport']==0 and packet['mac_dst']=='dca632fb69b5'
            assert not packet['truncated'] and not packet['fragmented']
            actual[frame]=packet
        if frame%100000==0:write('RAW_PROGRESS.json',dict(stage='INDEPENDENT_RAW_PASS_1',done=frame,total=spec['records']))
    assert frame==spec['records'] and len(actual)==20000
    keys={p['key'] for p in actual.values()};counts=collections.Counter();first={};at_query={};last_time={};reversed_owner=0
    for frame,packet in packets(path):
        if packet and packet['key'] in keys and 'dca632fb69b5' in (packet['mac_src'],packet['mac_dst']):
            key=packet['key'];counts[key]+=1;first.setdefault(key,frame)
            if key in last_time:assert packet['time_ns']>=last_time[key]
            last_time[key]=packet['time_ns']
            if frame in targets:at_query[frame]=counts[key]
        if frame%100000==0:write('RAW_PROGRESS.json',dict(stage='INDEPENDENT_RAW_PASS_2',done=frame,total=spec['records']))
    assert len(at_query)==20000
    headers=collections.Counter(tuple(p['header']) for p in actual.values())
    summary=dict(status='PASS',scope='Independent full raw UDP file scan, fixed 20000 selected queries, no production parser/context used',
                 raw_sha256=spec['sha256'],selected_sha256=seal['selected_sha256'],raw_frames=frame,queries=len(rows),
                 distinct_selected_keys=len(keys),distinct_selected_src_ips=len({p['src'] for p in actual.values()}),
                 query_prefix_packet_counts=dict(collections.Counter(at_query.values())),
                 selected_keys_full_capture_packet_counts=dict(collections.Counter(counts[k] for k in keys)),
                 query_is_first_key_frame=sum(first[p['key']]==f for f,p in actual.items()),
                 header_counts={str(k):v for k,v in headers.items()},payload_bytes=dict(collections.Counter(p['payload_bytes'] for p in actual.values())),
                 seconds=time.monotonic()-started,source_writes=0,limitations='Independent raw semantics; saved snapshot/encoder parity is checked separately.')
    write('RAW_UDP_RESULT.json',summary)
    write('RAW_PROGRESS.json',dict(stage='PASS',done=20000,total=20000))
    print(json.dumps(summary))
if __name__=='__main__':
    try:main()
    except Exception as e:write('RAW_STOP.json',dict(status='FAIL',error=repr(e)));raise
