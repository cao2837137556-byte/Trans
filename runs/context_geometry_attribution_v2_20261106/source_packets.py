"""PCAPNG container adapter, preserving the sealed IPv4 packet eligibility."""
import struct
from packet_reader import packets as classic_packets
SHB=b'\x0a\x0d\x0d\x0a'
def pcapng_records(path):
 with path.open('rb') as f:
  endian=None;interfaces=[];frame=0
  while head:=f.read(12):
   assert len(head)==12,'PCAPNG_HEADER_TRUNCATED'
   if head[:4]==SHB:
    endian={b'\x4d\x3c\x2b\x1a':'<',b'\x1a\x2b\x3c\x4d':'>'}.get(head[8:12]);interfaces=[]
   assert endian is not None,'PCAPNG_BYTE_ORDER';kind,n=struct.unpack(endian+'II',head[:8]);assert 12<=n<=64*1024**2 and n%4==0,'PCAPNG_BLOCK_SIZE'
   tail=f.read(n-12);assert len(tail)==n-12;block=head+tail;assert struct.unpack_from(endian+'I',block,n-4)[0]==n,'PCAPNG_TRAILER';body=block[8:-4]
   if kind==0x0a0d0d0a:
    assert len(body)>=16 and struct.unpack_from(endian+'H',body,4)[0]==1,'PCAPNG_VERSION'
   elif kind==1:
    assert len(body)>=8;link,reserved,snap=struct.unpack_from(endian+'HHI',body);denom=10**6;offset=0;j=8
    while j+4<=len(body):
     code,length=struct.unpack_from(endian+'HH',body,j);j+=4;assert j+length<=len(body);v=body[j:j+length];j+=(length+3)//4*4
     if code==0:assert length==0;break
     if code==9:assert length==1;exponent=v[0];denom=(2 if exponent&128 else 10)**(exponent&127)
     if code==14:assert length==8;offset=struct.unpack(endian+'q',v)[0]
    interfaces.append((link,snap,denom,offset))
   elif kind in [2,6]:
    assert len(body)>=20;iface=struct.unpack_from(endian+('H' if kind==2 else 'I'),body)[0];hi,lo,cap,wire=struct.unpack_from(endian+'IIII',body,4);assert iface<len(interfaces);link,snap,denom,offset=interfaces[iface];assert link==1,'UNSUPPORTED_LINKTYPE'
    assert cap<=wire and (not snap or cap<=snap) and len(body)>=20+(cap+3)//4*4,'PCAPNG_PACKET_LENGTH';ticks=(hi<<32)|lo;scaled=ticks*10**9;assert scaled%denom==0,'SUB_NANOSECOND_TIMESTAMP';tm=scaled//denom+offset*10**9;assert tm>=0;frame+=1
    yield frame,tm,body[20:20+cap]
   elif kind==3:raise ValueError('PACKET_WITHOUT_TIMESTAMP')
def decode(b):
 p=None;reason='NON_IPV4';off=14
 if len(b)>=14:
  eth=struct.unpack_from('!H',b,12)[0]
  while eth in (0x8100,0x88a8) and len(b)>=off+4:eth=struct.unpack_from('!H',b,off+2)[0];off+=4
  if eth==0x0800 and len(b)>=off+20:
   ihl=(b[off]&15)*4;total=struct.unpack_from('!H',b,off+2)[0];frag=struct.unpack_from('!H',b,off+6)[0];proto=b[off+9];reason='NON_TCP_UDP'
   if proto in (6,17):
    reason='FRAGMENT_OR_INCOMPLETE'
    if b[off]>>4==4 and ihl>=20 and total>=ihl+(20 if proto==6 else 8) and not frag&0x3fff and len(b)>=off+total:
     sport,dport=struct.unpack_from('!HH',b,off+ihl);src=int.from_bytes(b[off+12:off+16],'big');dst=int.from_bytes(b[off+16:off+20],'big');p=(proto,total,src,dst,sport,dport,b[:6].hex(),b[6:12].hex());reason='ELIGIBLE'
 return p,reason
def packets(path):
 with path.open('rb') as f:magic=f.read(4)
 if magic!=SHB:yield from classic_packets(path);return
 for frame,tm,b in pcapng_records(path):
  p,reason=decode(b);yield frame,tm,p,reason
