"""One attempt, one supervisor, owned scratch and sampled whole-job budgets.

CURRENT_ENGINEERING_ATTEMPT.json is the only authoritative status. Child
success is a candidate until the supervisor has checked resources and cleanup.
OS-enforced output locking survives crashes without stale-lock guessing.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid

import psutil

from checkpoint import atomic_json, require, sha

SCOPE = 'EDGE_FORMAL_WORKER_ENGINEERING_GATE'
CURRENT = 'CURRENT_ENGINEERING_ATTEMPT.json'


class ProcessesNotStopped(RuntimeError):
    """Scratch must be preserved when process termination was not confirmed."""


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def attempt_directory(output, attempt_id):
    require(type(attempt_id) is str and len(attempt_id) == 32 and
            all(c in '0123456789abcdef' for c in attempt_id), 'ENGINEERING_ATTEMPT_ID')
    output = Path(output).resolve()
    directory = output/'engineering_attempts'/attempt_id
    require(not directory.parent.is_symlink() and not directory.is_symlink() and
            directory.resolve().is_relative_to(output), 'ATTEMPT_DIRECTORY_SCOPE')
    return directory


def current_status(output, *, attempt_id=None, card_sha256=None):
    output = Path(output).resolve()
    value = read(output/CURRENT)
    if attempt_id is not None:
        require(value['attempt_id'] == attempt_id, 'CURRENT_ATTEMPT_MISMATCH')
    if card_sha256 is not None:
        require(value['card_sha256'] == card_sha256, 'CURRENT_CARD_MISMATCH')
    directory = attempt_directory(output, value['attempt_id'])
    target = directory/(value['status']+'.json')
    require(value.get('receipt') == target.relative_to(output).as_posix() and
            sha(target) == value['receipt_sha256'], 'CURRENT_RECEIPT_IDENTITY')
    receipt = read(target)
    require(all(receipt.get(k) == value[k] for k in ('status', 'attempt_id', 'card_sha256')),
            'CURRENT_RECEIPT_BINDING')
    if value['status'] == 'PASS':
        candidate = directory/'CANDIDATE.json'
        require(receipt.get('candidate') == candidate.name and
                sha(candidate) == receipt.get('candidate_sha256'), 'CURRENT_CANDIDATE_IDENTITY')
    return receipt


class Attempt:
    def __init__(self, output, card_sha256):
        raw = Path(output).absolute()
        require(not raw.is_symlink(), 'OUTPUT_SYMLINK')
        self.output = raw.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        lock = self.output/'ENGINEERING_OUTPUT.lock'
        require(not lock.is_symlink(), 'OUTPUT_LOCK_SYMLINK')
        self.lock = lock.open('a+b')
        self.id, self.card_sha = uuid.uuid4().hex, card_sha256
        self.scratch_plan = None
        try:
            if os.name == 'nt':
                import msvcrt
                if lock.stat().st_size == 0:
                    self.lock.write(b'0'); self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.lock.close()
            raise ValueError('ENGINEERING_OUTPUT_ALREADY_ACTIVE') from exc
        self.directory = attempt_directory(self.output, self.id)
        try:
            self.directory.mkdir(parents=True)
            self.publish('RUNNING', phase='STARTING')
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self.lock.closed:
            if os.name == 'nt':
                import msvcrt
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_UNLCK, 1)
            self.lock.close()

    def publish(self, status, **extra):
        require(status in ('RUNNING', 'PASS', 'STOP'), 'ATTEMPT_STATUS')
        target = self.directory/(status+'.json')
        require(not target.exists(), 'ATTEMPT_RECEIPT_IMMUTABLE')
        value = dict(extra, schema='EDGE_ENGINEERING_ATTEMPT_V2', status=status,
                     scope=SCOPE, attempt_id=self.id, card_sha256=self.card_sha,
                     external_quality_computed=False, automatic_resubmit=False)
        atomic_json(target, value)
        # Fallible progress/mirror writes precede the authoritative commit.
        atomic_json(self.output/'ENGINEERING_GATE_RECEIPT.json', value)
        atomic_json(self.output/'PROGRESS.json', dict(value, stage='ENGINEERING_GATE_'+status))
        pointer = {k: value[k] for k in ('status', 'scope', 'attempt_id', 'card_sha256')}
        pointer.update(receipt=target.relative_to(self.output).as_posix(), receipt_sha256=sha(target))
        atomic_json(self.output/CURRENT, pointer)
        return value

    def allocate_scratch(self, scratch_root):
        raw = Path(scratch_root).absolute()
        require(raw.is_dir() and not raw.is_symlink(), 'SCRATCH_ROOT_REQUIRED')
        root = raw.resolve()
        require(not root.is_relative_to(self.output) and not self.output.is_relative_to(root),
                'SCRATCH_OUTPUT_DISJOINT')
        self.scratch_plan = dict(scope=SCOPE, attempt_id=self.id, card_sha256=self.card_sha,
            output=str(self.output), scratch_root=str(root), supervisor_pid=os.getpid(), phases={})
        # Record each exact name before creation; even an early child crash cannot
        # make an untracked directory. The supervisor owns all three phases.
        for phase in ('main', 'crash', 'resume'):
            path = root/('edge-gate-owned-'+self.id+'-'+phase)
            owner = {k: v for k, v in self.scratch_plan.items() if k != 'phases'}
            owner.update(phase=phase, scratch=str(path))
            self.scratch_plan['phases'][phase] = owner
            atomic_json(self.directory/'SCRATCH_PLAN.json', self.scratch_plan)
            require(not path.exists() and not path.is_symlink(), 'OWNED_SCRATCH_ALREADY_EXISTS')
            path.mkdir()
            atomic_json(path/'OWNERSHIP.json', owner)
        return self.scratch_plan

    def cleanup(self):
        if self.scratch_plan is None:
            return []
        return cleanup_plan(self.scratch_plan)


def owned_path(plan, phase):
    owner = plan['phases'][phase]
    root = Path(plan['scratch_root'])
    candidate = Path(owner['scratch'])
    expected = root/('edge-gate-owned-'+plan['attempt_id']+'-'+phase)
    require(root.is_absolute() and not root.is_symlink() and root.resolve() == root and
            candidate == expected and not candidate.is_symlink() and candidate.resolve().parent == root,
            'OWNED_SCRATCH_SCOPE')
    for key in ('scope', 'attempt_id', 'card_sha256', 'output', 'scratch_root', 'supervisor_pid'):
        require(owner[key] == plan[key], 'OWNED_SCRATCH_PLAN_BINDING')
    require(owner['scope'] == SCOPE and owner['phase'] == phase, 'OWNED_SCRATCH_PHASE')
    require(read(candidate/'OWNERSHIP.json') == owner, 'OWNED_SCRATCH_DIRECTORY_OWNER')
    return candidate


def cleanup_plan(plan):
    removed = []
    for phase, owner in plan['phases'].items():
        path = Path(owner['scratch'])
        if not path.exists() and not path.is_symlink():
            continue
        path = owned_path(plan, phase)
        # Windows and Linux both delete through the validated concrete path.
        shutil.rmtree(path)
        removed.append(str(path))
    return removed


def child_scratch(output, attempt_id, phase, card_sha256):
    current = current_status(output, attempt_id=attempt_id, card_sha256=card_sha256)
    require(current['status'] == 'RUNNING', 'CHILD_ATTEMPT_NOT_RUNNING')
    plan = read(attempt_directory(output, attempt_id)/'SCRATCH_PLAN.json')
    require(plan['attempt_id'] == attempt_id and plan['card_sha256'] == card_sha256 and
            plan['output'] == str(Path(output).resolve()), 'CHILD_SCRATCH_PLAN_BINDING')
    return owned_path(plan, phase)


def tree_rss_snapshot(process):
    records = []
    try:
        processes = [process] + process.children(recursive=True)
    except psutil.NoSuchProcess:
        processes = []
    for child in processes:
        try:
            records.append(dict(pid=child.pid, rss_bytes=child.memory_info().rss))
        except psutil.NoSuchProcess:
            pass
    return records


class JobMonitor:
    def __init__(self, output, scratch_paths, budget):
        self.process = psutil.Process()
        self.output, self.scratch_paths = Path(output), list(scratch_paths)
        self.budget, self.last_disk = budget, -float('inf')
        self.samples = 0
        self.max_rss = self.max_output = self.max_scratch = 0
        self.peak_rss_processes = []
        self.previous_sample, self.max_sample_gap = None, 0.

    def sample(self, *, force_disk=False):
        now = time.monotonic()
        if self.previous_sample is not None:
            self.max_sample_gap = max(self.max_sample_gap, now-self.previous_sample)
        self.previous_sample = now
        snapshot = tree_rss_snapshot(self.process)
        rss = sum(p['rss_bytes'] for p in snapshot)
        if rss >= self.max_rss:
            self.max_rss, self.peak_rss_processes = rss, snapshot
        self.samples += 1
        require(rss <= self.budget['rss_bytes'], 'WHOLE_JOB_RSS_BUDGET_STOP')
        if force_disk or time.monotonic()-self.last_disk >= 60:
            self.last_disk = time.monotonic()
            def size(root):
                total = 0
                for p in root.rglob('*'):
                    try:
                        if p.is_file() and not p.is_symlink():
                            total += p.stat().st_size
                    except FileNotFoundError:
                        pass  # concurrent atomic rename; next sample sees the new name
                return total
            out = size(self.output)
            scratch = sum(size(p) for p in self.scratch_paths)
            self.max_output, self.max_scratch = max(self.max_output, out), max(self.max_scratch, scratch)
            require(out <= self.budget['disk_bytes'] and scratch <= self.budget['scratch_bytes'],
                    'WHOLE_JOB_DISK_BUDGET_STOP')
            for p in [self.output] + self.scratch_paths:
                if p.exists():
                    require(shutil.disk_usage(p).free >= 2*1024**3, 'WHOLE_JOB_DISK_FREE_STOP')

    def receipt(self):
        return dict(max_tree_rss_bytes=self.max_rss, rss_samples=self.samples,
            peak_rss_processes=self.peak_rss_processes,
            max_rss_sample_gap_seconds=self.max_sample_gap,
            output_disk_bytes_60s_sampled_max=self.max_output,
            scratch_disk_bytes_60s_sampled_max=self.max_scratch,
            scope='supervisor + all descendants, including retained main and recovery workers',
            peak_scope='Nominal 0.25s RSS polling and 60s disk scans; measured RSS gap reported; sampled, not instantaneous peaks')


def group_members(group):
    members = []
    for p in psutil.process_iter():
        try:
            if os.getpgid(p.pid) == group:
                members.append(p)
        except (ProcessLookupError, PermissionError, psutil.NoSuchProcess):
            pass
    return members


def terminate_owned(process, known, *, session):
    # A separate Linux session is owned only by the top supervisor's child.
    # killpg also catches grandchildren when their parent dies between samples.
    if session and os.name != 'nt':
        for child in group_members(process.pid):
            try:
                known[(child.pid, child.create_time())] = child
            except psutil.NoSuchProcess:
                pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for child in reversed(list(known.values())):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)
    _, alive = psutil.wait_procs(list(known.values()), timeout=5)
    # Linux orphan zombies have exited and cannot hold scratch files open.
    require(not any(p.is_running() and p.status() != psutil.STATUS_ZOMBIE for p in alive),
            'OWNED_PROCESS_STILL_RUNNING')
    if session and os.name != 'nt':
        remaining = group_members(process.pid)
        _, alive = psutil.wait_procs(remaining, timeout=5)
        require(not any(p.is_running() and p.status() != psutil.STATUS_ZOMBIE for p in alive),
                'OWNED_PROCESS_GROUP_STILL_RUNNING')


def bounded_process(command, log_path, deadline, on_exit=None, *, monitor=None, session=False):
    require(deadline-time.monotonic() > 5, 'ENGINEERING_DEADLINE_BEFORE_CHILD')
    known = {}
    with Path(log_path).open('ab') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=session and os.name != 'nt')
        try:
            while True:
                try:
                    parent = psutil.Process(process.pid)
                    for child in [parent] + parent.children(recursive=True):
                        known[(child.pid, child.create_time())] = child
                except psutil.NoSuchProcess:
                    pass
                if monitor is not None:
                    monitor.sample()
                require(time.monotonic() < deadline, 'ENGINEERING_HARD_DEADLINE')
                code = process.poll()
                if code is not None:
                    return code
                time.sleep(min(0.25, max(0., deadline-time.monotonic())))
        finally:
            # Even normal exits must leave no writer alive before scratch cleanup.
            try:
                terminate_owned(process, known, session=session)
            except BaseException as exc:
                raise ProcessesNotStopped('OWNED_PROCESS_STOP_UNCONFIRMED:'+str(exc)) from exc
            if on_exit is not None:
                on_exit(process.pid)
