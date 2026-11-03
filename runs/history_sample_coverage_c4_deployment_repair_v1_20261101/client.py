"""Chunked, resumable transfer via the user's existing authenticated SSH tunnel."""
import hashlib
import http.client
import json
from pathlib import Path
import socket
import struct
import tarfile
import time
from receiver import sha,read,write,need

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent/'history_sample_coverage_c4_execution_v1_20261101'

def exact(sock,n):
    b=b''
    while len(b)<n:
        p=sock.recv(n-len(b))
        if not p:raise ConnectionError('SOCKS closed')
        b+=p
    return b

def connect(port):
    s=socket.create_connection(('127.0.0.1',port),timeout=15)
    s.sendall(b'\x05\x01\x00');need(exact(s,2)==b'\x05\x00','SOCKS_AUTH')
    s.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01'+struct.pack('!H',18798))
    r=exact(s,4);need(r[:3]==b'\x05\x00\x00','SOCKS_CONNECT')
    exact(s,4 if r[3]==1 else 16 if r[3]==4 else exact(s,1)[0]);exact(s,2)
    return s

def request(route,body=b'',headers=None):
    cfg=read(HERE/'.private/connection.json')
    conn=http.client.HTTPConnection('127.0.0.1',18798,timeout=900)
    conn.sock=connect(cfg['socks_port']);conn.sock.settimeout(900)
    method='GET' if route in ('state','result') else 'POST'
    conn.request(method,'/'+cfg['token']+'/'+route,body=body,headers=headers or {})
    response=conn.getresponse()
    if response.status!=200:
        error=response.read().decode('utf-8',errors='replace');conn.close();raise RuntimeError(error)
    if route=='result':return conn,response
    value=json.loads(response.read());conn.close();return value

def upload(progress):
    manifest=read(HERE/'DELIVERY_MANIFEST.json');items=[dict(local_path=str(HERE/'bundle.tar'),**manifest['bundle']),*manifest['assets']]
    total=sum(i['bytes'] for i in items);started=time.monotonic();initial=None
    state=request('state');remaining=total-sum(v['offset'] for v in state['transfers'].values())
    need(state['free_bytes']>remaining+10*2**30,'REMOTE_TRANSFER_AND_SCRATCH_HEADROOM')
    for index,item in zip(['code','0','1','2'],items):
        p=Path(item['local_path']);need(p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],'LOCAL_TRANSFER_PIN')
        remote=request('state')['transfers'];current=remote[index]
        if initial is None:initial=sum(v['offset'] for v in remote.values())
        if current['complete']:continue
        offset=current['offset'];need(0<=offset<item['bytes'],'RESUME_OFFSET')
        with p.open('rb') as f:
            while offset<item['bytes']:
                f.seek(offset);data=f.read(min(16*2**20,item['bytes']-offset))
                try:
                    result=request('upload/'+index,data,{'X-Offset':str(offset),'X-Chunk-SHA256':hashlib.sha256(data).hexdigest()})
                    offset=result['offset']
                except (OSError,http.client.HTTPException):
                    # Transfer retry cannot repeat science or submission.
                    remote=request('state')['transfers'];offset=remote[index]['offset']
                remote[index]['offset']=offset
                done=sum(v['offset'] for v in remote.values());elapsed=time.monotonic()-started
                progress('UPLOADING',file=p.name,done_bytes=done,total_bytes=total,bytes_per_second=(done-initial)/max(elapsed,.001))
    return request('state')

def safe_members(archive,target):
    members=archive.getmembers();names=[m.name for m in members]
    need(len(names)==len(set(names)),'RESULT_DUPLICATES')
    for m in members:
        p=Path(m.name)
        need(m.isfile() and not p.is_absolute() and '..' not in p.parts and '\\' not in m.name and ':' not in m.name,'RESULT_PATH')
        need((target/p).resolve().is_relative_to(target.resolve()),'RESULT_SCOPE')
    need(sum(m.size for m in members)<2*2**30,'RESULT_EXPANSION')
    return members

def retrieve():
    target=PACKAGE/'retrieved';need(not target.exists(),'RETRIEVAL_ONCE')
    archive_path=HERE/'result.tar';need(not archive_path.exists(),'RESULT_ALREADY_SAVED')
    conn,response=request('result');expected=response.getheader('X-Content-SHA256')
    size=int(response.getheader('Content-Length'));need(0<size<2*2**30,'RESULT_SIZE')
    h=hashlib.sha256();count=0
    with archive_path.with_suffix('.part').open('xb') as f:
        while True:
            b=response.read(4*2**20)
            if not b:break
            count+=len(b);need(count<=size,'RESPONSE_TOO_LARGE');h.update(b);f.write(b)
    conn.close();need(count==size and h.hexdigest()==expected,'RESULT_TRANSFER_PIN')
    archive_path.with_suffix('.part').rename(archive_path)
    with tarfile.open(archive_path,'r:') as ar:
        members=safe_members(ar,target);target.mkdir()
        for m in members:
            p=target/m.name;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:
                src=ar.extractfile(m)
                for b in iter(lambda:src.read(4*2**20),b''):f.write(b)
    write(HERE/'RETRIEVAL_RECEIPT.json',dict(status='RETRIEVED',sha256=expected,bytes=count,files=len(members)))
    return target

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('action',choices=['state','install','preflight','submit','result']);args=a.parse_args()
    print(json.dumps(str(retrieve()) if args.action=='result' else request(args.action),ensure_ascii=False))
