"""Display the live WSL capture and open accepted results from the same batch."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys

import protocol
from progress import open_shared

OUT=Path(sys.argv[1])
PORT=int(sys.argv[2]) if len(sys.argv)>2 else 18836
HTML="""<!DOCTYPE html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>同端点第 5 高阈值校准</title>
<style>
:root{font:16px/1.6 system-ui,sans-serif;color-scheme:light dark}
main{max-width:42rem;margin:7vh auto;padding:1.2rem}
progress{width:100%;accent-color:#14815e} dt{font-weight:600}dd{margin:0 0 1rem}
</style>
<main><h1>同端点第 5 高阈值校准</h1>
<p id="stage">读取进度</p><progress id="bar" max="1" value="0"></progress><p id="capture"></p>
<dl><dt>校准连接</dt><dd id="cal">206 / 1,000</dd>
<dt>独立普通留出</dt><dd id="test">0 / 1,000</dd><dt>D 盘可用</dt><dd id="free">—</dd></dl>
<p><a href="/qualification">攻击数据资格</a> · <a href="/method">封存口径</a></p>
<p hidden id="threshold"><a href="/thresholds">新旧阈值</a></p>
<p hidden id="result"><a href="/summary">中文结论</a> · <a href="/table">日常误报与攻击检出</a> ·
<a href="/paired">分批配对</a> · <a href="/stress">合法重连压力</a> · <a href="/sha">SHA-256</a></p></main>
<script>
const el=id=>document.getElementById(id);
const labels={VERIFYING:"核验封存输入",BETWEEN_BATCHES:"等待批次间隔",CAPTURING:"录制 WSL 正常连接",
SCORING:"核对请求身份并评分",SEALING_THRESHOLD:"核出三组第 5 高阈值",VERIFYING_OUTPUTS:"核验结果",
ACCEPTED:"已验收",STOP:"运行中止"};
function tag(n){if(!n)return ""; const [kind,index]=n.split("_");
return ({"preflight":"短预检","calibration":"校准","holdout":"独立留出"}[kind]||kind)+(kind==="preflight"?"":" "+Number(index)+"/4");}
async function update(){
 try{
  const x=await(await fetch("/state",{cache:"no-store"})).json(), c=x.capture||{};
  el("stage").textContent=[labels[x.stage]||x.stage,tag(x.batch),x.error].filter(Boolean).join(" · ");
  const t=c.duration_seconds||1,now=c.elapsed_seconds||0;
  el("bar").max=t; el("bar").value=x.stage==="CAPTURING"?now:0;
  el("capture").textContent=x.stage==="CAPTURING"?now.toFixed(0)+" / "+t+" 秒 · "+(c.packets||0)+" 原始帧":"";
  el("cal").textContent=(x.calibration_connections??206).toLocaleString()+" / 1,000";
  el("test").textContent=(x.holdout_connections??0).toLocaleString()+" / 1,000";
  el("free").textContent=(x.free/1073741824).toFixed(2)+" GiB";
  el("threshold").hidden=!x.sealed;
  el("result").hidden=x.stage!=="ACCEPTED";
 }catch{el("stage").textContent="等待进度文件";}
}
update();setInterval(update,6000);
</script></html>"""


def read(path):
    try:
        with open_shared(path) as stream:
            return json.load(stream)
    except FileNotFoundError:
        return None


class View(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.path=="/":
            body,mime=HTML.encode("utf8"),"text/html"
        elif self.path=="/state":
            s=read(OUT/"RUN_STATUS.json") or dict(stage="VERIFYING")
            attempt=s.get("attempt")
            s.update(free=shutil.disk_usage(OUT).free,sealed=(OUT/"THRESHOLD_SEAL.json").is_file(),
                     capture=read(OUT/attempt/"COLLECTION_PROGRESS.json") if attempt else None)
            body,mime=json.dumps(s,ensure_ascii=False).encode("utf8"),"application/json"
        else:
            routes={"/summary":"RESULTS_FOR_PAPER.md","/table":"DAILY_AND_ATTACK.csv","/paired":"PAIRED.csv",
                    "/stress":"STRESS_PAIRED.csv","/thresholds":"THRESHOLD_COMPARISON.csv","/sha":"SHA256SUMS",
                    "/qualification":"ATTACK_QUALIFICATION.csv","/method":"METHOD.md"}
            name=routes.get(self.path)
            if not name or not (OUT/name).is_file():
                self.send_error(404)
                return
            with open_shared(OUT/name) as stream:
                body=stream.read()
            mime="text/plain"
        self.send_response(200)
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",PORT),View).serve_forever()
