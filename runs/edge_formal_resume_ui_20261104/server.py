"""Read-only local progress and accepted summaries for the formal evaluation."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'edge_formal_evaluation_resume_v2_20261104'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        try:
            if self.path=='/':data=(HERE/'index.html').read_bytes();kind='text/html'
            elif self.path=='/state':
                data=(SOURCE/'PROGRESS.json').read_bytes();kind='application/json'
            elif self.path=='/metrics':
                receipt=json.loads((SOURCE/'FINAL_ACCEPTANCE.json').read_text(encoding='utf-8-sig'))
                if receipt['status']!='PASS':self.send_error(409);return
                data=(SOURCE/'retrieved/outputs'/('gate_'+receipt['job_id'])/'evaluation/METRICS.json').read_bytes();kind='application/json'
            else:self.send_error(404);return
        except (OSError,ValueError):self.send_error(503);return
        self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',18799),Handler).serve_forever()
