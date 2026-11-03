"""New explicit authorization: one request each for unfinished dates; no auto retry."""
import hashlib
import http.client
import http.cookiejar
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import legacy_normal_supplement_audit_v1 as audit
from legacy_normal_supplement_acquire_v1 import ROOT, RESEARCH, BASE, MAGICS, dump

RUN=ROOT/'runs/legacy_normal_supplement_completion_v2_20260917'
PRIOR=ROOT/'runs/legacy_normal_supplement_acquisition_v1_20260917'
CAP=8589934592


def publish(s):
    s['updated_epoch']=time.time()
    dump(RUN/'status.json',s)
    a=json.loads((RUN/'audit_status.json').read_text(encoding='utf-8')) if (RUN/'audit_status.json').exists() else {}
    text=(f"# 剩余两天获取状态\n\n更新时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
          f"状态：{s['status']}；当前文件：{s.get('file','')}\n\n"
          f"完整文件：{s['completed_files']}/7；新增核验：{s['new_audits_completed']}/2\n\n"
          f"累计预算核算：{s['budget_charged_bytes']:,}/{CAP:,} 字节（包括前次失败预留）\n\n"
          f"本文件已保存：{s.get('current_saved_bytes',0):,} 字节\n\n"
          f"核验阶段：{a.get('stage','')}；已处理包：{a.get('packets',0):,}\n\n"
          f"停止原因：{s.get('reason','')}\n\n"
          "前五天复用封存结果；本次每个剩余文件只请求一次，无自动重试、特征或训练。\n")
    tmp=RUN/'PROGRESS.md.tmp';tmp.write_text(text,encoding='utf-8');tmp.replace(RUN/'PROGRESS.md')


def receive(response,fout,remaining,state,callback):
    digest=hashlib.sha256();size=0;prefix=b''
    while size<remaining:
        request_bytes=min(262144,remaining-size)
        # If a read fails, retain an upper budget bound even if internal bytes are lost.
        state['pending_read_charge']=request_bytes
        try:
            block=response.read(request_bytes)
        except http.client.IncompleteRead as exc:
            partial=exc.partial
            if len(partial)>request_bytes:raise RuntimeError('HTTP partial exceeds request budget')
            fout.write(partial);size+=len(partial)
            state['current_saved_bytes']=size
            state['failed_read_unsaved_reserve']=request_bytes-len(partial)
            state['pending_read_charge']=0
            raise
        if len(block)>request_bytes:raise RuntimeError('Response exceeded requested body length')
        state['pending_read_charge']=0
        if not block:
            if prefix not in MAGICS:raise RuntimeError('Invalid or empty capture body')
            return size,digest.hexdigest()
        fout.write(block);digest.update(block);size+=len(block)
        prefix=(prefix+block)[:4]
        state['current_saved_bytes']=size
        callback(size)
        if len(prefix)==4 and prefix not in MAGICS:raise RuntimeError('Response is not a PCAP')
    raise RuntimeError('Byte budget exhausted; EOF not established; partial retained')


