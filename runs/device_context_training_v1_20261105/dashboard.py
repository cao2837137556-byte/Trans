from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  if self.path=='/':b=(HERE/'index.html').read_bytes();mime='text/html'
  elif self.path=='/state':
   out={n:json.loads((HERE/(n+'.json')).read_text()) if (HERE/(n+'.json')).exists() else None for n in ['PROGRESS','ASSET_TRANSFER_COMPLETE','METADATA_ADMISSION','CHAIN_STATE','FINAL_ACCEPTANCE']};b=json.dumps(out).encode();mime='application/json'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',18806),H).serve_forever()
