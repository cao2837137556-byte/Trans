"""Local status and small result links for the formal acquisition."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys

OUT=Path(sys.argv[1])
HTML="""<!doctype html>
<html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paper04 同服务正式正常评价</title>
<style>
:root{font:16px/1.65 system-ui,sans-serif;color-scheme:light dark}
main{max-width:40rem;margin:7vh auto;padding:1.2rem}
progress{width:100%;accent-color:#128059}
dl{padding-top:1.2rem;border-top:1px solid #829a90}dt{font-weight:600}dd{margin:0 0 1rem}
</style>
<main><h1>同服务正式正常评价</h1><p id="phase">读取进度</p>
<progress max="7200" value="0" id="bar"></progress><p id="time"></p>
<dl><dt>评分快检</dt><dd id="quick">等待读回</dd>
<dt>原始帧</dt><dd id="frames">—</dd><dt>D 盘可用</dt><dd id="space">—</dd>
<dt>参考封存</dt><dd id="bank">—</dd></dl>
<p id="links" hidden><a href="/result">中文结论</a> · <a href="/paired">四组配对小表</a> · <a href="/sha">逐文件 SHA-256</a></p>
</main>
<script>
const e=id=>document.getElementById(id);
const label={STARTING_WSL:"正在建立隔离网络",RECORDING_ENROLLMENT:"录制两小时正常参考",
SEALING_REFERENCE:"验收原始边界并封存参考",REFERENCE_SEALING:"验收原始边界并封存参考",
READY_FOR_EVALUATION:"参考已封存",REFERENCE_SEAL_PAUSED:"参考封存暂停 · 原服务仍在等待",
RECORDING_EVALUATION:"录制独立正常评价",
SCORING_EVALUATION:"核对评价日志并计算四组误报",ACCEPTED:"采集和评价已验收",STOP:"流程已停止"};
async function update(){
  try{
    const x=await(await fetch("/state",{cache:"no-store"})).json();
    const c=x.capture||{}, q=x.quick||{}, b=x.bank||{};
    const active=["STARTING_WSL","READY_FOR_EVALUATION"].includes(x.stage);
    const stage=active?(c.stage||x.stage):x.stage;
    const t=c.elapsed_seconds||0;
    const planned=c.duration_seconds||7200;
    e("phase").textContent=(label[stage]||stage)+(x.error?" · "+x.error:"");
    e("bar").max=planned;
    e("bar").value=t;
    e("time").textContent=c.stage?.startsWith("RECORDING")?t.toFixed(0)+" / "+planned.toFixed(0)+" 秒（已采到原帧）":"";
    e("quick").textContent=q.status==="PASS"?"已复现 "+q.pilot.rows+" 条小试输入、"+q.archived_attack.rows+" 条封存攻击判决":"等待读回";
    e("frames").textContent=c.packets?.toLocaleString()??"—";
    e("space").textContent=(x.free/1073741824).toFixed(2)+" GiB";
    e("bank").textContent=b.status==="PASS"?b.reference_rows+" 条参考 · "+b.same_service_components+" 个同服务组件":"待封存";
    e("links").hidden=x.stage!=="ACCEPTED";
  }catch{e("phase").textContent="等待进度文件";}
}
update();setInterval(update,6000);
</script></html>"""


def read(name):
    path=OUT/name
    return json.loads(path.read_bytes()) if path.is_file() else None


class View(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.path=="/":
            body=HTML.encode("utf8")
            mime="text/html"
        elif self.path=="/state":
            s=read("RUN_STATUS.json") or read("EXPORT_PROGRESS.json") or dict(stage="STARTING_WSL")
            failure=read("COLLECTION_FAILURE.json")
            if failure and s["stage"]!="ACCEPTED":
                s.update(stage="STOP",error=failure["error"])
            s.update(free=shutil.disk_usage(OUT).free,capture=read("COLLECTION_PROGRESS.json"),
                     quick=read("QUICK_CHECK.json"),bank=read("BANK_READY.json"))
            body=json.dumps(s,ensure_ascii=False).encode("utf8")
            mime="application/json"
        else:
            name={"/result":"RESULTS_FOR_PAPER.md","/paired":"PAIRED.csv","/sha":"SHA256SUMS"}.get(self.path)
            if not name or not (OUT/name).is_file():
                self.send_error(404)
                return
            body=(OUT/name).read_bytes()
            mime="text/plain"
        self.send_response(200)
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",int(sys.argv[2]) if len(sys.argv)>2 else 18831),View).serve_forever()
