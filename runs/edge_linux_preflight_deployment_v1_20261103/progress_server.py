"""Read-only local progress panel. It never contacts HPC or starts work."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Edge · Linux 预检</title>
<style>body{font:16px/1.65 system-ui;background:#101920;color:#e7eff1;margin:30px auto;padding:0 24px;max-width:920px}h1{font-size:27px}section{background:#1c2933;padding:22px;border-radius:14px;margin:18px 0}small{color:#adbdc5}strong{color:#8de3cb}progress{width:100%;height:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.err{color:#ffaf98}</style>
<h1>Edge · Linux 真实切片预检</h1><small>本次仅检查工程链路与运行时，不启动正式外部测试。</small>
<section><strong id="stage">等待启动</strong><p id="message"></p><progress id="bar" hidden></progress><p id="detail"></p><p id="job"></p><p class="err" id="error"></p><small id="updated"></small></section>
<section>流程：校验本地材料 → 上传并核验 → 提交一次预检 → 取回核验。<br>预检上限：1 CPU / 6 GiB / 10 分钟；78 个切片端点＋13 次单行探针＝91 个逻辑端点。<br>超算连接由用户手动建立；程序复用已有通道，不自动重连、不自动重投。</section>
<section id="result" hidden></section><small>进度由普通程序更新，无需助手持续监测。排队时间另计；只有取回完整回执并通过严格门后才显示 Linux 预检通过。</small>
<script>const labels={LOCAL_PIN_CHECK:'核验本地文件',WAITING_FOR_RECEIVER:'等待超算交付通道',WAITING_FOR_USER_BOOTSTRAP:'等待你执行超算单行命令',UPLOADING:'上传预检材料',PREPARING_REMOTE:'远端核验与独立解包',SUBMITTING:'正在提交唯一一次预检',SUBMITTED:'预检已提交',HPC_PREFLIGHT:'Linux 预检排队或运行中',CONNECTION_INTERRUPTED:'进度连接中断',RETRIEVING:'取回预检结果',LINUX_PREFLIGHT_PASS:'Linux 预检通过',PREFLIGHT_STOPPED:'预检已停止，现场已保存',STOPPED:'交付停止，未自动重试',OBSERVATION_WINDOW_ENDED:'自动取回窗口结束'};
async function tick(){try{let s=await(await fetch('/state',{cache:'no-store'})).json();document.getElementById('stage').textContent=labels[s.stage]||s.stage||'等待启动';document.getElementById('message').textContent=s.message||'';let b=document.getElementById('bar');b.hidden=!s.total_bytes;if(s.total_bytes){b.max=s.total_bytes;b.value=s.done_bytes||0}let w=s.worker||{};document.getElementById('detail').textContent=s.total_bytes?((s.done_bytes||0)/2**20).toFixed(1)+' / '+(s.total_bytes/2**20).toFixed(1)+' MiB'+(s.bytes_per_second?' · '+(s.bytes_per_second/2**20).toFixed(2)+' MiB/s':''):(s.file||w.stage||w.phase||s.scheduler||'');document.getElementById('job').textContent=s.job_id?'超算作业号：'+s.job_id:'';document.getElementById('error').textContent=s.error||s.network_error||s.remote_error||'';document.getElementById('updated').textContent='更新时间：'+(s.updated_utc||'');if(s.result){let el=document.getElementById('result');el.hidden=false;el.textContent=s.result.linux_actual_preflight_pass?'Linux 真实切片、严格形状探针与最终回执核验通过。完整续跑与正式评价仍需后续准备。':'预检未通过：'+(s.result.delivery_status||'结果待查')+'。不会自动放宽门或重投。'}}catch(e){document.getElementById('error').textContent='本地进度暂不可读：'+e.message}}tick();setInterval(tick,4000);</script></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path not in ('/', '/state'):
            self.send_error(404)
            return
        if self.path == '/':
            payload = HTML.encode('utf-8')
            content_type = 'text/html; charset=utf-8'
        else:
            try:
                payload = (HERE / 'PROGRESS.json').read_bytes()
            except FileNotFoundError:
                payload = b'{}'
            content_type = 'application/json; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18791)
    args = parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
