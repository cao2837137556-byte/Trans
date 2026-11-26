"""Serve this experiment's loopback-only progress and accepted small tables."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"p4_login_formal_v1_20261121"))
from progress import open_shared

ROOT = Path(sys.argv[1])
PORT = int(sys.argv[2])
HTML = """<!doctype html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paper04 合法重连压力复测</title>
<style>
:root{color-scheme:light dark;font:16px/1.6 system-ui,sans-serif}
main{max-width:43rem;margin:7vh auto;padding:1.25rem}
progress{width:100%;accent-color:#10795b;margin:.6rem 0}dd{margin:0 0 .8rem} dt{font-weight:600}
</style>
<main><h1>合法重连压力复测</h1><p id="status">读取进度</p>
<progress id="bar" max="600" value="0"></progress>
<dl><dt>已验收正式连接</dt><dd id="done">0 / 600</dd>
<dt>当前批次</dt><dd id="batch">—</dd>
<dt>D 盘可用</dt><dd id="disk">—</dd></dl>
<p id="conclusion"></p><p><a href="/protocol">预登记</a> · <a href="/preflight">切片预检</a></p>
<p hidden id="results"><a href="/summary">合稿结果</a> · <a href="/rates">分档分批误报</a> ·
<a href="/frequency">同频率配对</a> · <a href="/proof">验收</a> · <a href="/sha">SHA-256</a></p>
<p id="perf"></p></main>
<script>
const el=k=>document.getElementById(k);
const labels={VERIFYING:"校验冻结资产",BETWEEN_BATCHES:"等待批次间静默",CAPTURING:"采集真实正常重连",
SCORING:"对齐 POST 并离线评分",VERIFYING_OUTPUTS:"验收全部结果",PREFLIGHT_PASSED:"预检通过",
ACCEPTED:"正式实验已验收",FAILED:"运行中止"};
async function tick(){
 try {
  const s=await(await fetch("/state",{cache:"no-store"})).json();
  el("status").textContent=[labels[s.stage]||s.stage,s.error].filter(Boolean).join(" · ");
  el("bar").value=s.connections||0; el("done").textContent=(s.connections||0)+" / 600";
  const c=s.capture||{};
  el("batch").textContent=[s.batch,s.scheduled_rate? s.scheduled_rate+" 次每分钟每客户端":"",
                        c.packets?c.packets+" 帧":""].filter(Boolean).join(" · ")||"—";
  el("disk").textContent=(s.free/1073741824).toFixed(2)+" GiB";
  el("results").hidden=s.stage!=="ACCEPTED";
  el("conclusion").textContent=s.conclusion||"";
  const perf={RUNNING:"本机性能测量中",PASS:"本机性能测量已验收",FAILED:"本机性能测量有待核查"};
  el("perf").textContent=perf[s.benchmark_status?.status]||"";
 }catch{el("status").textContent="等待进度回执";}
}
tick();setInterval(tick,6000);
</script></html>"""
ROUTES = {"/protocol":"REGISTRATION.json","/preflight":"PREFLIGHT.json","/summary":"RESULTS_FOR_PAPER.md",
          "/rates":"TABLE1_LEGAL_RECONNECT.csv","/frequency":"TABLE2_MATCHED_H60_MCNEMAR.csv",
          "/proof":"ACCEPTANCE.json","/sha":"SHA256SUMS"}


def read_maybe(path):
    try:
        with open_shared(path) as stream:
            return json.load(stream)
    except (OSError,ValueError):
        return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        mime = "text/plain; charset=utf-8"
        if self.path=="/":
            body,mime = HTML.encode("utf8"),"text/html; charset=utf-8"
        elif self.path=="/state":
            s = read_maybe(ROOT/"live/RUN_STATUS.json") or dict(stage="VERIFYING")
            attempt = s.get("attempt")
            s.update(free=shutil.disk_usage(ROOT).free,
                     capture=read_maybe(ROOT/attempt/"COLLECTION_PROGRESS.json") if attempt else None,
                     benchmark_status=read_maybe(ROOT/"live/BENCHMARK_STATUS.json"))
            body,mime = json.dumps(s,ensure_ascii=False).encode("utf8"),"application/json"
        else:
            name = ROUTES.get(self.path)
            if not name:
                return self.send_error(404)
            try:
                with open_shared(ROOT/"evidence"/name) as stream:
                    body=stream.read()
            except FileNotFoundError:
                return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",PORT),Handler).serve_forever()
