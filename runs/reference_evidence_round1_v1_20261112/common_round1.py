"""Shared identities, atomic artifacts and compute resource accounting."""
import csv
import gzip
import hashlib
import io
import json
import os
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOL = 2e-10
POOL = 'UNSW_DEV'
HEADS = ('27', '127', '227', 'ensemble')
RUN = 'reference_evidence_round1_v1_20261112'
ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
PYTHON = Path('/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python')
NUMPY_RUNTIME = Path('runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201')
JOB_NAMES = {'first': 'p04-ref-r1-d', 'eval': 'p04-ref-r1-eval'}
STAGES = {'first': 1, 'eval': 2}
MIB = 1024 ** 2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def load(path):
    return json.loads(read(path))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * MIB), b''):
            digest.update(block)
    return digest.hexdigest()


def uid_sha(uids):
    return hashlib.sha256(''.join(uid + '\n' for uid in uids).encode('utf-8')).hexdigest()


def temp_path(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.with_name(f'{path.name}.{os.getpid()}.tmp')


def write_text(path, text):
    tmp = temp_path(path)
    with tmp.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
    tmp.replace(path)


def dump(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')


def read_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def write_rows(path, records):
    tmp = temp_path(path)
    count = 0
    with tmp.open('wb') as raw, gzip.GzipFile(
        filename='', mode='wb', fileobj=raw, mtime=0
    ) as zipped, io.TextIOWrapper(zipped, encoding='utf-8', newline='\n') as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')
            count += 1
    tmp.replace(path)
    return count


def artifact(path, rows=None):
    path = Path(path)
    result = {'file': path.name, 'sha256': sha(path), 'bytes': path.stat().st_size}
    if rows is not None:
        result['rows'] = int(rows)
    return result


def table(directory, stem, records):
    directory = Path(directory)
    dump(directory / (stem + '.json'), records)
    path = directory / (stem + '.csv')
    tmp = temp_path(path)
    with tmp.open('w', encoding='utf-8', newline='') as stream:
        fields = list(dict.fromkeys(key for row in records for key in row))
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)
    tmp.replace(path)


def evidence_files(directory, names):
    return {name: artifact(directory / name) for name in names}


def verify_artifact(directory, spec):
    name = spec['file']
    require(Path(name).name == name, 'UNSAFE_ARTIFACT_NAME')
    path = Path(directory) / name
    require(path.is_file() and path.stat().st_size == spec['bytes'] and sha(path) == spec['sha256'],
            'ARTIFACT_MISMATCH:' + str(path))
    return path


def verify_package(package):
    package = Path(package)
    manifest = load(package / 'PACKAGE_MANIFEST.json')
    for name, digest in manifest['files'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'PACKAGE_PATH')
        path = package / relative
        require(path.is_file() and sha(path) == digest, 'PACKAGE_SHA:' + name)
        require(b'\r' not in path.read_bytes(), 'PACKAGE_NOT_LF:' + name)
    return manifest


def verify_runtime_paths(project):
    paths = (project / 'frontend_compat_v1/environment.sh',
             project / NUMPY_RUNTIME / 'numpy/__init__.py')
    require(PYTHON.is_file() and all(path.is_file() for path in paths), 'FROZEN_RUNTIME_PATHS')
    return {str(path): sha(path) for path in paths}


class Inputs:
    def __init__(self, project, pins, roles, local=False, progress=None):
        self.project = Path(project).resolve()
        self.roles = set(roles)
        self.local = local
        self.specs = pins['inputs']
        self.resolved = {}
        self.progress = progress

    def allowed_paths(self):
        return {
            self.project / relative
            for spec in self.specs.values() if spec['role'] in self.roles
            for relative in spec['local' if self.local else 'remote']
        }

    def get(self, name):
        spec = self.specs[name]
        require(spec['role'] in self.roles, 'INPUT_ROLE_DENIED:' + name)
        if name in self.resolved:
            return Path(self.resolved[name]['path'])
        candidates = spec['local' if self.local else 'remote']
        for relative in candidates:
            rel = Path(relative)
            require(not rel.is_absolute() and '..' not in rel.parts, 'INPUT_PATH_SCOPE:' + name)
            path = self.project / rel
            if path.is_file() and ('bytes' not in spec or path.stat().st_size == spec['bytes']):
                digest = sha(path)
                if digest == spec.get('sha256') or (name == 'query_context_uids' and spec.get('semantic')):
                    self.resolved[name] = dict(path=str(path), sha256=digest,
                                               bytes=path.stat().st_size, role=spec['role'],
                                               gate='UID_ORDER_AT_LOAD' if spec.get('semantic') else 'PINNED_SHA256')
                    return path
        raise FileNotFoundError(f'PINNED_ASSET_MISSING_OR_SHA_MISMATCH:{name}:{candidates}')

    def verify(self, names=None):
        if names is None:
            names = [name for name, spec in self.specs.items() if spec['role'] in self.roles]
        failures = {}
        for i, name in enumerate(names):
            if self.progress:
                self.progress('VERIFY_INPUTS', i, len(names), asset=name)
            try:
                self.get(name)
            except (OSError, ValueError) as exc:
                failures[name] = str(exc)
        return dict(status='PASS' if not failures else 'FAIL', site='local' if self.local else 'HPC',
                    checked=self.resolved, failures=failures)


def config_at(package=HERE):
    config = load(package / 'CONFIG.json')
    method = config['method']
    require(method['p'] == 4 and method['lambda_value'] == .25 and
            method['kernel'] == 'g(s)=1-(1-s)^4' and tuple(method['heads']) == HEADS and
            method['guard'] == 'SYN_AND_NOT_ACK_ALL_DEVICES' and len(method['cuts']) == 4 and
            len(method['scales']) == 3, 'FROZEN_P4_CONFIGURATION')
    return config


class Progress:
    def __init__(self, directory, phase, rss_limit_mib=None):
        self.directory = directory
        self.phase = phase
        self.started = time.monotonic()
        self.last = 0
        self.peak = 0
        self.rss_limit_mib = rss_limit_mib
        self.stages = []

    def sample(self):
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        self.peak = max(self.peak, peak, children)
        if self.rss_limit_mib:
            require(self.peak <= self.rss_limit_mib * 1024, 'RSS_HEADROOM_EXCEEDED')
        return self.peak

    def __call__(self, stage, done=0, total=1, *, force=False, **extra):
        if not force and stage == getattr(self, 'current', None) and time.monotonic() - self.last < 2:
            return
        self.current = stage
        self.last = time.monotonic()
        dump(self.directory / ('PROGRESS_' + self.phase + '.json'),
             dict(phase=self.phase, stage=stage, done=int(done), total=int(total),
                  updated_unix=time.time(), elapsed_seconds=self.last - self.started,
                  peak_rss_kib=self.sample(), **extra))

    def stage(self, name, fn):
        self(name, force=True)
        start = time.monotonic()
        row = {'stage': name}
        try:
            value = fn()
            row['status'] = 'PASS'
            return value
        except Exception:
            row['status'] = 'FAIL'
            raise
        finally:
            row['seconds'] = time.monotonic() - start
            row['peak_rss_kib'] = self.sample()
            self.stages.append(row)
            self.finish()

    def finish(self):
        import resource
        own = resource.getrusage(resource.RUSAGE_SELF)
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        dump(self.directory / ('RESOURCES_' + self.phase + '.json'),
             dict(phase=self.phase, stages=self.stages, peak_rss_kib=self.sample(),
                  elapsed_seconds=time.monotonic() - self.started,
                  user_cpu_seconds=own.ru_utime + children.ru_utime,
                  system_cpu_seconds=own.ru_stime + children.ru_stime))


def job_id(text):
    value = text.strip().split(';', 1)[0]
    require(re.fullmatch('[0-9]+', value) is not None, 'INVALID_SBATCH_RECEIPT')
    return value
