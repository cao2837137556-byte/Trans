"""Bounded read-only saved-input probe; no original PCAP replay or model execution."""
from pathlib import Path
from collections import Counter
import hashlib,json,pickle,os,time,threading,hmac
from http.server import BaseHTTPRequestHandler,HTTPServer
HERE=Path('/public/home/jiangxinwei.zr/work/paper04/runs/ab_edge_diagnosis_v1_20261104')
SOURCE=HERE.parent/'edge_formal_evaluation_resume_v2_20261104/outputs/gate_182089'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run():
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});start=time.monotonic()
    enc=read(SOURCE/'encoded/COMPLETE.json');assert sha(SOURCE/'encoded/COMPLETE.json')=='7b0ffe2288281e8b15d91d8955392710f747604d051ce248b053f7ab9266ca01'
    plan=read(SOURCE/'BATCH_PLAN.json');udp={u for b in plan if b['shape'][0]==17 for u in b['uids']}
    hashes=Counter();uids=set();selected_rows={};keysrc=set();keydst=set()
    for b in enc['batches']:
        if not set(b['uids'])&udp:continue
        folder=SOURCE/'encoded/batches'/b['batch_id'];m=read(folder/'MANIFEST.json')
        assert sha(folder/'MANIFEST.json')==b['manifest_sha256'] and sha(folder/'rows.json')==m['files']['rows.json']['sha256']
        for r in read(folder/'rows.json'):
            if r.get('source_role')=='UDP':
                hashes[r['_input_tensor_sha256']]+=1;uids.add(r['uid']);selected_rows[r['uid']]=r
        assert time.monotonic()-start<120,'PROBE_DEADLINE'
    take=set(sorted(uids)[:128]);records=[]
    imports=read(SOURCE/'COMPLETE_IMPORT.json')
    assert sha(SOURCE/'COMPLETE_IMPORT.json')=='2b169a24e39b250b58e6cd8ba227ec3b03b0215f5227ccf64dd8ec5c0e8416af'
    sp=SOURCE/'spools/UDP';assert sha(sp/'COMPLETE.json')==imports['roles']['UDP']['complete_sha256']
    complete=read(sp/'COMPLETE.json');attempt=sp/complete['attempt']
    for chunk in complete['chunks']:
        base=attempt/chunk['name'];assert sha(base/'INDEX.json')==chunk['index']['sha256']
        entries=[e for e in read(base/'INDEX.json') if e['uid'] in take]
        if not entries:continue
        with (base/'snapshots.bin').open('rb') as stream:
            for entry in entries:
                stream.seek(entry['offset']);data=stream.read(entry['bytes']);assert hashlib.sha256(data).hexdigest()==entry['sha256']
                value=pickle.loads(data);assert value['uid']==entry['uid'] and value['row']['uid']==entry['uid']
                body=value['body'];p=body['provenance'];flow=body['flow']
                assert p['query_frame']==value['row']['frame'] and p['namespace_sha256']==value['row']['session_id']
                assert value['q14']==entry['header']['q14']
                records.append(dict(uid=entry['uid'],packets=sum(flow['counts']),bursts=len(flow['counts']),duration=flow['flow_duration'],
                    flow_sha256=digest(flow),reset=p['reset_reason'],episode_first_equals_query=p['episode_first_frame']==p['query_frame'],
                    header=flow['burst_tokens'][0][:6]))
        assert time.monotonic()-start<120,'PROBE_DEADLINE'
    assert len(records)==len(take)==128
    result=dict(status='PASS',scope='20000 saved UDP tensor receipts plus 128 UID-ordered frozen snapshots',
        udp_rows=len(uids),distinct_input_tensor_hashes=len(hashes),tensor_hash_counts=dict(hashes),
        sample_rows=len(records),sample_packets=dict(Counter(str(r['packets']) for r in records)),
        sample_bursts=dict(Counter(str(r['bursts']) for r in records)),sample_duration=dict(Counter(str(r['duration']) for r in records)),
        sample_distinct_flows=len({r['flow_sha256'] for r in records}),sample_reset_reasons=dict(Counter(r['reset'] for r in records)),
        episode_first_equals_query=sum(r['episode_first_equals_query'] for r in records),sample_headers=dict(Counter(str(r['header']) for r in records)),
        sample_uid_sha256=digest(sorted(take)),seconds=time.monotonic()-start,source_writes=0,
        limitations='Frozen snapshots and tensor receipts, not fresh raw-PCAP reconstruction; identical-input claim is within recorded model inputs.')
    (HERE/'INPUT_PROBE_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
if __name__=='__main__':
    try:run()
    except Exception as e:(HERE/'INPUT_PROBE_RESULT.json').write_text(json.dumps(dict(status='FAIL',error=repr(e))))
    token=read(HERE/'.private.json')['token']
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_GET(self):
            if not hmac.compare_digest(self.path,'/'+token+'/result'):self.send_error(403);return
            data=(HERE/'INPUT_PROBE_RESULT.json').read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.send_header('X-SHA256',hashlib.sha256(data).hexdigest());self.end_headers();self.wfile.write(data)
    server=HTTPServer(('127.0.0.1',18836),Handler);timer=threading.Timer(600,server.shutdown);timer.daemon=True;timer.start();server.serve_forever()
