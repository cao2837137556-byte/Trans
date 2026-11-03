"""Local read-only Codex panel, safe to refresh while delivery is working."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
HTML='''<!doctype html><meta charset="utf-8"><title>C4 实验进度</title>
<style>body{font:16px/1.65 system-ui;background:#101820;color:#e4ecec;margin:32px;max-width:940px}h1{font-size:26px}section{background:#1b2832;padding:22px;border-radius:14px;margin:18px 0}small{color:#9caeb5}strong{color:#8ce4cd}progress{width:100%;height:20px}pre{white-space:pre-wrap;font-size:13px}#error{color:#ffa58f}</style>
<h1>C4 · 降低逐样本误报</h1><small>固定旧模型、阈值和 λ；补充历史正常参考；只验收一次。</small>
<section><strong id="stage">等待进度</strong><p id="detail"></p><progress id="bar" hidden></progress><p id="job"></p><p id="error"></p><small id="updated"></small></section>
<section>流程：上传 → 超算环境核验 → 超算选点和编码 → 历史校准门 → 一次 A/B → 独立验收。<br>基线：B 逐样本误报 <strong>11.4099%（8,494 / 74,444）</strong>；组件加权误报 1.7505%。<br>资源：4 CPU / 8 GiB；计算总时限 8 小时，距离对上限 10 亿。<br>目标 2% 单独报告；必须通过攻击保护和正常零回退，且逐样本误报严格改善才采纳。</section>
<section id="result" hidden></section><small>这是一轮作业的自动进度页。连接中断会明确显示，不会自动重跑实验。A/B 已作为开发集使用。</small>
<script>const labels={UPLOADING:'正在上传已有材料',INSTALLING:'正在安装本轮独立交付包',PREFLIGHT:'正在核验超算环境及输入校验值',SUBMITTING:'正在提交作业',HPC_RUNNING:'超算作业进行中',HPC_CONNECTION_INTERRUPTED:'进度连接中断，作业状态待恢复',RETRIEVING:'正在取回并校验编码',LOCAL_EVALUATION:'历史校准门及单次 A/B 验收',INDEPENDENT_VERIFICATION:'独立复核保存的结果数组',COMPLETE:'本轮已结束',STOPPED:'已停止，保留现场等待修复'};
const phases={STARTING:'正在初始化',INPUT_IDENTITY:'核验本台设备原包及时间角色',CHRONOLOGICAL_COPY:'按时间顺序整理原始包',ENDPOINT_CENSUS:'第一遍扫描：登记全部合法物理包',DETERMINISTIC_SELECTION:'按固定规则选取新增参考',SELECTED_SNAPSHOTS:'第二遍扫描：提取选中包的上下文',HISTORY_E3:'使用冻结模型编码正常点',PASS_1:'第一遍扫描',PASS_2:'第二遍提取',ENCODING:'编码选中的正常点',DEV_HEAD_SCORING:'冻结检测头打分',B_SUPPORT:'B 池参考支持计算',HIST_DEV_SUPPORT:'历史校准支持计算'};
async function tick(){try{let s=await(await fetch('/state',{cache:'no-store'})).json();document.getElementById('stage').textContent=labels[s.stage]||s.stage||'等待启动';let w=s.worker||{};let text='';let b=document.getElementById('bar');b.hidden=true;
if(s.total_bytes){text=s.file+' · '+(s.done_bytes/2**30).toFixed(2)+' / '+(s.total_bytes/2**30).toFixed(2)+' GiB · '+((s.bytes_per_second||0)/2**20).toFixed(2)+' MiB/s';b.hidden=false;b.max=s.total_bytes;b.value=s.done_bytes;}else{text=(phases[w.phase]||w.phase||s.scheduler||'')+' '+(w.device||w.member||'');let n=w.done??w.completed??w.raw_packets;if(n!=null&&w.total){text+=' · '+n+' / '+w.total;b.hidden=false;b.max=w.total;b.value=n;}if(w.elapsed_seconds!=null)text+=' · 已计算 '+(w.elapsed_seconds/60).toFixed(1)+' 分钟';}
document.getElementById('detail').textContent=text;document.getElementById('job').textContent=s.job_id?'超算作业号：'+s.job_id:'';document.getElementById('error').textContent=s.error||s.network_error||'';document.getElementById('updated').textContent='更新时间：'+(s.updated_beijing||'');
if(s.result){let r=s.result;let el=document.getElementById('result');el.hidden=false;el.textContent='科学结论：'+r.status+(r.new_sample_fpr!=null?'；B 逐样本误报 '+(100*r.new_sample_fpr).toFixed(4)+'%（'+r.new_fp+'/'+r.normal_rows+'）':'；历史校准门未通过，未进行 A/B。');}}
catch(e){document.getElementById('error').textContent='本地进度暂不可读：'+e.message;}}tick();setInterval(tick,5000);</script>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path not in ('/','/state'):self.send_error(404);return
        if self.path=='/':data=HTML.encode();kind='text/html; charset=utf-8'
        else:
            try:data=(HERE/'PROGRESS.json').read_bytes()
            except FileNotFoundError:data=b'{}'
            kind='application/json'
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',18789),Handler).serve_forever()
