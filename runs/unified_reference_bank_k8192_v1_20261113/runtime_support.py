"""Pinned asset access and progress for the independent frozen run."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time

from frozen_selector import need
from motion_ingress import digest

HERE = Path(__file__).resolve().parent
POOLS = ('CIC_DEV', 'UNSW_DEV', 'EDGE')
TSHARK_SHA = '08573896ff5af2028972278388d7bd3b5cb3fb635a1e105bf45284adef93c301'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def asset(path, **fields):
    return dict(bytes=path.stat().st_size, sha256=digest(path), **fields)


class Store:
    def __init__(self, project, roles):
        self.project = Path(project).resolve()
        self.roles = set(roles)
        self.specs = read(HERE / 'REMOTE_ASSET_PINS.json')['files']
        self.checked = {}

    def get(self, key):
        if key in self.checked:
            return Path(self.checked[key]['path'])
        spec = self.specs[key]
        need(spec['group'] in self.roles, 'ASSET_ROLE_DENIED:' + key)
        for relative in spec['paths']:
            path = (self.project / relative).resolve()
            need(path.is_relative_to(self.project), 'ASSET_PATH_SCOPE')
            if not path.is_file():
                continue
            before = path.stat()
            if spec['bytes'] is not None and before.st_size != spec['bytes']:
                continue
            sha = digest(path)
            after = path.stat()
            need((before.st_ino, before.st_size, before.st_mtime_ns) ==
                 (after.st_ino, after.st_size, after.st_mtime_ns), 'MUTATING_INPUT:' + key)
            if spec['sha256'] is None or sha == spec['sha256']:
                self.checked[key] = dict(path=str(path), bytes=after.st_size, sha256=sha)
                return path
        raise FileNotFoundError('PINNED_ASSET_MISSING_OR_DIFFERENT:' + key)


class Progress:
    def __init__(self, target, phase):
        self.target = target
        self.phase = phase
        self.start = time.monotonic()
        self.last = 0
        self.current = None
        self.children = []
        self.stages = []
        self.encoded_rows = 0
        self.rss_limit = int(os.environ['K8192_RSS_MIB'])
        self.time_limit = int(os.environ['K8192_WALL_SECONDS'])

    def rss(self):
        import resource
        return max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)

    def guard(self):
        need(self.rss() <= self.rss_limit * 1024, 'COMPUTE_RSS_HEADROOM')
        need(time.monotonic()-self.start < self.time_limit-180, 'COMPUTE_WALL_HEADROOM')

    def __call__(self, stage, done=0, total=1, *, force=False, **extra):
        now = time.monotonic()
        if stage == self.current and not force and now-self.last < 2:
            return
        self.guard()
        self.current, self.last = stage, now
        write(self.target / 'PROGRESS.json', dict(phase=self.phase, stage=stage, done=int(done),
              total=int(total), elapsed_seconds=now-self.start, peak_rss_kib=self.rss(),
              updated_unix=time.time(), job=os.environ['SLURM_JOB_ID'], **extra))

    def update(self, stage, **extra):
        done = extra.pop('completed', extra.pop('raw_packets', extra.pop('encoded_rows', 0)))
        total = extra.pop('total', extra.pop('total_rows', max(1, done)))
        self(stage, done, total, **extra)

    def encoded(self, count):
        self.encoded_rows += count
        self.guard()

    @contextmanager
    def measure(self, stage):
        start = time.monotonic()
        self(stage, force=True)
        try:
            yield
        finally:
            self.stages.append(dict(stage=stage, seconds=time.monotonic()-start,
                                    peak_rss_kib=self.rss()))
            write(self.target / f'RESOURCES_{self.phase}.json',
                  dict(stages=self.stages, peak_rss_kib=self.rss()))
