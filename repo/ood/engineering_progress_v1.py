"""Existing guards with explicit ephemeral-file handling and stage observations."""
from pathlib import Path
import shutil
import stat
import time
import continuous_common_v3 as c
from legacy_unsw_archival_runtime_v1 import tree_rss
from resource_observation_v1 import RSS_SCOPE,StageRecorder
from scratch_registry_v1 import may_disappear


def disk_bytes(folder):
    """Count regular files; tolerate only known concurrent scratch cleanup."""
    total = 0
    for path in Path(folder).rglob('*'):
        try:
            info = path.stat()
        except FileNotFoundError:
            if path.name.endswith('.json.next') or may_disappear(path):
                continue
            raise
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total


class Progress(c.Progress):
    def __init__(self,out,limits,*,storage_scope=None):
        self.recorder=StageRecorder(out);self.storage_scope=Path(storage_scope) if storage_scope else None
        if self.storage_scope is not None:
            c.require(Path(out).resolve().is_relative_to(self.storage_scope.resolve()), 'STORAGE_SCOPE_EXCLUDES_MONITOR')
        super().__init__(out,limits)

    def guard(self):
        # Do not call the inherited guard: it scans self.out with the legacy
        # disk_bytes first, before our scope scan can handle SQLite cleanup.
        c.require(self.error is None,self.error or 'PRIOR_FAILURE')
        with self.guard_lock:
            now=time.monotonic()
            if now-getattr(self,'_last_guard',0)>=1:
                self._last_guard=now
                c.require(not (self.out/'STOP_REQUESTED').exists(),'USER_STOP_REQUESTED')
                c.require(now-self.started<self.limits['wall_seconds'],'WALL_TIME_LIMIT')
                self.rss=tree_rss()
                c.require(self.rss<self.limits['memory_gib']*1024**3,'COMBINED_MEMORY_LIMIT')
                if now-self.disk_at>30:
                    scope=self.out if self.storage_scope is None else self.storage_scope
                    label='OUTPUT_DISK_LIMIT' if self.storage_scope is None else 'WORKING_DISK_LIMIT'
                    c.require(disk_bytes(scope)<self.limits['disk_gib']*1024**3,label)
                    c.require(shutil.disk_usage(self.out).free>1024**3,'OUTPUT_DISK_FREE_LIMIT')
                    self.disk_at=now
        self.peak_rss=max(getattr(self,'peak_rss',0),self.rss)
        self.recorder.observe(self.stage,self.rss)

    def emit(self,status='RUNNING',**extra):
        self.recorder.observe(self.stage,self.rss,force=status!='RUNNING')
        super().emit(status,sampled_peak_tree_rss_gib=getattr(self,'peak_rss',0)/1024**3,
                     resource_measure=RSS_SCOPE,**extra)
