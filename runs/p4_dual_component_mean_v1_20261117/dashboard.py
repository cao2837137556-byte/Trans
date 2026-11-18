"""Local-only experiment progress and verified paper return."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = 18812


class Page(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        files = {'/':('progress.html','text/html'), '/state':('LOCAL_PROGRESS.json','application/json'),
                 '/start':('.private/START.txt','text/plain'), '/paper':('received/RESULTS_FOR_PAPER.md','text/plain'),
                 '/pairs':('received/PAIRED.csv','text/csv'), '/metrics':('received/METRICS.csv','text/csv'),
                 '/receipt':('received/LOCAL_ACCEPTANCE.json','application/json')}
        route = files.get(self.path)
        if route is None or not (HERE/route[0]).is_file():
            self.send_error(404)
            return
        data = (HERE/route[0]).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', route[1]+'; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1',PORT),Page).serve_forever()
