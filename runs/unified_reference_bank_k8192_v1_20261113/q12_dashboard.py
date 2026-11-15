"""Serve the two local status files maintained by the existing result receivers."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from q12_recovery_relay import RUNS

HERE=Path(__file__).resolve().parent


class Dashboard(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.path=='/state':
            values={}
            for mode,name in RUNS.items():
                source=HERE.parent/name/'LOCAL_PROGRESS.json'
                values[mode]=json.loads(source.read_text(encoding='utf-8')) if source.is_file() else None
            data=json.dumps(values).encode()
            kind='application/json'
        elif self.path=='/':
            data=(HERE/'q12_progress.html').read_bytes()
            kind='text/html'
        else:
            return self.send_error(404)
        self.send_response(200)
        self.send_header('Content-Type',kind+'; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)


if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',18811),Dashboard).serve_forever()
