"""Read-only progress server for a Codex right-side panel; never runs science."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
TERMINAL = ('COMPLETED', 'EXCEPTION_STOPPED')


def _age(raw):
    try:
        age = (datetime.now(timezone.utc) -
               datetime.fromisoformat(raw.replace('Z', '+00:00'))).total_seconds()
        return max(0., age)
    except (ValueError, TypeError, AttributeError):
        return None


def snapshot(status_file):
    path = Path(status_file)
    if not path.is_file():
        return dict(technical_status='NOT_RUN', scientific_status='NOT_EVALUATED',
                    freshness='not_started', automatic_retry=False)
    if path.stat().st_size > 2**20:
        raise ValueError('STATUS_TOO_LARGE')
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if value.get('technical_status') == 'NOT_RUN':
        value['freshness'] = 'not_started'
        return value
    work = _age(value.get('work_heartbeat_utc'))
    service = _age(value.get('service_heartbeat_utc'))
    final = value.get('technical_status') in TERMINAL
    value.update(work_heartbeat_age_seconds=work, service_heartbeat_age_seconds=service)
    value['freshness'] = ('terminal' if final else
                          'fresh' if work is not None and work <= 90 else 'stale')
    if not final and value['freshness'] == 'stale':
        value['display_status'] = 'UNKNOWN_WORKER_PROGRESS'
    return value


def handler(status_file):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if self.path == '/api/status':
                    body = json.dumps(snapshot(status_file), ensure_ascii=False,
                                      allow_nan=False).encode('utf-8')
                    content = 'application/json; charset=utf-8'
                elif self.path == '/':
                    body = (PACKAGE / 'progress.html').read_bytes()
                    content = 'text/html; charset=utf-8'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', content)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self.send_error(503, str(exc))

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status-file', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18785)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(args.status_file.resolve()))
    print('READ_ONLY_PROGRESS http://127.0.0.1:' + str(args.port) + '/', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
