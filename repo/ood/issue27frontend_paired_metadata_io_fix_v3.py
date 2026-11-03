"""Bounded handling of Windows sharing conflicts for atomic JSON receipts."""
import os
import time
import issue27frontend_paired_metadata_v1 as original


def atomic_json(path, value):
    raw = original.canonical(value) + b'\n'
    original.require(len(raw) < 64 * 1024**2, 'JSON_OUTPUT_SIZE')
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    # Only repeat the filesystem rename, never the data read or experiment.
    # Total requested sleep <= 0.5 s; persistent denial still fails closed.
    for attempt in range(21):
        try:
            os.replace(temp, path)
            return
        except PermissionError as exc:
            if getattr(exc, 'winerror', None) not in (5, 32, 33) or attempt == 20:
                raise
            time.sleep(0.025)
