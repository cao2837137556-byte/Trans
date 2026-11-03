"""Read-only failed-job storage/CPU inspection; no decoding or model run."""
import json
from pathlib import Path
import sqlite3
import subprocess
import time

ROOT = Path('/public/home/jiangxinwei.zr/work/paper04/runs/edge_linux_preflight_deployment_v1_20261103')
OUTPUT = ROOT / 'outputs/edge_preflight_181403'


def main():
    started = time.monotonic()
    report = dict(job_id='181403', scope='READ_ONLY_FAILED_JOB_METADATA',
                  new_job_submitted=False, model_loaded=False, files=[], databases=[])
    for path in sorted(OUTPUT.rglob('*')):
        if not path.is_file():
            continue
        stat = path.stat()
        report['files'].append(dict(path=path.relative_to(OUTPUT).as_posix(),
                                    bytes=stat.st_size, mtime_ns=stat.st_mtime_ns))
        if path.suffix == '.sqlite':
            item = dict(path=path.relative_to(OUTPUT).as_posix(), readonly=True)
            before = (stat.st_size, stat.st_mtime_ns)
            try:
                with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2) as db:
                    db.execute('PRAGMA query_only=ON')
                    item['object_rows'], item['serialized_bytes'], item['max_object_bytes'] = db.execute(
                        'SELECT COUNT(*),SUM(LENGTH(value)),MAX(LENGTH(value)) FROM objects').fetchone()
            except sqlite3.Error as error:
                item['read_error'] = repr(error)
            stat = path.stat()
            item['database_bytes_and_mtime_unchanged'] = before == (stat.st_size, stat.st_mtime_ns)
            report['databases'].append(item)
    command = ['sacct', '-j', '181403', '--noheader', '--parsable2',
               '--format=JobIDRaw,State,Elapsed,TotalCPU,UserCPU,SystemCPU,MaxRSS,AveDiskRead,AveDiskWrite']
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    report['scheduler'] = dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    report['elapsed_seconds'] = time.monotonic() - started
    (ROOT / 'TIMEOUT_READONLY_AUDIT.json').write_text(json.dumps(report, indent=2)+'\n')
    print('EDGE_TIMEOUT_METADATA_READY', flush=True)


if __name__ == '__main__':
    main()
