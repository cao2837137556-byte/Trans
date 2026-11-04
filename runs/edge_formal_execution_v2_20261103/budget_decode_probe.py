"""Bounded 32k UDP causal-state probe; no snapshots, encoder or scores."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
if os.name == 'nt':
    sys.path.insert(0, str(ROOT/'runs/diagnostics_step2_r2_v1_20261025/benchmark_deps'))


def write(path, value):
    path = Path(path)
    tmp = path.with_name(path.name+'.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as out:
        json.dump(value, out, ensure_ascii=False, allow_nan=False, indent=2)
        out.write('\n')
    tmp.replace(path)


def worker(scratch):
    import psutil
    process = psutil.Process()
    process.cpu_affinity([process.cpu_affinity()[0]])
    sys.path.insert(0, str(ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter'))
    import edge_adapter as edge
    started = time.monotonic()
    deadline = started+25.
    db = scratch/'udp.sqlite'
    result = dict(schema='EDGE_BOUNDED_UDP_NUMERICAL_CONTEXT_PROBE_V1',
        model_calls=0, snapshots_emitted=0, scores_computed=0, cloud_jobs=0,
        scope='WINDOWS_LOCAL_NUMERICAL_STATE_ONLY_NOT_LINUX_RUNTIME_PASS',
        packet_cap=32768, hard_wall_seconds=30, hard_temporary_bytes=256*1024**2,
        python=sys.version, cpu_affinity=process.cpu_affinity(), samples=[])
    ctx = source = None
    rows = 0
    decode = append = 0.
    try:
        value = edge.card()
        spec = value['raw_inputs']['UDP']
        raw = Path(spec['path'])
        if raw.stat().st_size != spec['bytes'] or edge.sha(raw) != spec['sha256']:
            raise ValueError('RAW_PIN')
        result['raw_sha256'] = spec['sha256']
        result['source_pins'] = {str(p.relative_to(ROOT)).replace('\\','/'):edge.sha(p) for p in (
            Path(edge.__file__), ROOT/'repo/ood/continuous_input_v3.py',
            ROOT/'repo/ood/continuous_input_engineering_v1.py', ROOT/'repo/ood/spill_mapping_v1.py')}
        api = edge.prep.old.legacy_runtime()[0]
        ctx = edge.numerical_context(edge.segments('UDP',value)[0]['capture_id'], api, db,
                                     max_states=spec['records']+1)
        source = edge.decode_rows(raw, scratch/'decoder.stderr.log', stop_after=32768, deadline=deadline)

        def sample():
            size = sum(p.stat().st_size for p in scratch.iterdir() if p.is_file())
            rss = process.memory_info().rss
            for child in process.children(recursive=True):
                try: rss += child.memory_info().rss
                except psutil.NoSuchProcess: pass
            point = dict(frame=rows, seconds=time.monotonic()-started,
                decode_next_seconds=decode, append_seconds=append,
                states=len(ctx.states), spill=dict(ctx.states.stats),
                temporary_bytes=size, tree_rss_bytes=rss)
            result['samples'].append(point)
            write(HERE/'UDP_PROBE_STATUS.json', dict(result, status='RUNNING'))
            if size > result['hard_temporary_bytes']:
                raise ValueError('UDP_PROBE_TEMPORARY_CAP')
        while rows < 32768:
            if time.monotonic() >= deadline:
                result['status']='BOUNDED_TIME_LIMIT'
                break
            before=time.monotonic()
            packet=next(source)
            decode+=time.monotonic()-before
            before=time.monotonic()
            ctx.append(packet)
            append+=time.monotonic()-before
            rows+=1
            if rows%4096==0: sample()
        else:
            result['status']='COMPLETE_32768_PACKET_PROBE'
        sample()
        result.update(rows_completed=rows, seconds=time.monotonic()-started,
            decode_next_seconds=decode, append_seconds=append,
            final_store=dict(ctx.states.stats), raw_sha256_unchanged=edge.sha(raw)==spec['sha256'])
    except BaseException as exc:
        result.update(status='BOUNDED_PROBE_STOPPED', error=repr(exc),
            traceback=traceback.format_exc(), rows_completed=rows, seconds=time.monotonic()-started)
    finally:
        if source is not None: source.close()
        if ctx is not None: ctx.close()
        write(HERE/'UDP_PROBE_RESULT.json', result)


def supervise():
    import psutil
    scratch=Path(tempfile.mkdtemp(prefix='udp-budget-owned-',dir=HERE)).resolve()
    marker=scratch/'OWNERSHIP.json'
    write(marker, dict(pid=os.getpid(), purpose='BOUNDED_UDP_BUDGET_PROBE'))
    started=time.monotonic()
    limit=256*1024**2
    child=None
    stop=None
    with (HERE/'UDP_PROBE_WORKER.log').open('w',encoding='utf-8') as out:
        child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__)),'--scratch',str(scratch)],stdout=out,stderr=subprocess.STDOUT)
        try:
            while child.poll() is None:
                size=sum(p.stat().st_size for p in scratch.iterdir() if p.is_file())
                if time.monotonic()-started>=30 or size>limit:
                    stop='HARD_WALL_CAP' if time.monotonic()-started>=30 else 'HARD_TEMPORARY_CAP'
                    break
                try: child.wait(timeout=.25)
                except subprocess.TimeoutExpired: pass
            if stop:
                process=psutil.Process(child.pid)
                for descendant in reversed(process.children(recursive=True)):
                    try: descendant.kill()
                    except psutil.NoSuchProcess: pass
                try: process.kill()
                except psutil.NoSuchProcess: pass
                child.wait(timeout=5)
        finally:
            if scratch.parent!=HERE.resolve() or not marker.is_file():
                raise ValueError('CLEANUP_SCOPE')
            peak=max([0]+[s['temporary_bytes'] for s in json.loads((HERE/'UDP_PROBE_RESULT.json').read_text())['samples']]) if (HERE/'UDP_PROBE_RESULT.json').exists() else None
            shutil.rmtree(scratch)
            write(HERE/'UDP_PROBE_SUPERVISOR.json', dict(
                exit_code=child.returncode, stop_reason=stop, seconds=time.monotonic()-started,
                owned_temporary_removed=not scratch.exists(), peak_sampled_temporary_bytes=peak,
                hard_wall_seconds=30, hard_temporary_bytes=limit, model_calls=0,
                linux_runtime_gate_pass=False))
    print('UDP_BUDGET_PROBE_FINISHED')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--scratch')
    args=parser.parse_args()
    worker(Path(args.scratch).resolve()) if args.scratch else supervise()
