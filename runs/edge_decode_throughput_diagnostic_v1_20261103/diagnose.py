"""One bounded local HTTP causal-state throughput diagnostic; no encoder."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = HERE / 'scratch'
DB = SCRATCH / 'http_context.sqlite'
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
sys.path.insert(0, str(ROOT/'runs/diagnostics_step2_r2_v1_20261025/benchmark_deps'))


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


def cleanup_owned_db():
    root = SCRATCH.resolve()
    for suffix in ('', '-journal', '-wal', '-shm'):
        path = Path(str(DB)+suffix).resolve()
        if path.parent != root:
            raise RuntimeError('DIAGNOSTIC_SCRATCH_SCOPE')
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def worker():
    import psutil
    process = psutil.Process()
    available = process.cpu_affinity()
    process.cpu_affinity([available[0]])
    sys.path.insert(0, str(ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter'))
    import edge_adapter as edge
    started = time.monotonic()
    deadline = started+55
    result = dict(scope='LOCAL_HTTP_CONTEXT_THROUGHPUT_ONLY', model_evaluations=0,
                  encoder_loaded=False, training=False, cloud_run=False,
                  packet_cap=32768, wall_hard_seconds=60, db_cap_bytes=256*1024**2,
                  process_cpu_affinity=process.cpu_affinity(), python=sys.version,
                  snapshots=[])
    ctx = source = None
    rows = 0
    decode_seconds = append_seconds = 0.
    samples = []
    def snapshot():
        paths = [Path(str(DB)+suffix) for suffix in ('','-journal','-wal','-shm')]
        sizes = {path.name:path.stat().st_size for path in paths if path.is_file()}
        tree = [process]+process.children(recursive=True)
        rss = sum(p.memory_info().rss for p in tree if p.is_running())
        sample = dict(frame=rows, elapsed_seconds=time.monotonic()-started,
                      decode_next_seconds=decode_seconds, context_append_seconds=append_seconds,
                      state_store=dict(ctx.states.stats) if ctx else None,
                      state_count=len(ctx.states) if ctx else None,
                      db_files_bytes=sizes, db_total_bytes=sum(sizes.values()), tree_rss_bytes=rss)
        samples.append(sample)
        write(HERE/'STATUS.json', dict(result, status='RUNNING', samples=samples))
        if sample['db_total_bytes'] > result['db_cap_bytes']:
            raise RuntimeError('DIAGNOSTIC_DB_CAP')
        return sample
    try:
        value = edge.card()
        spec = value['raw_inputs']['HTTP']
        raw = Path(spec['path'])
        result['raw_input'] = dict(path=str(raw), sha256=edge.sha(raw), bytes=raw.stat().st_size)
        edge.frozen.require(result['raw_input']['sha256']==spec['sha256'] and result['raw_input']['bytes']==spec['bytes'], 'RAW_PIN')
        result['code_pins'] = {str(p.relative_to(ROOT)).replace('\\','/'):edge.sha(p) for p in (
            Path(edge.__file__), ROOT/'repo/ood/continuous_input_v3.py',
            ROOT/'repo/ood/continuous_input_engineering_v1.py', ROOT/'repo/ood/spill_mapping_v1.py')}
        SCRATCH.mkdir(exist_ok=False)
        api = edge.prep.old.legacy_runtime()[0]
        ctx = edge.numerical_context(edge.segments('HTTP',value)[0]['capture_id'], api, DB,
                                     max_states=spec['records']+1)
        source = edge.decode_rows(raw, HERE/'decoder.stderr.log', stop_after=32768, deadline=deadline)
        while rows < 32768:
            if time.monotonic() >= deadline:
                result['status']='BOUNDED_TIME_LIMIT'
                break
            before = time.monotonic()
            packet = next(source)
            decode_seconds += time.monotonic()-before
            before = time.monotonic()
            ctx.append(packet)
            append_seconds += time.monotonic()-before
            rows += 1
            if rows%4096==0:
                snapshot()
        else:
            result['status']='COMPLETE_32768_PACKET_DIAGNOSTIC'
        snapshot()
        result.update(rows_completed=rows, samples=samples, elapsed_seconds=time.monotonic()-started,
                      final_store_stats=dict(ctx.states.stats), numerical_snapshots_emitted=0,
                      raw_sha256_unchanged=(edge.sha(raw)==spec['sha256']))
    except BaseException as error:
        result.update(status='DIAGNOSTIC_STOPPED', error=repr(error), traceback=traceback.format_exc(),
                      rows_completed=rows, samples=samples, elapsed_seconds=time.monotonic()-started)
    finally:
        if source is not None:
            source.close()
        if ctx is not None:
            ctx.close()
        cleanup_owned_db()
        result['owned_temporary_database_removed']=not any(Path(str(DB)+s).exists() for s in ('','-journal','-wal','-shm'))
        write(HERE/'RESULT.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','snapshots','code_pins','raw_input')}, ensure_ascii=False))


def supervise():
    import psutil
    started=time.monotonic()
    with (HERE/'worker.log').open('x',encoding='utf-8') as log:
        child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__)),'--worker'],stdout=log,stderr=subprocess.STDOUT)
        try:
            code=child.wait(timeout=60)
        except subprocess.TimeoutExpired:
            parent=psutil.Process(child.pid)
            descendants=parent.children(recursive=True)
            for descendant in reversed(descendants):
                try:descendant.kill()
                except psutil.NoSuchProcess:pass
            parent.kill()
            child.wait(timeout=5)
            cleanup_owned_db()
            write(HERE/'SUPERVISOR_TIMEOUT.json',dict(status='HARD_60_SECONDS_LIMIT',elapsed_seconds=time.monotonic()-started,temporary_db_removed=True,model_evaluations=0))
            code=124
    print(json.dumps(dict(exit_code=code,elapsed_seconds=time.monotonic()-started,results=str(HERE/'RESULT.json'))))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    worker() if args.worker else supervise()
