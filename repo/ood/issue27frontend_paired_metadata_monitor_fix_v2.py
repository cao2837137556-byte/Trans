"""Atomic writer-aware directory size sampling; no experiment entry point."""
import stat


def directory_bytes(folder):
    # Re-snapshot the whole directory when an atomic-write temporary disappears.
    # Never silently drop a vanished persistent artifact or return a partial sum.
    for attempt in range(3):
        total = 0
        for path in folder.iterdir():
            try:
                info = path.stat()
            except FileNotFoundError:
                if not path.name.endswith('.tmp'):
                    raise
                break
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
        else:
            return total
    raise RuntimeError('OUTPUT_DIRECTORY_SNAPSHOT_UNSTABLE_AFTER_3_SCANS')
