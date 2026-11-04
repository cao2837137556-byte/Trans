"""Local read-only presentation; the sealed worker and pipeline stay unchanged."""
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent/'edge_formal_gate_resume_v4_20261104/PROGRESS.json'
samples = deque(maxlen=1000)
lock = threading.Lock()
TOTALS = {'NORMAL': 1629749, 'HTTP': 229142, 'UDP': 3215732}

def state():
    value = json.loads(SOURCE.read_text(encoding='utf-8-sig'))
    worker = value.get('worker') or {}
    replay = worker.get('replay') or worker
    role, frame, elapsed = replay.get('role'), replay.get('frame'), replay.get('role_elapsed_seconds')
    key = (value.get('job_id'), value.get('attempt_id'), role)
    analytics = {'role_total': TOTALS.get(role), 'eta_scope': 'current_role_only', 'resume_origin': 2877608}
    with lock:
        if frame and elapsed:
            if samples and samples[-1][0] != key: samples.clear()
            if not samples or elapsed > samples[-1][1]: samples.append((key, elapsed, frame))
            recent = [s for s in samples if 0 < elapsed-s[1] <= 300]
            rate = None
            if recent and elapsed-recent[0][1] >= 60:
                rate = (frame-recent[0][2])/(elapsed-recent[0][1])
            analytics['rate_kind'] = 'recent' if rate else 'resumed_suffix_average'
            rate = rate or max(0, frame-2877608)/elapsed
            analytics['frames_per_second'] = rate
            if role in TOTALS and rate > 0:
                analytics['role_remaining_seconds'] = max(0, TOTALS[role]-frame)/rate
    value['display'] = analytics
    value['read_utc'] = datetime.now(timezone.utc).isoformat()
    return value

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path not in ('/', '/state'): self.send_error(404); return
        try:
            data = (HERE/'index.html').read_bytes() if self.path == '/' else json.dumps(state(), ensure_ascii=False).encode()
        except (OSError, ValueError): self.send_error(503); return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8' if self.path == '/' else 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

if __name__ == '__main__': ThreadingHTTPServer(('127.0.0.1', 18797), Handler).serve_forever()
