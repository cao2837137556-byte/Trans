"""Candidate: atomic visibility for live telemetry, durable scientific records.

Not installed in job 181645. Only the two exact live paths are routed here.
Power loss may lose the last progress update; it cannot authorize reuse/PASS.
The caller must bind these source bytes into a NEW execution delivery.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid


def live_json(path, value):
    """Same canonical bytes and atomic rename, without file/directory fsync."""
    path = Path(path)
    payload = (json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        if created and temporary.exists():
            temporary.unlink()  # only the exclusive temporary created above


def routed_writer(durable_writer, allowed_path):
    # Absolute lexical path: do not add a shared-filesystem realpath syscall
    # to every heartbeat. The caller owns and validates the output directory.
    target = os.path.abspath(os.fspath(allowed_path))

    def write(path, value):
        if os.path.abspath(os.fspath(path)) == target:
            return live_json(path, value)
        return durable_writer(path, value)
    return write


@contextmanager
def install(replay_module, worker_module, output):
    """Scope to replay's heartbeat and this worker's UI progress only.

    Proposed integration: wrap the replay.install block in prepare_inputs.
    No checkpoint-module or runtime-control writer is ever replaced. STOP,
    COMPLETE, CURRENT, candidate, batch and authorization writes remain durable.
    A process must not run concurrent installs against these same modules.
    """
    output = Path(output).absolute()
    original_replay = replay_module._write_json
    original_worker = worker_module.atomic_json
    replay_module._write_json = routed_writer(
        original_replay, output/'replay_status'/'REPLAY_HEARTBEAT.json')
    worker_module.atomic_json = routed_writer(original_worker, output/'PROGRESS.json')
    try:
        yield
    finally:
        replay_module._write_json = original_replay
        worker_module.atomic_json = original_worker
