"""Read-only export of the failed job's small receipts and file inventory."""
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import hashlib,json,os,threading
ROOT=Path('/public/home/jiangxinwei.zr/work/paper04')
SOURCE=ROOT/'runs/history_sample_coverage_c4_header_repair_v1_20261101/outputs/encoding'
OUT=ROOT/'runs/history_sample_coverage_c4_resume_audit_20261102'
def main(token):
    names=['STATUS.json','workers/NETATMO_prepare.json','workers/NETATMO_prepare_COMPLETE.json',
           'workers/NETATMO_encode.json','workers/NETATMO_encode_ERROR.json',
           'history/NETATMO/PREPARE_RESULT.json','history/NETATMO/DECODER_DIAGNOSTIC_AUDIT.json',
           'history/NETATMO/CENSUS_CHECKPOINT.json','history/NETATMO/selection/SELECTION.json',
           'history/NETATMO/selection_replay/SELECTION.json','history/NETATMO/encoded/BATCH_LEDGER.jsonl']
    result=dict(job='180670',files={},member_inventory=[])
    for name in names:
        p=SOURCE/name
        if p.exists():
            b=p.read_bytes();assert len(b)<4*2**20
            result['files'][name]=dict(text=b.decode(),bytes=len(b),mtime_ns=p.stat().st_mtime_ns,sha256=hashlib.sha256(b).hexdigest())
    for p in sorted((SOURCE/'history/NETATMO').rglob('*')):
        if p.is_file():result['member_inventory'].append(dict(name=p.relative_to(SOURCE).as_posix(),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns))
    result['source_preserved']=True
    OUT.mkdir(parents=True,exist_ok=True)
    b=json.dumps(result).encode();(OUT/'REMOTE_REPORT.json').write_bytes(b)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path!='/'+token+'/report':self.send_error(404);return
            self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    server=HTTPServer(('127.0.0.1',18814),Handler)
    timer=threading.Timer(1800,server.shutdown);timer.daemon=True;timer.start()
    print('C4_READONLY_REPORT_READY',flush=True)
    try:server.serve_forever()
    finally:timer.cancel();server.server_close()
if __name__=='__main__':main(os.environ['C4_REPORT_TOKEN'])
