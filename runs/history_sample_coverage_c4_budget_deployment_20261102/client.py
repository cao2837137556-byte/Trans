"""Code-only resumable transfer over the user's existing authenticated tunnel."""
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import socket
import struct
import tarfile
import time

from controller import PORT,MAX_RESULT,MAX_CHUNK,sha,read,write,need,safe_name

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent/'history_sample_coverage_c4_batch_resume_v1_20261102'


def exact(sock,count):
    result=b''
    while len(result)<count:
        chunk=sock.recv(count-len(result))
        if not chunk:raise ConnectionError('SOCKS_CLOSED')
        result+=chunk
    return result


def connect(port,timeout):
    sock=socket.create_connection(('127.0.0.1',port),timeout=timeout)
    try:
        sock.sendall(b'\x05\x01\x00');need(exact(sock,2)==b'\x05\x00','SOCKS_AUTH')
        sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01'+struct.pack('!H',PORT))
        reply=exact(sock,4);need(reply[:3]==b'\x05\x00\x00','SOCKS_CONNECT')
        need(reply[3] in (1,3,4),'SOCKS_ADDRESS_TYPE')
        exact(sock,4 if reply[3]==1 else 16 if reply[3]==4 else exact(sock,1)[0]);exact(sock,2)
        return sock
    except BaseException:sock.close();raise


def request(route,body=b'',headers=None,*,timeout=30):
    cfg=read(HERE/'.private/connection.json');timeout=max(.1,min(float(timeout),900))
    connection=http.client.HTTPConnection('127.0.0.1',PORT,timeout=timeout)
    connection.sock=connect(cfg['socks_port'],timeout);connection.sock.settimeout(timeout)
    connection._transfer_socket=connection.sock
    try:
        connection.request('GET' if route in ('state','result') else 'POST','/'+cfg['token']+'/'+route,body=body,headers=headers or {})
        response=connection.getresponse()
        if response.status not in ((200,206) if route=='result' else (200,)):
            raise ValueError('REMOTE_ACTION_FAILED:'+response.read().decode('utf-8',errors='replace'))
        if route=='result':return connection,response
        value=json.loads(response.read());connection.close();return value
    except BaseException:connection.close();raise


def upload(progress=lambda *args,**kwargs:None):
    manifest=read(HERE/'DELIVERY_MANIFEST.json');spec=manifest['bundle'];path=HERE/'bundle.tar'
    need(path.stat().st_size==spec['bytes'] and sha(path)==spec['sha256'],'LOCAL_CODE_BUNDLE_PIN')
    current=request('state')['transfers']['code'];started=time.monotonic();initial=current['offset'];failures=0
    with path.open('rb') as stream:
        while not current['complete']:
            offset=current['offset'];need(0<=offset<spec['bytes'],'UPLOAD_OFFSET')
            stream.seek(offset);payload=stream.read(min(MAX_CHUNK,spec['bytes']-offset))
            try:
                current=request('upload/code',payload,{'X-Offset':str(offset),'X-Chunk-SHA256':hashlib.sha256(payload).hexdigest()},timeout=60)
                failures=0
            except (OSError,http.client.HTTPException):
                failures+=1;need(failures<=3,'CODE_TRANSFER_RETRY_LIMIT');current=request('state')['transfers']['code']
            progress('UPLOADING',file='bundle.tar',done_bytes=current['offset'],total_bytes=spec['bytes'],
                bytes_per_second=(current['offset']-initial)/max(.001,time.monotonic()-started),code_only=True)
    return current


def safe_members(archive,target):
    members=archive.getmembers();names=[m.name for m in members]
    need(len(names)==len(set(names)),'RESULT_DUPLICATES')
    for member in members:
        safe_name(member.name);need(member.isfile(),'RESULT_REGULAR_FILES_ONLY')
        need((target/member.name).resolve().is_relative_to(target.resolve()),'RESULT_SCOPE')
        need(Path(member.name).suffix.lower() not in ('.pcap','.pcapng','.sqlite'),'RESULT_NO_RAW_OR_SQLITE')
    need(sum(m.size for m in members)<MAX_RESULT,'RESULT_EXPANSION_LIMIT')
    return members