def main():
    if (RUN/'execution_started.json').exists():raise RuntimeError('Continuation already attempted; no automatic retry')
    manifest=json.loads((RUN/'authorization.json').read_text(encoding='utf-8'))
    scope=json.loads((RESEARCH/'proposed_acquisition_scope.json').read_text(encoding='utf-8'))
    used=manifest['prior_conservative_charge_bytes']
    state=dict(status='REGISTERING',completed_files=5,new_audits_completed=0,budget_charged_bytes=used,
               prior_charge_bytes=used,file='',reason='',current_saved_bytes=0,automatic_retries=0,
               new_explicit_attempt_on_previously_failed_file=True,model_calls=0)
    dump(RUN/'execution_started.json',dict(started_epoch=time.time(),script_sha256=audit.old.sha(Path(__file__))))
    publish(state)
    try:
        identity=json.loads(sys.stdin.readline())
        jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        opener.addheaders=[('User-Agent','Mozilla/5.0'),('Accept-Encoding','identity')]
        with opener.open(BASE,timeout=60) as response:
            html=response.read(400000).decode('utf-8','replace')
        if 'action="insert.php"' not in html:raise RuntimeError('Official registration action changed')
        request=urllib.request.Request(BASE+'insert.php',data=urllib.parse.urlencode(identity).encode('utf-8'))
        with opener.open(request,timeout=60) as response:response.read(400000)
        del identity,request
        for index in (5,6):
            item=scope['files'][index]
            attempt=RUN/('%02d_attempt.json'%index)
            if attempt.exists():raise RuntimeError('Duplicate attempt forbidden')
            state.update(status='CONNECTING',file=item['file'],current_saved_bytes=0,pending_read_charge=0,failed_read_unsaved_reserve=0)
            remaining=CAP-used
            if remaining<=0:raise RuntimeError('No remaining cumulative budget')
            dump(attempt,dict(index=index,file=item,previous_charge=used,remaining_budget=remaining,
                              authorization_sha256=audit.old.sha(RUN/'authorization.json'),start_epoch=time.time()))
            publish(state)
            destination=RUN/'raw'/Path(item['file']).name
            partial=destination.with_suffix('.pcap.partial')
            if partial.exists() or destination.exists():raise RuntimeError('Refuse overwrite')
            tick=[0.0]
            def progress(n):
                state['budget_charged_bytes']=used+n
                if time.monotonic()-tick[0]>=5:
                    publish(state);tick[0]=time.monotonic()
            try:
                with opener.open(item['url'],timeout=60) as response:
                    headers={k.lower():v for k,v in response.headers.items() if k.lower() in ('content-type','content-length','content-disposition','transfer-encoding','etag','last-modified')}
                    dump(RUN/('%02d_headers.json'%index),dict(status=response.status,url=response.url,headers=headers))
                    if response.status!=200 or 'text/html' in headers.get('content-type','').lower():raise RuntimeError('HTTP/content mismatch')
                    if destination.name not in headers.get('content-disposition',''):raise RuntimeError('Attachment identity mismatch')
                    length=int(headers['content-length']) if 'content-length' in headers else None
                    if length is not None and length>remaining:raise RuntimeError('Declared file exceeds cumulative remaining budget')
                    state['status']='DOWNLOADING';publish(state)
                    with partial.open('xb') as fout:size,digest=receive(response,fout,remaining,state,progress)
                    if length is not None and size!=length:raise RuntimeError('Incomplete declared body')
                partial.replace(destination);used+=size
                dump(RUN/('%02d_receipt.json'%index),dict(file=item['file'],local_path=str(destination),bytes=size,sha256=digest,
                    transport_eof=True,completed_epoch=time.time(),source_published_hash_available=False))
            except BaseException:
                saved=partial.stat().st_size if partial.exists() else state['current_saved_bytes']
                reserve=state.get('failed_read_unsaved_reserve',0)
                if not reserve and state.get('pending_read_charge',0):
                    # Generic failures may hide internal body bytes; no further requests follow.
                    reserve=state['pending_read_charge']
                state['budget_charged_bytes']=min(CAP,used+saved+reserve)
                state['current_saved_bytes']=saved
                state['body_accounting']='Saved bytes plus conservative unfinished-read reserve'
                raise
            state.update(status='RAW_AUDIT',completed_files=index+1,budget_charged_bytes=used)
            publish(state)
            audit.RUN=RUN
            audit.audit(index)
            state['new_audits_completed']+=1
            publish(state)
        state.update(status='ACQUISITION_AND_RAW_AUDIT_COMPLETE',reason='')
        publish(state)
        print(json.dumps(state,ensure_ascii=False))
    except BaseException as exc:
        state.update(status='STOPPED_NO_AUTOMATIC_RETRY',reason=type(exc).__name__+': '+str(exc))
        publish(state)
        raise


if __name__=='__main__':main()
