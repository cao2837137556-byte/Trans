"""Local single-worker P/T/E supervision with explicit cache-row authorization."""
import argparse
import html
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
import issue27dualview_support_v1 as s
from issue27frontend_paired_train_control_v3 import Job, pid_alive, peak_memory


def caps(r,stage):
    c=r['resource_caps']
    return dict(seconds=c[stage+'_wall_seconds'],memory=c['process_tree_RSS_bytes'],output=c['new_artifact_bytes'])


def directory_bytes(out):
    return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())


def verify_workspace(cfg, check=lambda: None):
    git = cfg['git_path']; s.require(s.sha(git,check) == cfg['git_sha256'], 'GIT_EXECUTABLE')
    for command,expected in [('rev-parse HEAD',cfg['head']),('branch --show-current',cfg['branch'])]:
        result = subprocess.check_output([git]+command.split(),cwd=s.ROOT,text=True,timeout=15).strip()
        s.require(result == expected, 'GIT_WORKSPACE')
        check()


def readiness(check=lambda: None, verify_git=True):
    s.manifest(s.PACKAGE,check=check)
    cfg = s.read_json(s.PACKAGE/'config.json')
    acceptance = s.read_json(s.PACKAGE/'acceptance.json')
    s.require(acceptance['status'] == 'PASS' and acceptance['tests_run'] == acceptance['tests_passed']
              and acceptance['real_model_forwards'] == acceptance['real_teacher_rows'] == acceptance['real_optimizer_steps'] == 0
              and acceptance['config_sha256'] == s.sha(s.PACKAGE/'config.json',check), 'IMPLEMENTATION_ACCEPTANCE')
    s.require(cfg['recipe_sha256'] == s.RECIPE_SHA, 'CONFIG_RECIPE')
    for path,h in cfg['code_pins'].items():
        s.require(s.sha(s.ROOT/path,check) == h, 'IMPLEMENTATION_DRIFT:'+path)
    for path,h in cfg['runtime_pins'].items():
        s.require(s.sha(Path(path),check) == h, 'RUNTIME_PIN')
    for path,h in cfg['unrelated_tracked_sha256'].items():
        s.require(s.sha(s.ROOT/path,check) == h, 'UNRELATED_CHANGED')
    s.require(Path(sys.executable).resolve() == s.PYTHON.resolve(), 'PYTHON_EXECUTABLE')
    if verify_git:
        verify_workspace(cfg,check)
    return s.recipe()


class Budget:
    def __init__(self,out,start,limits):
        self.out,self.start,self.limits = out,start,limits
        self.last = 0.; self.state = {}
        self.targets_total = 560632
        self.stage = None
        self.access = dict.fromkeys(('optimizer_steps','historical_student_loads','new_candidate_loads',
            'encoder_forwards','AB_target_states','head_training_forwards','head_evaluation_forwards',
            'evaluated_targets','feature_bytes_decoded','E3_numeric_rows','opaque_E3_bytes_streamed',
            'E3_model_loads','E3_forwards','teacher_passes','raw_decodes','retries','network_requests'),0)


    def check(self,force=False,**state):
        self.state.update(state)
        now = time.monotonic()
        s.require(now-self.start < self.limits['seconds']-2, 'WORKER_WALL_CAP')
        if force or now-self.last >= 1:
            self.last = now
            s.atomic_json(self.out/'progress.json',dict(self.state,elapsed_seconds=now-self.start,access=self.access))


