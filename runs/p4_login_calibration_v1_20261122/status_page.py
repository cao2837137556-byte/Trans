"""Show the local experiment progress and returned small tables."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys

from sources import FORMAL
from progress import open_shared

OUT=Path(sys.argv[1])
PORT=int(sys.argv[2]) if len(sys.argv)>2 else 18834
PAGE="""<!DOCTYPE html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>同服务阈值校准</title>
<style>
:root{font:16px/1.6 system-ui,sans-serif;color-scheme:light dark}
main{max-width:40rem;margin:7vh auto;padding:1.2rem}
progress{width:100%;accent-color:#14815e}dt{font-weight:600}dd{margin:0 0 1rem}
</style>
<main><h1>同服务阈值校准</h1><p id="stage">读取进度</p>
<progress max="3600" value="0" id="bar"></progress><p id="elapsed"></p>
<dl><dt>原始帧</dt><dd id="frames">—</dd>
<dt>阈值校准</dt><dd id="cal">待封存</dd>
<dt>D 盘可用</dt><dd id="disk">—</dd></dl>
<p><a href="/qualification">攻击数据资格</a> · <a href="/flood">原泛洪回检</a></p>
<p hidden id="results"><a href="/summary">中文结论</a> · <a href="/paired">正常留出配对表</a> ·
<a href="/stress">突发重连配对表</a> · <a href="/thresholds">校准阈值</a> · <a href="/sha">SHA-256</a></p>
</main>
<script>
const el=id=>document.getElementById(id);
const names={PREFLIGHT:"核验封存参考和评分",STARTING_WSL:"准备隔离采集",
RECORDING_CALIBRATION:"录制正常校准批次",CALIBRATING:"核对请求并封存三组阈值",
READY_FOR_HOLDOUT:"校准阈值已封存",RECORDING_HOLDOUT:"录制独立正常留出批次",
SCORING_HOLDOUT:"固定阈值评价与逐文件验收",ACCEPTED:"实验已验收",
CALIBRATION_PAUSED:"评分暂停 · WSL 服务仍在等待",HOLDOUT_SCORING_PAUSED:"留出评分暂停",STOP:"实验已停止"};
async function update(){
  try{
    const x=await(await fetch("/state",{cache:"no-store"})).json(), c=x.capture||{};
    const stage=["STARTING_WSL","READY_FOR_HOLDOUT"].includes(x.stage)&&c.stage?.startsWith("RECORDING")?c.stage:x.stage;
    el("stage").textContent=(names[stage]||stage)+(x.error?" · "+x.error:"");
    el("elapsed").textContent=stage.startsWith("RECORDING")?(c.elapsed_seconds||0).toFixed(0)+" / "+(c.duration_seconds||3600)+" 秒（已采到原帧）":"";
    el("bar").value=stage.startsWith("RECORDING")?c.elapsed_seconds||0:0;
    el("frames").textContent=c.packets?.toLocaleString()??"—";
    el("cal").textContent=x.calibration?"已封存 · "+x.calibration.calibration_connections+" 条校准连接 · 上限 "+x.calibration.max_fp+" 条误报":"待封存";
    el("disk").textContent=(x.free/1073741824).toFixed(2)+" GiB";
    el("results").hidden=x.stage!=="ACCEPTED";
  }catch{el("stage").textContent="等待进度文件";}
}
update();setInterval(update,6000);
</script></html>"""


def get(name):
    try:
        with open_shared(OUT/name) as stream:
            return json.load(stream)
    except FileNotFoundError:
        return None


class View(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.path=="/":
            body=PAGE.encode("utf8")
            mime="text/html"
        elif self.path=="/state":
            s=get("RUN_STATUS.json") or dict(stage="PREFLIGHT")
            fail=get("COLLECTION_FAILURE.json")
            if fail and s["stage"]!="ACCEPTED":
                s.update(stage="STOP",error=fail["error"])
            s.update(capture=get("COLLECTION_PROGRESS.json"),calibration=get("CALIBRATION_READY.json"),
                     free=shutil.disk_usage(OUT).free)
            body=json.dumps(s,ensure_ascii=False).encode("utf8")
            mime="application/json"
        else:
            allowed={"/summary":"RESULTS_FOR_PAPER.md","/paired":"PAIRED.csv","/stress":"STRESS_PAIRED.csv",
                     "/thresholds":"THRESHOLDS.csv","/sha":"SHA256SUMS","/qualification":"ATTACK_QUALIFICATION.csv",
                     "/flood":"ORIGINAL_FLOOD_CHECK.csv"}
            name=allowed.get(self.path)
            if not name or not (OUT/name).is_file():
                self.send_error(404)
                return
            with open_shared(OUT/name) as stream:
                body=stream.read()
            mime="text/plain"
        self.send_response(200)
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Type",mime+"; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__=="__main__":
    ThreadingHTTPServer(("127.0.0.1",PORT),View).serve_forever()
