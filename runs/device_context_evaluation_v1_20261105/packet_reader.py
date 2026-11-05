"""Pinned independent Ethernet/IPv4 raw reader reused from accepted diagnostic."""
import struct
def packets(path):
 """Raw Ethernet IPv4 TCP/UDP tuples; integer nanoseconds, no labels/scores."""
 with path.open('rb') as f:
  h=f.read(24);formats={b'\xd4\xc3\xb2\xa1':('<',1000),b'\xa1\xb2\xc3\xd4':('>',1000),b'\x4d\x3c\xb2\xa1':('<',1),b'\xa1\xb2\x3c\x4d':('>',1)}
  endian,mult=formats[h[:4]];assert struct.unpack_from(endian+'I',h,20)[0]==1
  frame=0
  while h:=f.read(16):
   assert len(h)==16;sec,sub,cap,wire=struct.unpack(endian+'IIII',h);b=f.read(cap);assert len(b)==cap;frame+=1;tm=sec*1000000000+sub*mult
   p=None;reason='NON_IPV4';off=14
   if len(b)>=14:
    eth=struct.unpack_from('!H',b,12)[0]
    while eth in (0x8100,0x88a8) and len(b)>=off+4:eth=struct.unpack_from('!H',b,off+2)[0];off+=4
    if eth==0x0800 and len(b)>=off+20:
     ihl=(b[off]&15)*4;total=struct.unpack_from('!H',b,off+2)[0];frag=struct.unpack_from('!H',b,off+6)[0];proto=b[off+9];reason='NON_TCP_UDP'
     if proto in (6,17):
      reason='FRAGMENT_OR_INCOMPLETE'
      if b[off]>>4==4 and ihl>=20 and total>=ihl+(20 if proto==6 else 8) and not frag&0x3fff and len(b)>=off+total:
       sport,dport=struct.unpack_from('!HH',b,off+ihl);src=int.from_bytes(b[off+12:off+16],'big');dst=int.from_bytes(b[off+16:off+20],'big')
       p=(proto,total,src,dst,sport,dport,b[:6].hex(),b[6:12].hex());reason='ELIGIBLE'
   yield frame,tm,p,reason
