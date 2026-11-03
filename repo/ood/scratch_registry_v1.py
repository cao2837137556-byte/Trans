"""Exact in-process registry for ephemeral SQLite files and sidecars.

Registrations survive cleanup so a concurrent disk scan that already enumerated
an owned path can finish. This is not a registry of trusted input databases.
"""
from pathlib import Path
import threading

_lock = threading.RLock()
_files = set()
_directories = set()


def register_sqlite(path):
    """Call only after exclusively creating a new private working database."""
    path = Path(path).resolve()
    with _lock:
        _files.update(Path(str(path) + suffix) for suffix in ('', '-journal', '-wal', '-shm'))
        # Cleanup also removes the containing private cache directory. Only its
        # exact path is recorded; descendants are not implicitly exempted.
        _directories.add(path.parent)


def register_sqlite_sidecars(path):
    """Register only transient sidecars of a newly created persistent database.

    The database and its containing directory remain required output artifacts;
    disappearance of either must still fail a concurrent disk scan.
    """
    path = Path(path).resolve()
    with _lock:
        _files.update(Path(str(path) + suffix) for suffix in ('-journal', '-wal', '-shm'))


def may_disappear(path):
    path = Path(path).resolve()
    with _lock:
        return path in _files or path in _directories
