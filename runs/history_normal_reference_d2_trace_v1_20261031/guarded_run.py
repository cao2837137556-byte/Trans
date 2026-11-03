"""One bounded local diagnostic process: 4 logical CPUs, 4 GiB RSS, 900 s."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil

HERE=Path(__file__).resolve().parent


def main():
    latch=HERE/'EXECUTION_ATTEMPT.json'
    started=time.monotonic()
    with latch.open('x',encoding='utf-8') as stream:
        json.dump(dict(started_utc=datetime.now(timezone.utc).isoformat(),max_wall_seconds=900,
                       max_pairs=80_000_000,max_rss_bytes=4*1024**3,cpus=4,diagnostic_only=True),stream,indent=2)
    environment=os.environ.copy()
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        environment[name]='4'
    proc=psutil.Process();original=proc.cpu_affinity();proc.cpu_affinity(original[:4])
    peak=0;reason=None
    try:
        with (HERE/'RUN.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,'-B',str(HERE/'trace.py')],env=environment,stdout=log,stderr=subprocess.STDOUT)
            running=psutil.Process(child.pid)
            while child.poll() is None:
                try:rss=sum(p.memory_info().rss for p in [running]+running.children(recursive=True))
                except psutil.NoSuchProcess:rss=0
                peak=max(peak,rss)
                if time.monotonic()-started>900:reason='HARD_WALL_BUDGET_STOP'
                if rss>4*1024**3:reason='HARD_RSS_BUDGET_STOP'
                if reason:
                    for p in running.children(recursive=True):p.kill()
                    child.kill();child.wait();break
                time.sleep(.25)
            code=child.wait()
    finally:proc.cpu_affinity(original)
    receipt=dict(status=reason or ('COMPLETE' if code==0 else 'FAILED_NO_RETRY'),returncode=code,
                 wall_seconds=time.monotonic()-started,peak_rss_bytes=peak,cpus=original[:4],automatic_retry=False)
    (HERE/'RUNTIME_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt),flush=True)
    raise SystemExit(code if not reason else 2)


if __name__=='__main__':main()
