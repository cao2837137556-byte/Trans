"""Q reference correction contracts and durable status; no asset reads on import."""
from pathlib import Path
import gzip
import hashlib
import json
import os
import time

RECIPE_SHA = 'bf00e65895baf99b3bd48be5933cf3a6afa0e8b84ee567f60777333bf2d04a1b'
RECIPE_REL = 'runs/mainline_docs/legacy_q_reference_correction_recipe_v1_20260922.json'
IMPLEMENTATION_REL = 'runs/legacy_q_reference_implementation_v1_20260922'
SEEDS = (27, 127, 227)


class Stop(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise Stop(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def uid_sha(uids):
    return hashlib.sha256(''.join(u + '\n' for u in sorted(uids)).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def confined(root, relative):
    root = Path(root).resolve()
    rel = str(relative).replace('\\', '/')
    p = (root / rel).resolve()
    require(p.is_relative_to(root), 'PATH_ESCAPE')
    return p


def pin(path, expected):
    require(sha(path) == expected, 'IDENTITY_MISMATCH:' + str(path))
    return Path(path)


def load_recipe(root):
    return read(pin(confined(root, RECIPE_REL), RECIPE_SHA))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def seal(folder):
    folder = Path(folder)
    files = sorted(p for p in folder.rglob('*') if p.is_file())
    with (folder / 'SHA256SUMS').open('x', encoding='utf-8', newline='\n') as f:
        for p in files:
            f.write(sha(p) + '  ' + p.relative_to(folder).as_posix() + '\n')


def verify(folder):
    folder = Path(folder)
    listed = set()
    for line in (folder / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h, name = line.split('  ', 1)
        require(name not in listed, 'DUPLICATE_SEAL_PATH')
        listed.add(name)
        pin(confined(folder, name), h)
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p != folder/'SHA256SUMS'}
    require(actual == listed, 'SEAL_FILE_SET')


def rss_bytes():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in
                ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
                 'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        x = Counters(); x.cb = ctypes.sizeof(x)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        fn = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
        fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        require(fn(kernel.GetCurrentProcess(), ctypes.byref(x), x.cb), 'MEMORY_ACCOUNTING_FAILED')
        return int(x.WorkingSetSize)
    with open('/proc/self/statm') as f:
        return int(f.read().split()[1]) * os.sysconf('SC_PAGE_SIZE')


class Progress:
    """Immutable numbered receipts avoid replacing a JSON file held open by a reader."""
    def __init__(self, out, total, hours=24, ram_gib=64, disk_gib=16):
        self.out = Path(out); self.out.mkdir(exist_ok=False, parents=True)
        (self.out/'progress').mkdir()
        self.start = time.monotonic(); self.deadline = self.start + hours*3600
        self.ram = ram_gib*1024**3; self.disk = disk_gib*1024**3
        self.total = total; self.done = 0; self.sequence = 0; self.last_disk = -1e9
        self.completed = []; self.stage = 'PREFLIGHT'
        self.emit()

    def guard(self):
        require(not (self.out/'STOP_REQUESTED').exists(), 'USER_STOP_REQUESTED')
        require(time.monotonic() < self.deadline, 'WALL_TIME_LIMIT')
        require(rss_bytes() <= self.ram, 'MEMORY_LIMIT')
        now = time.monotonic()
        if now - self.last_disk >= 30:
            used = sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())
            require(used <= self.disk, 'OUTPUT_DISK_LIMIT')
            self.last_disk = now

    def emit(self, status='RUNNING', **extra):
        self.sequence += 1
        value = dict(status=status, stage=self.stage, completed_updates=self.done, total_updates=self.total,
                     elapsed_seconds=time.monotonic()-self.start, completed_stages=self.completed[:],
                     retries=0, heldout_opened=False, **extra)
        # Readers only observe renamed complete files. Destination is new, never overwritten.
        target = self.out/'progress'/('%08d.json' % self.sequence)
        temporary = target.with_suffix('.pending')
        write(temporary, value); os.rename(str(temporary), str(target))
        return value

    def tick(self, updates=0, **extra):
        self.done += updates; self.guard()
        if self.done % 100 == 0 or updates == 0:
            self.emit(**extra)

    def finish_stage(self, name):
        self.completed.append(name); self.emit()

    def finish(self, status, **extra):
        value = self.emit(status, **extra)
        target=self.out/'status.json'
        if target.exists():
            target=self.out/('terminal_%08d.json'%self.sequence)
        write(target, value)


def status(out):
    out = Path(out)
    entries = sorted((out/'progress').glob('*.json'))
    if entries:
        return read(entries[-1])
    return read(out/'status.json') if (out/'status.json').exists() else {'status':'NOT_STARTED'}
