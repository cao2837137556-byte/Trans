"""Versioned IO and fail-closed identities for learned onboarding V1."""
import hashlib
import contextlib
import io
import json
import math
import os
from pathlib import Path
import platform
import tempfile
import time

import numpy as np

LINEAGE = 'NEW_RECONSTRUCTION_LINEAGE'
PARENT_PARITY = 'PARENT_PARITY_UNAVAILABLE'
SEED = 27
GROUPS = (('Amcrest Camera', 'ArloQ Camera', 'Atomi Coffee Maker'),
          ('Philips Hue Bridge', 'SimCam', 'Globe Lamp'))
ARMS = ('L_STANDARD', 'L_HARD', 'L_QUERY_ONLY')
LAMBDAS = (0.0, 0.05, 0.1, 0.25)
ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT/'runs/learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md'
SPEC_SHA256 = 'a07d736c7c9c756478a7d163873611132ff0b14abc855ab3a3709257433674b8'


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def uid_hash(uids, ordered=False):
    values = list(uids)
    require(all(isinstance(u, str) and u and '\n' not in u for u in values), 'UID_SCHEMA')
    if not ordered:
        values.sort()
    return hashlib.sha256(('\n'.join(values)+'\n').encode()).hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        return json.load(f)


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False,
                      default=_json_default)+'\n'
    fd, tmp = tempfile.mkstemp(prefix='.'+path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def record(schema, **fields):
    return dict(schema=schema, version=1, spec_sha256=SPEC_SHA256,
                lineage=LINEAGE, parent_parity=PARENT_PARITY, **fields)


def check_spec():
    require(sha(SPEC) == SPEC_SHA256, 'SPEC_IDENTITY_CHANGED')


def pin(path, expected):
    path = Path(path).resolve()
    require(path.is_file(), 'MISSING_INPUT:'+str(path))
    require(isinstance(expected, str) and len(expected) == 64 and sha(path) == expected.lower(),
            'INPUT_SHA256:'+str(path))
    return path


def fresh(path):
    path = Path(path)
    require(not path.exists(), 'OUTPUT_ALREADY_EXISTS:'+str(path))
    path.mkdir(parents=True)
    return path


def seal(folder):
    folder = Path(folder)
    entries = {str(p.relative_to(folder)).replace('\\', '/'): sha(p)
               for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'SEAL.json'}
    write(folder/'SEAL.json', record('learned-onboarding-seal-v1', status='SEALED', files=entries))
    return sha(folder/'SEAL.json')


def verify_seal(folder, expected=None):
    folder = Path(folder)
    if expected is not None:
        pin(folder/'SEAL.json', expected)
    value = read(folder/'SEAL.json')
    require(value['spec_sha256'] == SPEC_SHA256 and value['status'] == 'SEALED', 'SEAL_SPEC')
    for name, expected_sha in value['files'].items():
        target = (folder/name).resolve()
        require(folder.resolve() in target.parents, 'SEAL_PATH_ESCAPE')
        pin(target, expected_sha)
    actual = {str(p.relative_to(folder)).replace('\\', '/') for p in folder.rglob('*')
              if p.is_file() and p.name != 'SEAL.json'}
    require(actual == set(value['files']), 'SEAL_EXTRA_OR_MISSING_FILES')
    return value


def environment():
    import torch
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        np.show_config()
    return dict(python=platform.python_version(), platform=platform.platform(),
                numpy=np.__version__, torch=torch.__version__,
                torch_threads=torch.get_num_threads(),
                deterministic=torch.are_deterministic_algorithms_enabled(),
                device='cpu', numpy_blas_config=output.getvalue(),
                thread_environment={k: os.environ.get(k) for k in
                    ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})


class Guard:
    """Process-tree RSS, elapsed time and output ceiling; never retries."""
    def __init__(self, folder, hours=10, rss_gib=8, output_gib=2, budget_folder=None):
        self.folder = Path(folder)
        self.budget_folder = Path(budget_folder) if budget_folder is not None else self.folder
        self.started = time.monotonic()
        self.seconds = hours*3600
        self.rss_limit = rss_gib*1024**3
        self.output_limit = output_gib*1024**3
        self.peak_rss = 0
        self.last_resource_check = -float('inf')
        self.last_status_write = -float('inf')

    def check(self, force=False, **progress):
        now = time.monotonic()
        require(now-self.started <= self.seconds, 'RESOURCE_TIME_LIMIT')
        # Optimizer updates may take milliseconds; avoid fsync/tree walks per update.
        if not force and now-self.last_resource_check < 1.0:
            return
        self.last_resource_check = now
        try:
            import psutil
        except ImportError as exc:
            raise ContractError('PROCESS_TREE_MONITOR_UNAVAILABLE') from exc
        parent = psutil.Process()
        processes = [parent]+parent.children(recursive=True)
        rss = 0
        for process in processes:
            try:
                rss += process.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        self.peak_rss = max(self.peak_rss, rss)
        require(rss <= self.rss_limit, 'RESOURCE_RSS_LIMIT')
        elapsed = time.monotonic()-self.started
        require(elapsed <= self.seconds, 'RESOURCE_TIME_LIMIT')
        size = sum(p.stat().st_size for p in self.budget_folder.rglob('*') if p.is_file())
        require(size <= self.output_limit, 'RESOURCE_OUTPUT_LIMIT')
        if now-self.last_status_write >= 5.0:
            self.last_status_write = now
            write(self.folder/'status.json', record('learned-onboarding-progress-v1',
                  status='RUNNING', elapsed_seconds=elapsed, peak_process_tree_rss=self.peak_rss,
                  output_bytes=size, **progress))
