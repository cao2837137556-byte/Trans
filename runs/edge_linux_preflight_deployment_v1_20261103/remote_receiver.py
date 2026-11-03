"""Loopback-only, pinned Edge preflight transfer and exactly-one Slurm submit.

The user starts this receiver inside their authenticated Linux terminal. It
never opens SSH, installs dependencies, alters the sealed checkout or runs the
formal external evaluation. No credentials are written to public receipts.
"""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import tarfile
import threading
import time

# Snapshot at module load, before the source path can be replaced by a later
# deployment. State reports this running instance's identity, not disk's latest
# bytes. The installer starts this source through runpy with __file__ set.
RECEIVER_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
PORT = 18817
DEPLOYMENT = 'edge_linux_preflight_deployment_v1_20261103'
PACKAGE = 'runs/edge_linux_preflight_package_v1_20261103'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
TSHARK = '/share/software/tshark-4.6.6/bin/tshark'
MAX_CHUNK = 4 * 1024**2
MAX_RESULT = 64 * 1024**2
ARCHIVE_SHA = 'c683ccbe4e3f1b92fc51638ed9345777f6577edc1f171486279e20248f9541d9'
MANIFEST_SHA = 'f61af6ca64c629565e6914ef520c85352b65a5987e7af6d9515d1848cc4ccbd6'
SLURM_PATH_ASSIGNMENTS = {
    'EDGE_PACKAGE_DIR': 'EDGE_PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"',
    'EDGE_ROOT': 'EDGE_ROOT="$(cd -- "${EDGE_PACKAGE_DIR}/../.." && pwd)"',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + str(threading.get_ident()) + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def safe_name(name):
    need(isinstance(name, str) and bool(name), 'ARCHIVE_NAME_TYPE')
    value = PurePosixPath(name)
    need(not value.is_absolute() and '..' not in value.parts and '\\' not in name
         and ':' not in name and value.as_posix() == name and name not in ('.', ''),
         'ARCHIVE_PATH')
    return value


def regular_members(archive, maximum_bytes):
    members = archive.getmembers()
    names = [member.name for member in members]
    need(len(names) == len(set(names)), 'ARCHIVE_DUPLICATE')
    need(sum(member.size for member in members) <= maximum_bytes, 'ARCHIVE_EXPANSION_LIMIT')
    for member in members:
        value = safe_name(member.name)
        need(value.parts[0] == 'edge_preflight_checkout' and len(value.parts) > 1,
             'ARCHIVE_PREFIX')
        need(member.isfile() and not member.issym() and not member.islnk(), 'ARCHIVE_REGULAR_ONLY')
    return members


def adapt_slurm_paths(source, checkout, package):
    """Replace exactly two known assignments; preserve every other source byte."""
    lines = source.decode('utf-8').splitlines(keepends=True)
    replacements = []
    for name, value in (('EDGE_PACKAGE_DIR', package), ('EDGE_ROOT', checkout)):
        expected = SLURM_PATH_ASSIGNMENTS[name]
        positions = [i for i, line in enumerate(lines) if line.rstrip('\r\n').startswith(name + '=')]
        need(len(positions) == 1 and lines[positions[0]].rstrip('\r\n') == expected,
             'SLURM_PATH_ASSIGNMENT_IDENTITY:' + name)
        index = positions[0]
        ending = lines[index][len(expected):]
        replacement = name + '=' + shlex.quote(str(value))
        lines[index] = replacement + ending
        replacements.append(dict(variable=name, original=expected, replacement=replacement))
    return ''.join(lines).encode('utf-8'), replacements


class Receiver:
    def __init__(self, config, root=ROOT, runner=subprocess.run):
        self.root = Path(root).resolve()
        self.here = self.root / 'runs' / DEPLOYMENT
        self.incoming = self.here / 'incoming'
        self.raw = self.here / 'raw'
        self.unpack = self.here / 'unpacked'
        self.checkout = self.unpack / 'edge_preflight_checkout'
        self.outputs = self.here / 'outputs'
        self.config = config
        self.receiver_source_sha256 = RECEIVER_SOURCE_SHA256
        self.runner = runner
        self.lock = threading.RLock()
        self.last_error = None
        need(set(config['files']) == {'archive', 'NORMAL', 'HTTP', 'UDP'}, 'EXACT_DELIVERY_FILES')
        need(config['archive_manifest_sha256'] == MANIFEST_SHA, 'PINNED_MANIFEST_IDENTITY')
        need(config['files']['archive']['sha256'] == ARCHIVE_SHA, 'PINNED_ARCHIVE_IDENTITY')
        for key, item in config['files'].items():
            need(safe_name(item['filename']).name == item['filename'], 'FLAT_INPUT_NAME')
            need(type(item['bytes']) is int and item['bytes'] > 0
                 and re.fullmatch(r'[a-f0-9]{64}', item['sha256']), 'FILE_SCHEMA')
        for directory in (self.here, self.incoming, self.raw, self.outputs):
            directory.mkdir(parents=True, exist_ok=True)
        binding = {k: config[k] for k in ('files', 'archive_manifest_sha256')}
        binding_file = self.here / 'DELIVERY_BINDING.json'
        if binding_file.exists():
            need(read(binding_file) == binding, 'PREEXISTING_DIFFERENT_DELIVERY')
        else:
            write(binding_file, binding)

    def path(self, key):
        need(key in self.config['files'], 'UNKNOWN_UPLOAD_KEY')
        return (self.incoming if key == 'archive' else self.raw) / self.config['files'][key]['filename']

    def file_state(self, key):
        item = self.config['files'][key]
        target = self.path(key)
        partial = target.with_name(target.name + '.part')
        pin = target.with_name(target.name + '.verified.json')
        complete = False
        if target.exists():
            need(target.is_file() and target.stat().st_size == item['bytes'], 'EXISTING_INPUT_SIZE:' + key)
            old = read(pin) if pin.exists() else None
            stat = target.stat()
            if old != dict(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=item['sha256']):
                need(sha(target) == item['sha256'], 'EXISTING_INPUT_SHA:' + key)
                write(pin, dict(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=item['sha256']))
            complete = True
        elif partial.exists() and partial.stat().st_size == item['bytes']:
            self.finalize(key)
            complete = True
        offset = item['bytes'] if complete else partial.stat().st_size if partial.exists() else 0
        need(0 <= offset <= item['bytes'], 'UPLOAD_OVERSIZE:' + key)
        return dict(offset=offset, bytes=item['bytes'], sha256=item['sha256'], complete=complete)

    def finalize(self, key):
        target = self.path(key)
        part = target.with_name(target.name + '.part')
        item = self.config['files'][key]
        need(part.stat().st_size == item['bytes'] and sha(part) == item['sha256'], 'UPLOAD_FINAL_PIN:' + key)
        need(not target.exists(), 'UPLOAD_DESTINATION_EXISTS')
        part.replace(target)
        stat = target.stat()
        write(target.with_name(target.name + '.verified.json'),
              dict(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=item['sha256']))

    def upload(self, key, payload, offset, chunk_sha):
        with self.lock:
            need(len(payload) <= MAX_CHUNK and payload, 'UPLOAD_CHUNK_SIZE')
            need(hashlib.sha256(payload).hexdigest() == chunk_sha, 'UPLOAD_CHUNK_SHA')
            current = self.file_state(key)
            if current['complete']:
                return current
            need(type(offset) is int and offset == current['offset'], 'UPLOAD_OFFSET')
            need(offset + len(payload) <= current['bytes'], 'UPLOAD_OVERFLOW')
            need(shutil.disk_usage(self.here).free > len(payload) + 256 * 1024**2, 'UPLOAD_DISK_HEADROOM')
            part = self.path(key).with_name(self.path(key).name + '.part')
            with part.open('ab' if offset else 'xb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if offset + len(payload) == current['bytes']:
                self.finalize(key)
            return self.file_state(key)

    def phase(self, name, **extra):
        write(self.here / 'PREPARE_STATUS.json', dict(status='PREPARING', stage=name, **extra))

    def shell_environment(self):
        root = self.root.as_posix()
        return ('source ' + shlex.quote(root + '/frontend_compat_v1/environment.sh') + '\n'
                + 'export PYTHONPATH=' + shlex.quote(root + '/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'
                + root + '/environment/vendor_py311_v1') + ':"${PYTHONPATH:-}"\n'
                + 'export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUTF8=1\n')

    def storage(self):
        disk = shutil.disk_usage(self.here)
        values = dict(free_bytes=disk.free, total_bytes=disk.total,
                      shared_filesystem_free_is_not_personal_quota=True)
        for name, command in (('df', ['df', '-h', str(self.here)]),
                              ('quota', ['quota', '-s']),
                              ('lustre_quota', ['lfs', 'quota', '-u', str(os.getuid()), str(self.here)])):
            try:
                result = self.runner(command, capture_output=True, text=True, timeout=10)
                values[name] = dict(returncode=result.returncode, stdout=result.stdout[-12000:], stderr=result.stderr[-2000:])
            except (OSError, subprocess.SubprocessError) as error:
                values[name] = dict(unavailable=repr(error))
        write(self.here / 'STORAGE_RECEIPT.json', values)
        return values

    def validate_extracted(self):
        folder = self.checkout / PACKAGE
        manifest_path = folder / 'PACKAGE_MANIFEST.json'
        need(sha(manifest_path) == self.config['archive_manifest_sha256'], 'EXTRACTED_MANIFEST_PIN')
        manifest = read(manifest_path)
        checked = 0
        for name, item in manifest['files'].items():
            safe_name(name)
            path = (self.checkout / name).resolve()
            need(path.is_relative_to(self.checkout.resolve()) and path.is_file(), 'MANIFEST_PATH')
            need(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'MANIFEST_FILE_PIN:' + name)
            checked += 1
        contract = read(folder / 'PACKAGE_CONTRACT.json')
        need(contract['total_preflight_logical_with_probes'] == 91
             and not contract['full_quality_evaluation_authorized'], 'PREFLIGHT_SCOPE')
        return dict(files=checked, manifest_sha256=sha(manifest_path), contract=contract)

    def create_path_adapter(self):
        original = self.checkout / PACKAGE / 'preflight.slurm'
        manifest = read(self.checkout / PACKAGE / 'PACKAGE_MANIFEST.json')
        need(sha(original) == manifest['files'][PACKAGE + '/preflight.slurm']['sha256'],
             'ORIGINAL_SLURM_MANIFEST_PIN')
        adapted, replacements = adapt_slurm_paths(original.read_bytes(),
            self.checkout.resolve().as_posix(), (self.checkout / PACKAGE).resolve().as_posix())
        target = self.here / 'PREFLIGHT_PATH_ADAPTER.slurm'
        target.write_bytes(adapted)
        syntax = self.runner(['bash', '-n', str(target)], capture_output=True, text=True, timeout=10)
        need(syntax.returncode == 0, 'SLURM_PATH_ADAPTER_SYNTAX')
        return dict(schema='EDGE_PREFLIGHT_SLURM_PATH_ADAPTER_V1',
                    original_slurm_path=original.resolve().as_posix(), original_slurm_sha256=sha(original),
                    adapter_path=target.resolve().as_posix(), adapter_sha256=sha(target),
                    checkout_root=self.checkout.resolve().as_posix(),
                    package_directory=(self.checkout / PACKAGE).resolve().as_posix(),
                    replacements=replacements, resource_directives_unchanged=True)

    def validate_path_adapter(self, prepared):
        adapter = prepared.get('slurm_path_adapter')
        need(isinstance(adapter, dict), 'SLURM_PATH_ADAPTER_REQUIRED')
        target = self.here / 'PREFLIGHT_PATH_ADAPTER.slurm'
        original = self.checkout / PACKAGE / 'preflight.slurm'
        need(adapter['adapter_path'] == target.resolve().as_posix()
             and adapter['original_slurm_path'] == original.resolve().as_posix()
             and adapter['checkout_root'] == self.checkout.resolve().as_posix()
             and adapter['package_directory'] == (self.checkout / PACKAGE).resolve().as_posix(),
             'SLURM_PATH_ADAPTER_BINDING')
        need(sha(target) == adapter['adapter_sha256'], 'SLURM_PATH_ADAPTER_CHANGED')
        need(sha(original) == adapter['original_slurm_sha256'], 'ORIGINAL_SLURM_CHANGED')
        expected, replacements = adapt_slurm_paths(original.read_bytes(),
            adapter['checkout_root'], adapter['package_directory'])
        need(hashlib.sha256(expected).hexdigest() == adapter['adapter_sha256']
             and replacements == adapter['replacements'], 'SLURM_PATH_ADAPTER_SCOPE')

    def prepare(self):
        with self.lock:
            receipt_path = self.here / 'PREPARE_RECEIPT.json'
            if receipt_path.exists():
                receipt = read(receipt_path)
                need(receipt['status'] == 'PREPARED_NOT_SUBMITTED', 'PREVIOUS_PREPARE_FAILED')
                self.validate_extracted()
                self.validate_path_adapter(receipt)
                return receipt
            self.phase('INPUT_HASHES_AND_STORAGE')
            for key in self.config['files']:
                need(self.file_state(key)['complete'], 'INPUT_NOT_COMPLETE:' + key)
                need(sha(self.path(key)) == self.config['files'][key]['sha256'], 'INPUT_READBACK_PIN:' + key)
            storage = self.storage()
            need(storage['free_bytes'] > self.config['files']['archive']['bytes'] + 512 * 1024**2,
                 'EXTRACTION_DISK_HEADROOM')
            self.phase('SAFE_EXTRACT')
            reused_extraction = self.unpack.exists() and any(self.unpack.iterdir())
            if reused_extraction:
                # A decoder/runtime check can fail after extraction completed.
                # Reuse only a complete byte-verified checkout; partial or
                # changed files still require explicit repair and review.
                self.phase('EXISTING_EXTRACTION_MANIFEST_READBACK')
                try:
                    validated = self.validate_extracted()
                except (OSError, ValueError, KeyError, TypeError) as error:
                    raise ValueError('PARTIAL_EXTRACTION_REQUIRES_MANUAL_REVIEW:'
                                     + repr(error)) from error
            else:
                self.unpack.mkdir(exist_ok=True)
                with tarfile.open(self.path('archive'), 'r:') as archive:
                    members = regular_members(archive, self.config['files']['archive']['bytes'])
                    for member in members:
                        destination = self.unpack.joinpath(*PurePosixPath(member.name).parts)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        need(not destination.exists(), 'EXTRACTION_DESTINATION_EXISTS')
                        with archive.extractfile(member) as src, destination.open('xb') as out:
                            shutil.copyfileobj(src, out, 4 * 1024**2)
                self.phase('MANIFEST_READBACK')
                validated = self.validate_extracted()
            for role, item in validated['contract']['raw_inputs_separate_not_archived'].items():
                need(self.path(role).name == item['filename']
                     and self.path(role).stat().st_size == item['bytes'] and sha(self.path(role)) == item['sha256'],
                     'RAW_CONTRACT_PIN:' + role)
            self.phase('EXISTING_RUNTIME_METADATA')
            metadata_code = "import json,platform,importlib.metadata as m;print(json.dumps({'python':platform.python_version(),'numpy':m.version('numpy'),'torch':m.version('torch'),'transformers':m.version('transformers')}))"
            command = self.shell_environment() + 'exec ' + shlex.quote(PYTHON) + ' -X utf8 -B -c ' + shlex.quote(metadata_code)
            result = self.runner(['bash', '-c', command], capture_output=True, text=True, timeout=45)
            need(result.returncode == 0, 'RUNTIME_METADATA_FAILED:' + result.stderr[-1500:])
            observed = json.loads(result.stdout.strip().splitlines()[-1])
            expected = validated['contract']['expected_runtime']
            need(observed['python'] == expected['Python'] and observed['numpy'] == expected['numpy']
                 and observed['torch'].split('+')[0] == expected['torch']
                 and observed['transformers'] == expected['transformers'], 'RUNTIME_METADATA_IDENTITY')
            # Decoder uses the same library environment as the actual Slurm
            # worker. A bare binary invocation can fail before main() when
            # shared libraries are supplied by environment.sh.
            decoder_command = self.shell_environment() + 'exec ' + shlex.quote(TSHARK) + ' --version'
            try:
                decoder = self.runner(['bash', '-c', decoder_command],
                                      capture_output=True, text=True, timeout=15)
            except (OSError, subprocess.SubprocessError) as error:
                captured = {}
                for field in ('stdout', 'stderr'):
                    value = getattr(error, field, None)
                    captured[field] = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
                write(self.here / 'DECODER_IDENTITY.json', dict(
                    status='FAILED', binary=TSHARK, expected_version=expected['TShark'],
                    same_worker_environment=True, returncode=None,
                    error=repr(error), **captured))
                raise
            decoder_first_line = decoder.stdout.splitlines()[0] if decoder.stdout.splitlines() else ''
            decoder_ok = (decoder.returncode == 0 and re.search(
                r'(?<![\d.])' + re.escape(expected['TShark']) + r'(?![\d.])',
                decoder_first_line) is not None)
            write(self.here / 'DECODER_IDENTITY.json', dict(
                status='PASS' if decoder_ok else 'FAILED', binary=TSHARK,
                expected_version=expected['TShark'], same_worker_environment=True,
                returncode=decoder.returncode, stdout=decoder.stdout, stderr=decoder.stderr))
            need(decoder_ok, 'TSHARK_IDENTITY')
            self.phase('SEALED_SLURM_PATH_ADAPTER')
            path_adapter = self.create_path_adapter()
            wrapper = ('#!/usr/bin/env bash\nset -euo pipefail\numask 077\n' + self.shell_environment()
                       + 'export EDGE_PYTHON=' + shlex.quote(PYTHON) + '\n'
                       + 'export EDGE_TSHARK=' + shlex.quote(TSHARK) + '\n'
                       + 'export EDGE_RAW_DIRECTORY=' + shlex.quote(self.raw.as_posix()) + '\n'
                       + 'export EDGE_OUTPUT_BASE=' + shlex.quote(self.outputs.as_posix()) + '\n'
                       + 'cd ' + shlex.quote(self.checkout.as_posix()) + '\n'
                       + 'exec sbatch --parsable --partition=amd ' + shlex.quote(path_adapter['adapter_path']) + '\n')
            script = self.here / 'SUBMIT_PREFLIGHT_ONCE.sh'
            script.write_bytes(wrapper.encode('utf-8'))
            syntax = self.runner(['bash', '-n', str(script)], capture_output=True, text=True, timeout=10)
            need(syntax.returncode == 0, 'SUBMIT_WRAPPER_SYNTAX')
            receipt = dict(status='PREPARED_NOT_SUBMITTED', archive_sha256=ARCHIVE_SHA,
                           manifest_files_verified=validated['files'], runtime_metadata=observed,
                           tshark_version=decoder_first_line, submit_wrapper_sha256=sha(script),
                           reused_verified_extraction=bool(reused_extraction),
                           slurm_path_adapter=path_adapter,
                           storage=storage, training=False, model_loaded=False, formal_external_evaluation=False)
            write(receipt_path, receipt)
            self.phase('COMPLETE_PREPARED_NOT_SUBMITTED')
            return receipt

    def submit(self):
        with self.lock:
            confirmed = self.here / 'SUBMIT_RECEIPT.json'
            attempted = self.here / 'SUBMIT_ATTEMPT.json'
            if confirmed.exists():
                return read(confirmed)
            need(not attempted.exists(), 'STOP_UNCERTAIN_SUBMISSION_NO_RETRY')
            prepared = read(self.here / 'PREPARE_RECEIPT.json')
            need(prepared['status'] == 'PREPARED_NOT_SUBMITTED', 'PREPARE_REQUIRED')
            script = self.here / 'SUBMIT_PREFLIGHT_ONCE.sh'
            need(sha(script) == prepared['submit_wrapper_sha256'], 'SUBMIT_WRAPPER_CHANGED')
            self.validate_extracted()
            self.validate_path_adapter(prepared)
            write(attempted, dict(status='SUBMIT_ATTEMPT_RECORDED_NO_RETRY',
                  created_utc=datetime.now(timezone.utc).isoformat(), script_sha256=sha(script),
                  allowed_jobs=1, wall_seconds=600, formal_external_evaluation=False))
            try:
                result = self.runner(['bash', str(script)], capture_output=True, text=True, timeout=20)
                # Any outcome after starting sbatch is uncertain until a job id
                # has been durably saved; even a nonzero exit never auto-retries.
                need(result.returncode == 0, 'SBATCH_NOT_CONFIRMED:' + result.stderr[-1500:])
                lines = [x.strip() for x in result.stdout.splitlines() if x.strip()]
                need(lines and re.fullmatch(r'\d+(?:;[A-Za-z0-9_.-]+)?', lines[-1]), 'SBATCH_RESPONSE_UNCERTAIN')
                job_id = lines[-1].split(';', 1)[0]
                receipt = dict(status='SUBMITTED', job_id=job_id,
                     created_utc=datetime.now(timezone.utc).isoformat(), partition='amd',
                     cpu=1, memory_gib=6, wall_seconds=600, automatic_retry=False,
                     formal_external_evaluation=False, training=False,
                     output_directory=str(self.outputs / ('edge_preflight_' + job_id)))
                write(confirmed, receipt)
                return receipt
            except BaseException as error:
                self.last_error = repr(error)
                write(self.here / 'SUBMIT_UNCERTAIN.json', dict(status='STOP_UNCERTAIN_NO_RETRY', error=repr(error)))
                raise

    def state(self):
        with self.lock:
            files = {key: self.file_state(key) for key in self.config['files']}
            job = read(self.here / 'SUBMIT_RECEIPT.json') if (self.here / 'SUBMIT_RECEIPT.json').exists() else None
            state = dict(status='READY_TO_UPLOAD', files=files, job=job, last_error=self.last_error,
                         receiver_source_sha256=self.receiver_source_sha256,
                         scheduler=None, delivery_status=None, delivery_result=None,
                         real_slice_status=None, result_ready=False,
                         prepare_receipt=read(self.here / 'PREPARE_RECEIPT.json')
                         if (self.here / 'PREPARE_RECEIPT.json').exists() else None,
                         prepare_status=read(self.here / 'PREPARE_STATUS.json')
                         if (self.here / 'PREPARE_STATUS.json').exists() else None)
            if (self.here / 'SUBMIT_UNCERTAIN.json').exists():
                state.update(status='STOP_UNCERTAIN_NO_RETRY', last_error=read(self.here / 'SUBMIT_UNCERTAIN.json')['error'])
            elif (self.here / 'SUBMIT_ATTEMPT.json').exists() and job is None:
                state.update(status='STOP_UNCERTAIN_NO_RETRY')
            elif (self.here / 'PREPARE_RECEIPT.json').exists():
                state['status'] = 'PREPARED_NOT_SUBMITTED'
            if job:
                state['status'] = 'SUBMITTED'
                output = Path(job['output_directory'])
                for field, relative in [('delivery_status', 'DELIVERY_STATUS.json'),
                                        ('delivery_result', 'DELIVERY_RESULT.json'),
                                        ('real_slice_status', 'real_slice/STATUS.json')]:
                    path = output / relative
                    if path.exists():
                        try:
                            state[field] = read(path)
                        except (OSError, ValueError) as error:
                            state[field] = dict(read_error=repr(error))
                try:
                    scheduler = self.runner(['sacct', '-j', job['job_id'], '--noheader', '--parsable2',
                        '--format=JobIDRaw,State,ExitCode,Elapsed,MaxRSS'], capture_output=True, text=True, timeout=8)
                    state['scheduler'] = dict(returncode=scheduler.returncode,
                                             stdout=scheduler.stdout[-10000:], stderr=scheduler.stderr[-2000:])
                except (OSError, subprocess.SubprocessError) as error:
                    state['scheduler'] = dict(error=repr(error))
                if state['delivery_result']:
                    state['status'] = state['delivery_result'].get('status', 'RESULT_RECEIPT_PRESENT')
                    state['result_ready'] = True
                elif state['scheduler'] and any(x in state['scheduler'].get('stdout', '')
                        for x in ('FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'COMPLETED')):
                    state['status'] = 'SCHEDULER_TERMINAL_NO_FINAL_RECEIPT'
                    state['result_ready'] = True
            return state

    def results(self):
        with self.lock:
            state = self.state()
            need(state['job'] and state['result_ready'], 'RESULTS_NOT_READY')
            output = Path(state['job']['output_directory'])
            files = []
            for directory in (output, self.checkout):
                if not directory.exists():
                    continue
                if directory == self.checkout:
                    candidates = [directory / ('edge-preflight-' + state['job']['job_id'] + ending)
                                  for ending in ('.out', '.err')]
                else:
                    candidates = list(directory.rglob('*'))
                for path in candidates:
                    if path.is_file() and not path.is_symlink() and path.suffix in ('.json', '.jsonl', '.log', '.out', '.err', '.sha256'):
                        need(path.stat().st_size <= 16 * 1024**2, 'RESULT_FILE_TOO_LARGE:' + path.name)
                        files.append(path)
            files += [p for p in self.here.glob('*.json') if not p.name.startswith('.')]
            need(sum(p.stat().st_size for p in set(files)) <= MAX_RESULT - 1024**2, 'RESULT_ARCHIVE_SIZE')
            members = {path.relative_to(self.here).as_posix(): path for path in set(files)}
            synthesized = []
            if not (output / 'DELIVERY_RESULT.json').exists():
                stop_path = self.here / 'EXPORT_TERMINAL_WITHOUT_RESULT.json'
                write(stop_path, dict(status='STOPPED_NO_RETRY', generated_export_receipt=True,
                     reason='SCHEDULER_TERMINAL_WITHOUT_FINAL_DELIVERY_RESULT',
                     actual_delivery_result_emitted=False, scheduler=state['scheduler'],
                     job_id=state['job']['job_id'], final_runtime_gate_pass=False,
                     scope='ENGINEERING_ONLY_NOT_FULL_EVALUATION', automatic_retry=False))
                name = output.relative_to(self.here).as_posix() + '/DELIVERY_RESULT.json'
                members[name] = stop_path
                synthesized.append(name)
            result_manifest = dict(schema='EDGE_PREFLIGHT_RESULT_EXPORT_MANIFEST_V1',
                files={name: dict(bytes=path.stat().st_size, sha256=sha(path))
                       for name, path in sorted(members.items())},
                synthesized_failure_receipts=synthesized, formal_external_evaluation=False)
            encoded_manifest = (json.dumps(result_manifest, indent=2) + '\n').encode('utf-8')
            archive = self.here / 'preflight_results.tar'
            temporary = archive.with_name(archive.name + '.tmp')
            with tarfile.open(temporary, 'w') as stream:
                for name, path in sorted(members.items()):
                    need(path.resolve().is_relative_to(self.here.resolve()), 'RESULT_FILE_SCOPE')
                    stream.add(path, arcname=name, recursive=False)
                info = tarfile.TarInfo('RESULT_MANIFEST.json')
                info.size = len(encoded_manifest)
                stream.addfile(info, io.BytesIO(encoded_manifest))
            temporary.replace(archive)
            need(archive.stat().st_size <= MAX_RESULT, 'RESULT_ARCHIVE_FINAL_SIZE')
            return archive


def main(config):
    receiver = Receiver(config)
    token = config['token']
    need(isinstance(token, str) and re.fullmatch(r'[a-f0-9]{48,128}', token), 'TOKEN_FORMAT')

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_):
            pass

        def respond(self, value, status=200):
            payload = json.dumps(value, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(payload)
            self.close_connection = True

        def action(self):
            parts = self.path.split('/')
            need(len(parts) >= 3 and hmac.compare_digest(parts[1], token), 'NOT_AUTHORIZED')
            return '/'.join(parts[2:])

        def do_GET(self):
            try:
                action = self.action()
                if action == 'state':
                    self.respond(receiver.state())
                elif action == 'results':
                    path = receiver.results()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/x-tar')
                    self.send_header('Content-Length', str(path.stat().st_size))
                    self.send_header('X-Content-Total-Bytes', str(path.stat().st_size))
                    self.send_header('X-Content-SHA256', sha(path))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    with path.open('rb') as stream:
                        shutil.copyfileobj(stream, self.wfile, 1024**2)
                    self.close_connection = True
                else:
                    raise ValueError('UNKNOWN_ACTION')
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except BaseException as error:
                receiver.last_error = repr(error)
                self.respond(dict(error=repr(error)), 409)

        def do_POST(self):
            try:
                action = self.action()
                size = int(self.headers.get('Content-Length', '0'))
                need(0 <= size <= MAX_CHUNK, 'REQUEST_SIZE')
                body = self.rfile.read(size)
                need(len(body) == size, 'REQUEST_SHORT_BODY')
                if action.startswith('upload/'):
                    self.respond(receiver.upload(action.split('/', 1)[1], body,
                        int(self.headers.get('X-Offset', '-1')), self.headers.get('X-Chunk-SHA256', '')))
                elif action in ('prepare', 'submit'):
                    need(size == 0, 'EMPTY_ACTION_BODY_REQUIRED')
                    self.respond(receiver.prepare() if action == 'prepare' else receiver.submit())
                else:
                    raise ValueError('UNKNOWN_ACTION')
            except (BrokenPipeError, ConnectionResetError):
                # A lost HTTP response must not turn an already committed
                # upload/prepare/submit into a new server-side action failure.
                self.close_connection = True
            except BaseException as error:
                receiver.last_error = repr(error)
                write(receiver.here / 'LAST_ERROR.json', dict(error=repr(error),
                      created_utc=datetime.now(timezone.utc).isoformat()))
                self.respond(dict(error=repr(error)), 409)

    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    server.daemon_threads = True
    lifetime = threading.Timer(4 * 3600, server.shutdown)
    lifetime.daemon = True
    lifetime.start()
    print('EDGE_PREFLIGHT_DELIVERY_READY', flush=True)
    try:
        server.serve_forever(poll_interval=1)
    finally:
        server.server_close()
