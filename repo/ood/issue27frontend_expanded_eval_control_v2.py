"""V2 startup correction: pinned direct Git, unchanged frozen evaluation."""
from __future__ import annotations
import argparse
import html
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import issue27frontend_expanded_eval_support_v1 as s
from issue27frontend_inheritance_outer_control_v1 import Job,pid_alive
from issue27frontend_inheritance_n1_support_v1 import peak_memory

REAL=s.ROOT/'runs/frontend_expanded_eval_v2_20260910'
FIX=s.ROOT/'runs/frontend_expanded_eval_startup_diagnosis_v2_20260910'
DIRECT_GIT=Path('C:/Program Files/Git/mingw64/bin/git.exe')
DIRECT_GIT_SHA='fc0f1cae1304fcdcf4d0749f421c5ed21471efc856301f92f56d4b844be84363'


def verify_correction():
    receipt=s.read_json(FIX/'acceptance.json')
    s.require(receipt['status']=='PASS','V2_ACCEPTANCE')
    for line in (FIX/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        digest,rel=line.split('  ',1)
        s.require(s.sha_file(FIX/rel)==digest,'V2_SEAL')
    for rel,h in receipt['code_pins'].items():
        s.require(s.sha_file(s.ROOT/rel)==h,'V2_CODE_DRIFT:'+rel)
    s.require(s.sha_file(DIRECT_GIT)==DIRECT_GIT_SHA,'DIRECT_GIT_IDENTITY')



def readiness():
    verify_correction()
    config=s.read_json(s.PACKAGE/'config.json')
    require=s.require
    require(config['authorization']==s.AUTH and config['caps']==s.CAPS,'CONFIG_AUTH_OR_CAPS')
    for line in (s.PACKAGE/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        digest,rel=line.split('  ',1)
        require(s.sha_file(s.PACKAGE/rel)==digest,'PACKAGE_SEAL:'+rel)
    accept=s.read_json(s.PACKAGE/'synthetic_acceptance.json')
    require(accept['status']=='PASS' and accept['tests_passed']==accept['tests_run'] and accept['tests_run']>=8,'SYNTHETIC_ACCEPTANCE')
    require(accept['config_sha256']==s.sha_file(s.PACKAGE/'config.json'),'ACCEPTANCE_CONFIG')
    for rel,h in config['code_pins'].items():require(s.sha_file(s.ROOT/rel)==h,'SOURCE_DRIFT:'+rel)
    for path,h in config['runtime_pins'].items():require(s.sha_file(path)==h,'RUNTIME_DRIFT:'+Path(path).name)
    require(Path(sys.executable).resolve()==s.PYTHON.resolve(),'PYTHON_PATH')
    require(s.sha_file(s.PACKAGE/'targets.csv.gz')==config['targets_sha256'],'TARGETS_SHA')
    require(s.sha_file(s.ROOT/config['candidate_path'])==config['candidate_file_sha256'],'AB_SHA')
    archive=Path(config['archive']);st=archive.stat()
    require(st.st_size==config['archive_bytes'] and st.st_mtime_ns==config['archive_mtime_ns'],'RAW_ARCHIVE_CHANGED')
    require(s.read_json(s.PACKAGE/'archive_identity.json')['sha256']==config['archive_sha256'],'ARCHIVE_RECEIPT')
    require(s.sha_file(config['tshark']['executable_path'])==config['tshark']['executable_sha256'],'DECODER_SHA')
    require(shutil.disk_usage(s.ROOT).free>=config['caps']['minimum_free_bytes'],'FREE_DISK')
    require(subprocess.check_output([str(DIRECT_GIT),'rev-parse','HEAD'],cwd=s.ROOT,text=True).strip()==config['head'],'HEAD_DRIFT')
    require(subprocess.check_output([str(DIRECT_GIT),'branch','--show-current'],cwd=s.ROOT,text=True).strip()=='codex/exp-mainline','BRANCH_DRIFT')
    return config


def status(out=REAL):
    if not out.exists():return {'status':'NOT_STARTED','final':False}
    terminal=out/'supervisor_terminal.json'
    if terminal.exists():
        value=s.read_json(terminal)
        return {**value,'final':(out/'SHA256SUMS').exists()}
    attempt=s.read_json(out/'attempt.json')
    if not pid_alive(attempt['controller_pid']):return {'status':'INTERRUPTED_DO_NOT_RESTART','final':False}
    path=out/'progress.json'
    return {**(s.read_json(path) if path.exists() else {'status':'STARTING'}),'final':False}


def present(out,value):
    stages={'STARTING':'启动中','LOADING_QUALIFIED_TARGETS':'加载已核定名单',
            'DISCOVERING_TARGET_ROUTES':'准备输入：定位目标上下文','MATERIALIZING_F4_PREFIXES':'准备输入：提取流量特征',
            'VERIFYING_PREPARED_INPUTS':'核验全部输入','EVALUATING_FIXED_AB':'测试固定AB模型',
            'WORKER_COMPLETE_PENDING_VERIFICATION':'测试结束，核验结果中','VERIFYING_RESULTS':'核验结果中',
            'FIXED_AB_EXPANDED_DEVELOPMENT_EVALUATION_COMPLETE':'测试完成，结果已核验',
            'INPUT_OR_EXECUTION_STOP':'已停止，请查看原因','INTERRUPTED_DO_NOT_RESTART':'运行中断，禁止自动重启'}
    name=stages.get(value.get('status'),value.get('status','等待状态'))
    lines=['# 新模型扩大测试进度','', '**'+name+'**','',
           '- 已准备成员：%s / 40'%value.get('members_complete',0),
           '- 输入处理包数：%s / 46,297,382（两遍处理）'%format(value.get('decoder_packets',0),','),
           '- 已测试目标：%s / 262,050'%format(value.get('targets_complete',0),','),
           '- 运行时间：%.1f分钟'%(value.get('elapsed_seconds',0)/60),
           '- 自动重试：0']
    if value.get('reason'):lines+=['','停止原因：'+str(value['reason'])]
    if value.get('member'):lines+=['','当前文件：`'+value['member']+'`']
    if value.get('status')=='FIXED_AB_EXPANDED_DEVELOPMENT_EVALUATION_COMPLETE':
        lines+=['','[查看测试结果](%s)'%(out/'result.md').as_posix()]
    lines+=['','这是固定模型的开发复评，不包含重新训练。','']
    temp=out/'status.md.tmp';temp.write_text('\n'.join(lines),encoding='utf-8');os.replace(temp,out/'status.md')
    body='<h1>新模型扩大测试</h1><h2>'+html.escape(name)+'</h2>'
    body+='<p>输入处理：{:,} / 46,297,382 包 · 成员 {} / 40</p>'.format(value.get('decoder_packets',0),value.get('members_complete',0))
    body+='<p>模型测试：{:,} / 262,050 条</p>'.format(value.get('targets_complete',0))
    body+='<p>运行 {:.1f} 分钟 · 自动重试 0 次</p>'.format(value.get('elapsed_seconds',0)/60)
    if value.get('reason'):body+='<p>'+html.escape(str(value['reason']))+'</p>'
    body+='<p>完整结果保存于同目录 result.md；终态以 supervisor_terminal.json 为准。</p>'
    text='<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>扩大测试状态</title><style>body{font:18px system-ui;max-width:850px;margin:70px auto;padding:24px;background:#f4f7fa;color:#132d40}h2{color:#176b66}</style>'+body
    temp=out/'status.html.tmp';temp.write_text(text,encoding='utf-8');os.replace(temp,out/'status.html')


def validate_results(config,out):
    term=s.read_json(out/'worker_terminal.json')
    s.require(term['status']=='FIXED_AB_EXPANDED_DEVELOPMENT_EVALUATION_COMPLETE','WORKER_NOT_COMPLETE')
    prepared=s.read_json(out/'preparation_receipt.json');inference=s.read_json(out/'inference_receipt.json')
    s.require(prepared['targets']==inference['targets']==262050 and prepared['decoder_packets']==46297382 and prepared['decoder_calls']==80,'TERMINAL_COUNTS')
    s.require(inference['optimizer_steps']==inference['teacher_forwards']==inference['retries']==0 and inference['model_loads']==1,'FORBIDDEN_ACTIONS')
    for name in ('candidate_before.json','candidate_after.json'):
        s.require(s.read_json(out/name)['state_sha256']==config['candidate_state_sha256'],'MODEL_CHANGED')
    s.require(s.sha_file(out/'predictions.csv.gz')==inference['predictions_sha256'],'PREDICTIONS_SHA')
    metadata={t['uid']:t for t in s.read_csv(s.PACKAGE/'targets.csv.gz')}
    rows=[];seen=set()
    int_fields=('label','position','old_hard','old_missing','event_index','ab_hard')
    bool_fields=('uid_in_ab_train','uid_in_ab_check','member_in_ab_train','member_in_ab_check','context_in_ab_train',
                 'target_within_trained_prefix','context_in_ab_check','feature_prefix_seen_in_ab_train')
    for row in s.read_csv(out/'predictions.csv.gz'):
        uid=row['uid'];s.require(uid not in seen and uid in metadata,'RESULT_UID');seen.add(uid)
        original=metadata[uid]
        for k,v in original.items():s.require(str(row[k])==str(v),'RESULT_METADATA_DRIFT:'+k)
        for k in int_fields:row[k]=int(row[k])
        for k in bool_fields:row[k]=bool(s.boolean(row[k]))
        row['ab_logit']=float(row['ab_logit'])
        s.require(math.isfinite(row['ab_logit']) and row['ab_hard']==int(row['ab_logit']>=0),'RESULT_HARD_RULE')
        s.require(row['owner']==('B' if row['old_missing'] else 'A'),'OWNER_RULE')
        rows.append(row)
    s.require(seen==set(metadata),'RESULT_CONSERVATION');s.validate_targets(rows)
    recomputed=s.metrics(rows);saved=s.read_json(out/'comparison.json')
    for k,v in recomputed.items():s.require(saved[k]==v,'METRIC_RECOMPUTATION:'+k)
    s.require(len({r['context_key'] for r in rows})==prepared['contexts']==inference['contexts'],'CONTEXT_COUNTS')
    s.atomic_json(out/'independent_verification.json',{'status':'PASS','targets':262050,'metadata_identity':True,
                  'hard_rule':True,'metrics_recomputed':True,'model_state_unchanged':True,'new_model_forwards':0})
    pending=(out/'result_pending.md').read_text(encoding='utf-8')
    (out/'result.md').write_text(pending.replace('模型推理完成；终态核验尚未完成。','完整执行完成，终态核验通过。'),encoding='utf-8')
    return saved


def supervise(config,command=None,out=REAL,synthetic=False):
    out.mkdir();started=time.monotonic();process=None;job=None;peak=0;reason=None
    s.atomic_json(out/'attempt.json',{'controller_pid':os.getpid(),'started_unix':time.time(),'retries':0,
                  'authorization':config['authorization'],'new_attempt_authorization':config.get('new_attempt_authorization'),'synthetic':synthetic,'caps':config['caps']})
    s.atomic_json(out/'progress.json',{'status':'STARTING','elapsed_seconds':0})
    command=command or [str(s.PYTHON),'-B',str(Path(__file__).resolve()),'worker']
    try:
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='2705',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',TORCH_FORCE_WEIGHTS_ONLY_LOAD='1')
        with (out/'worker.stdout.log').open('xb') as stdout,(out/'worker.stderr.log').open('xb') as stderr:
            process=subprocess.Popen(command,cwd=s.ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
            job=Job(process,config['caps']['memory_bytes']-1536*1024**2)
            s.atomic_json(out/'worker_gate.json',{'pid':process.pid,'parent_pid':os.getpid(),'started':started})
            last=0
            while process.poll() is None:
                now=time.monotonic()
                if now-last>=2:
                    last=now;peak=max(peak,job.peak()+peak_memory())
                    if peak>config['caps']['memory_bytes']:reason='AGGREGATE_MEMORY_CAP'
                    if now-started>config['caps']['wall_seconds']-5:reason='WALL_CAP'
                    if sum(p.stat().st_size for p in out.rglob('*') if p.is_file())>config['caps']['output_bytes']-64*1024**2:reason='OUTPUT_CAP'
                    try:present(out,s.read_json(out/'progress.json'))
                    except (ValueError,OSError):pass
                if reason:job.terminate();break
                time.sleep(.25)
            process.wait(timeout=15);peak=max(peak,job.peak()+peak_memory())
        if not reason and process.returncode!=0:
            term=s.read_json(out/'worker_terminal.json') if (out/'worker_terminal.json').exists() else {}
            reason=term.get('reason','WORKER_EXIT_'+str(process.returncode))
    except Exception as exc:reason=type(exc).__name__+': '+str(exc)
    finally:
        if process is not None and process.poll() is None:
            if job:job.terminate()
            else:process.kill()
            process.wait(timeout=15)
        if job:job.close()
    result=None
    if not reason:
        try:
            s.atomic_json(out/'progress.json',{'status':'VERIFYING_RESULTS','decoder_packets':46297382,'members_complete':40,
                          'targets_complete':262050,'elapsed_seconds':time.monotonic()-started})
            present(out,s.read_json(out/'progress.json'))
            result=validate_results(config,out)
            s.require(time.monotonic()-started<config['caps']['wall_seconds'],'VERIFICATION_WALL_CAP')
            s.require(peak_memory()<config['caps']['memory_bytes'],'VERIFICATION_MEMORY_CAP')
        except Exception as exc:reason='VERIFICATION_'+type(exc).__name__+': '+str(exc)
    state={'status':'INPUT_OR_EXECUTION_STOP' if reason else 'FIXED_AB_EXPANDED_DEVELOPMENT_EVALUATION_COMPLETE',
           'reason':reason,'elapsed_seconds':time.monotonic()-started,'aggregate_peak_bytes_upper_bound':max(peak,peak_memory()),
           'worker_exit_code':None if process is None else process.returncode,'retries':0,
           'verified':not bool(reason),'targets_complete':262050 if not reason else 0,
           'members_complete':40 if not reason else 0,'decoder_packets':46297382 if not reason else 0,
           'independent_confirmation':False,'optimizer_steps':0,'teacher_forwards':0}
    if reason:
        if (out/'progress.json').exists():state['last_progress']=s.read_json(out/'progress.json')
        (out/'STOP.md').write_text('# 本次扩大测试已停止\n\n'+reason+'\n\n不自动重试；未产生完整有效科学结果。\n',encoding='utf-8')
    present(out,state);s.atomic_json(out/'supervisor_terminal.json',state)
    s.seal(out)
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['readiness','run','worker','status'])
    parser.add_argument('--new-attempt-authorization',default='')
    args=parser.parse_args()
    if args.mode=='status':print(json.dumps(status(),ensure_ascii=False));return
    if args.mode=='worker':
        deadline=time.monotonic()+30
        while not (REAL/'worker_gate.json').exists():
            s.require(time.monotonic()<deadline,'WORKER_GATE_TIMEOUT');time.sleep(.05)
        gate=s.read_json(REAL/'worker_gate.json')
        s.require(gate['pid']==os.getpid() and gate['parent_pid']==os.getppid(),'WORKER_GATE')
        config=readiness()
        from issue27frontend_expanded_eval_runner_v1 import worker
        raise SystemExit(worker(config,REAL,gate['started']))
    config=readiness();s.require(not REAL.exists(),'REAL_ATTEMPT_ALREADY_EXISTS')
    if args.mode=='readiness':print('V2_READY_REQUIRES_NEW_ATTEMPT_AUTHORIZATION');return
    s.require(bool(args.new_attempt_authorization.strip()),'NEW_ATTEMPT_NOT_AUTHORIZED')
    config['new_attempt_authorization']=args.new_attempt_authorization
    print(json.dumps(supervise(config),ensure_ascii=False))


if __name__=='__main__':main()
