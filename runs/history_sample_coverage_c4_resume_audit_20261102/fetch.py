import sys,http.client,json,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'history_sample_coverage_c4_preflight_repair_20261102'))
import client
cfg=json.loads((HERE/'.private/connection.json').read_text())
original=client.struct.pack
def connect():
    import socket
    s=socket.create_connection(('127.0.0.1',cfg['socks_port']),timeout=15)
    s.sendall(b'\x05\x01\x00');assert client.exact(s,2)==b'\x05\x00'
    s.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01'+struct.pack('!H',18814))
    r=client.exact(s,4);assert r[:3]==b'\x05\x00\x00'
    client.exact(s,4 if r[3]==1 else 16 if r[3]==4 else client.exact(s,1)[0]);client.exact(s,2);return s
c=http.client.HTTPConnection('127.0.0.1',18814,timeout=30);c.sock=connect()
c.request('GET','/'+cfg['token']+'/report');r=c.getresponse();assert r.status==200
b=r.read();c.close();(HERE/'REMOTE_REPORT.json').write_bytes(b)
v=json.loads(b)
for name in ('workers/NETATMO_prepare.json','workers/NETATMO_encode.json'):
    record=v['files'][name];q=json.loads(record['text'])
    print(json.dumps(dict(file=name,mtime_ns=record['mtime_ns'],status=q),ensure_ascii=False))
print(json.dumps(dict(encoded_files=[x for x in v['member_inventory'] if '/encoded/' in x['name']])))