def retrieve(progress=lambda *args,**kwargs:None,*,budget=None):
    target=PACKAGE/'retrieved';need(not target.exists(),'RETRIEVAL_ONCE')
    path=HERE/'result.tar';part=HERE/'result.part';metadata_path=HERE/'RESULT_TRANSFER_META.json'
    need(not path.exists(),'RESULT_ALREADY_SAVED');attempt=0
    def remaining():
        value=budget() if budget is not None else 900
        return 900 if value is None else value
    while True:
        need(remaining()>0,'RETRIEVAL_WALL_BUDGET')
        metadata=read(metadata_path) if metadata_path.exists() else None
        offset=part.stat().st_size if part.exists() else 0
        if metadata and offset==metadata['bytes']:
            need(sha(part)==metadata['sha256'],'RETAINED_RESULT_PIN');break
        connection=None
        try:
            connection,response=request('result',headers={'Range':f'bytes={offset}-'} if offset else None,timeout=min(30,remaining()))
            size=int(response.getheader('X-Content-Total-Bytes'));expected=response.getheader('X-Content-SHA256')
            need(0<size<MAX_RESULT and int(response.getheader('Content-Length'))==size-offset,'RESULT_RESPONSE_SIZE')
            if offset:need(response.status==206 and response.getheader('Content-Range')==f'bytes {offset}-{size-1}/{size}','RESULT_RANGE_BINDING')
            need(shutil.disk_usage(PACKAGE).free>=max(2**30,2*size+256*2**20),'LOCAL_RESULT_DISK_HEADROOM')
            current=dict(bytes=size,sha256=expected)
            need(metadata is None or metadata==current,'RESUMED_RESULT_IDENTITY');write(metadata_path,current);metadata=current
            with part.open('xb' if offset==0 else 'ab') as stream:
                while offset<size:
                    need(remaining()>0,'RETRIEVAL_WALL_BUDGET')
                    connection._transfer_socket.settimeout(max(.1,min(30,remaining())))
                    payload=response.read(min(4*2**20,size-offset))
                    if not payload:raise ConnectionError('RESULT_EARLY_EOF')
                    stream.write(payload);offset+=len(payload)
                    progress('RETRIEVING',done_bytes=offset,total_bytes=size)
            connection.close();connection=None;need(sha(part)==expected,'RESULT_TRANSFER_PIN');break
        except (OSError,http.client.HTTPException):
            attempt+=1;need(attempt<=3,'RESULT_TRANSFER_RETRY_LIMIT')
        finally:
            if connection is not None:connection.close()
    need(remaining()>0,'RETRIEVAL_WALL_BUDGET');part.rename(path)
    with tarfile.open(path,'r:') as archive:
        members=safe_members(archive,target);target.mkdir(exist_ok=False)
        for member in members:
            need(remaining()>0,'RETRIEVAL_WALL_BUDGET');destination=target/member.name;destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as stream:
                src=archive.extractfile(member)
                for payload in iter(lambda:src.read(4*2**20),b''):stream.write(payload)
    receipt=read(target/'STAGE_RECEIPT.json');need(receipt.get('technical_status')=='COMPLETED','RETRIEVED_COMPLETE_STAGE')
    for name,digest in receipt['outputs'].items():
        safe_name(name);need(sha(target/name)==digest,'RETRIEVED_OUTPUT_PIN:'+name)
    need(read(target/'RESULT.json')['execution_card_sha256']==sha(PACKAGE/'EXECUTION_CARD.json'),'RETRIEVED_CARD_PIN')
    write(HERE/'RETRIEVAL_RECEIPT.json',dict(status='RETRIEVED',**metadata,files=len(members),all_stage_outputs_verified=True))
    return target
