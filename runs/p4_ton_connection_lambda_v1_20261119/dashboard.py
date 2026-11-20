from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
ROUTES = {
    "/": "progress.html",
    "/state": "LOCAL_PROGRESS.json",
    "/start": ".private/START.txt",
    "/paper": "received/RESULTS_FOR_PAPER.md",
    "/sweep": "received/LAMBDA_CONNECTIONS.csv",
    "/receipt": "received/LOCAL_ACCEPTANCE.json",
}


class Page(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = HERE / ROUTES[self.path] if self.path in ROUTES else None
        if not path or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            {".html": "text/html", ".json": "application/json", ".csv": "text/csv"}.get(
                path.suffix, "text/plain"
            )
            + "; charset=utf-8",
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18816), Page).serve_forever()
