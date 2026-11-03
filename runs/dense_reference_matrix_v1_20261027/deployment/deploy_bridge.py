"""Fixed r2 archive, fixed prefix job; temporary authenticated loopback bridge.

Deployment transport only. No endpoint accepts commands, filenames, paths,
arbitrary scheduler arguments, or target-evaluation permission. Submission is
at most once, including an uncertain scheduler timeout. Run beside a private
.bootstrap.json; no secrets are printed or returned.
"""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import time

ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
NAME = 'dense_reference_matrix_v1_20261027'
PACKAGE = ROOT/'runs'/NAME
HERE = ROOT/'runs/dense_reference_deployment_20261027'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
SBATCH = '/usr/local/slurm-25.11.0-build/bin/sbatch'
ARCHIVE_SHA = '43c31bd5ba3dc169aa95fae0079f2b856801043c46fd7862736110cb603b0140'
MANIFEST_SHA = 'ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120'
ARCHIVE_SIZE = 115876260
MANIFEST_FILES = 1492
TAR_MEMBERS = 1572
TAR_BYTES = 190255172
MAX_CHUNK = 4*1024**2
PORT = 18781
STATUS_PORT = 18780
LIFETIME_SECONDS = 3600


def require(ok, name):
    if not ok:
        raise ValueError(name)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def payload(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)+'\n').encode()


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('wb') as stream:
        stream.write(payload(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)


def exclusive(path, value):
    """A crash after O_EXCL still consumes the attempt; never mint a retry."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload(value))
        stream.flush()
        os.fsync(stream.fileno())


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def approval_valid(value):
    require(isinstance(value, dict) and value.get('user_authorized') is True and
            value.get('scope') == 'DENSE_REFERENCE_V1' and value.get('package_sha256') == MANIFEST_SHA and
            value.get('stages') == ['runtime', 'encode', 'source_cal'] and value.get('retries') == 0 and
            type(value.get('total_wall_seconds')) is int and 0 < value['total_wall_seconds'] <= 43200 and
            bool(value.get('evidence')), 'PREFIX_APPROVAL_IDENTITY_OR_SCOPE')


def bootstrap_valid(config):
    require(isinstance(config, dict) and config.get('schema') == 'paper04-dense-deploy-bootstrap-v1' and
            set(config) == {'schema', 'token', 'status_token', 'approval'}, 'BOOTSTRAP_SCHEMA')
    for name in ('token', 'status_token'):
        require(isinstance(config[name], str) and 32 <= len(config[name]) <= 256 and
                re.fullmatch(r'[A-Za-z0-9_-]+', config[name]) is not None, 'PRIVATE_TOKEN_FORMAT')
    require(config['token'] != config['status_token'], 'SEPARATE_TRANSPORT_STATUS_TOKENS_REQUIRED')
    approval_valid(config['approval'])


def member_path(name):
    require(isinstance(name, str) and name and '\\' not in name and '\x00' not in name,
            'UNSAFE_ARCHIVE_MEMBER')
    p = PurePosixPath(name.rstrip('/'))
    require(not p.is_absolute() and '..' not in p.parts and p.parts and p.parts[0] == NAME and
            str(p) == name.rstrip('/'), 'UNSAFE_ARCHIVE_MEMBER')
    return p


def parse_manifest(data):
    require(hashlib.sha256(data).hexdigest() == MANIFEST_SHA, 'MANIFEST_IDENTITY')
    expected = {}
    for line in data.decode('utf-8').splitlines():
        digest, name = line.split('  ', 1)
        require(re.fullmatch('[0-9a-f]{64}', digest) is not None, 'INVALID_MANIFEST_SHA')
        p = member_path(NAME+'/'+name)
        require(len(p.parts) > 1 and name not in expected and name != 'PACKAGE_SHA256SUMS', 'INVALID_MANIFEST_MEMBER')
        expected[name] = digest
    require(len(expected) == MANIFEST_FILES, 'MANIFEST_FILE_COUNT')
    return expected


def inspect_archive(archive):
    require(archive.stat().st_size == ARCHIVE_SIZE and sha(archive) == ARCHIVE_SHA, 'SEALED_ARCHIVE_IDENTITY')
    with tarfile.open(archive, 'r:gz') as handle:
        members = handle.getmembers()
        require(len(members) == TAR_MEMBERS and sum(m.size for m in members) == TAR_BYTES, 'ARCHIVE_MEMBER_BUDGET')
        names, files = set(), set()
        for member in members:
            p = member_path(member.name)
            key = str(p)
            require(key not in names and (member.isfile() or member.isdir()), 'UNSAFE_OR_DUPLICATE_ARCHIVE_MEMBER')
            require(member.size >= 0 and (not member.isdir() or member.size == 0), 'ARCHIVE_MEMBER_SIZE')
            names.add(key)
            if member.isfile():
                require(len(p.parts) > 1, 'ROOT_MUST_BE_DIRECTORY')
                files.add(key)
        manifest = handle.extractfile(NAME+'/PACKAGE_SHA256SUMS').read()
        expected = parse_manifest(manifest)
        require(files == {NAME+'/'+name for name in expected} | {NAME+'/PACKAGE_SHA256SUMS'}, 'MANIFEST_MEMBER_SET')
        for member in members:
            if member.isfile() and member.name != NAME+'/PACKAGE_SHA256SUMS':
                relative = str(member_path(member.name).relative_to(NAME))
                h = hashlib.sha256()
                stream = handle.extractfile(member)
                for block in iter(lambda: stream.read(4*1024**2), b''):
                    h.update(block)
                require(h.hexdigest() == expected[relative], 'ARCHIVE_FILE_SHA:'+relative)
    return expected


def verify_tree(expected=None):
    require(PACKAGE.is_dir() and not PACKAGE.is_symlink(), 'DEPLOYED_PACKAGE_MISSING')
    expected = parse_manifest((PACKAGE/'PACKAGE_SHA256SUMS').read_bytes()) if expected is None else expected
    actual = set()
    for path in PACKAGE.rglob('*'):
        require(not path.is_symlink(), 'DEPLOYED_SYMLINK_FORBIDDEN')
        if path.is_file():
            relative = path.relative_to(PACKAGE).as_posix()
            if relative.split('/')[0] not in ('.private', 'runtime') and relative != 'PACKAGE_SHA256SUMS':
                actual.add(relative)
    require(actual == set(expected), 'DEPLOYED_MEMBER_SET')
    for relative, digest in expected.items():
        require(sha(PACKAGE/relative) == digest, 'POST_WRITE_FILE_SHA:'+relative)
    return expected


def upload_state():
    done, partial = HERE/'sealed_package.tar.gz', HERE/'sealed_package.tar.gz.part'
    if done.exists():
        require(done.stat().st_size == ARCHIVE_SIZE, 'COMPLETED_ARCHIVE_SIZE_CHANGED')
        return dict(status='UPLOADED_VERIFIED', received_bytes=ARCHIVE_SIZE, total_bytes=ARCHIVE_SIZE,
                    archive_sha256=ARCHIVE_SHA)
    current = partial.stat().st_size if partial.exists() else 0
    require(0 <= current <= ARCHIVE_SIZE, 'PARTIAL_ARCHIVE_SIZE_INVALID')
    return dict(status='UPLOADING', received_bytes=current, total_bytes=ARCHIVE_SIZE, max_chunk_bytes=MAX_CHUNK)


def upload_chunk(body, content_range, chunk_sha):
    require(isinstance(body, bytes) and 0 < len(body) <= MAX_CHUNK, 'CHUNK_LENGTH')
    require(re.fullmatch('[0-9a-f]{64}', chunk_sha or '') is not None and
            hashlib.sha256(body).hexdigest() == chunk_sha, 'CHUNK_SHA256')
    match = re.fullmatch(r'bytes ([0-9]+)-([0-9]+)/([0-9]+)', content_range or '')
    require(match is not None, 'CONTENT_RANGE')
    start, end, total = map(int, match.groups())
    require(total == ARCHIVE_SIZE and 0 <= start <= end < total and end-start+1 == len(body), 'CHUNK_RANGE')
    state = upload_state()
    path = HERE/('sealed_package.tar.gz' if state['status'] == 'UPLOADED_VERIFIED' else 'sealed_package.tar.gz.part')
    current = state['received_bytes']
    if start < current:
        require(end < current, 'PARTIAL_OVERLAP_QUERY_STATUS_AND_RESUME')
        with path.open('rb') as stream:
            stream.seek(start)
            require(stream.read(len(body)) == body, 'REPLAYED_CHUNK_BYTES_MISMATCH')
        return dict(state, replayed_chunk=True)
    require(start == current and state['status'] != 'UPLOADED_VERIFIED', 'CHUNK_OFFSET_MUST_MATCH_RECEIVED')
    with path.open('ab') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    if end+1 == ARCHIVE_SIZE:
        require(sha(path) == ARCHIVE_SHA, 'FULL_ARCHIVE_SHA256_MISMATCH_PRESERVE_PARTIAL')
        os.replace(path, HERE/'sealed_package.tar.gz')
        write(HERE/'upload.json', dict(status='UPLOADED_VERIFIED', archive_sha256=ARCHIVE_SHA,
              bytes=ARCHIVE_SIZE, completed_epoch=time.time()))
    return upload_state()


def deploy(config):
    receipt = HERE/'deployment.json'
    if receipt.exists():
        verify_tree()
        return read(receipt)
    require(not PACKAGE.exists() and not (HERE/'DEPLOYMENT_ATTEMPT.json').exists(),
            'PACKAGE_OR_DEPLOYMENT_ATTEMPT_ALREADY_EXISTS_PRESERVE_SCENE')
    archive = HERE/'sealed_package.tar.gz'
    expected = inspect_archive(archive)
    exclusive(HERE/'DEPLOYMENT_ATTEMPT.json', dict(status='ATTEMPTING', epoch=time.time(), automatic_retry=False))
    PACKAGE.mkdir(mode=0o700)
    try:
        with tarfile.open(archive, 'r:gz') as handle:
            for member in handle.getmembers():
                relative = member_path(member.name).relative_to(NAME)
                destination = PACKAGE.joinpath(*relative.parts)
                require(destination.resolve().is_relative_to(PACKAGE.resolve()), 'EXTRACTION_PATH_ESCAPE')
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open('xb') as output:
                        source = handle.extractfile(member)
                        for block in iter(lambda: source.read(4*1024**2), b''):
                            output.write(block)
                    destination.chmod(0o600)
        verify_tree(expected)
        (PACKAGE/'runtime').mkdir(mode=0o700)
        private = PACKAGE/'.private'
        private.mkdir(mode=0o700)
        exclusive(private/'APPROVED.json', config['approval'])
        report = dict(status='DEPLOYED_VERIFIED', archive_sha256=ARCHIVE_SHA,
            package_sha256=MANIFEST_SHA, archive_bytes=ARCHIVE_SIZE, files_verified=MANIFEST_FILES,
            remote_root=str(PACKAGE), approval_sha256=sha(private/'APPROVED.json'), epoch=time.time(),
            stages=['runtime','encode','source_cal'], target_matrix_authorized=False)
        write(receipt, report)
        return report
    except BaseException as exc:
        write(HERE/'deployment_error.json', dict(status='DEPLOYMENT_ERROR_PRESERVE_SCENE',
              error_type=type(exc).__name__, reason=str(exc), automatic_retry=False, epoch=time.time()))
        raise


def _text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else (value or '')


def submit(config):
    receipt = HERE/'submission.json'
    if receipt.exists():
        return read(receipt)
    require(not (HERE/'SUBMISSION_ATTEMPT.json').exists(), 'SUBMISSION_ALREADY_ATTEMPTED_UNKNOWN_NO_REPEAT')
    require((HERE/'deployment.json').is_file(), 'NOT_DEPLOYED')
    verify_tree()
    approval = PACKAGE/'.private/APPROVED.json'
    approval_valid(read(approval))
    require(approval.read_bytes() == payload(config['approval']), 'INSTALLED_APPROVAL_CHANGED')
    require((PACKAGE/'runtime').is_dir(), 'RUNTIME_LOG_DIRECTORY_REQUIRED_BEFORE_SBATCH')
    exclusive(HERE/'SUBMISSION_ATTEMPT.json', dict(status='ATTEMPTING', epoch=time.time(),
              package_sha256=MANIFEST_SHA, automatic_retry=False, command='sbatch --export=NONE hpc/run_dense.slurm'))
    report = dict(epoch=time.time(), automatic_retry=False, package_sha256=MANIFEST_SHA)
    try:
        result = subprocess.run([SBATCH, '--export=NONE', 'hpc/run_dense.slurm'], cwd=PACKAGE,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        report.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        match = re.fullmatch(r'Submitted batch job ([1-9][0-9]*)\s*', result.stdout)
        if result.returncode == 0 and match:
            report.update(status='SUBMITTED', job_id=match[1])
        else:
            report.update(status='SUBMISSION_ERROR_PRESERVE_NO_RETRY')
    except subprocess.TimeoutExpired as exc:
        report.update(status='SUBMISSION_TIMEOUT_UNKNOWN_NO_RETRY', returncode=None,
                      stdout=_text(exc.stdout), stderr=_text(exc.stderr))
    except OSError as exc:
        report.update(status='SUBMISSION_OS_ERROR_PRESERVE_NO_RETRY', returncode=None,
                      error_type=type(exc).__name__, reason=str(exc))
    write(receipt, report)
    return report


def monitor(config):
    receipt = HERE/'monitor.json'
    if receipt.exists():
        return read(receipt)
    submitted = read(HERE/'submission.json')
    job = submitted.get('job_id')
    require(submitted.get('status') == 'SUBMITTED' and isinstance(job, str) and
            re.fullmatch('[1-9][0-9]*', job) is not None, 'ONLY_VERIFIED_SUBMITTED_FIXED_JOB')
    require(not (HERE/'MONITOR_ATTEMPT.json').exists(), 'MONITOR_ALREADY_ATTEMPTED_NO_REPEAT')
    token_file = PACKAGE/'.private'/('status_job_'+job+'.json')
    exclusive(token_file, dict(token=config['status_token'], job_id=job, remote_port=STATUS_PORT))
    exclusive(HERE/'MONITOR_ATTEMPT.json', dict(job_id=job, port=STATUS_PORT, epoch=time.time(), automatic_retry=False))
    log = (HERE/'status_bridge.log').open('ab')
    try:
        proc = subprocess.Popen([PYTHON, '-B', str(PACKAGE/'hpc/status_bridge.py'),
            '--root', str(PACKAGE/'runtime'), '--job-id', job, '--token-file', str(token_file),
            '--port', str(STATUS_PORT)], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True)
    finally:
        log.close()
    report = dict(status='STATUS_BRIDGE_STARTED', job_id=job, pid=proc.pid, port=STATUS_PORT,
                  lifetime_seconds=86400, epoch=time.time(), token_exposed=False)
    write(receipt, report)
    return report


def status():
    result = dict(schema='paper04-dense-deployment-status-v1', upload=upload_state(),
                  package_sha256=MANIFEST_SHA, archive_sha256=ARCHIVE_SHA)
    for name in ('deployment','deployment_error','submission','monitor','DEPLOYMENT_ATTEMPT',
                 'SUBMISSION_ATTEMPT','MONITOR_ATTEMPT'):
        path = HERE/(name+'.json')
        if path.exists():
            try:
                result[name.lower()] = read(path)
            except (OSError, ValueError):
                result[name.lower()] = dict(status='UNREADABLE_PRESERVED_NO_AUTOMATIC_REPEAT')
    return result


def handler_class(config, deadline):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def handle_request(self):
            if time.monotonic() >= deadline:
                self.send_error(410)
                return
            if not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+config['token']):
                self.send_error(403)
                return
            try:
                key = self.command, self.path
                length = int(self.headers.get('Content-Length','0'))
                require(0 <= length <= MAX_CHUNK, 'REQUEST_SIZE')
                if key == ('PUT','/archive'):
                    self.connection.settimeout(30)
                    body = self.rfile.read(length)
                    require(len(body) == length, 'TRUNCATED_CHUNK')
                    value = upload_chunk(body, self.headers.get('Content-Range'), self.headers.get('X-Chunk-SHA256'))
                else:
                    require(length == 0, 'NO_REQUEST_PARAMETERS_ACCEPTED')
                    if key == ('GET','/health'):
                        value = dict(status='READY', schema='paper04-dense-deploy-bridge-v1',
                            package_sha256=MANIFEST_SHA, archive_sha256=ARCHIVE_SHA,
                            archive_bytes=ARCHIVE_SIZE, port=PORT, status_port=STATUS_PORT,
                            max_chunk_bytes=MAX_CHUNK, expires_in_seconds=max(0,int(deadline-time.monotonic())))
                    elif key == ('GET','/status'):
                        value = status()
                    elif key == ('POST','/deploy'):
                        value = deploy(config)
                    elif key == ('POST','/submit'):
                        value = submit(config)
                    elif key == ('POST','/monitor'):
                        value = monitor(config)
                    else:
                        raise ValueError('FIXED_ENDPOINT_ONLY')
                code = 200
            except Exception as exc:
                code, value = 409, dict(status='REQUEST_REJECTED', error_type=type(exc).__name__, reason=str(exc))
            raw = payload(value)
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Connection','close')
            self.end_headers()
            self.wfile.write(raw)

        do_GET = handle_request
        do_PUT = handle_request
        do_POST = handle_request
    return Handler


def main():
    require(Path(__file__).resolve().parent == HERE.resolve(), 'FIXED_BRIDGE_LOCATION_REQUIRED')
    config_path = HERE/'.bootstrap.json'
    require(config_path.is_file() and (config_path.stat().st_mode & 0o077) == 0, 'PRIVATE_BOOTSTRAP_PERMISSIONS')
    config = read(config_path)
    bootstrap_valid(config)
    server = HTTPServer(('127.0.0.1', PORT), handler_class(config, time.monotonic()+LIFETIME_SECONDS))
    server.timeout = 1
    deadline = time.monotonic()+LIFETIME_SECONDS
    try:
        while time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
