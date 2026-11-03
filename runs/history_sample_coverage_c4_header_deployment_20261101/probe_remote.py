"""Engineering-only outer-header qualification; no RECENT/model/evaluation."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import csv, hashlib, io, json, os, struct, subprocess, sys, time, traceback
import numpy as np

ROOT=Path('/public/home/jiangxinwei.zr/work/paper04')
OLD=ROOT/'runs/history_sample_coverage_c4_checkpoint_repair_v1_20261101'
OUT=ROOT/'runs/history_sample_coverage_c4_header_deployment_20261101/qualification'
sys.path.insert(0,str(OLD))
from decoder_guard import parse_stderr, audit_packet, _interface, _block

def main():
    started=time.monotonic();OUT.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((OLD/'config/EXECUTION.json').read_text())
    spec=next(d for d in cfg['devices'] if d['key']=='NETATMO')
    member=OLD/'outputs/encoding/history/NETATMO'
    logical=json.loads((member/'LOGICAL_INPUT.json').read_text())
    warnings=parse_stderr((member/'decoder_pass1.stderr.log').read_bytes(),packets=4967010)
    frames=sorted(warnings)
    index=np.load(spec['packet_index']['path'],mmap_mode='r',allow_pickle=False)
    order=np.load(spec['chronological_order']['path'],mmap_mode='r',allow_pickle=False)
    tiny=OUT/'warning_headers.pcapng'
    with Path(spec['raw']['path']).open('rb') as f,tiny.open('xb') as w:
        endian,_,_,end=_interface(f);f.seek(0);w.write(f.read(end))
        for frame in frames:
            item=index[int(order[frame-1])];f.seek(int(item['block_offset']))
            kind,block=_block(f,endian);assert kind==6;w.write(block)
    command=[cfg['tshark'],'-n','-r',str(tiny),'-T','fields','-E','header=y','-E','separator=/t','-E','quote=d','-E','occurrence=f']
    for name in logical['decoder']['fields']:command+=['-e',name]
    ran=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60)
    (OUT/'decoder_fields.tsv').write_text(ran.stdout)
    (OUT/'decoder_stderr.log').write_text(ran.stderr)
    parsed=csv.DictReader(io.StringIO(ran.stdout),delimiter='\t',quotechar='"')
    assert parsed.fieldnames==logical['decoder']['fields']
    rr=list(parsed);assert len(rr)==len(frames) and ran.returncode==0
    report=[]
    with Path(spec['raw']['path']).open('rb') as f:
        for slot,(frame,row) in enumerate(zip(frames,rr),1):
            assert int(row['frame.number'])==slot and None not in row and None not in row.values()
            row['frame.number']=str(frame)
            item=index[int(order[frame-1])]
            try:result=audit_packet(row,f,item)
            except Exception as exc:result=dict(error=str(exc))
            report.append(dict(logical_frame=frame,row=row,audit=result))
    details={}
    for rel in ('workers/NETATMO_prepare_ERROR.json','workers/NETATMO_prepare.log','STATUS.json'):
        p=OLD/'outputs/encoding'/rel
        if p.exists():details[rel]=p.read_text()
    result=dict(status='ENGINEERING_QUALIFICATION_ONLY',rows=report,details=details,
        decoder_exit=ran.returncode,fields=len(parsed.fieldnames),
        tiny_sha256=hashlib.sha256(tiny.read_bytes()).hexdigest(),
        elapsed_seconds=time.monotonic()-started,
        limit='Static outer headers only. Not RECENT replay, stream-state validation, warning signature acceptance or model evaluation.')
    (OUT/'PROBE.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__':
    try:main()
    except BaseException:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'PROBE.json').write_text(json.dumps(dict(error=traceback.format_exc())))
    token=os.environ['C4_PROBE_TOKEN']
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path!='/'+token+'/probe':self.send_error(404);return
            b=(OUT/'PROBE.json').read_bytes()
            self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    print('C4_HEADER_PROBE_READY',flush=True)
    HTTPServer(('127.0.0.1',18808),Handler).serve_forever()
