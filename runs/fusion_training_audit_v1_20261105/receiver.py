from http.server import BaseHTTPRequestHandler,HTTPServer
import hmac,json,threading
from pathlib import Path
HERE=Path(__file__).resolve().parent
token=(HERE/'.token').read_text()
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def do_GET(self):
  if not hmac.compare_digest(self.path,'/'+token+'/result'):self.send_error(403);return
  b=(HERE/'RESULT.json').read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
s=HTTPServer(('127.0.0.1',18849),H)
t=threading.Timer(3600,s.shutdown);t.daemon=True;t.start();s.serve_forever()
