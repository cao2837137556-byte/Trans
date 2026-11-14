"""Expose only this run's local receipts through a loopback progress page."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/':
            data = (HERE/'progress.html').read_bytes()
            content = 'text/html'
        elif self.path == '/state':
            remote = HERE/'LOCAL_PROGRESS.json'
            motion = HERE/'MOTION_UPLOAD_PROGRESS.json'
            status = json.loads(remote.read_text(encoding='utf-8')) if remote.is_file() else None
            attempt = 'received_repair_183971' if ((status or {}).get('install') or {}).get(
                'failed_prepare_job') == '183971' else 'received'
            data = json.dumps(dict(
                remote=status,
                motion=json.loads(motion.read_text(encoding='utf-8')) if motion.is_file() else None,
                retrieved=(HERE/attempt/'RETURN.json').is_file())).encode()
            content = 'application/json'
        else:
            return self.send_error(404)
        self.send_response(200)
        self.send_header('Content-Type', content + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1',18809),Handler).serve_forever()
