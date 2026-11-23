"""Show actual capture progress and the accepted paired results."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

from design import PRIOR_CONNECTIONS, SEEDS, TARGET_CONNECTIONS
from progress import open_shared

OUT = Path(sys.argv[1])
PORT = int(sys.argv[2])
PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>同服务正常留出扩充</title>
<style>
:root{font:16px/1.65 system-ui,sans-serif;color-scheme:light dark}
main{max-width:34rem;margin:8vh auto;padding:1.2rem}
progress{width:100%;accent-color:#14795f}dt{font-weight:600}dd{margin:0 0 1rem}
</style>
<main><h1>同服务正常留出扩充</h1><p id="stage" role="status">载入进度</p>
<progress id="bar" max="1" value="0" aria-label="当前采集批次"></progress>
<dl><dt>当前原始帧</dt><dd id="frames">—</dd>
<dt>已验收普通留出</dt><dd id="count">—</dd></dl>
<p hidden id="report"><a href="/summary">结果概览</a> · <a href="/paired">配对表</a> ·
<a href="/sha">SHA-256</a></p></main>
<script>
const el=id=>document.getElementById(id);
const titles={PREFLIGHT:"核对封存资产",CAPTURING:"采集中",SCORING:"逐帧对齐与评分",
BETWEEN_BATCHES:"批次间隔",ACCEPTED:"已验收",STOP:"运行中止"};
async function refresh(){
  try{
    const res=await fetch("/state",{cache:"no-store"});
    const x=await res.json(), c=x.capture||{};
    const batch=x.batch===0?" · 预检":x.batch?" · 第 "+x.batch+"/"+x.batches+" 批":"";
    el("stage").textContent=(titles[x.stage]||x.stage)+batch+(x.error?" · "+x.error:"");
    el("bar").max=c.duration_seconds||1;
    el("bar").value=c.elapsed_seconds||0;
    el("frames").textContent=c.packets?.toLocaleString()??"—";
    el("count").textContent=x.completed+" 条连接，目标 ≥ "+x.target+" 条";
    el("report").hidden=x.stage!=="ACCEPTED";
  }catch{el("stage").textContent="暂未取到进度";}
}
refresh();setInterval(refresh,5000);
</script></html>"""


def read_state(path):
    try:
        with open_shared(path) as stream:
            return json.load(stream)
    except FileNotFoundError:
        return None


class View(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            mime, body = "text/html", PAGE.encode("utf8")
        elif self.path == "/state":
            state = read_state(OUT / "RUN_STATUS.json") or dict(stage="PREFLIGHT", completed=PRIOR_CONNECTIONS)
            capture = None
            if state.get("attempt"):
                capture = read_state(OUT / state["attempt"] / "COLLECTION_PROGRESS.json")
            state.update(capture=capture, target=TARGET_CONNECTIONS, batches=len(SEEDS) - 1)
            mime, body = "application/json", json.dumps(state, ensure_ascii=False).encode("utf8")
        else:
            names = {"/summary": "RESULTS_FOR_PAPER.md", "/paired": "PAIRED.csv", "/sha": "SHA256SUMS"}
            file = names.get(self.path)
            if not file or not (OUT / file).is_file():
                self.send_error(404)
                return
            with open_shared(OUT / file) as stream:
                mime, body = "text/plain", stream.read()
        self.send_response(200)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), View).serve_forever()
