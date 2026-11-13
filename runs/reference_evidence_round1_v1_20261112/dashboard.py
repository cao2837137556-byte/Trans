"""Same loopback dashboard pattern as the existing paper04 progress page."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

from common_round1 import HERE, load


class Dashboard(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/':
            data = (HERE / 'progress.html').read_bytes()
            content = 'text/html'
        elif self.path == '/state':
            source = HERE / 'LOCAL_PROGRESS.json'
            data = json.dumps(load(source) if source.is_file() else dict(stage='PREPARED')).encode()
            content = 'application/json'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 18807), Dashboard).serve_forever()
