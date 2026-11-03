"""Bounded read-only progress copy for this one job; never submits or evaluates."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import time
from client import request, PACKAGE, HERE


def main():
    end = time.monotonic() + 7800
    while time.monotonic() < end:
        # Never race with the subsequent local evaluation's progress writer.
        if (PACKAGE / 'output').exists(): return
        try:
            state = request('state')
            worker = state.get('STATUS.json', {})
            runtime = state.get('ENCODE_RUNTIME.json', {})
            now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
            done, total = worker.get('completed'), worker.get('total', 278)
            phase = worker.get('stage', 'WAITING_FOR_WORKER')
            message = {'ENCODING_LOAD': '正在加载冻结编码器', 'ENCODING': '正在编码新增正常参考点',
                       'ENCODED': '超算编码完成，等待取回核验和一次评价', 'TECHNICAL_STOP': '执行已停止，等待读取故障记录'}.get(phase, '作业已提交，等待编码进度')
            record = dict(stage='HPC_' + phase, message=message, job_id=state.get('job_id'), updated_beijing=now,
                          completed=done, total=total, worker=worker, runtime=runtime, read_only=True)
            (HERE / 'STATUS_BRIDGE.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            lines = ['# C3 实验进度', '', '**' + message + '**', '', '超算作业：' + str(state.get('job_id')),
                     '本次只编码 278 个新增正常参考点（TCP 212、UDP 66）。',
                     '资源上限：4 CPU / 8 GiB / 2 小时。', '',
                     '编码进度：' + (str(done) + ' / ' + str(total) if done is not None else '尚未收到行数'), '',
                     '后续：取回并校验编码 → 原 HIST_DEV 一致性门 → 一次 A/B → 独立验收并冻结。', '',
                     '目前无新 A/B 成绩。', '进度更新时间（北京时间）：' + now, '']
            if not (PACKAGE / 'output').exists():
                (PACKAGE / 'PROGRESS.md').write_text('\n'.join(lines), encoding='utf-8')
            if phase in ('ENCODED', 'TECHNICAL_STOP') or runtime: return
            if any(x in state.get('sacct', {}).get('stdout', '') for x in ('FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY')): return
        except Exception as exc:
            (HERE / 'BRIDGE_NETWORK_ERROR.json').write_text(json.dumps(dict(error=str(exc), scientific_status_overwritten=False)) + '\n')
        time.sleep(30)


if __name__ == '__main__': main()
