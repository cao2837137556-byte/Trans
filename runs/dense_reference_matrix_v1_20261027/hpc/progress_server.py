"""Local read-only progress page. Serves a synced JSON cache, not HPC commands."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import read
from status_bridge import reconcile


def execution_scope(progress):
    stages = [item.get('name') if isinstance(item, dict) else item
              for item in progress.get('stages', [])]
    declared = progress.get('evaluation_scope')
    full = declared == 'FULL_MATRIX' or (declared != 'AUTHORIZED_STAGE_PREFIX_ONLY'
                                         and 'matrix' in stages)
    if full:
        return dict(evaluation_scope='FULL_MATRIX', matrix_included=True,
            scope_label='本作业包含正式目标矩阵',
            scope_message='执行顺序：私有环境 → 原104门禁与补编码 → 密源CAL → 正式目标矩阵。各阶段是否运行和完成以下方状态为准。')
    return dict(evaluation_scope='AUTHORIZED_STAGE_PREFIX_ONLY', matrix_included=False,
        scope_label='本次仅运行环境检查、补编码和密源CAL',
        scope_message='正式目标矩阵未运行；当前封存包仍缺第三池冻结证据。这里的完成只表示本次授权范围完成，不代表完整目标实验已完成。')


def view(cache, now=None):
    cache = Path(cache)
    sync = read(cache / 'sync.json') if (cache / 'sync.json').exists() else {}
    if not (cache / 'bundle.json').exists():
        if sync:
            return dict(status='UNKNOWN', label='尚未取得远端状态', terminal=False,
                job_id=sync.get('job_id'), transport=sync, heartbeat_required=True,
                scientific_status='尚未评价',
                message='同步程序尚未取得可信快照；不能据此判断实验是否在跑。',
                reason=sync.get('reason'), **execution_scope({}))
        return dict(status='NOT_SUBMITTED', label='尚未提交实验', terminal=False,
                    scientific_status='尚未评价',
                    message='实现与本地验收阶段；旧 BASE/CTX 完成页保持原记录。',
                    **execution_scope({}))
    bundle = read(cache / 'bundle.json')
    scheduler = bundle.get('scheduler') or {}
    result = reconcile(bundle.get('progress') or {}, scheduler)
    status = result.get('status', 'UNKNOWN')
    terminal = status in ('COMPLETE', 'EXCEPTION_STOP', 'BLOCKED')
    if not terminal:
        stamp = datetime.fromisoformat(bundle['observed_utc'])
        age = ((now or datetime.now(timezone.utc)) - stamp).total_seconds()
        if sync.get('status') != 'OK' or age > 90:
            status = 'UNKNOWN'
            result['reason'] = ('同步已停止：' + str(sync.get('reason')) if sync.get('status') == 'IDENTITY_STOP'
                                else '同步连接不可用或快照已过期；远端运行状态待确认。')
    labels = dict(COMPLETE='授权范围已完成', EXCEPTION_STOP='异常停止', BLOCKED='前置证据缺失',
                  QUEUED='已排队或正在准备计算资源',
                  STARTING='调度器已启动，等待实验启动回执',
                  RUNNING='正在运行', FINALIZING='计算阶段完成，等待调度器最终回执',
                  UNKNOWN='连接中断，远端状态待确认')
    result.update(status=status, label=labels.get(status, status), terminal=terminal,
                  job_id=bundle['job_id'], scheduler=scheduler, transport=sync,
                  heartbeat_required=not terminal, scientific_status=result.get('scientific_status', '尚未评价'))
    result.update(execution_scope(result))
    if status == 'COMPLETE' and not result['matrix_included']:
        result['label'] = '本次授权范围已完成（未运行目标矩阵）'
    return result


HTML = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Paper04 密参考实验</title>
<style>body{max-width:960px;margin:36px auto;padding:0 24px;font:16px/1.7 system-ui;color:#172b4d;background:#f3f6fa}section{background:white;border-radius:12px;padding:22px;margin:18px 0}h1{font-size:26px}.error{color:#b42318}li{margin:8px}pre{white-space:pre-wrap;font-size:13px}b{font-size:21px}</style>
<h1>Paper04 · 密参考入网验证</h1><section><b id="state">读取状态…</b><div id="summary"></div></section>
<section><strong id="scope">本次仅运行环境检查、补编码和密源CAL</strong>
<div id="scope-message">正式目标矩阵未运行；当前封存包仍缺第三池冻结证据。</div>
<ol id="stages"></ol><div id="stage-progress"></div><div id="reason" class="error"></div></section>
<section>页面自动读取普通后台程序同步的状态。科学未达标与运行异常分别显示；连接中断显示未知。完成记录保留，无需持续心跳。<details><summary>查看状态明细</summary><pre id="raw"></pre></details></section>
<script>const names={runtime:'私有环境与导入检查',encode:'原104门禁与补编码',source_cal:'密源CAL',matrix:'正式矩阵',preflight:'输入身份预检'},states={PENDING:'等待',RUNNING:'进行中',COMPLETE:'已完成',EXCEPTION_STOP:'异常停止'},science={NOT_EVALUATED:'尚未评价',SEE_RESULT:'查看阶段报告',FAIL:'科研未达标',PASS:'通过'};async function refresh(){try{const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error(r.status);const s=await r.json();document.getElementById('state').textContent=s.label;document.getElementById('scope').textContent=s.scope_label;document.getElementById('scope-message').textContent=s.scope_message;document.getElementById('summary').textContent='作业：'+(s.job_id||'未提交')+'　阶段：'+(names[s.stage]||s.stage||'准备中')+'　科研结果：'+(science[s.scientific_status]||s.scientific_status);document.getElementById('reason').textContent=s.reason||s.message||'';const list=document.getElementById('stages');list.replaceChildren();for(const x of s.stages||[]){const li=document.createElement('li');li.textContent=(names[x.name]||x.name)+'：'+(states[x.state]||x.state);list.append(li)}const p=s.stage_progress||{};let detail=p.stage?'当前子阶段：'+p.stage:'';if(Number.isFinite(p.completed)&&Number.isFinite(p.total)&&p.total>0)detail+='　'+p.completed.toLocaleString()+' / '+p.total.toLocaleString()+'（'+(100*p.completed/p.total).toFixed(1)+'%）';document.getElementById('stage-progress').textContent=detail;document.getElementById('raw').textContent=JSON.stringify(s,null,2)}catch(e){document.getElementById('state').textContent='本地状态服务不可用';document.getElementById('reason').textContent=String(e)}}refresh();setInterval(refresh,3000)</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True)
    parser.add_argument('--port', type=int, default=18770)
    args = parser.parse_args()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                data, mime = HTML.encode(), 'text/html; charset=utf-8'
            elif self.path == '/status':
                data, mime = json.dumps(view(args.cache), ensure_ascii=False).encode(), 'application/json'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *_):
            pass
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
