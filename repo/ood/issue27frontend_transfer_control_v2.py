"""V2 I/O overlay: reuse sealed P; a new explicitly authorized T/E attempt only."""
import argparse
import html
from pathlib import Path
import sys
import issue27frontend_transfer_support_v1 as s
import issue27frontend_transfer_control_v1 as v1
from issue27frontend_transfer_io_v2 import read_json,atomic_json

P_SEAL = '80019634c8b158e901678f55b369476fc488104b4bf1177193750432b83d567d'
PACKAGE = s.ROOT/'runs/frontend_task_knowledge_transfer_implementation_v2_20260911'
TOKENS = {p:'I_AUTHORIZE_ONE_NEW_TASK_KNOWLEDGE_TRANSFER_V2_'+p for p in ('T','E','TE')}
_base_readiness = v1.readiness

# Narrow, explicit runtime overlay; V1 source and all frozen recipes stay intact.
# The old numerical modules share this same support module object.
s.read_json = read_json
s.atomic_json = atomic_json
s.PACKAGE = PACKAGE
s.OUTPUTS = {'P':s.ROOT/'runs/frontend_task_knowledge_transfer_p_v1_20260911',
             'T':s.ROOT/'runs/frontend_task_knowledge_transfer_t_v2_20260911',
             'E':s.ROOT/'runs/frontend_task_knowledge_transfer_e_v2_20260911'}


def readiness(check=lambda:None,verify_git=True):
    r = _base_readiness(check,verify_git)
    s.manifest(s.OUTPUTS['P'],P_SEAL,check)
    s.require(s.read_json(s.OUTPUTS['P']/'supervisor_terminal.json')['status'] == 'COMPLETE', 'REUSED_P_NOT_COMPLETE')
    return r


v1.readiness = readiness


def present(out,value):
    state=value.get('status',value.get('phase','STARTING'))
    labels={'COMPLETE':'完成，封存核验通过','STOP':'已停止，不重试','TRAINING':'训练中','STARTING':'启动中'}
    text='# 任务知识迁移 V2\n\n**'+labels.get(state,state)+'**\n\n'
    text+='阶段：%s；训练臂：%s；轮数：%s/%s；更新：%s/%s。\n\n'%(value.get('stage','—'),value.get('arm','—'),value.get('epoch','—'),value.get('epochs',20),value.get('updates','—'),value.get('updates_total',3940))
    text+='评估目标：%s/%s；耗时：%.1f分钟。\n\n'%(value.get('targets_complete',0),value.get('targets_total',840948),value.get('elapsed_seconds',0)/60)
    text+=(value.get('reason') or '')+'\n\n机器进度：progress.jsonl；终态：supervisor_terminal.json与SHA256SUMS。\n'
    # Human views need no atomic replacement; the journal is authoritative.
    # A reader can momentarily see an incomplete view and refresh it safely.
    (out/'status.md').write_text(text,encoding='utf-8')
    (out/'status.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>实验进度</title><pre style="font:20px system-ui;white-space:pre-wrap;margin:40px">'+html.escape(text)+'</pre>',encoding='utf-8')


v1.present=present


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('status','check-implementation','run','worker'))
    parser.add_argument('--stage',choices=('T','E','TE'),default='TE')
    parser.add_argument('--authorization')
    args = parser.parse_args()
    if args.mode == 'status':
        print(s.canonical([v1.status(p) for p in args.stage]).decode('utf-8'));return
    if args.mode == 'check-implementation':
        readiness();print('V2_IMPLEMENTATION_READY_P_REUSED_NO_NEW_REAL_EXECUTION');return
    s.require(args.authorization == TOKENS[args.stage], 'EXPLICIT_NEW_V2_ATTEMPT_AUTHORIZATION_REQUIRED')
    if args.mode == 'worker':
        s.require(args.stage in ('T','E'), 'WORKER_STAGE')
        raise SystemExit(v1.worker(args.stage))
    s.require(all(not s.OUTPUTS[p].exists() for p in args.stage), 'V2_ATTEMPT_ALREADY_EXISTS')
    for stage in args.stage:
        limits = dict(seconds=14400 if stage=='T' else 1800,memory=8*1024**3,output=512*1024**2)
        command = [str(s.PYTHON),'-B',str(Path(__file__).resolve()),'worker','--stage',stage,'--authorization',TOKENS[stage]]
        result = v1.supervise(stage,s.OUTPUTS[stage],limits,command)
        print(s.canonical(result).decode('utf-8'),flush=True)
        if result['status'] != 'COMPLETE':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
