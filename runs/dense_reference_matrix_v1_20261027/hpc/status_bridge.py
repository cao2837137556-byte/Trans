"""Fixed-job, authenticated, loopback-only read-only progress bridge."""
import argparse
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import read, require


FAILED_STATES = frozenset(('FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'CANCELLED',
    'NODE_FAIL', 'BOOT_FAIL', 'DEADLINE', 'PREEMPTED', 'REVOKED', 'SPECIAL_EXIT'))
TERMINAL_PROGRESS = frozenset(('COMPLETE', 'EXCEPTION_STOP', 'BLOCKED'))


def reconcile(progress, scheduler, launch=None):
    """Outer failures override child success; missing completion stays visible."""
    result = dict(progress)
    child_status = result.get('status', 'UNKNOWN')
    if child_status == 'FINALIZING' and result.get('scientific_child_status') == 'COMPLETE':
        child_status = 'COMPLETE'
        result['status'] = 'COMPLETE'
    launch = launch or {}
    state = str(scheduler.get('state', 'UNKNOWN')).split('+')[0].split(' ')[0]
    reason = None
    if launch.get('status') == 'EXCEPTION_STOP':
        reason = launch.get('reason') or 'LAUNCH_OR_WORKER_EXIT'
    elif state in FAILED_STATES:
        reason = result.get('reason') or 'SLURM_' + state
    elif state == 'COMPLETED':
        if scheduler.get('exit_code') not in (None, '0:0'):
            reason = 'SLURM_NONZERO_EXIT:' + str(scheduler['exit_code'])
        elif child_status not in TERMINAL_PROGRESS:
            reason = 'SLURM_COMPLETED_WITHOUT_CHAIN_COMPLETE_RECEIPT'
    if reason is not None:
        result.setdefault('scientific_child_status', child_status)
        result.update(status='EXCEPTION_STOP', reason=reason, worker_alive=False)
    elif child_status == 'COMPLETE' and state != 'COMPLETED':
        # The chain can finish before the shell trap or Slurm accounting. Do
        # not freeze a successful cache before an outer failure can be seen.
        result.update(status='FINALIZING', scientific_child_status='COMPLETE',
                      worker_alive=False)
    elif child_status in ('UNKNOWN', 'QUEUED', 'STARTING'):
        if state in ('PENDING', 'CONFIGURING'):
            result.update(status='QUEUED', worker_alive=False)
        elif state == 'RUNNING':
            result.update(status='STARTING', worker_alive=False)
    return result


def collect(root, job_id):
    require(job_id.isdecimal() and int(job_id) > 0, 'JOB_ID')
    attempt = Path(root).resolve() / ('job_' + job_id)
    path = attempt / 'science/status.json'
    progress = read(path) if path.exists() else dict(status='UNKNOWN', stage='launch')
    launch = attempt / 'launch.json'
    launch_record = read(launch) if launch.exists() else {}
    scheduler = dict(job_id=job_id, state='UNKNOWN')
    try:
        query = subprocess.run(['/usr/local/slurm-25.11.0-build/bin/sacct', '-n', '-P',
            '-j', job_id, '--format=JobIDRaw,State,ExitCode,Elapsed,NodeList'],
            check=True, capture_output=True, text=True, timeout=5)
        for line in query.stdout.splitlines():
            fields = line.strip().split('|')
            if len(fields) >= 5 and fields[0] == job_id:
                scheduler.update(state=fields[1].split('+')[0].split(' ')[0], exit_code=fields[2],
                                 elapsed=fields[3], node=fields[4])
    except (OSError, subprocess.SubprocessError):
        pass
    progress = reconcile(progress, scheduler, launch_record)
    # Expose the encoder's actual original104/tokenization/row progress. This
    # reads the worker's own atomic file; it never infers counts from a stage.
    stage = progress.get('stage')
    if stage in ('runtime', 'encode', 'source_cal', 'matrix'):
        detail = attempt / 'science' / stage / 'status.json'
        if detail.exists():
            progress['stage_progress'] = read(detail)
    return dict(schema='paper04-dense-progress-bundle-v1', job_id=job_id,
        observed_utc=datetime.now(timezone.utc).isoformat(), progress=progress,
        scheduler=scheduler, read_only=True, automatic_retry=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--port', type=int, default=18780)
    args = parser.parse_args()
    secret = read(args.token_file)['token']
    require(args.job_id.isdecimal() and int(args.job_id) > 0, 'JOB_ID')
    require(isinstance(secret, str) and len(secret) >= 32, 'PRIVATE_TOKEN')
    expiry = time.monotonic() + 86400
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if time.monotonic() > expiry:
                self.send_error(410)
                return
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + secret):
                self.send_error(403)
                return
            if self.path != '/status/job_' + args.job_id:
                self.send_error(404)
                return
            value = json.dumps(collect(args.root, args.job_id)).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(value)))
            self.end_headers()
            self.wfile.write(value)
        def do_POST(self):
            self.send_error(405)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.timeout = 1
    while time.monotonic() < expiry:
        server.handle_request()


if __name__ == '__main__':
    main()
