"""One fixed-A evaluation on the sealed AB inputs; no decoding or fitting."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import html
import json
import math
import os
import struct
import subprocess
import sys
import time
import traceback
from pathlib import Path
import issue27frontend_expanded_eval_support_v1 as s
from issue27frontend_inheritance_outer_control_v1 import Job,pid_alive
from issue27frontend_inheritance_n1_support_v1 import peak_memory

SOURCE=s.ROOT/'runs/frontend_expanded_eval_v2_20260910'
PACKAGE=s.ROOT/'runs/frontend_a_expanded_eval_implementation_v1_20260911'
REAL=s.ROOT/'runs/frontend_a_expanded_eval_v1_20260911'
CANDIDATE=s.ROOT/'runs/frontend_paired_train_v3_20260910/candidate_A.pt'
CANDIDATE_SHA='1dd82c0162ab9ae3db8acb7d11560bd52fc17e8d9beb05a2d74a939f79e77093'
STATE_SHA='8d11b770ab98c401e4d05359e34328d8c7fa4e56b4242c2e7211e53535e457a4'
SOURCE_SEAL='5e35e97dc681c718d4002b9777ecee855e1c66bc402f13ce411858691b44a7bb'
CAPS={'wall_seconds':1800,'memory_bytes':8*1024**3,'output_bytes':512*1024**2}
AUTH='2026-09-11 用户：行，动手吧，我授权，我睡午觉去了。希望起来能看到a模型结果好嘛。'
INT_FIELDS=('label','position','old_hard','old_missing','event_index','ab_hard','a_hard')
BOOL_FIELDS=('uid_in_ab_train','uid_in_ab_check','member_in_ab_train','member_in_ab_check',
             'context_in_ab_train','target_within_trained_prefix','context_in_ab_check','feature_prefix_seen_in_ab_train')


def load_rows(path):
    rows=[]
    for row in s.read_csv(path):
        for k in INT_FIELDS:
            if k in row:row[k]=int(row[k])
        for k in BOOL_FIELDS:
            if k in row:row[k]=bool(s.boolean(row[k]))
        for k in ('ab_logit','a_logit'):
            if k in row:
                row[k]=float(row[k]);s.require(math.isfinite(row[k]),'NONFINITE_LOGIT')
        rows.append(row)
    return rows


def compare(rows):
    return {'old_vs_A':s.metrics([{**t,'ab_hard':t['a_hard']} for t in rows]),
            'old_vs_AB':s.metrics(rows),
            'A_vs_AB':s.metrics([{**t,'old_hard':t['a_hard']} for t in rows])}


def validate_prediction(row,original):
    s.require(set(row)==set(original)|{'a_logit','a_hard'},'PREDICTION_SCHEMA')
    s.require(all(row[k]==v for k,v in original.items()),'BASELINE_ROW_CHANGED')
    s.require(math.isfinite(row['a_logit']) and row['a_hard']==int(row['a_logit']>=0),'A_HARD_RULE')


def prefix_hash(raw,event):
    return hashlib.sha256(b'F4_INPUT_V1\0'+struct.pack('<II',event+1,131)+raw[:(event+1)*524]).hexdigest()


def verify_manifest(folder,digest=None,check=lambda:None):
    if digest:s.require(s.sha_file(folder/'SHA256SUMS')==digest,'MANIFEST_IDENTITY')
    for line in (folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected,rel=line.split('  ',1)
        s.require(s.sha_file(folder/rel,check)==expected,'SEALED_FILE_DRIFT:'+rel)


def readiness():
    verify_manifest(PACKAGE)
    cfg=s.read_json(PACKAGE/'config.json');accept=s.read_json(PACKAGE/'acceptance.json')
    s.require(cfg['authorization']==AUTH and cfg['caps']==CAPS,'SCOPE')
    s.require(accept['status']=='PASS' and accept['config_sha256']==s.sha_file(PACKAGE/'config.json'),'ACCEPTANCE')
    for rel,h in cfg['code_pins'].items():s.require(s.sha_file(s.ROOT/rel)==h,'CODE_DRIFT:'+rel)
    for path,h in cfg['runtime_pins'].items():s.require(s.sha_file(path)==h,'RUNTIME_DRIFT')
    for rel,h in cfg['input_pins'].items():s.require(s.sha_file(s.ROOT/rel)==h,'INPUT_IDENTITY')
    for rel,h in cfg['unrelated_tracked_sha256'].items():s.require(s.sha_file(s.ROOT/rel)==h,'UNRELATED_CHANGED')
    s.require(Path(sys.executable).resolve()==s.PYTHON.resolve(),'PYTHON_PATH')
    git=cfg['git_path'];s.require(s.sha_file(git)==cfg['git_sha256'],'GIT_IDENTITY')
    s.require(subprocess.check_output([git,'rev-parse','HEAD'],cwd=s.ROOT,text=True).strip()==s.scope.HEAD,'HEAD')
    s.require(subprocess.check_output([git,'branch','--show-current'],cwd=s.ROOT,text=True).strip()=='codex/exp-mainline','BRANCH')
    s.require(s.sha_file(CANDIDATE)==CANDIDATE_SHA,'A_CHECKPOINT')
    return cfg


class Progress:
    def __init__(self,out,start):self.out=out;self.start=start;self.last=0;self.data={}
    def check(self,force=False,**values):
        self.data.update(values);now=time.monotonic()
        s.require(now-self.start<CAPS['wall_seconds']-10,'WALL_CAP')
        if force or now-self.last>=2:
            self.last=now;s.atomic_json(self.out/'progress.json',{**self.data,'elapsed_seconds':now-self.start,'updated_unix':time.time()})


def infer_contexts(model,contexts,baseline,source,progress,torch,np):
    seen=set();handles={};batches=0;events=0
    try:
        with torch.inference_mode():
            for start in range(0,len(contexts),32):
                batch=contexts[start:start+32];sequences=[]
                for c in batch:
                    if c['member_id'] not in handles:handles[c['member_id']]=(source/'members'/c['member_id']/'features.f32le').open('rb')
                    f=handles[c['member_id']];f.seek(c['offset']);raw=f.read(c['length']*524)
                    s.require(len(raw)==c['length']*524,'SHORT_INPUT')
                    for t in c['targets']:
                        o=baseline[t['uid']]
                        s.require(o['context_key']==c['key'] and o['event_index']==t['event'] and o['member_id']==c['member_id'],'INPUT_TARGET_JOIN')
                        s.require(prefix_hash(raw,t['event'])==t['feature_prefix_sha256']==o['feature_prefix_sha256'],'PREFIX_SHA')
                    sequences.append(torch.from_numpy(np.frombuffer(raw,dtype='<f4').copy().reshape(c['length'],131)))
                qs=model(sequences,[c['key'] for c in batch]);batches+=1
                for c,q in zip(batch,qs):
                    events+=c['length']
                    for t in c['targets']:
                        uid=t['uid'];s.require(uid not in seen,'DUPLICATE_TARGET');seen.add(uid)
                        value=float(q[t['event']]);s.require(math.isfinite(value),'NONFINITE_A')
                        baseline[uid].update(a_logit=value,a_hard=int(value>=0))
                progress.check(status='EVALUATING_A',targets_complete=len(seen),contexts_complete=start+len(batch),batches=batches)
    finally:
        for f in handles.values():f.close()
    s.require(seen==set(baseline),'PREDICTION_CONSERVATION')
    return batches,events


def worker(out,start):
    progress=Progress(out,start)
    try:
        progress.check(True,status='VERIFYING_REUSED_INPUTS',targets_complete=0)
        verify_manifest(SOURCE,SOURCE_SEAL,progress.check)
        prepared=s.read_json(SOURCE/'preparation_receipt.json')
        rows=load_rows(SOURCE/'predictions.csv.gz');s.validate_targets(rows)
        baseline={r['uid']:r for r in rows};contexts=[]
        for receipt in prepared['members']:
            offset=0
            with gzip.open(SOURCE/'members'/receipt['member_id']/'contexts.jsonl.gz','rt',encoding='utf-8') as f:
                for line in f:
                    c=json.loads(line);s.require(c['offset']==offset and 1<=c['length']<=256,'CONTEXT_LAYOUT')
                    c['member_id']=receipt['member_id'];contexts.append(c);offset+=c['length']*524
            s.require(offset==receipt['feature_bytes'],'MEMBER_BYTES')
        contexts.sort(key=lambda c:c['key'])
        s.require(len(contexts)==len({c['key'] for c in contexts})==57686,'CONTEXT_COUNT')
        targets=[t['uid'] for c in contexts for t in c['targets']]
        s.require(len(targets)==len(set(targets))==262050 and set(targets)==set(baseline),'TARGET_JOIN')
        for c in contexts:
            for t in c['targets']:s.require(0<=t['event']<c['length'],'TARGET_EVENT')
        s.atomic_json(out/'input_receipt.json',{'targets':262050,'contexts':57686,'feature_bytes':prepared['feature_bytes'],
                      'reused_source_manifest':SOURCE_SEAL,'all_source_hashes_verified':True,'raw_decodes':0})
        import numpy as np
        import torch
        import issue27frontend_paired_train_model_v1 as m
        m.configure();s.require(s.sha_file(CANDIDATE)==CANDIDATE_SHA,'CANDIDATE_BEFORE_LOAD')
        model=m.Student();model.load_state_dict(torch.load(CANDIDATE,map_location='cpu',weights_only=True),strict=True);model.eval()
        before=m.state_hash(model);s.require(before==STATE_SHA,'CANDIDATE_STATE')
        s.atomic_json(out/'candidate_before.json',{'state_sha256':before,'file_sha256':CANDIDATE_SHA})
        progress.check(True,status='EVALUATING_A');infer_start=time.monotonic()
        batches,events=infer_contexts(model,contexts,baseline,SOURCE,progress,torch,np)
        seconds=time.monotonic()-infer_start;after=m.state_hash(model);s.require(before==after,'MODEL_CHANGED')
        s.require(batches==1803 and events==548389,'FORWARD_COUNTS')
        s.atomic_json(out/'candidate_after.json',{'state_sha256':after})
        progress.check(True,status='WRITING_COMPARISON',targets_complete=262050)
        with gzip.open(out/'predictions.csv.gz','wt',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(sorted(rows,key=lambda t:t['uid']))
        s.atomic_json(out/'comparison.json',compare(rows))
        s.atomic_json(out/'worker_terminal.json',{'status':'A_EVALUATION_COMPLETE_PENDING_VERIFICATION','targets':262050,'contexts':57686,
                      'batches':batches,'events':events,'model_loads':1,'AB_model_loads':0,'optimizer_steps':0,'raw_decodes':0,'retries':0,
                      'inference_seconds':seconds,'predictions_sha256':s.sha_file(out/'predictions.csv.gz')})
        return 0
    except Exception as exc:
        (out/'failure_traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        s.atomic_json(out/'worker_terminal.json',{'status':'STOP','reason':type(exc).__name__+': '+str(exc),'retries':0})
        return 1


def validate(out):
    term=s.read_json(out/'worker_terminal.json')
    s.require(term['status']=='A_EVALUATION_COMPLETE_PENDING_VERIFICATION','WORKER_STATUS')
    for k,v in {'targets':262050,'contexts':57686,'batches':1803,'events':548389,'model_loads':1,'AB_model_loads':0,'optimizer_steps':0,'raw_decodes':0,'retries':0}.items():s.require(term[k]==v,'COUNTS:'+k)
    s.require(s.sha_file(out/'predictions.csv.gz')==term['predictions_sha256'],'PREDICTION_SHA')
    for name in ('candidate_before.json','candidate_after.json'):s.require(s.read_json(out/name)['state_sha256']==STATE_SHA,'STATE_CHANGED')
    old={r['uid']:r for r in load_rows(SOURCE/'predictions.csv.gz')};rows=load_rows(out/'predictions.csv.gz')
    s.validate_targets(rows);seen=set()
    for row in rows:
        s.require(row['uid'] in old and row['uid'] not in seen,'VALIDATION_UID');seen.add(row['uid'])
        validate_prediction(row,old[row['uid']])
    s.require(seen==set(old),'VALIDATION_CONSERVATION')
    recomputed=compare(rows);s.require(recomputed==s.read_json(out/'comparison.json'),'METRICS_RECOMPUTATION')
    original=s.read_json(SOURCE/'comparison.json')
    s.require(all(original[k]==v for k,v in recomputed['old_vs_AB'].items()),'EXISTING_AB_RESULT_DRIFT')
    s.atomic_json(out/'independent_verification.json',{'status':'PASS','targets':262050,'baseline_preserved':True,
                  'hard_rule':True,'metrics_recomputed':True,'model_unchanged':True,'new_forwards':0})
    return recomputed


def report(out,result):
    a=result['old_vs_A'];ab=result['old_vs_AB'];delta=result['A_vs_AB']
    rate=lambda v:'—' if v is None else '%.4f%%'%(v*100)
    lines=['# 固定A / AB扩大对照结果','', '**全部262,050目标完成，终态核验通过。**','',
           '| 指标 | 旧P2 | 新A | 新AB |','|---|---:|---:|---:|']
    for key,label in [('attack','攻击召回'),('future_query','future-query攻击召回')]:
        lines.append('| %s | %s | %s | %s |'%(label,rate(a[key]['old_recall']),rate(a[key]['ab_recall']),rate(ab[key]['ab_recall'])))
    ag={tuple(g['values']):g for g in a['groups'] if g['dimensions']==['pool']}
    for g in ab['groups']:
        if g['dimensions']==['pool'] and g['benign']:
            lines.append('| %s正常误报 | %s | %s | %s |'%(g['values'][0],rate(g['old_fpr']),rate(ag[tuple(g['values'])]['ab_fpr']),rate(g['ab_fpr'])))
    d=delta['attack'];lines+=['','A检出、AB漏检：%d条；A漏检、AB检出：%d条。'%(d['old_correct_new_wrong'],d['old_wrong_new_correct']),
        '本次只加载固定A模型一次，AB和旧P2结果复用；无重训、重新解码或阈值调整。',
        'A/AB同初始化、相同A训练呈现；差别为AB加入B监督。A/B不等于ID/OOD。',
        '这是历史暴露后的开发复评，不是新独立确认；旧严格继承FAIL保持，新设备入网未测试。',
        '旧missing行是零表示+missingflag经P2和冻结阈值产生判决，非硬编码报警。',
        'ID沿用既有检查151条FP0；未新增ID推理。完整分族/来源/输入可用性对照见comparison.json。','',
        '| 攻击族 | 分母 | 旧P2召回 | 新A召回 | 新AB召回 |','|---|---:|---:|---:|---:|']
    af={tuple(g['values']):g for g in a['groups'] if g['dimensions']==['attack_family']}
    for g in ab['groups']:
        if g['dimensions']==['attack_family'] and g['attacks']:
            lines.append('| %s | %d | %s | %s | %s |'%(g['values'][0],g['targets'],rate(g['old_recall']),rate(af[tuple(g['values'])]['ab_recall']),rate(g['ab_recall'])))
    (out/'result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def present(out,value):
    state=value.get('status','STARTING');n=value.get('targets_complete',0)
    names={'STARTING':'启动中','VERIFYING_REUSED_INPUTS':'核验复用输入','EVALUATING_A':'测试固定A模型',
           'WRITING_COMPARISON':'整理A/AB对照','VERIFYING_RESULTS':'核验完整结果','COMPLETE':'完成，结果核验通过','STOP':'已停止，请查看原因'}
    text='# 固定A扩大测试\n\n**%s**\n\n已测试：%s / 262,050；已运行 %.1f 分钟。\n\n%s\n\n结果：同目录 result.md。无训练、无重新解码、零重试。\n'%(names.get(state,state),format(n,','),value.get('elapsed_seconds',0)/60,value.get('reason') or '')
    tmp=out/'status.md.tmp';tmp.write_text(text,encoding='utf-8');os.replace(tmp,out/'status.md')
    tmp=out/'status.html.tmp';tmp.write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>A模型测试进度</title><pre style="font:20px system-ui;white-space:pre-wrap;margin:50px">'+html.escape(text)+'</pre>',encoding='utf-8');os.replace(tmp,out/'status.html')


def supervise(command=None,out=REAL):
    out.mkdir();started=time.monotonic();p=None;job=None;reason=None;peak=0
    s.atomic_json(out/'attempt.json',{'authorization':AUTH,'controller_pid':os.getpid(),'started_unix':time.time(),'caps':CAPS,'retries':0})
    s.atomic_json(out/'progress.json',{'status':'STARTING','targets_complete':0});present(out,{'status':'STARTING'})
    try:
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='2705',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',TORCH_FORCE_WEIGHTS_ONLY_LOAD='1')
        with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
            p=subprocess.Popen(command or [str(s.PYTHON),'-B',str(Path(__file__).resolve()),'worker'],cwd=s.ROOT,env=env,
                stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
            job=Job(p,CAPS['memory_bytes']-1536*1024**2)
            s.atomic_json(out/'worker_gate.json',{'pid':p.pid,'parent_pid':os.getpid(),'started':started})
            last=0
            while p.poll() is None:
                now=time.monotonic()
                if now-last>=2:
                    last=now;peak=max(peak,job.peak()+peak_memory())
                    s.require(peak<CAPS['memory_bytes'],'MEMORY_CAP');s.require(now-started<CAPS['wall_seconds']-10,'WALL_CAP')
                    s.require(sum(f.stat().st_size for f in out.rglob('*') if f.is_file())<CAPS['output_bytes'],'OUTPUT_CAP')
                    value=s.read_json(out/'progress.json');value['elapsed_seconds']=now-started;present(out,value)
                time.sleep(.25)
            peak=max(peak,job.peak()+peak_memory())
            if p.returncode!=0:
                term=s.read_json(out/'worker_terminal.json') if (out/'worker_terminal.json').exists() else {}
                raise RuntimeError(term.get('reason','WORKER_EXIT_'+str(p.returncode)))
    except Exception as exc:reason=type(exc).__name__+': '+str(exc)
    finally:
        if p is not None and p.poll() is None:
            if job:job.terminate()
            else:p.kill()
            p.wait(timeout=15)
        if job:job.close()
    if reason is None:
        try:
            present(out,{'status':'VERIFYING_RESULTS','targets_complete':262050,'elapsed_seconds':time.monotonic()-started})
            result=validate(out)
            s.require(time.monotonic()-started<CAPS['wall_seconds'] and peak_memory()<CAPS['memory_bytes'],'VALIDATION_RESOURCE_CAP')
            report(out,result)
        except Exception as exc:reason='VERIFICATION_'+type(exc).__name__+': '+str(exc)
    state={'status':'STOP' if reason else 'COMPLETE','verified':reason is None,'reason':reason,'retries':0,
           'targets_complete':262050 if reason is None else 0,'elapsed_seconds':time.monotonic()-started,
           'worker_exit_code':None if p is None else p.returncode,'aggregate_peak_bytes_upper_bound':max(peak,peak_memory()),
           'raw_decodes':0,'optimizer_steps':0}
    if reason:(out/'STOP.md').write_text('# 已停止\n\n'+reason+'\n\n没有完整有效结果，不自动重试。\n',encoding='utf-8')
    s.atomic_json(out/'supervisor_terminal.json',state);present(out,state);s.seal(out)
    return state


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['readiness','run','worker','status']);args=parser.parse_args()
    if args.mode=='status':
        if not REAL.exists():print('NOT_STARTED');return
        path=REAL/'supervisor_terminal.json'
        if path.exists():print(json.dumps({**s.read_json(path),'sealed':(REAL/'SHA256SUMS').exists()},ensure_ascii=False));return
        attempt=s.read_json(REAL/'attempt.json')
        print(json.dumps(s.read_json(REAL/'progress.json') if pid_alive(attempt['controller_pid']) else {'status':'INTERRUPTED_DO_NOT_RESTART'},ensure_ascii=False));return
    if args.mode=='worker':
        deadline=time.monotonic()+30
        while not (REAL/'worker_gate.json').exists():s.require(time.monotonic()<deadline,'GATE_TIMEOUT');time.sleep(.05)
        gate=s.read_json(REAL/'worker_gate.json');s.require(gate['pid']==os.getpid() and gate['parent_pid']==os.getppid(),'GATE')
        readiness();raise SystemExit(worker(REAL,gate['started']))
    readiness();s.require(not REAL.exists(),'ONE_ATTEMPT_ALREADY_EXISTS')
    if args.mode=='readiness':print('READY_FOR_AUTHORIZED_A_EVALUATION');return
    print(json.dumps(supervise(),ensure_ascii=False))


if __name__=='__main__':main()
