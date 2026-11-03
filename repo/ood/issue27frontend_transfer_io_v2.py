"""Append-only progress journal; immutable pointer and complete-record reads."""
import json
from pathlib import Path
import issue27frontend_transfer_support_v1 as s

original_atomic_json = s.atomic_json
original_read_json = s.read_json
MAX_RECORD_BYTES = 1024*1024


def atomic_json(path,value):
    path = Path(path)
    if path.name != 'progress.json':
        return original_atomic_json(path,value)
    journal = path.with_suffix('.jsonl')
    data = s.canonical(value)+b'\n'
    s.require(len(data) <= MAX_RECORD_BYTES,'PROGRESS_RECORD_TOO_LARGE')
    # Single writer. Readers may hold ordinary Windows handles: no rename/delete.
    with journal.open('ab') as f:
        f.write(data)
    if not path.exists():
        # Immutable compatibility pointer, created only after a complete record.
        with path.open('xb') as f:
            f.write(s.canonical({'format':'append_only_progress_v2','journal':'progress.jsonl'})+b'\n')


def read_progress(path):
    with Path(path).open('rb') as f:
        f.seek(0,2);size=f.tell();offset=max(0,size-2*MAX_RECORD_BYTES)
        f.seek(offset);raw=f.read()
    end=raw.rfind(b'\n')
    s.require(end >= 0,'NO_COMPLETE_PROGRESS_RECORD')
    start=raw.rfind(b'\n',0,end)+1
    s.require(start > 0 or offset == 0,'TRUNCATED_PROGRESS_WINDOW')
    return json.loads(raw[start:end].decode('utf-8'))


def read_json(path):
    path=Path(path)
    if path.name == 'progress.json' and path.with_suffix('.jsonl').exists():
        return read_progress(path.with_suffix('.jsonl'))
    return original_read_json(path)
