from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = {
    "/": "progress.html",
    "/state": "LOCAL_PROGRESS.json",
    "/start": ".private/START.txt",
    "/eligibility": "EXTERNAL_ELIGIBILITY.md",
    "/rules": "EXPERIMENT_CARD.json",
    "/paper": "received/RESULTS_FOR_PAPER.md",
    "/receipt": "received/LOCAL_ACCEPTANCE.json",
    "/threshold": "received/GROUP_HEADLINE.csv",
    "/k1": "received/K1_HEADLINE.csv",
    "/ports": "received/PORT_HEADLINE.csv",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = HERE / FILES[self.path] if self.path in FILES else None
        if path is None or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        mime = {".html": "text/html", ".json": "application/json", ".csv": "text/csv"}.get(
            path.suffix, "text/plain"
        )
        self.send_response(200)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18813), Handler).serve_forever()
