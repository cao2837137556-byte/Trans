"""Compute-node qualification, reference preparation and one formal comparison."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

import numpy as np

from frozen_selector import need
from motion_index import build
from motion_ingress import REPAIR_RUN, RUN
from runtime_support import HERE, Progress, Store, TSHARK_SHA, asset, digest, read, write

CARD_SHA = '3a346a76bc05d8428a60dbd0e73c7951463d21b2452230b12e620b59088e5368'
PYTHON = Path('/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python')
NUMPY = 'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201'


def runtime(args, package):
    need(sys.platform.startswith('linux') and os.environ.get('SLURM_JOB_ID', '').isdigit() and
         os.environ.get('SLURMD_NODENAME') and os.environ.get('SLURM_CPUS_PER_TASK') == '4',
         'COMPUTE_NODE_RUNTIME')
    need(sys.version_info[:2] == (3,11) and np.__version__ == '2.0.1' and not sys.flags.optimize and
         Path(sys.executable).resolve() == PYTHON.resolve() and
         Path(np.__file__).resolve().is_relative_to((args.project / NUMPY).resolve()),
         'FROZEN_PYTHON_NUMPY_RUNTIME')
    for name, pin in package['files'].items():
        path = HERE / name
        need(path.resolve().is_relative_to(HERE) and digest(path) == pin, 'PACKAGE_SHA:' + name)
    need(package['card_sha256'] == digest(HERE/'freeze.md') == CARD_SHA, 'FROZEN_CARD_ID')
    tshark = shutil.which('tshark')
    need(tshark and digest(Path(tshark)) == TSHARK_SHA, 'FROZEN_TSHARK_4_6_6')
    import torch
    need(torch.__version__.split('+')[0] == '2.5.1', 'FROZEN_TORCH_VERSION')
    write(args.target/f'RUNTIME_{args.phase}.json', dict(status='PASS',
        node=os.environ['SLURMD_NODENAME'], job_id=os.environ['SLURM_JOB_ID'],
        python=sys.version, numpy=np.__version__, torch=torch.__version__, tshark=tshark,
        tshark_sha256=TSHARK_SHA, package=asset(HERE/'PACKAGE_MANIFEST.json')))
    return tshark


def method_check(cfg, geom):
    method = cfg['method']
    need(all(geom['method'][k] == value for k,value in method.items()) and
         method['p'] == 4 and method['lambda_value'] == .25 and
         method['kernel'] == 'g(s)=1-(1-s)^4' and method['guard'] == 'SYN_AND_NOT_ACK_ALL_DEVICES' and
         method['heads'] == ['27','127','227','ensemble'], 'P4_MAIN_METHOD_IDENTITY')


def resume_motion(parent, target):
    witness = read(HERE/'MOTION_ROLE_HEADER_WITNESS.json')
    sources = read(HERE/'REFERENCE_SOURCES.json')
    motion = parent/'motion'
    receipt = read(motion/'ROLE_BINDING.json')
    pins = receipt['assets']
    expected = dict(sources['motion_index_sha256'], raw=witness['raw_sha256'])
    paths = dict(raw='BelkinWemoMotionSensor_ec1a59832811.pcap', packet_index='packet_index.npy',
                 chronological_order='chronological_order.npy')
    need(set(pins) == set(expected) == set(paths), 'PREDECESSOR_MOTION_SCOPE')
    for name, pin in pins.items():
        path = motion/paths[name]
        need(Path(pin['path']) == path and pin['sha256'] == expected[name] == digest(path),
             'PREDECESSOR_MOTION_PIN:' + name)
    for key in ('packets','bank_end_frame','first_dev_frame','reference_end_us','first_dev_time_us',
                'observed_utc_dates','ref_dates','dev_dates'):
        need(receipt[key] == witness[key], 'PREDECESSOR_MOTION_ROLE:' + key)
    write(target/'PREPARATION_REUSE.json', dict(status='PASS', predecessor=str(parent),
        reused_motion=receipt, role_receipt=asset(motion/'ROLE_BINDING.json')))
    return pins, receipt


def first(args, cfg, geom, tshark, progress):
    from prepare_reference import prepare
    from paired_replay import run

    store = Store(args.project, ('raw_or_index', 'reference', 'census', 'runtime'))
    parent = args.project/'runs'/RUN if args.target.name == REPAIR_RUN else None
    prior_probe = parent/'preflight' if parent else None
    if parent is None:
        motion_root = args.target/'motion'
        with progress.measure('MOTION_RAW_AND_INDEX'):
            motion = build(args.archive, motion_root, read(HERE/'MOTION_ROLE_HEADER_WITNESS.json'), progress)
            motion_receipt = read(motion_root/'ROLE_BINDING.json')
    else:
        with progress.measure('VERIFY_REUSED_MOTION_RAW_AND_INDEX'):
            motion, motion_receipt = resume_motion(parent, args.target)
    probe_dir = args.target/'preflight'
    prepare(store, probe_dir, motion, progress, tshark, cfg, probe=True, prior_probe=prior_probe)
    candidate = args.target/'candidate'
    prepare(store, candidate, motion, progress, tshark, cfg, probe=False, prior_probe=prior_probe)
    # Open frozen evaluation assets only after the complete candidate is sealed.
    eval_store = Store(args.project, ('reference','query'))
    result = run(eval_store, probe_dir, args.target, cfg, geom, progress, probe=True)
    preflight = args.target/'PREFLIGHT.json'
    write(preflight, dict(status='PASS', scope='ACTUAL_COMPUTE_NODE_REAL_INPUT',
          job_id=os.environ['SLURM_JOB_ID'], motion=motion_receipt,
          sealed_probe=asset(probe_dir/'CANDIDATE.json'), peak_rss_kib=progress.rss(), **result))
    result = run(eval_store, candidate, args.target, cfg, geom, progress, probe=False, sizing_only=True)
    pools = result['pools']
    seconds = sum(p['probe']['geometry_seconds'] * max(1., p['pair_count']/p['probe']['pairs'])
                  for pool,p in pools.items() if pool != 'EDGE')
    requested = max(3600, int((900 + 2*seconds+59)//60)*60)
    need(requested <= 21600, 'MEASURED_FORMAL_WALLTIME_EXCEEDS_6H:' + str(requested))
    need(progress.rss() <= 10*1024**2, 'MEASURED_FORMAL_MEMORY_HEADROOM')
    sizing = args.target/'FORMAL_SIZING.json'
    write(sizing, dict(status='PASS', planned_wall_seconds=requested, memory_mib=12288,
          measured_peak_rss_kib=progress.rss(), projected_seconds=seconds, actual_reference_slice=pools))
    write(args.target/'PREP_RECEIPT.json', dict(status='READY_FOR_ONE_PAIRED_REPLAY',
          job_id=os.environ['SLURM_JOB_ID'], candidate=asset(candidate/'CANDIDATE.json'),
          preflight=asset(preflight), sizing=asset(sizing)))


def formal(args, cfg, geom, progress):
    from paired_replay import run

    receipt = read(args.target/'PREP_RECEIPT.json')
    candidate = args.target/'candidate'
    need(receipt['status'] == 'READY_FOR_ONE_PAIRED_REPLAY' and
         receipt['preflight']['sha256'] == digest(args.target/'PREFLIGHT.json') and
         receipt['candidate']['sha256'] == digest(candidate/'CANDIDATE.json') and
         receipt['sizing']['sha256'] == digest(args.target/'FORMAL_SIZING.json'), 'FORMAL_PREPARATION_GATE')
    with (args.target/'FORMAL_REPLAY_STARTED').open('x') as marker:
        marker.write(os.environ['SLURM_JOB_ID']+'\n')
        marker.flush()
        os.fsync(marker.fileno())
    result = run(Store(args.project, ('reference','query')), candidate, args.target, cfg,
                 geom, progress, probe=False)
    status = 'ZERO_DEGRADATION_PASS' if not result['failures'] else 'ZERO_DEGRADATION_FAIL'
    path = args.target/'ACCEPTANCE.json'
    write(path, dict(status=status, candidate=receipt['candidate'], formal_replays=1,
        job_id=os.environ['SLURM_JOB_ID'], resource=asset(args.target/'RESOURCES_replay.json'), **result))
    metrics = read(args.target/'METRICS.json')
    summary = [r for r in metrics if r['head']=='ensemble' and r['guard_stratum']=='ALL' and
               r['view']==('full' if r['pool']=='EDGE' else 'post_window_primary') and
               r['group'] in ('NORMAL','ATTACK','HTTP','UDP')]
    write(args.target/'RESULT_INDEX.json', dict(status=status, acceptance=asset(path),
          card_sha256=CARD_SHA, summary=summary, failure_count=len(result['failures'])))
    write(args.target/'REPLAY_RECEIPT.json', dict(status='FORMAL_REPLAY_COMPLETE',
          job_id=os.environ['SLURM_JOB_ID'], acceptance=asset(path), outcome=status))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare','replay'))
    parser.add_argument('project', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    start = time.monotonic()
    progress = Progress(args.target, args.phase)
    try:
        tshark = runtime(args, read(HERE/'PACKAGE_MANIFEST.json'))
        cfg, geom = read(HERE/'CONFIG.json'), read(HERE/'GEOMETRY.json')
        method_check(cfg, geom)
        if args.phase == 'prepare':
            first(args, cfg, geom, tshark, progress)
        else:
            formal(args, cfg, geom, progress)
        progress('COMPLETE', 1, 1, force=True)
    except Exception as err:
        write(args.target/f'FAILURE_{args.phase}.json', dict(status='ENGINEERING_STOP',
              stage=progress.current, error=str(err), traceback=traceback.format_exc(),
              wall_seconds=time.monotonic()-start, peak_rss_kib=progress.rss()))
        raise


if __name__ == '__main__':
    main()
