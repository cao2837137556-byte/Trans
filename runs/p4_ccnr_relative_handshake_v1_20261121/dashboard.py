from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROUTES={"/":"progress.html","/state":"LOCAL_PROGRESS.json","/start":".private/START.txt",
        "/paper":"received/RESULTS_FOR_PAPER.md","/receipt":"received/LOCAL_ACCEPTANCE.json",
        "/preflight":"PREFLIGHT_READBACK.json", "/login":"received/LOGIN_QUALIFICATION.md",
        "/unsw":"received/UNSW_ATTRIBUTION.json"}

class Page(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        path=HERE/ROUTES[self.path] if self.path in ROUTES else None
        if not path or not path.is_file():
            self.send_error(404);return
        body=path.read_bytes()
        types={".html":"text/html",".json":"application/json"}
        self.send_response(200)
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Type",types.get(path.suffix,"text/plain")+"; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",18829),Page).serve_forever()
