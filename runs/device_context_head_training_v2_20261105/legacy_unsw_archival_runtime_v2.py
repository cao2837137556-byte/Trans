"""Versioned monitor and durable feature blocks. Frozen E3 arithmetic stays in v1."""
import gzip
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import threading
import time
import traceback

import legacy_unsw_archival_common_v1 as c
import legacy_unsw_archival_runtime_v1 as old

e3_runtime = old.e3_runtime
fields = old.fields
BLOCK_ROWS = 1024  # Storage boundary only; model batch size remains 16.


def disk_bytes(folder):
    total = 0
    for path in Path(folder).rglob('*'):
        try:
            info = path.stat()  # One stat, not is_file followed by a second stat.
        except FileNotFoundError:
            # Only common.write's atomic JSON temporary is allowed to vanish.
            if path.name.endswith('.json.next'):
                continue
            raise
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total


class Progress(old.Progress):
    def __init__(self, out, limits):
        self.guard_lock = threading.RLock()
        self.write_lock = threading.RLock()
        self.first_failure = None
        super().__init__(out, limits)

    def record_failure(self, exc, origin):
        with self.write_lock:
            if self.first_failure is None:
                self.first_failure = dict(origin=origin, exception=repr(exc),
                    traceback=''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    stage=self.stage, elapsed_seconds=time.monotonic()-self.started)
                self.error = repr(exc)
                # stderr survives even if the output filesystem cannot write.
                print('FIRST_FAILURE ' + json.dumps(self.first_failure), file=sys.stderr, flush=True)
                try:
                    c.write(self.out/'first_failure.json', self.first_failure)
                except BaseException as write_exc:
                    print('FAILURE_RECORD_WRITE_ERROR ' + repr(write_exc), file=sys.stderr, flush=True)
            return self.first_failure

    def guard(self):
        with self.guard_lock:
            c.require(self.error is None, self.error or 'WATCHDOG_FAILURE')
            c.require(not (self.out/'STOP_REQUESTED').exists(), 'USER_STOP_REQUESTED')
            c.require(time.monotonic()-self.started < self.limits['wall_seconds'], 'WALL_TIME_LIMIT')
            self.rss = old.tree_rss()
            c.require(self.rss < self.limits['memory_gib']*1024**3, 'COMBINED_MEMORY_LIMIT')
            if time.monotonic()-self.disk_at > 30:
                used = disk_bytes(self.out)
                c.require(used < self.limits['disk_gib']*1024**3, 'OUTPUT_DISK_LIMIT')
                c.require(shutil.disk_usage(self.out).free > 1024**3, 'OUTPUT_DISK_FREE_LIMIT')
                self.disk_at = time.monotonic()

    def watch(self):
        while not self.closed.wait(2):
            try:
                self.guard()
            except Exception as exc:
                self.record_failure(exc, 'watchdog')
                for process in list(self.children):
                    if process.poll() is None:
                        process.kill()
                return

    def emit(self, status='RUNNING', **extra):
        with self.write_lock:
            if self.first_failure is not None:
                extra['first_failure'] = self.first_failure
            extra['computed_rows'] = getattr(self, 'computed_rows', 0)
            extra['completed_means'] = 'verified durable block rows during E3_FEATURES'
            super().emit(status, **extra)

    def stop(self, status, error=None, **extra):
        if status == 'COMPLETE':
            try:
                self.guard()
            except BaseException as exc:
                self.record_failure(exc, 'completion_guard')
                raise
        self.closed.set()
        self.thread.join(timeout=5)
        for process in self.children:
            if process.poll() is None:
                process.kill()
        for process in self.children:
            process.wait(timeout=30)
        # Retain the last durable count when stopping. It is still not a commit.
        values = dict(self.latest)
        values.update(extra)
        self.emit(status, error=error, **values)


def fsync_file(path):
    # Windows FlushFileBuffers needs a writable handle; r+b preserves bytes.
    with Path(path).open('r+b') as stream:
        os.fsync(stream.fileno())


