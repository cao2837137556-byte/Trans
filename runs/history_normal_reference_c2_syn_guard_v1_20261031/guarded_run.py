"""One local saved-input execution with hard CPU, RSS, time and output limits."""
from datetime import datetime, timezone
import os
import subprocess
import sys
import time

import psutil

from common import HERE, OUTPUT, need, progress, read, sha, write


def main():
    card = read(HERE / 'EXECUTION_CARD.json')
    tests = read(HERE / 'IMPLEMENTATION_CHECK.json')
    need(tests['status'] == 'PASS' and tests['execution_card_sha256'] == sha(HERE / 'EXECUTION_CARD.json'), 'ENGINEERING_CHECK_REQUIRED')
    limits = card['limits']
    started = time.monotonic()
    with (HERE / 'EXECUTION_ATTEMPT.json').open('x', encoding='utf-8') as stream:
        import json
        json.dump(dict(started_utc=datetime.now(timezone.utc).isoformat(),
                       candidate=card['candidate'], execution_card_sha256=sha(HERE / 'EXECUTION_CARD.json'),
                       limits=limits, automatic_retry=False), stream, indent=2)
    environment = os.environ.copy()
    environment['PYTHONUTF8'] = '1'
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        environment[key] = str(limits['cpus'])
    original = psutil.Process().cpu_affinity()
    psutil.Process().cpu_affinity(original[:limits['cpus']])
    peak, peak_output, reason = 0, 0, None
    try:
        with (HERE / 'RUN.log').open('x', encoding='utf-8') as log:
            child = subprocess.Popen([sys.executable, '-B', str(HERE / 'run.py')], env=environment,
                                     stdout=log, stderr=subprocess.STDOUT)
            process = psutil.Process(child.pid)
            checked_output = 0.
            while child.poll() is None:
                try:
                    rss = sum(p.memory_info().rss for p in [process] + process.children(recursive=True))
                except psutil.NoSuchProcess:
                    rss = 0
                peak = max(peak, rss)
                now = time.monotonic()
                if now - checked_output > 2:
                    peak_output = max(peak_output, sum(p.stat().st_size for p in OUTPUT.rglob('*') if p.is_file()))
                    checked_output = now
                if now - started > limits['wall_seconds']:
                    reason = 'HARD_TIME_LIMIT'
                if rss > limits['rss_bytes']:
                    reason = 'HARD_RSS_LIMIT'
                if peak_output > limits['output_bytes']:
                    reason = 'HARD_OUTPUT_LIMIT'
                if reason:
                    for descendant in process.children(recursive=True):
                        descendant.kill()
                    child.kill()
                    break
                time.sleep(.25)
            code = child.wait()
    finally:
        psutil.Process().cpu_affinity(original)
    receipt = dict(status=reason or ('COMPLETE' if code == 0 else 'TECHNICAL_FAILURE_NO_AUTOMATIC_RETRY'),
                   returncode=code, wall_seconds=time.monotonic() - started, peak_rss_bytes=peak,
                   peak_output_bytes=peak_output, cpus=original[:limits['cpus']], automatic_retry=False)
    write(HERE / 'RUNTIME_RECEIPT.json', receipt)
    if reason:
        progress('BUDGET_STOP', '已触及资源上限并停止，未自动重试', reason=reason)
    print(receipt, flush=True)
    raise SystemExit(code if not reason else 2)


if __name__ == '__main__':
    main()
