"""Run one explicit stage with hard process-tree resource limits, no retry."""
import subprocess
import time
import psutil
from common import *


def main():
    need(len(sys.argv) == 2 and sys.argv[1] in ('prepare', 'encode', 'evaluate'), 'ONE_FIXED_STAGE')
    stage = sys.argv[1]
    card, _ = verify_contract(remote=stage == 'encode')
    need(stage == 'evaluate', 'TECHNICAL_RECOVERY_EVALUATION_ONLY')
    prior_elapsed = card['technical_recovery']['previous_elapsed_seconds']
    remaining_seconds = LIMITS['wall_seconds'] - prior_elapsed
    need(remaining_seconds > 0, 'CUMULATIVE_WALL_BUDGET_EXHAUSTED')
    test = read(HERE / 'IMPLEMENTATION_CHECK.json')
    need(test['status'] == 'PASS' and test['execution_card_sha256'] == sha(HERE / 'EXECUTION_CARD.json'), 'ENGINEERING_CHECK_REQUIRED')
    write(HERE / (stage.upper() + '_GUARD_ATTEMPT.json'), dict(candidate=CANDIDATE,
        limits=LIMITS, stage=stage, retries=0), exclusive=True)
    original = psutil.Process().cpu_affinity()
    psutil.Process().cpu_affinity(original[:LIMITS['cpu']])
    started, peak, reason, child = time.monotonic(), 0, None, None
    try:
        with (HERE / (stage.upper() + '.log')).open('x', encoding='utf-8') as log:
            child = subprocess.Popen([sys.executable, '-B', str(HERE / (stage + '.py'))], stdout=log, stderr=subprocess.STDOUT)
            process = psutil.Process(child.pid)
            while child.poll() is None:
                try: rss = sum(p.memory_info().rss for p in [process] + process.children(recursive=True))
                except psutil.NoSuchProcess: rss = 0
                peak = max(peak, rss)
                if rss > LIMITS['rss_bytes']: reason = 'HARD_RSS_LIMIT'
                if time.monotonic() - started > remaining_seconds: reason = 'HARD_WALL_LIMIT'
                size = sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
                if size > LIMITS['output_bytes']: reason = 'HARD_OUTPUT_LIMIT'
                if reason:
                    for p in process.children(recursive=True): p.kill()
                    child.kill(); break
                time.sleep(.5)
            code = child.wait()
    finally:
        psutil.Process().cpu_affinity(original)
    receipt = dict(stage=stage, status=reason or ('COMPLETE' if code == 0 else 'TECHNICAL_FAILURE_NO_RETRY'),
        returncode=code, elapsed_seconds=time.monotonic() - started, peak_rss_bytes=peak,
        cpu_count=LIMITS['cpu'], automatic_retry=False, previous_elapsed_seconds=prior_elapsed,
        cumulative_elapsed_seconds=prior_elapsed + time.monotonic() - started,
        evaluation_attempt=2)
    write(HERE / (stage.upper() + '_RUNTIME.json'), receipt)
    if code or reason: progress('TECHNICAL_STOP', '本阶段已停止，保留现场，没有自动重试', failed_stage=stage,
                               **{k: v for k, v in receipt.items() if k != 'stage'})
    print(json.dumps(receipt), flush=True)
    raise SystemExit(code if not reason else 2)


if __name__ == '__main__': main()
