"""One C3 delivery over the user's existing SSH tunnel; fixed actions only."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import threading

ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
PACKAGE = ROOT / 'runs/history_normal_reference_c3_small_bank_v1_20261101'
DEPLOY = ROOT / 'runs/history_normal_reference_c3_deployment_20261101'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
ENVFILE = ROOT / 'frontend_compat_v1/environment.sh'
ENV_SHA = '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf'
C1_CONFIG = ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031/config/EXECUTION.json'
C1_CONFIG_SHA = 'b2c80539fa91008191cecb1fa81899e0ce49e3a3f0c764a05d98677b7bed7c3d'


def need(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024**2), b''): h.update(b)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'); temp.replace(path)


def validate_members(archive, expected):
    members = archive.getmembers()
    need(len(members) == len(expected) and {m.name for m in members} == set(expected), 'EXACT_ARCHIVE_ALLOWLIST')
    for member in members:
        name = Path(member.name)
        need(member.isfile() and not name.is_absolute() and '..' not in name.parts and '\\' not in member.name,
             'REGULAR_RELATIVE_FILES_ONLY')
        data = archive.extractfile(member).read()
        need(len(data) == expected[member.name]['bytes'] and hashlib.sha256(data).hexdigest() == expected[member.name]['sha256'], 'MEMBER_PIN')
    return members


def main(config):
    DEPLOY.mkdir(parents=True, exist_ok=True)
    need(config['bundle_bytes'] < 32 * 1024**2 and len(config['token']) == 48, 'BOUNDED_REQUEST')
    state = dict(status='READY', candidate='C3_ADMITTED_SMALL_BANK_COMPLETE', submitted=False)
    lock = threading.Lock()
    def save(): write(DEPLOY / 'STATE.json', state)
    def package_pins():
        for name, expected in config['files'].items():
            p = PACKAGE / name
            need(p.is_file() and not p.is_symlink() and sha(p) == expected['sha256'], 'PACKAGE_PIN:' + name)
        need(sha(C1_CONFIG) == C1_CONFIG_SHA, 'EXACT_PREVIOUS_HPC_ENCODER_CONFIG')
        need(sha(ENVFILE) == ENV_SHA, 'ENVIRONMENT_SCRIPT_PIN')
    def run_python(code, timeout=240):
        prefix = ('source ' + shlex.quote(str(ENVFILE)) + '\nexport PYTHONPATH=' +
            shlex.quote(str(ROOT / 'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201') + ':' +
                        str(ROOT / 'environment/vendor_py311_v1')) + ':"${PYTHONPATH:-}"\n' +
            'export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 PYTHONUTF8=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1\n' +
            'cd ' + shlex.quote(str(PACKAGE)) + '\n' + shlex.quote(PYTHON) + ' -B -c ' + shlex.quote(code))
        return subprocess.run(['bash', '-lc', prefix], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def route(self):
            prefix = '/' + config['token']
            need(self.path.startswith(prefix + '/'), 'UNKNOWN_ROUTE')
            return self.path[len(prefix):]
        def send_json(self, value, code=200):
            data = (json.dumps(value, ensure_ascii=False) + '\n').encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            try:
                route = self.route()
                if route == '/state':
                    result = dict(state)
                    for name in ('STATUS.json', 'ENCODE_RUNTIME.json'):
                        p = PACKAGE / name
                        if p.is_file(): result[name] = read(p)
                    if state.get('job_id'):
                        done = subprocess.run(['sacct', '-j', state['job_id'], '--format=JobID,State,ExitCode,Elapsed,MaxRSS', '--noheader', '--parsable2'], capture_output=True, text=True, timeout=15)
                        result['sacct'] = dict(returncode=done.returncode, stdout=done.stdout, stderr=done.stderr)
                    self.send_json(result); return
                if route == '/result':
                    allowed = [p for folder in ('encoded',) for p in (PACKAGE / folder).rglob('*') if p.is_file() and not p.is_symlink()]
                    allowed += [PACKAGE / name for name in ('ENCODE_RUNTIME.json', 'ENCODE_ATTEMPT.json', 'ENCODE_GUARD_ATTEMPT.json', 'ENCODE.log', 'STATUS.json') if (PACKAGE / name).is_file()]
                    allowed += list(PACKAGE.glob('SLURM-*.log'))
                    need(allowed, 'NO_RESULTS_YET')
                    payload = io.BytesIO()
                    with tarfile.open(fileobj=payload, mode='w') as archive:
                        for p in allowed:
                            need(p.resolve().is_relative_to(PACKAGE) and not p.is_symlink(), 'RESULT_PATH')
                            archive.add(p, arcname=p.relative_to(PACKAGE).as_posix(), recursive=False)
                    data = payload.getvalue(); need(len(data) < 64 * 1024**2, 'RESULT_SIZE_LIMIT')
                    self.send_response(200); self.send_header('Content-Length', str(len(data)))
                    self.send_header('Content-Type', 'application/x-tar'); self.send_header('X-Content-SHA256', hashlib.sha256(data).hexdigest())
                    self.end_headers(); self.wfile.write(data); return
                self.send_error(404)
            except Exception as exc: self.send_json(dict(error=str(exc)), 409)
        def do_POST(self):
            try:
                route = self.route()
                with lock:
                    if route == '/upload':
                        need(not PACKAGE.exists() and state['status'] == 'READY', 'PACKAGE_ALREADY_EXISTS')
                        need(int(self.headers.get('Content-Length', '-1')) == config['bundle_bytes'], 'UPLOAD_LENGTH')
                        data = self.rfile.read(config['bundle_bytes'])
                        need(hashlib.sha256(data).hexdigest() == config['bundle_sha256'], 'UPLOAD_SHA256')
                        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
                            members = validate_members(archive, config['files'])
                            PACKAGE.mkdir(exist_ok=False)
                            for member in members:
                                p = PACKAGE / member.name; p.parent.mkdir(parents=True, exist_ok=True)
                                with p.open('xb') as f: f.write(archive.extractfile(member).read())
                        state['status'] = 'INSTALLED'; save(); self.send_json(dict(status='INSTALLED', files=len(config['files']))); return
                    need(int(self.headers.get('Content-Length', '0')) == 0, 'NO_ACTION_BODY')
                    if route == '/preflight':
                        need(state['status'] == 'INSTALLED', 'PREFLIGHT_ONCE')
                        state['status'] = 'PREFLIGHT_RUNNING'; save(); package_pins()
                        code = "import os,platform,json,unittest; os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4]); import numpy as np, torch; observed=dict(python=platform.python_version(),numpy=np.__version__,torch=str(torch.__version__).split('+')[0]); print(json.dumps(observed),flush=True); assert observed==dict(python='3.11.11',numpy='2.0.1',torch='2.5.1'); import common; common.verify_contract(remote=True); import test_c3; suite=unittest.defaultTestLoader.loadTestsFromModule(test_c3); result=unittest.TextTestRunner(verbosity=2).run(suite); assert result.wasSuccessful() and result.testsRun==14"
                        ran = run_python(code)
                        (DEPLOY / 'PREFLIGHT.log').write_text(ran.stdout, encoding='utf-8')
                        state['status'] = 'PREFLIGHT_PASS' if ran.returncode == 0 else 'PREFLIGHT_FAIL'
                        state['preflight'] = dict(returncode=ran.returncode, log_sha256=sha(DEPLOY / 'PREFLIGHT.log'), log_tail=ran.stdout[-6000:], config_sha256=C1_CONFIG_SHA, environment_script_sha256=ENV_SHA)
                        save(); self.send_json(dict(status=state['status'], preflight=state['preflight'])); return
                    if route == '/submit':
                        need(state['status'] == 'PREFLIGHT_PASS' and not state['submitted'], 'ONE_SUBMISSION_AFTER_PREFLIGHT')
                        package_pins()
                        with (DEPLOY / 'SUBMIT_ATTEMPT.json').open('x') as f: json.dump(dict(candidate=state['candidate'], retries=0), f)
                        state['status'] = 'SUBMISSION_ATTEMPTED'; save()
                        ran = subprocess.run(['sbatch', '--parsable', str(PACKAGE / 'run_encode.slurm')], cwd=PACKAGE, capture_output=True, text=True, timeout=30)
                        state['submission'] = dict(returncode=ran.returncode, stdout=ran.stdout, stderr=ran.stderr)
                        if ran.returncode == 0:
                            job = ran.stdout.strip().split(';')[0]; need(job.isdigit(), 'JOB_ID')
                            state.update(status='SUBMITTED', submitted=True, job_id=job)
                        else: state['status'] = 'SUBMIT_FAILED_NO_RETRY'
                        save(); self.send_json(state); return
                    self.send_error(404)
            except Exception as exc:
                state['last_error'] = str(exc); save(); self.send_json(dict(error=str(exc), state=state['status']), 409)
    server = ThreadingHTTPServer(('127.0.0.1', 18794), Handler)
    save(); print('C3_DELIVERY_READY port=18794', flush=True)
    timer = threading.Timer(14400, server.shutdown); timer.daemon = True; timer.start()
    try: server.serve_forever(poll_interval=.5)
    finally: timer.cancel(); server.server_close()