def worker(stage, synthetic=False):
    out = s.OUTPUTS[stage]; deadline = time.monotonic()+30
    while not (out/'worker_gate.json').exists():
        s.require(time.monotonic() < deadline, 'GATE_TIMEOUT'); time.sleep(.05)
    gate = s.read_json(out/'worker_gate.json')
    s.require(gate['pid'] == os.getpid() and gate['parent_pid'] == os.getppid() and gate['workspace_verified']==(not synthetic), 'WORKER_GATE')
    budget = Budget(out,gate['started'],gate['caps']); budget.stage=stage
    try:
        budget.check(True,phase='IMPLEMENTATION_READINESS')
        r = readiness(budget.check,verify_git=False)
        s.require(gate['caps'] == caps(r,stage), 'CAP_DRIFT')
        import issue27dualview_model_v1 as m
        import issue27dualview_pipeline_v1 as pipeline
        m.configure(); budget.targets_total=r['stages']['E']['head_scores_total']
        budget.state['representation_targets_total']=r['stages'].get(stage,{}).get('AB_target_states',0)
        budget.state['E3_rows_total']=r['stages'].get(stage,{}).get('E3_numeric_rows',0)
        result={'P':pipeline.prepare,'T':pipeline.fit,'E':pipeline.evaluate}[stage](r,out,budget)
        budget.check(True,phase='VERIFYING_RESULTS')
        pipeline.verify_stage(stage,out,r,budget)
        # Recheck protected workspace bytes before accepting the stage.
        cfg = {'unrelated_tracked_sha256':{}} if synthetic else s.read_json(s.PACKAGE/'config.json')
        for path,h in cfg['unrelated_tracked_sha256'].items():
            s.require(s.sha(s.ROOT/path,budget.check) == h, 'UNRELATED_CHANGED')
        terminal = dict(status='WORK_COMPLETE_VERIFIED',stage=stage,result=result,recipe_sha256=s.RECIPE_SHA)
    except Exception as exc:
        terminal = dict(status='STOP',stage=stage,reason=type(exc).__name__+': '+str(exc),recipe_sha256=s.RECIPE_SHA)
        (out/'failure_traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
    s.atomic_json(out/'access.json',budget.access)
    outputs = [p for p in out.iterdir() if p.is_file() and p.name not in ('progress.json','status.md','status.html','stdout.log','stderr.log','worker_terminal.json')]
    terminal['output_hashes'] = {p.name:s.sha(p) for p in outputs}
    s.atomic_json(out/'worker_terminal.json',terminal)
    return 0 if terminal['status'] == 'WORK_COMPLETE_VERIFIED' else 1


def present(out,value):
    # Terminal receipts carry status, while the last journal carries completed work.
    # Preserve both so a finished run never appears as zero completed targets.
    if value.get('status') in ('COMPLETE','STOP') and (out/'progress.json').exists():
        try:
            value=dict(s.read_json(out/'progress.json'),**value)
        except (OSError,ValueError):
            pass  # The terminal reason remains visible even with damaged progress.
    state = value.get('status',value.get('phase','STARTING'))
    labels = {'COMPLETE':'完成，结果核验通过','STOP':'已停止，不会重试','STARTING':'启动中',
              'TRAINING':'正在训练','IMPLEMENTATION_READINESS':'核对封存与环境','VERIFYING_RESULTS':'核验结果',
              'VERIFYING_METRICS':'复核终点指标','ENTRY_PREFLIGHT':'核对起点、训练输入与原始顺序',
              'ENCODER_EXTRACTION':'准备统一表示','SELECTING_E3_ROWS':'读取获准旧特征','EVALUATION':'评估终点','ENDPOINT_METRICS':'汇总结果'}
    text = '# 双视图能力实验运行状态\n\n**'+labels.get(state,state)+'**\n\n'
    text += '阶段：%s；训练臂：%s；轮数：%s/%s；更新：%s/%s。\n\n'%(value.get('stage','—'),value.get('arm','—'),value.get('epoch','—'),value.get('epochs',50),value.get('updates','—'),value.get('updates_total',5900))
    if value.get('stage')=='E':
        text += '已评估目标：%s/%s；耗时：%.1f分钟。\n\n'%(value.get('access',{}).get('evaluated_targets',0),value.get('targets_total',560632),value.get('elapsed_seconds',0)/60)
        text += '统一表示：%s/%s；有效旧特征：%s/%s。\n\n'%(value.get('access',{}).get('AB_target_states',0),value.get('representation_targets_total','—'),value.get('access',{}).get('E3_numeric_rows',0),value.get('E3_rows_total','—'))
    elif value.get('stage')=='P':
        text += '表示准备目标：%s/%s；有效旧特征：%s/%s；耗时：%.1f分钟。\n\n'%(value.get('access',{}).get('AB_target_states',0),value.get('representation_targets_total','—'),value.get('access',{}).get('E3_numeric_rows',0),value.get('E3_rows_total','—'),value.get('elapsed_seconds',0)/60)
    else:
        text += '耗时：%.1f分钟。\n\n'%(value.get('elapsed_seconds',0)/60)
    text += (value.get('reason') or '')+'\n\n终态见 supervisor_terminal.json；E阶段结果见 result.md。\n'
    for name,content in [('status.md',text),('status.html','<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>实验进度</title><pre style="font:20px system-ui;white-space:pre-wrap;margin:40px">'+html.escape(text)+'</pre>')]:
        (out/name).write_text(content,encoding='utf-8')


def supervise(stage,out,limits,command,synthetic=False):
    if synthetic:s.require((s.ROOT/'tmp/dualview_synthetic_v1').resolve() in out.resolve().parents,'SYNTHETIC_OUTPUT_SCOPE')
    out.mkdir(parents=True,exist_ok=False)
    started = time.monotonic(); process = job = None; reason = None; peak = 0; last = 0
    s.atomic_json(out/'attempt.json',dict(controller_pid=os.getpid(),started_unix=time.time(),stage=stage,
                                       recipe_sha256=s.RECIPE_SHA,retries=0,synthetic=synthetic))
    present(out,dict(status='STARTING',stage=stage))
    def check():
        nonlocal peak
        controller = peak_memory(); peak = max(peak,controller+(job.peak() if job else 0))
        s.require(time.monotonic()-started < limits['seconds']-1, 'SUPERVISOR_WALL_CAP')
        s.require(controller < 512*1024**2 and peak < limits['memory'], 'SUPERVISOR_MEMORY_CAP')
        s.require((directory_bytes(out) if synthetic else sum(directory_bytes(p) for p in s.OUTPUTS.values() if p.exists())) < limits['output']-1024*1024, 'SUPERVISOR_OUTPUT_CAP')
    try:
        # Git is a short controller-side check, inside this stage's budget.
        # The numerical worker's Windows Job permits exactly one process.
        if not synthetic:
            verify_workspace(s.read_json(s.PACKAGE/'config.json'),check)
        env = dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='2705',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
        with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
            process = subprocess.Popen(command,cwd=s.ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
            job = Job(process,limits['memory']-512*1024**2)
            s.atomic_json(out/'worker_gate.json',dict(pid=process.pid,parent_pid=os.getpid(),started=started,caps=limits,workspace_verified=not synthetic))
            while process.poll() is None:
                check(); now = time.monotonic()
                if now-last >= 1:
                    last = now
                    value = s.read_json(out/'progress.json') if (out/'progress.json').exists() else {'phase':'STARTING'}
                    present(out,dict(value,stage=stage,elapsed_seconds=now-started))
                time.sleep(.2)
            check()
            terminal = s.read_json(out/'worker_terminal.json')
            s.require(process.returncode == 0 and terminal['status'] == 'WORK_COMPLETE_VERIFIED', terminal.get('reason','WORKER_FAILED'))
            s.require(terminal['stage'] == stage and terminal['recipe_sha256'] == s.RECIPE_SHA, 'WORKER_RECEIPT_SCOPE')
            s.require(terminal['output_hashes'], 'NO_SCIENTIFIC_OUTPUTS')
            for name,h in terminal['output_hashes'].items():
                p = (out/name).resolve()
                s.require(p.parent == out.resolve(), 'OUTPUT_RECEIPT_PATH')
                s.require(s.sha(p,check) == h, 'OUTPUT_RECEIPT_DRIFT')
    except Exception as exc:
        reason = type(exc).__name__+': '+str(exc)
    finally:
        if process is not None and process.poll() is None:
            if job:
                job.terminate()
            else:
                process.kill()
            process.wait(timeout=15)
    state = dict(status='STOP' if reason else 'COMPLETE',stage=stage,reason=reason,verified=reason is None,retries=0,
                 elapsed_seconds=time.monotonic()-started,aggregate_peak_bytes_upper_bound=peak,
                 worker_exit_code=None if process is None else process.returncode,synthetic=synthetic,recipe_sha256=s.RECIPE_SHA)
    try:
        s.atomic_json(out/'supervisor_terminal.json',state); present(out,state)
        s.seal(out,check if reason is None else lambda:None)
        if reason is None:
            check()
    except Exception as exc:
        # A sealing failure must never leave a visible COMPLETE terminal.
        state.update(status='STOP',verified=False,reason='SEAL_OR_FINAL_BUDGET: '+str(exc))
        if (out/'SHA256SUMS').exists():
            os.replace(out/'SHA256SUMS',out/'incomplete_seal.txt')
        s.atomic_json(out/'supervisor_terminal.json',state); present(out,state)
        s.seal(out)
    finally:
        if job:
            job.close()
    return state


def status(stage):
    out = s.OUTPUTS[stage]
    if not out.exists():
        return dict(stage=stage,status='NOT_STARTED')
    if (out/'SHA256SUMS').exists():
        try:
            s.manifest(out)
            return dict(s.read_json(out/'supervisor_terminal.json'),seal_verified=True)
        except Exception as exc:
            return dict(stage=stage,status='SEAL_INVALID',reason=str(exc))
    try:
        if not pid_alive(s.read_json(out/'attempt.json')['controller_pid']):
            return dict(stage=stage,status='INTERRUPTED_DO_NOT_RESTART')
        return dict(s.read_json(out/'progress.json'),stage=stage)
    except (OSError,ValueError,KeyError):
        return dict(stage=stage,status='STARTING_OR_SEALING')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('status','check-implementation','run','worker'))
    parser.add_argument('--stage',choices=('P','T','E','PTE'),default='PTE')
    parser.add_argument('--authorization')
    args = parser.parse_args()
    if args.mode == 'status':
        print(s.canonical([status(p) for p in args.stage]).decode('utf-8')); return
    if args.mode == 'check-implementation':
        readiness(); print('IMPLEMENTATION_READY_NO_REAL_EXECUTION'); return
    s.require(args.authorization == s.TOKENS[args.stage], 'EXPLICIT_STAGE_AUTHORIZATION_REQUIRED')
    if args.mode == 'worker':
        s.require(args.stage in 'PTE' and len(args.stage) == 1, 'WORKER_STAGE')
        raise SystemExit(worker(args.stage))
    readiness()
    s.require(all(not s.OUTPUTS[p].exists() for p in args.stage), 'ONE_ATTEMPT_ALREADY_EXISTS')
    for stage in args.stage:
        # Dispatch limits are checked against the sealed recipe inside the Job.
        limits = caps(s.recipe(),stage)
        command = [str(s.PYTHON),'-B',str(Path(__file__).resolve()),'worker','--stage',stage,'--authorization',s.TOKENS[stage]]
        result = supervise(stage,s.OUTPUTS[stage],limits,command)
        print(s.canonical(result).decode('utf-8'),flush=True)
        if result['status'] != 'COMPLETE':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
