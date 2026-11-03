"""Bounded, append-only stage observations; never treats RSS as cgroup usage."""
import json
import os
from pathlib import Path
import threading
import time
import continuous_common_v3 as c

RSS_SCOPE = ('Windows current-process RSS; child processes not included' if os.name == 'nt' else
             'sampled process-tree RSS sum; shared mappings may be counted repeatedly')


def cgroup_observation(proc_root=Path('/proc'), fs_root=Path('/')):
    """Read the process's cgroup-v2 memory counters, if discoverable.

    Other processes and child cgroups in this scope may be included. Record the
    scope explicitly; do not sum this value across workers or use it as RSS.
    """
    proc_root, fs_root = Path(proc_root), Path(fs_root)
    try:
        entries = (proc_root/'self/cgroup').read_text().splitlines()
        relative = next(line.split(':', 2)[2] for line in entries if line.startswith('0::'))
        mounts = (proc_root/'self/mountinfo').read_text().splitlines()
        for line in mounts:
            before, after = line.split(' - ', 1)
            if after.split()[0] != 'cgroup2': continue
            columns = before.split(); mount_root, mount_point = columns[3], columns[4]
            cg = Path(relative); mr = Path(mount_root)
            if not cg.is_relative_to(mr): continue
            folder = fs_root / mount_point.lstrip('/') / cg.relative_to(mr)
            values = {}
            for name in ('memory.current', 'memory.peak', 'memory.max'):
                path = folder/name
                if path.exists():
                    value = path.read_text().strip()
                    values[name] = None if value == 'max' else int(value)
            if values:
                return dict(status='AVAILABLE', hierarchy='v2', path=str(folder), counters=values,
                            scope='process cgroup including child cgroups; may include other processes; not necessarily whole job; not additive across workers')
    except (OSError, ValueError, IndexError, StopIteration):
        pass
    return dict(status='UNAVAILABLE', scope='No usable cgroup-v2 memory counters; no replacement peak invented')


class StageRecorder:
    def __init__(self, output, *, interval=5., clock=time.monotonic, sample=cgroup_observation):
        self.output = Path(output); self.interval = interval; self.clock = clock; self.sample = sample
        self.started = clock(); self.last = None; self.stages = {}; self.lock = threading.RLock()

    def observe(self, stage, rss_bytes, *, force=False):
        with self.lock:
            now = self.clock()
            if not force and self.last is not None and now-self.last < self.interval: return
            self.last = now; group = self.sample()
            item = dict(stage=stage, elapsed_seconds=now-self.started, process_tree_rss_bytes=int(rss_bytes),
                        rss_scope=RSS_SCOPE, cgroup=group)
            with (self.output/'resource_samples.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(item, ensure_ascii=True, allow_nan=False, separators=(',', ':'))+'\n')
            stat = self.stages.setdefault(stage, dict(samples=0, first_seconds=item['elapsed_seconds'],
                                                      sampled_tree_rss_peak_bytes=0))
            stat['samples'] += 1; stat['last_seconds'] = item['elapsed_seconds']
            stat['sampled_tree_rss_peak_bytes'] = max(stat['sampled_tree_rss_peak_bytes'], int(rss_bytes))
            stat['last_cgroup_observation'] = group
            c.write(self.output/'resource_summary.json', dict(stages=self.stages,
                    sampling_interval_seconds=self.interval, cpu_count=os.cpu_count(),
                    cgroup_peak_is_not_stage_local=True, sampled_peak_is_not_hard_bound=True), replace=True)
