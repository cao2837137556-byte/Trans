"""Extra strict singleton probes without changing ordinary frozen batch layout.

This module is a runtime adapter, not an encoder or numerical replacement.
All probes call the exact original forward, discard their vectors, and retain
only engineering byte-identity receipts. Dependencies are injected for tests.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


@contextmanager
def replaced_attribute(target, name, replacement):
    previous = getattr(target, name)
    setattr(target, name, replacement)
    try:
        yield previous
    finally:
        setattr(target, name, previous)


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class AttributeProxy:
    def __init__(self, original, **overrides):
        self._original = original
        self._overrides = overrides

    def __getattr__(self, key):
        return self._overrides[key] if key in self._overrides else getattr(self._original, key)


class StrictShapeProbes:
    """Probe once per required actual shape before its first ordinary batch.

    ``batch_plan`` is the unchanged encoder's sorted shape/UID grouping plan.
    It avoids guessing IP protocol from tokenizer-specific protocol tensors.
    Probe work is reserved against base endpoint count before any tensor clone
    or model call; ordinary forwards keep their original batch and return.
    """
    def __init__(self, required_shapes, batch_plan, base_rows, out, forward,
                 physical_batch, tensor_hash, guard, max_logical=100):
        self.required = {tuple(map(int, x)) for x in required_shapes}
        self.plan = [(tuple(map(int, shape)), int(rows)) for shape, rows in batch_plan]
        self.base_rows = int(base_rows)
        self.out = Path(out)
        self.original_forward = forward
        self.physical_batch = physical_batch
        self.tensor_hash = tensor_hash
        self.guard = guard
        self.max_logical = int(max_logical)
        self.cursor = 0
        self.attempted = set()
        self.passed = set()
        self.failed = []
        self.extra_logical = 0
        self.extra_physical = 0
        self.extra_seconds = 0.0
        require(self.required and all(len(x) == 3 and min(x) > 0 for x in self.required),
                'REQUIRED_SHAPES_INVALID')
        require(self.base_rows > 0 and sum(n for _, n in self.plan) == self.base_rows,
                'BASE_BATCH_PLAN_ROWS')
        require(self.required <= {shape for shape, _ in self.plan}, 'REQUIRED_SHAPE_NOT_IN_SLICE')
        require(self.base_rows + len(self.required) <= self.max_logical,
                'BASE_PLUS_REQUIRED_PROBES_EXCEEDS_CAP')

    def _ledger(self, value):
        with (self.out / 'STRICT_SHAPE_PROBE_LEDGER.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def summary(self):
        return dict(schema='STRICT_REQUIRED_SHAPE_SINGLETON_PROBES_V1',
            required_shapes=[list(x) for x in sorted(self.required)],
            attempted_shapes=[list(x) for x in sorted(self.attempted)],
            passed_shapes=[list(x) for x in sorted(self.passed)], failures=self.failed,
            ordinary_base_rows=self.base_rows, ordinary_batches_completed=self.cursor,
            ordinary_batches_planned=len(self.plan), extra_logical_rows=self.extra_logical,
            extra_physical_rows=self.extra_physical, extra_seconds=self.extra_seconds,
            total_logical_reserved=self.base_rows+self.extra_logical,
            maximum_total_logical=self.max_logical,
            strict_byte_identity_unchanged=True, original_batch_layout_unchanged=True,
            probe_vectors_discarded=True, external_quality_used=False,
            status='PASS' if self.passed == self.required and not self.failed else 'NOT_PASSED')

    def save(self):
        write_json(self.out / 'STRICT_SHAPE_PROBE_SUMMARY.json', self.summary())

    def _probe(self, model, batch, shape, device):
        import numpy as np
        self.guard()
        require(self.base_rows+self.extra_logical+1 <= self.max_logical,
                'EXTRA_PROBE_LOGICAL_CAP')
        self.attempted.add(shape)
        self.extra_logical += 1
        self.extra_physical += 16
        record = dict(shape=list(shape), ordinary_batch=self.cursor, status='ATTEMPT',
            extra_logical_reserved=self.extra_logical, extra_physical_reserved=self.extra_physical,
            total_logical_reserved=self.base_rows+self.extra_logical)
        self._ledger(record)
        self.save()
        started = time.monotonic()
        actual = None
        values = None
        try:
            singleton = {}
            for key, value in batch.items():
                require(hasattr(value, 'shape') and len(value.shape) >= 1 and value.shape[0] > 0,
                        'PROBE_BATCH_TENSOR_ONLY')
                first = value[:1]
                singleton[key] = first.clone() if hasattr(first, 'clone') else first.copy()
            actual, physical = self.physical_batch(singleton, 1, self.tensor_hash)
            require(physical == 16, 'PROBE_PHYSICAL_BATCH_NOT_16')
            hashes = [self.tensor_hash(actual, j) for j in range(physical)]
            require(len(set(hashes)) == 1, 'PROBE_CLONE_INPUT_BYTES_DIFFER')
            values = self.original_forward(model, [actual], device)
            require(isinstance(values, np.ndarray) and values.shape == (16, 768)
                    and values.dtype == np.float32 and np.isfinite(values).all(),
                    'PROBE_E3_SCHEMA_FINITE')
            output_hashes = [hashlib.sha256(v.tobytes()).hexdigest() for v in values]
            require(all(v.tobytes() == values[0].tobytes() for v in values),
                    'STRICT_SHAPE_SINGLETON_OUTPUT_BYTES_DIFFER')
            self.passed.add(shape)
            self._ledger(dict(record, status='PASS', seconds=time.monotonic()-started,
                input_tensor_sha256=hashes, output_sha256=output_hashes))
            self.guard()
        except BaseException as error:
            failure = dict(record, status='FAIL', error=repr(error), seconds=time.monotonic()-started)
            if actual is not None:
                failure['input_tensor_sha256'] = [self.tensor_hash(actual, j) for j in range(16)]
            if isinstance(values, np.ndarray):
                failure['output_sha256'] = [hashlib.sha256(v.tobytes()).hexdigest() for v in values]
                if values.ndim == 2 and len(values):
                    failure['max_absolute_output_difference'] = float(np.max(np.abs(values-values[:1])))
            self.failed.append(failure)
            self._ledger(failure)
            write_json(self.out / 'STRICT_SHAPE_PROBE_FAILURE.json', failure)
            raise
        finally:
            self.extra_seconds += time.monotonic()-started
            self.save()

    def forward(self, model, batches, device='cpu'):
        require(device == 'cpu', 'PROBE_CPU_RUNTIME_ONLY')
        batches = list(batches)
        require(len(batches) == 1 and self.cursor < len(self.plan), 'ORDINARY_FORWARD_PLAN')
        batch = batches[0]
        shape, logical = self.plan[self.cursor]
        physical = 16 if logical == 1 else logical
        require(tuple(batch['input_ids'].shape) == (physical, shape[1]*shape[2]),
                'ORDINARY_BATCH_GEOMETRY')
        require(tuple(batch['dataset_burst_sizes'].shape) == (physical, shape[2]),
                'ORDINARY_BURST_GEOMETRY')
        if shape in self.required and shape not in self.attempted:
            self._probe(model, batch, shape, device)
        self.guard()
        # The exact input mapping and the original normal batch size survive.
        values = self.original_forward(model, batches, device)
        self.cursor += 1
        self.save()
        return values

    def require_complete(self):
        require(self.cursor == len(self.plan), 'ORDINARY_FORWARD_COVERAGE')
        require(self.passed == self.required and not self.failed, 'REQUIRED_SINGLETON_PROBE_COVERAGE')

