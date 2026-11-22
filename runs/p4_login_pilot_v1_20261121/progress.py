"""Show counts and elapsed time for the local pilot on the loopback interface."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys

PAGE = """<!doctype html>
<html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper04 登录采集小试</title>
<style>
:root{font:16px/1.65 system-ui,sans-serif;color-scheme:light dark}
main{max-width:40rem;margin:8vh auto;padding:0 1.2rem}
progress{width:100%;accent-color:#148562}
dt{font-weight:600}dd{margin:0 0 1rem}
</style>
<main><h1>同服务正常登录采集</h1><p id="phase">读取进度</p>
<progress id="bar" max="600" value="0"></progress>
<dl><dt>采集时长</dt><dd id="elapsed"></dd><dt>采集文件</dt><dd id="size"></dd>
<dt>D 盘可用空间</dt><dd id="free"></dd><dt>验收</dt><dd id="accept"></dd></dl></main>
<script>
const el = id => document.getElementById(id);
const phases={CAPTURING:"隔离网络采集中",CAPTURED:"采集结束",SEALED_CAPTURE:"采集封存，正在验收",
              PASS:"采集及验收通过",REVIEW:"查看验收回执"};
async function show() {
  try {
    const s=await (await fetch("/state",{cache:"no-store"})).json();
    const seconds=s.capture?.duration_seconds??Math.max(0,Math.min(600,(Date.now()-Date.parse(s.started_utc))/1000));
    el("phase").textContent=phases[s.acceptance?.status??s.stage]??s.stage;
    el("bar").value=seconds;
    el("elapsed").textContent=seconds.toFixed(1)+" / 600 秒";
    el("size").textContent=(s.size/1048576).toFixed(3)+" / 100 MiB";
    el("free").textContent=(s.free/1073741824).toFixed(2)+" GiB";
    const a=s.acceptance;
    el("accept").textContent=a?"握手 "+a.handshakes+" · 对齐请求 "+a.aligned+" · 790 维 "+a.features:"等待原帧及认证日志核验";
  } catch { el("phase").textContent="等待运行状态"; }
}
show(); setInterval(show,5000);
</script></html>"""

OUT = Path(sys.argv[1])


class View(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            content = PAGE.encode("utf8")
            mime = "text/html"
        elif self.path == "/state":
            s = json.loads((OUT/"CAPTURE_PROGRESS.json").read_bytes())
            s["free"] = shutil.disk_usage(OUT).free
            s["size"] = sum(p.stat().st_size for p in OUT.iterdir()
                            if p.name == "login.pcap" or p.name == "server.jsonl" or p.name.startswith("client_"))
            if (OUT/"ACCEPTANCE.json").is_file():
                a = json.loads((OUT/"ACCEPTANCE.json").read_bytes())
                s["acceptance"] = dict(status=a["status"],handshakes=a["checks"]["complete_duplex_handshakes"],
                                       aligned=a["checks"]["aligned_requests"],features=a["features"]["status"])
            content = json.dumps(s).encode("utf8")
            mime = "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Content-Length",str(len(content)))
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1",18830), View).serve_forever()
