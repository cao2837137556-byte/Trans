"""Retrieve the one-time evidence bundle through an existing SSH SOCKS tunnel."""
import hashlib
import http.client
import json
from pathlib import Path
import socket
import struct
import tarfile

HERE = Path(__file__).resolve().parent


def exact(sock, count):
    result=b''
    while len(result)<count:
        part=sock.recv(count-len(result))
        if not part:raise ConnectionError('incomplete SOCKS response')
        result+=part
    return result


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(4*1024**2),b''):h.update(part)
    return h.hexdigest()


def main():
    config=json.loads((HERE/'.private/transfer.json').read_text())
    assert not (HERE/'retrieved').exists(), 'refuse overwrite existing retrieved evidence'
    sock=None
    failures=[]
    for port in config['socks_candidates']:
        try:
            sock=socket.create_connection(('127.0.0.1',port),timeout=8)
            sock.sendall(b'\x05\x01\x00');assert exact(sock,2)==b'\x05\x00'
            sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01'+struct.pack('!H',config['port']))
            rep=exact(sock,4);assert rep[:3]==b'\x05\x00\x00'
            exact(sock,4 if rep[3]==1 else 16 if rep[3]==4 else exact(sock,1)[0]);exact(sock,2)
            break
        except (OSError,AssertionError) as exc:
            failures.append(dict(port=port,error=type(exc).__name__))
            if sock:sock.close()
            sock=None
    if sock is None:raise RuntimeError('Export not reachable: '+str(failures))
    sock.settimeout(60)
    conn=http.client.HTTPConnection('127.0.0.1',config['port'],timeout=60)
    conn.sock=sock
    conn.request('GET','/'+config['token']+'/bundle.tar',headers={'Connection':'close'})
    response=conn.getresponse()
    assert response.status==200, 'export HTTP status '+str(response.status)
    size=int(response.getheader('Content-Length'))
    expected=response.getheader('X-Content-SHA256')
    assert 0<size<256*1024**2 and len(expected)==64
    part=HERE/'bundle.tar.part'
    total=0
    with part.open('xb') as stream:
        while True:
            data=response.read(4*1024**2)
            if not data:break
            total+=len(data);assert total<=size
            stream.write(data)
            print('D2_TRANSFER '+str(total)+'/'+str(size),flush=True)
    conn.close()
    assert total==size and sha(part)==expected, 'bundle SHA/size mismatch'
    final=HERE/'bundle.tar';part.rename(final)
    with tarfile.open(final) as archive:
        members=archive.getmembers()
        inventory=json.load(archive.extractfile('REMOTE_TRACE_INVENTORY.json'))
        selected={r['path']:r for r in inventory['files'] if r['transfer']}
        assert len(members)==len(selected)+1
        assert {m.name for m in members}==set(selected)|{'REMOTE_TRACE_INVENTORY.json'}
        output=HERE/'retrieved';output.mkdir()
        for member in members:
            path=(output/member.name).resolve()
            assert member.isfile() and path.is_relative_to(output.resolve())
            path.parent.mkdir(parents=True,exist_ok=True)
            with archive.extractfile(member) as source,path.open('xb') as dest:
                while True:
                    data=source.read(4*1024**2)
                    if not data:break
                    dest.write(data)
            if member.name in selected:
                pin=selected[member.name]
                assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256']
    (HERE/'RETRIEVAL_RECEIPT.json').write_text(json.dumps(dict(status='ALL_REMOTE_PINS_VERIFIED',
         bytes=size,bundle_sha256=expected,socks_port=port,files=len(selected),
         model_forwards=0,distances=0),indent=2)+'\n',encoding='utf-8')
    print('ALL_REMOTE_PINS_VERIFIED',flush=True)


if __name__=='__main__':main()
