import http.client,json,socket,struct,sys
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'history_sample_coverage_c4_checkpoint_deployment_20261101'))
from client import exact
cfg=json.loads((HERE/'.private/probe_connection.json').read_text())
s=socket.create_connection(('127.0.0.1',cfg['socks_port']),timeout=15)
s.sendall(b'\x05\x01\x00');assert exact(s,2)==b'\x05\x00'
s.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01'+struct.pack('!H',18808))
r=exact(s,4);assert r[:3]==b'\x05\x00\x00'
exact(s,4 if r[3]==1 else 16 if r[3]==4 else exact(s,1)[0]);exact(s,2)
c=http.client.HTTPConnection('127.0.0.1',18808);c.sock=s
c.request('GET','/'+cfg['token']+'/probe');r=c.getresponse();assert r.status==200
b=r.read();c.close();(HERE/'HEADER_PROBE.json').write_bytes(b)
v=json.loads(b)
print(v.get('error') or dict(rows=len(v['rows']),flags={k:dict(Counter(r['row'][k] for r in v['rows'])) for k in ('tcp.flags.syn','tcp.flags.ack','tcp.flags.reset','tcp.flags.fin')},errors=dict(Counter(r['audit'].get('error','PASS') for r in v['rows'])),elapsed_seconds=v['elapsed_seconds']))