def fsync_directory(path):
    if os.name != 'nt':
        fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def commit_block(folder, index, start, uids, values, identity):
    import numpy as np
    target = Path(folder)/('block_%06d' % index)
    target.mkdir(parents=True, exist_ok=False)
    c.require(len(set(uids)) == len(uids) and 0 < len(uids) <= BLOCK_ROWS, 'BLOCK_UIDS')
    c.require(values.shape == (len(uids),768) and values.dtype == np.float32 and
              np.isfinite(values).all(), 'BLOCK_VALUES')
    with (target/'features.npy').open('xb') as stream:
        np.save(stream, values, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    c.write(target/'uids.json', uids)
    c.write(target/'receipt.json', dict(identity=identity, start=start, rows=len(uids)))
    c.seal(target)
    fsync_file(target/'SHA256SUMS')
    fsync_directory(target)
    # A block without this durable marker is never reusable.
    c.write(target/'COMMITTED.json', dict(seal_sha256=c.sha(target/'SHA256SUMS')))
    fsync_directory(target)
    fsync_directory(target.parent)
    return target


def read_block(target, expected_uids, start, identity):
    import numpy as np
    target = Path(target)
    c.require((target/'COMMITTED.json').is_file(), 'BLOCK_NOT_COMMITTED')
    c.pin(target/'SHA256SUMS', c.read(target/'COMMITTED.json')['seal_sha256'])
    c.verify(target, exact=False)
    c.require({p.name for p in target.iterdir()} ==
              {'features.npy','uids.json','receipt.json','SHA256SUMS','COMMITTED.json'}, 'BLOCK_FILE_SET')
    receipt = c.read(target/'receipt.json')
    c.require(receipt == dict(identity=identity, start=start, rows=len(expected_uids)), 'BLOCK_IDENTITY')
    c.require(c.read(target/'uids.json') == expected_uids, 'BLOCK_UID_ORDER')
    values = np.load(target/'features.npy', allow_pickle=False)
    c.require(values.shape == (len(expected_uids),768) and values.dtype == np.float32 and
              np.isfinite(values).all(), 'BLOCK_VALUES')
    return values


def feature_worker(root, out, shard, explicit):
    c.require(explicit is True, 'REAL_EXECUTION_NOT_AUTHORIZED')
    root, out = Path(root), Path(out)
    c.verify(root, exact=False)
    c.verify(out/'manifests'); c.verify(out/'flows')
    launch = c.read(out/'launch.json')
    c.require(launch['recipe_sha256'] == c.RECIPE_SHA and
              launch['scope'] == 'SEALED_INPUTS_FROZEN_RECOVERY_V2', 'WORKER_AUTHORITY')
    contract = c.read(root/'runtime_contract.json')
    progress = Progress(out/('worker_%02d'%shard), contract['limits'])
    try:
        import numpy as np
        spec = c.read(out/'flows/index.json')['shards'][shard]
        identity = dict(recipe_sha256=c.RECIPE_SHA, shard=shard,
            flow_sha256=c.sha(out/'flows'/spec['file']),
            manifest_sha256=c.sha(out/'manifests/SHA256SUMS'),
            package_sha256=c.sha(root/'SHA256SUMS'),
            checkpoint_sha256=contract['checkpoint_sha256'], batch_size=16)
        c.pin(root/'vendor/netFound-base/model.safetensors', contract['checkpoint_sha256'])
        embed, translator, model, tokenizer, collator = e3_runtime(root)
        progress.stage = 'E3_FEATURES'
        uids, chunk_uids, chunks, flows = [], [], [], []
        done, committed, block_index = 0, 0, 0
        def commit():
            nonlocal chunk_uids, chunks, committed, block_index
            if not chunk_uids: return
            values = np.concatenate(chunks, axis=0)
            block = commit_block(progress.out/'blocks', block_index, committed, chunk_uids, values, identity)
            read_block(block, chunk_uids, committed, identity)
            committed += len(chunk_uids); block_index += 1
            chunk_uids, chunks = [], []
            progress.tick(committed, spec['count'], force=True)
        def flush():
            nonlocal done, flows
            if not flows: return
            progress.guard()
            values = embed.embed_flows(translator, model, tokenizer, collator, flows, 'cpu', 16)
            c.require(values.shape == (len(flows),768) and values.dtype == np.float32 and
                      np.isfinite(values).all(), 'E3_OUTPUT')
            chunks.append(values); done += len(flows); flows = []
            progress.computed_rows = done
            if done-committed == BLOCK_ROWS: commit()
            else: progress.tick(committed, spec['count'])
        with gzip.open(out/'flows'/spec['file'], 'rt', encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                uids.append(row['uid']); chunk_uids.append(row['uid']); flows.append(row['flow'])
                if len(flows) == 16: flush()
        flush(); commit()
        c.require(done == committed == spec['count'] and len(set(uids)) == len(uids), 'WORKER_COVERAGE')
        target = progress.out/'features.npy'
        features = np.lib.format.open_memmap(target, mode='w+', dtype=np.float32, shape=(done,768))
        for index, start in enumerate(range(0, done, BLOCK_ROWS)):
            progress.guard()
            part = uids[start:start+BLOCK_ROWS]
            features[start:start+len(part)] = read_block(progress.out/'blocks'/('block_%06d'%index), part, start, identity)
        features.flush(); del features; fsync_file(target)
        c.write(progress.out/'uids.json', uids)
        progress.stop('COMPLETE', completed=done, total=done, committed_rows=committed)
        c.seal(progress.out)
    except BaseException as exc:
        progress.record_failure(exc, 'feature_worker')
        progress.stop('STOPPED_NO_RETRY', repr(exc))
        raise


def launch_features(root, out, progress):
    root, out = Path(root), Path(out)
    workers = c.read(root/'runtime_contract.json')['workers']
    processes, logs = [], []
    before_cleanup = []
    try:
        for shard in range(workers):
            stream = (out/('worker_%02d.log'%shard)).open('x', encoding='utf-8')
            logs.append(stream)
            process = subprocess.Popen([sys.executable, str(root/'repo/ood/legacy_unsw_archival_runner_v2.py'),
                'worker','--root',str(root),'--output',str(out),'--shard',str(shard),'--authorize-recovery'],
                stdout=stream, stderr=subprocess.STDOUT)
            processes.append(process); progress.children.append(process)
        while True:
            # Check persistent watchdog cause even when every child has exited.
            progress.guard()
            codes = [p.poll() for p in processes]
            if any(code not in (None,0) for code in codes):
                raise RuntimeError('FEATURE_WORKER_FAILED:'+json.dumps(codes))
            if all(code == 0 for code in codes): break
            done = 0
            for shard in range(workers):
                path = out/('worker_%02d'%shard)/'status.json'
                if path.exists(): done += c.read(path).get('completed',0)
            progress.tick(done, c.read(out/'flows/index.json')['total'])
            time.sleep(2)
    except BaseException as exc:
        progress.record_failure(exc, 'feature_supervisor')
        raise
    finally:
        before_cleanup = [p.poll() for p in processes]
        for p in processes:
            if p.poll() is None: p.kill()
        for p in processes: p.wait(timeout=30)
        for stream in logs: stream.close()
        c.write(out/'worker_exits.json', dict(before_cleanup=before_cleanup,
            final=[p.returncode for p in processes], first_failure=progress.first_failure))
        # Do not overwrite a worker's original status/seal; record supervisor interpretation separately.
        terminal = []
        for shard, p in enumerate(processes):
            path = out/('worker_%02d'%shard)/'status.json'
            state = c.read(path) if path.exists() else {}
            terminal.append(dict(shard=shard, returncode=p.returncode,
                observed_status=state.get('status','NOT_STARTED'),
                effective_status='COMPLETE' if p.returncode == 0 and state.get('status') == 'COMPLETE'
                else 'STOPPED_NO_RETRY', completed=state.get('completed',0)))
        c.write(out/'worker_terminal_states.json', terminal)
