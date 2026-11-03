"""Small progress/budget adapter for an isolated C4 worker.

The coordinator owns process-tree RSS, output and cumulative budgets. A worker
only enforces its allocated wall time and local logical encoding allowance.
Charging encoding authorizes a forward pass; it never claims completed rows.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import threading
import time


def utc():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class WorkerRuntime:
    def __init__(self, output_status: Path, wall_seconds, encoded_cap):
        require(type(wall_seconds) in (int, float) and
                math.isfinite(wall_seconds) and wall_seconds > 0,
                'POSITIVE_FINITE_WALL_SECONDS')
        require(type(encoded_cap) is int and encoded_cap >= 0,
                'NONNEGATIVE_INTEGER_ENCODED_CAP')
        self.output_status = Path(output_status)
        self.wall_seconds = wall_seconds
        self.encoded_cap = encoded_cap
        self.children = []
        self.started = time.monotonic()
        self._encoded = 0
        self._last_flush = None
        self._lock = threading.RLock()
        self.state = dict(phase='STARTING', elapsed_seconds=0.,
                          encoded_charged=0, work_heartbeat_utc=utc())
        self._flush(self.started)

    def _check(self):
        now = time.monotonic()
        require(now - self.started <= self.wall_seconds, 'WALL_SECONDS_LIMIT')
        require(self._encoded <= self.encoded_cap, 'ENCODED_LIMIT')
        return now

    def _flush(self, now):
        self.state.update(elapsed_seconds=now - self.started,
                          encoded_charged=self._encoded)
        temporary = self.output_status.with_name(
            '.' + self.output_status.name + '.' + str(os.getpid()) + '.' +
            str(threading.get_ident()) + '.tmp')
        try:
            self.output_status.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(self.state, sort_keys=True, indent=2)
                                 + '\n', encoding='utf-8')
            temporary.replace(self.output_status)
            self._last_flush = now
        except PermissionError as exc:
            # A display reader on Windows may hold the destination briefly.
            # This must not stop science or obscure a budget failure.
            self.state['display_write_warning'] = str(exc)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except PermissionError:
                pass

    def guard(self):
        """Check limits without reporting new work or refreshing its heartbeat."""
        with self._lock:
            now = self._check()
            if self._last_flush is None or now - self._last_flush >= .5:
                self._flush(now)

    def update(self, stage=None, **fields):
        with self._lock:
            now = self._check()
            require(not any(key in fields for key in
                    ('phase', 'elapsed_seconds', 'encoded_charged',
                     'work_heartbeat_utc')), 'RESERVED_PROGRESS_FIELD')
            if stage is not None and str(stage) != self.state['phase']:
                for key in ('done', 'completed', 'total', 'raw_packets',
                            'decoder_pass', 'selected_snapshots',
                            'encoding_batches'):
                    self.state.pop(key, None)
            self.state.update(fields)
            if stage is not None:
                self.state['phase'] = str(stage)
            self.state['work_heartbeat_utc'] = utc()
            self._flush(now)

    def encoded(self, count):
        """Reserve local logical rows before forwarding; reject overflow first."""
        require(type(count) is int and count >= 0, 'NONNEGATIVE_INTEGER_COUNT')
        with self._lock:
            now = self._check()
            value = self._encoded + count
            require(value <= self.encoded_cap, 'ENCODED_LIMIT')
            self._encoded = value
            self._flush(now)

    def tick(self, done=None, total=None, **fields):
        for key, value in (('done', done), ('total', total)):
            if value is not None:
                require(type(value) is int and value >= 0,
                        'NONNEGATIVE_INTEGER_' + key.upper())
                fields[key] = value
        self.update(**fields)
