"""Single authorized P/T/K chain, fresh output, bounded workers, no retry."""
import argparse
import gc
import importlib.metadata
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import numpy as np
import torch
import query_tail_core_v2 as k
import query_tail_prepare_v2 as p
import query_tail_train_v2 as t
import query_tail_evaluate_v2 as e
c = k.c


class Progress(c.Progress):
    def guard(self):
        super().guard()
        self.peak_rss = max(getattr(self, 'peak_rss', 0), self.rss)

    def emit(self, status='RUNNING', **extra):
        super().emit(status, sampled_peak_tree_rss_gib=getattr(self, 'peak_rss', 0)/1024**3,
                     resource_measure='sampled process-tree RSS; shared mappings may be counted repeatedly', **extra)


def authorize(root, explicit):
    c.require(explicit, 'REAL_CHAIN_NOT_AUTHORIZED')
    root = Path(root).resolve(); c.verify(root, exact=False)
    design = c.read(c.pin(root/'design_contract.json', k.DESIGN_SHA))
    runtime = c.read(root/'runtime_contract.json')
    c.require(runtime['design_sha256'] == k.DESIGN_SHA and runtime['retries'] == 0 and runtime['train_workers'] == 3, 'RUNTIME_CONTRACT')
    c.require(runtime['cpus'] == 16 and runtime['slurm']['memory'] == '64G' and runtime['limits']['memory_gib'] == 56, 'RESOURCE_CONTRACT')
    c.require(runtime['limits']['wall_seconds'] == 70*3600 and runtime['slurm']['time'] == '3-00:00:00', 'WALL_CONTRACT')
    c.require(sys.version_info[:2] == (3, 9), 'PYTHON39_REQUIRED')
    for package, expected in runtime['versions'].items():
        c.require(importlib.metadata.version(package).split('+')[0] == expected, 'RUNTIME_VERSION:'+package)
    return design, runtime


def prepared(run):
    run = Path(run); complete = c.read(run/'P_COMPLETE.json')
    c.require(complete['status'] == 'COMPLETE' and complete['design_sha256'] == k.DESIGN_SHA, 'P_NOT_COMPLETE')
    c.pin(run/'prepared/SHA256SUMS', complete['prepared_seal']); c.verify(run/'prepared')
    return run/'prepared'


def worker(root, run, arm, seed, explicit):
    design, runtime = authorize(root, explicit); run = Path(run)
    # Worker cannot use an arbitrary unapproved prepared directory.
    c.require(run.resolve() == (Path(root)/'runs/query_tail').resolve(), 'WORKER_RUN_SCOPE')
    launch = c.read(run/'launch_T.json')
    c.pin(run/'P_COMPLETE.json', launch['P_sha256'])
    progress = Progress(run/('monitor_'+arm+'_'+str(seed)), runtime['worker_limits'])
    def stop_signal(signum, frame): raise RuntimeError('SIGNAL_STOP:'+str(signum))
    signal.signal(signal.SIGTERM, stop_signal); signal.signal(signal.SIGINT, stop_signal)
    try:
        folder = prepared(run)
        rows = list(c.rows(folder/'LEARN.jsonl.gz'))
        with np.load(folder/'FIT.npz', allow_pickle=False) as f: ix = f['indices'].copy()
        with np.load(folder/'normalizer.npz', allow_pickle=False) as f: norm = f['mean'].copy(), f['scale'].copy()
        path = Path(runtime['base_run'])/'features/LEARN.npy'
        pins = p.manifest(path.parent, design['provenance']['feature_manifest_sha256']); c.pin(path, pins['LEARN.npy'])
        values = np.load(path, mmap_mode='r', allow_pickle=False)
        q = np.load(folder/'LEARN_q.npy', mmap_mode='r', allow_pickle=False)
        windows = np.load(folder/'LEARN_window.npy', mmap_mode='r', allow_pickle=False)
        t.train(design, rows, values, q, norm, ix, windows['stage'], arm, seed, run/'endpoints'/(arm+'_'+str(seed)), progress)
        progress.stop('COMPLETE', completed=design['training']['updates_per_head'], total=design['training']['updates_per_head'])
    except BaseException as exc:
        progress.record_failure(exc, 'training_worker'); progress.stop('STOPPED_NO_RETRY', error=repr(exc)); raise


