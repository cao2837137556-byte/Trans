"""Sample a changing tree without failing on an atomic commit rename.

Only vanished descendants are skipped. Missing roots and permission/I/O errors
remain fatal. Inode deduplication avoids double-counting a moved directory;
the existing 60s sampled-disk semantics and free-space reserve remain unchanged.
"""
import os
import stat
from pathlib import Path

def tree_bytes(root, *, scandir=None):
    root=Path(root);scan=scandir or os.scandir
    root.stat()  # A missing monitored root is not an expected descendant race.
    stack=[root];seen=set();total=0
    while stack:
        directory=stack.pop()
        try:
            with scan(directory) as entries:
                for entry in entries:
                    try:info=entry.stat(follow_symlinks=False)
                    except FileNotFoundError:continue
                    if stat.S_ISLNK(info.st_mode):continue
                    if stat.S_ISDIR(info.st_mode):stack.append(Path(entry.path))
                    elif stat.S_ISREG(info.st_mode):
                        key=(info.st_dev,info.st_ino)
                        if key not in seen:seen.add(key);total+=info.st_size
        except FileNotFoundError:
            if directory==root:raise
            # Atomic pending/<id> -> batches/<id> publication can remove an
            # already enumerated path. A later sample sees the stable target.
            continue
    return total

# Keep the worker's wall/RSS/disk guards; change only the directory iterator.
import shutil
import time
from worker import Guard as FrozenGuard
from checkpoint import require

class Guard(FrozenGuard):
    def __call__(self):
        require(time.monotonic()-self.started<self.budget['wall_seconds']-120,'WALL_BUDGET_STOP')
        if time.monotonic()-self.last<2:return
        self.last=time.monotonic();rss=0
        for proc in [self.process]+self.process.children(recursive=True):
            try:rss+=proc.memory_info().rss
            except self.psutil.NoSuchProcess:pass
        self.max_rss=max(self.max_rss,rss)
        require(rss<=self.budget['rss_bytes'],'RSS_BUDGET_STOP')
        require(shutil.disk_usage(self.out).free>=2*1024**3 and shutil.disk_usage(self.scratch).free>=2*1024**3,'DISK_FREE_STOP')
        if time.monotonic()-self.last_disk>=60:
            self.last_disk=time.monotonic()
            for root,limit,field in ((self.out,self.budget['disk_bytes'],'max_output_disk_bytes'),
                                    (self.scratch,self.budget['scratch_bytes'],'max_scratch_disk_bytes')):
                total=tree_bytes(root);setattr(self,field,max(getattr(self,field),total))
                require(total<=limit,'DISK_BUDGET_STOP:'+str(root))
