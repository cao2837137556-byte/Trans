"""Read-only local progress; no job actions from the browser."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
HERE=Path(__file__).resolve().parent
HTML='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Edge v2 · Linux工程验证</title>
<style>body{font:16px/1.7 system-ui;background:#101920;color:#e7eff1;max-width:960px;margin:28px auto;padding:0 24px}section{background:#1c2933;padding:22px;border-radius:14px;margin:18px 0}h1{font-size:26px}strong{color:#8de3cb}small{color:#adbdc5}progress{width:100%;height:20px}.err{color:#ffaf98}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}</style>
<h1>Edge v2 · Linux工程验证</h1><small>1 CPU · 8 GiB · 最长2小时；排队时间另计。仅一次作业，不自动重投。</small>
<section><strong id="stage">准备交付</strong><p id="message"></p><progress id="bar" hidden></progress><p id="detail"></p><p id="job"></p><p id="worker"></p><p class="err" id="error"></p><small id="updated"></small></section>
<section>验证流程：依赖与运行时核验 → 完整角色因果重放 → 73种形状编码计时 → 真实中断恢复 → 源CAL一致性及合成距离 → 取回验收。<br>模型与完整数组保留超算；此轮不产生正式外部检测成绩。</section>
<section><strong>当前预算与停止规则</strong><p>内存8 GiB；节点临时盘启动时至少空闲32 GiB，scratch和持久输出各24 GiB守卫。超时或越限停止并保留已提交检查点。只有当前轮次回执及调度终态均通过才显示验收通过。</p></section>
<small>普通程序自动刷新，无需助手持续监测。连接中断会明确显示；页面不会重新提交作业。</small>
<script>const labels={LOCAL_CHECK:'核验交付文件',WAITING_CONNECTION:'等待现有超算通道',UPLOADING:'上传v2增量',PREPARING:'核验依赖、原包和运行时',SUBMITTING:'提交唯一一次工程验证',SUBMITTED:'已提交，等待调度',RUNNING:'Linux工程验证运行中',RETRIEVING:'取回小型验收回执',PASS:'Linux工程验证已验收通过',STOP:'已停止，现场保留',CONNECTION_INTERRUPTED:'进度通道中断',OBSERVATION_ENDED:'自动观察窗口结束'};
async function tick(){try{const s=await(await fetch('/state',{cache:'no-store'})).json();document.querySelector('#stage').textContent=labels[s.stage]||s.stage||'准备交付';document.querySelector('#message').textContent=s.message||'';const b=document.querySelector('#bar');b.hidden=!s.total_bytes;if(s.total_bytes){b.max=s.total_bytes;b.value=s.done_bytes||0}document.querySelector('#detail').textContent=s.total_bytes?((s.done_bytes||0)/2**20).toFixed(1)+' / '+(s.total_bytes/2**20).toFixed(1)+' MiB':(s.scheduler_state||'');document.querySelector('#job').textContent=s.job_id?'作业号：'+s.job_id:'';let w=s.worker||{},r=w.replay||w;document.querySelector('#worker').textContent=[w.stage,r.role?'角色 '+r.role:'',r.frame?'第 '+r.frame+' 帧':'',r.selected_persisted?'已保存 '+r.selected_persisted+' 端点':'',w.completed_shapes?'编码形状 '+w.completed_shapes+'/'+w.total_shapes:'',w.max_tree_rss_bytes?'观测RSS '+(w.max_tree_rss_bytes/2**30).toFixed(2)+' GiB':'',s.attempt_id?'轮次 '+s.attempt_id:''].filter(Boolean).join(' · ');document.querySelector('#error').textContent=s.error||'';document.querySelector('#updated').textContent='更新时间：'+(s.updated_utc||'');}catch(e){document.querySelector('#error').textContent='本地进度暂不可读'}}tick();setInterval(tick,4000);</script></html>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path not in ('/','/state'):self.send_error(404);return
        if self.path=='/':data=HTML.encode();kind='text/html; charset=utf-8'
        else:data=(HERE/'PROGRESS.json').read_bytes() if (HERE/'PROGRESS.json').exists() else b'{}';kind='application/json'
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',18793),Handler).serve_forever()