def launch(root, run, design, runtime, progress):
    tasks = [(arm, seed) for arm in k.ARMS for seed in c.SEEDS]; pending = tasks[:]; active = []; all_jobs = []
    progress.stage = 'T_NINE_FIXED_HEADS'
    try:
        while pending or active:
            progress.guard()
            while pending and len(active) < runtime['train_workers']:
                arm, seed = pending.pop(0); name = arm+'_'+str(seed)
                log = (run/'logs'/(name+'.log')).open('x', encoding='utf-8')
                command = [sys.executable, str(Path(root)/'repo/ood/query_tail_runner_v2.py'), 'worker', '--root', str(root), '--run', str(run), '--arm', arm, '--seed', str(seed), '--authorize-chain']
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
                process.continuous_group = os.name != 'nt'; progress.children.append(process)
                item = dict(name=name, process=process, log=log); active.append(item); all_jobs.append(item)
            for item in active[:]:
                code = item['process'].poll()
                if code is None: continue
                item['log'].close()
                c.require(code == 0, 'WORKER_FAILED:'+item['name']+':'+str(code))
                c.require(c.read(run/('monitor_'+item['name'])/'status.json')['status'] == 'COMPLETE', 'WORKER_INCOMPLETE')
                active.remove(item)
            updates = 0
            for arm, seed in tasks:
                status = run/('monitor_'+arm+'_'+str(seed))/'status.json'
                if status.exists(): updates += c.read(status).get('optimizer_updates', 0)
            progress.optimizer_updates = updates
            progress.tick(updates, design['training']['new_total_updates'])
            if active: progress.closed.wait(2)
        receipts = [c.read(run/'endpoints'/(arm+'_'+str(seed))/'endpoint.json') for arm,seed in tasks]
        c.require(sum(r['updates'] for r in receipts) == design['training']['new_total_updates'], 'TOTAL_UPDATES')
        for seed in c.SEEDS:
            same = [r for r in receipts if r['seed'] == seed]
            c.require(all(r['order_hashes'] == same[0]['order_hashes'] and r['weight_sha256'] == same[0]['weight_sha256'] for r in same), 'ARM_BATCH_OR_WEIGHT_DRIFT')
        c.write(run/'T_COMPLETE.json', dict(status='COMPLETE', endpoints=receipts, total_updates=design['training']['new_total_updates']))
    finally:
        progress.kill_children()
        for item in all_jobs:
            try: item['process'].wait(timeout=15)
            except subprocess.TimeoutExpired: item['process'].kill(); item['process'].wait()
            item['log'].close()
        c.write(run/'worker_exit_codes.json', {x['name']:x['process'].returncode for x in all_jobs})


def run(root, explicit):
    design, runtime = authorize(root, explicit); root = Path(root).resolve(); run = root/'runs/query_tail'
    c.require(not run.exists(), 'NO_RETRY_EXISTING_RUN')
    progress = Progress(run, runtime['limits']); (run/'logs').mkdir(); (run/'endpoints').mkdir()
    def stop_signal(signum, frame): raise RuntimeError('SIGNAL_STOP:'+str(signum))
    signal.signal(signal.SIGTERM, stop_signal); signal.signal(signal.SIGINT, stop_signal)
    try:
        c.require(shutil.disk_usage(root).free >= runtime['minimum_free_gib']*1024**3, 'P_FREE_DISK')
        c.write(run/'authorization.json', dict(explicit_whole_chain=True, design_sha256=k.DESIGN_SHA, retries=0, job_id=os.environ.get('SLURM_JOB_ID'), package_seal=c.sha(root/'SHA256SUMS')))
        base = Path(runtime['base_run'])
        metadata, indices, arrays, norm = p.prepare(root, base, run, design, progress)
        del metadata, indices, arrays, norm; gc.collect()
        c.write(run/'launch_T.json', dict(P_sha256=c.sha(run/'P_COMPLETE.json'), new_heads=9, updates=869040))
        launch(root, run, design, runtime, progress)
        progress.stage = 'K_VERIFY_INPUTS'
        prepared(run)
        metadata, indices = p.load_metadata(base, design)
        arrays, norm = p.arrays(base, design, progress=progress)
        # Baseline scores/metadata remain byte-bound at K, not only at P.
        for rel, digest in c.read(root/'parent_pins.json').items(): c.pin(base/rel, digest)
        decision = e.evaluate(root, base, run, design, metadata, indices, arrays, norm, progress)
        progress.stage = 'COMPLETE'
        progress.stop('COMPLETE', completed=9, total=9, scientific_gate=decision['core_capability_pass'])
        c.seal(run); c.verify(run)
    except BaseException as exc:
        progress.record_failure(exc, 'chain'); progress.stop('STOPPED_NO_RETRY', error=repr(exc)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run', 'worker']); parser.add_argument('--root', required=True)
    parser.add_argument('--run'); parser.add_argument('--arm', choices=k.ARMS); parser.add_argument('--seed', type=int, choices=c.SEEDS)
    parser.add_argument('--authorize-chain', action='store_true'); args = parser.parse_args()
    if args.mode == 'run': run(args.root, args.authorize_chain)
    else:
        c.require(args.run and args.arm and args.seed, 'WORKER_ARGUMENTS')
        worker(args.root, args.run, args.arm, args.seed, args.authorize_chain)
