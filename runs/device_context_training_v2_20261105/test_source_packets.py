"""Independent dpkt packet bytes/time parity and corrupted-block rejection."""
import itertools,json,struct,tempfile
from pathlib import Path
import dpkt
from source_packets import pcapng_records,decode
from source_admission import write
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
 counts={};samples=[]
 base=ROOT/'runs/legacy_commissioning_unsw_raw_v1_20260926/acquisition/raw'
 for name in ['unsw-benign-20180528.pcap','unsw-mixed-20180601.pcap']:
  path=base/name;checks=eligible=0
  with path.open('rb') as f:
   for (frame,ns,b),(ts,reference) in itertools.islice(zip(pcapng_records(path),dpkt.pcapng.Reader(f)),10000):
    assert b==reference and abs(ns/1e9-ts)<1e-6;checks+=1;p,reason=decode(b)
    if p:
     ip=dpkt.ethernet.Ethernet(b).data;assert p[:6]==(ip.p,ip.len,int.from_bytes(ip.src,'big'),int.from_bytes(ip.dst,'big'),ip.data.sport,ip.data.dport);eligible+=1
    if len(samples)<2:samples.append((ns,b))
  counts[name]=dict(raw_records=checks,eligible_headers=eligible)
 def block(kind,body,endian='<'):
  n=12+len(body);return struct.pack(endian+'II',kind,n)+body+struct.pack(endian+'I',n)
 tested=0
 with tempfile.TemporaryDirectory(dir=HERE/'.private') as folder:
  for endian in ['<','>']:
   sh=block(0x0a0d0d0a,struct.pack(endian+'IHHq',0x1a2b3c4d,1,0,-1),endian)
   for resolution,denom in [(6,10**6),(9,10**9),(128+10,2**10)]:
    opts=struct.pack(endian+'HH',9,1)+bytes([resolution])+b'\0'*3+struct.pack(endian+'HHq',14,8,2)+b'\0'*4;idb=block(1,struct.pack(endian+'HHI',1,0,65535)+opts,endian);ns,b=samples[0];ticks=17*denom
    epb=block(6,struct.pack(endian+'IIIII',0,ticks>>32,ticks&0xffffffff,len(b),len(b))+b+b'\0'*((-len(b))%4),endian);path=Path(folder)/'test.pcapng';path.write_bytes(sh+idb+epb);assert list(pcapng_records(path))==[(1,19*10**9,b)];tested+=1
    path.write_bytes(sh+idb+epb[:-1])
    try:list(pcapng_records(path))
    except AssertionError:pass
    else:raise AssertionError('TRUNCATION_NOT_REJECTED')
 result=dict(status='PASS',existing_raw_prefixes=counts,synthetic_endian_resolution_offset_cases=tested,truncated_blocks_rejected=tested,scope='Container adapter only; IPv6/fragments remain explicit unsupported-query STOP')
 write('LOCAL_PACKET_READER_REGRESSION.json',result);print(json.dumps(result))
if __name__=='__main__':main()
