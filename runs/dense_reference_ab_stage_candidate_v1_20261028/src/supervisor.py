"""Bound one stage, preserve failure and never retry a scientific operation."""
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import time

import psutil

from common import read, require, write


def now():
    return datetime.now(timezone.utc).isoformat()


def tree(child, tracked):
    try:
        parent = psutil.Process(child.pid)
        current = [parent] + parent.children(recursive=True)
    except psutil.NoSuchProcess:
        current = []
    for process in current:
        try:
            tracked[process.pid] = process.create_time()
        except psutil.NoSuchProcess:
            pass
    current = []
    for pid, created in tracked.items():
        try:
            process = psutil.Process(pid)
            if process.create_time() == created and process.status() != psutil.STATUS_ZOMBIE:
                current.append(process)
        except psutil.NoSuchProcess:
            pass
    return current


def kill_tree(child, tracked):
    current = tree(child, tracked)
    if os.name != 'nt':
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for process in reversed(current):
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(current, timeout=3)
    if os.name != 'nt':
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=3)
    child.wait(timeout=5)
    return [p.pid for p in tree(child, tracked)]


def directory_bytes(root):
    total = 0
    directories = [Path(root)]
    while directories:
        directory = directories.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            directories.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except FileNotFoundError:
                        pass
        except FileNotFoundError:
            pass
    return total


def run_stage(argv, *, output, control, limits, env=None, stop_file=None,
              expected=('COMPLETE',), notify=None):
    output, control = Path(output).resolve(), Path(control).resolve()
    require(not output.exists() and not control.exists(), 'FRESH_STAGE_DIRECTORIES_REQUIRED')
    require(not output.is_relative_to(control) and not control.is_relative_to(output),
            'STAGE_DIRECTORY_OVERLAP')
    control.mkdir(parents=True)
    started = time.monotonic()
    record = dict(status='RUNNING', started_utc=now(), updated_utc=now(),
                  retries=0, worker_alive=True, argv=argv)
    tracked, child, peak, failure = {}, None, 0, None
    with (control / 'stdout.log').open('xb') as stdout, (control / 'stderr.log').open('xb') as stderr:
        try:
            # Reject already-cancelled or impossible resource budgets before
            # launching even a tiny child. The loop retains the same guards.
            require(limits['wall_seconds'] > 0 and limits['rss_bytes'] > 0
                    and limits['output_bytes'] > 0 and limits['min_free_bytes'] >= 0,
                    'INVALID_STAGE_LIMITS')
            require(psutil.disk_usage(str(control)).free >= limits['min_free_bytes'], 'FREE_SPACE_LIMIT')
            require(stop_file is None or not Path(stop_file).exists(), 'USER_STOP_REQUESTED')
            child = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=env,
                start_new_session=os.name != 'nt',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            record['worker_pid'] = child.pid
            while True:
                processes = tree(child, tracked)
                rss = 0
                for process in processes:
                    try:
                        rss += process.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                peak = max(peak, rss)
                elapsed = time.monotonic() - started
                used = directory_bytes(output) + directory_bytes(control)
                require(elapsed <= limits['wall_seconds'], 'WALL_LIMIT')
                require(rss <= limits['rss_bytes'], 'TREE_RSS_LIMIT')
                require(used <= limits['output_bytes'], 'OUTPUT_LIMIT')
                require(psutil.disk_usage(str(control)).free >= limits['min_free_bytes'], 'FREE_SPACE_LIMIT')
                require(stop_file is None or not Path(stop_file).exists(), 'USER_STOP_REQUESTED')
                record.update(updated_utc=now(), elapsed_seconds=elapsed, peak_rss_bytes=peak,
                              output_bytes=used, worker_alive=child.poll() is None)
                write(control / 'status.json', record)
                if notify:
                    notify(record)
                if child.poll() is not None:
                    break
                time.sleep(limits.get('poll_seconds', 2))
            require(child.returncode == 0, 'WORKER_EXIT:' + str(child.returncode))
            require(not tree(child, tracked), 'SURVIVING_CHILD_PROCESS')
            result = read(output / 'RESULT.json')
            require(result.get('status') in expected, 'MISSING_OR_INVALID_COMPLETE_RESULT')
            record.update(status='COMPLETE', result_status=result['status'],
                          scientific_status=result.get('scientific_status', 'SEE_RESULT'))
        except BaseException as exc:
            failure = exc
            record.update(status='EXCEPTION_STOP', reason=str(exc), error_type=type(exc).__name__)
        finally:
            if child is not None:
                try:
                    remaining = kill_tree(child, tracked) if tree(child, tracked) or child.poll() is None else []
                    record.update(returncode=child.returncode, worker_alive=bool(remaining),
                                  surviving_pids=remaining, cleanup_confirmed=not remaining)
                except BaseException as cleanup_error:
                    record.update(status='EXCEPTION_STOP', cleanup_confirmed=False,
                        cleanup_error=repr(cleanup_error), worker_alive=True,
                        reason=record.get('reason') or 'CLEANUP_NOT_CONFIRMED')
                    if failure is None:
                        failure = cleanup_error
            else:
                record.update(worker_alive=False, cleanup_confirmed=True, surviving_pids=[])
            record.update(updated_utc=now(), elapsed_seconds=time.monotonic() - started,
                          peak_rss_bytes=peak, evidence_preserved=True, automatic_retry=False)
            write(control / 'status.json', record)
    if failure is not None:
        raise RuntimeError('STAGE_STOP:' + str(failure)) from failure
    return record
