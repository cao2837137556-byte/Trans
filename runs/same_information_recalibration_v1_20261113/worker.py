"""Run reference-only calibration, then evaluate the accepted frozen queries."""
import argparse
import gc
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np

from calibration import fit
from common_round1 import (HERE, ROOT, PYTHON, NUMPY_RUNTIME, Inputs, Progress, artifact,
                           config_at, dump, load, require, sha, table, temp_path,
                           uid_sha, verify_package, verify_runtime_paths)
from evaluation import evaluate
from reference_assets import bank, forward, model_setup, uids

POOLS = ('CIC_DEV','UNSW_DEV','EDGE')


def runtime(project, out):
    require(sys.platform.startswith('linux') and os.environ.get('SLURM_JOB_ID','').isdigit(),
            'ACTUAL_SLURM_COMPUTE_CONTEXT_REQUIRED')
    require(sys.version_info[:2] == (3,11) and np.__version__ == '2.0.1' and not sys.flags.optimize,
            'FROZEN_LINUX_PYTHON_NUMPY')
    require(Path(sys.executable).resolve() == PYTHON.resolve() and
            Path(np.__file__).resolve().is_relative_to((project / NUMPY_RUNTIME).resolve()),
            'FROZEN_RUNTIME_MODULE_IDENTITY')
    dump(out/'RUNTIME_first.json',dict(status='PASS', python=sys.version, executable=sys.executable,
         numpy_version=np.__version__, numpy_path=np.__file__, node=os.environ['SLURMD_NODENAME'],
         slurm_job_id=os.environ['SLURM_JOB_ID'], runtime_source_hashes=verify_runtime_paths(project)))


def reference_stage(project, pins, config, out, progress):
    import torch
    store = Inputs(project,pins,('reference',),progress=progress)
    model = progress.stage('LOAD_FROZEN_MLP',lambda:model_setup(store,config))
    refs, fits, probes = {}, {}, {}
    for pool in POOLS:
        rows,z,q,x = progress.stage('LOAD_REFERENCE_' + pool,
                                     lambda:bank(store,config,pool,progress))
        n = len(rows)
        ix = np.unique(np.linspace(0,n-1,min(1024,n),dtype=int))
        start = time.monotonic()
        small = progress.stage('REAL_REFERENCE_PREFLIGHT_' + pool, lambda:
                    forward(model,z,q,x,ix,progress,'PREFLIGHT_FORWARD_' + pool))
        sample_fit = fit([rows[i] for i in ix],small,q[ix],config['method']['cuts'])
        elapsed = time.monotonic()-start
        estimate = elapsed * n / len(ix)
        require(estimate * 3 + 300 < config['wall_seconds'] * .7, 'REFERENCE_FORWARD_RESOURCE_GATE')
        probes[pool] = dict(rows=len(ix),seconds=elapsed,projected_seconds=estimate,
                           reference_uid_sha256=uid_sha([rows[i]['uid'] for i in ix]),
                           finite_scores=True, target_reference_fit=True,
                           threshold_check=sample_fit)
        dump(out/'REAL_PREFLIGHT.json',dict(status='REFERENCE_PROBE',pools=probes))
        scores = progress.stage('FULL_REFERENCE_FORWARD_' + pool,lambda:
                    forward(model,z,q,x,np.arange(n),progress,'REFERENCE_FORWARD_' + pool))
        err = float(np.max(np.abs(scores[ix]-small)))
        # The small and full passes have different physical batch boundaries.
        require(err <= 2e-4, 'REFERENCE_BATCH_NUMERIC_PARITY:' + pool)
        probes[pool]['batch_max_abs_error'] = err
        fitted = progress.stage('FIT_THRESHOLDS_' + pool,lambda:fit(rows,scores,q,config['method']['cuts']))
        fits[pool] = fitted
        path = out / (pool + '_REFERENCE_RAW.npz')
        tmp = temp_path(path)
        with tmp.open('wb') as f:
            np.savez(f,uid=np.asarray(uids(rows)),raw=scores)
        tmp.replace(path)
        with np.load(path,allow_pickle=False) as saved:
            require(saved['uid'].tolist() == uids(rows) and np.array_equal(saved['raw'],scores),
                    'REFERENCE_SCORE_READBACK')
        fitted['reference_scores'] = artifact(path,n)
        fitted['reference_uid_sha256'] = config['reference'][pool]['full_bank']['uid_sha256']
        refs[pool] = rows
        del z,q,x,scores,small
        gc.collect()
    require(all(v['role']=='reference' for v in store.resolved.values()), 'QUERY_ASSET_USED_DURING_FIT')
    thresholds = out/'THRESHOLD_SEAL.json'
    value = dict(status='PASS', pools=fits, config_sha256=sha(HERE/'CONFIG.json'),
                 package_manifest_sha256=sha(HERE/'PACKAGE_MANIFEST.json'),
                 source_cuts=config['method']['cuts'], weights=config['calibration'],
                 score='frozen FUSION790 CPU; three seed logits and ordered float64 mean',
                 torch_version=torch.__version__, inputs=store.resolved, evaluation_used=False)
    dump(thresholds,value)
    require(load(thresholds)==value, 'THRESHOLD_SEAL_READBACK')
    return refs, probes, value


def execute(project, out, progress):
    config = config_at()
    pins = load(HERE/'INPUT_PINS.json')
    require(config['calibration']==dict(budget=.01,groups=['device','capture_id','component_id'],
              with_guard='conditional_1pct'), 'APPROVED_CALIBRATION_RULE')
    refs, probes, value = reference_stage(project,pins,config,out,progress)
    threshold_path = out/'THRESHOLD_SEAL.json'
    threshold_sha = sha(threshold_path)
    sealed = load(threshold_path)
    require(sealed == value and sealed['status']=='PASS', 'SEALED_FIT_IDENTITY')
    eval_store = Inputs(project,pins,('query',),progress=progress)
    expected = load(HERE/'EXPECTED_BASELINE.json')
    metrics,pairs,summary = [],[],{}
    for pool in POOLS:
        m,p,s = progress.stage('EVALUATE_' + pool,lambda:
            evaluate(eval_store,config,pool,refs.pop(pool),sealed['pools'][pool],expected,out,progress))
        metrics.extend(m)
        pairs.extend(p)
        summary[pool] = s
    require(sha(threshold_path)==threshold_sha,'THRESHOLDS_UNCHANGED_AFTER_EVALUATION')
    table(out,'METRICS',metrics)
    table(out,'PAIRED_CHANGES',pairs)
    dump(out/'QUERY_EVALUATION.json',dict(status='PASS',pools=summary,inputs=eval_store.resolved,
         protected_and_prebank_invariants='PASS',baseline_comparison='RAW and P4_MAIN metric parity',
         threshold_sha256=threshold_sha,outputs={n:artifact(out/n) for n in
         ('METRICS.json','METRICS.csv','PAIRED_CHANGES.json','PAIRED_CHANGES.csv')}))
    dump(out/'REAL_PREFLIGHT.json',dict(status='PASS',pools=probes,
         query_rows={p:v['real_slice_rows'] for p,v in summary.items()}, no_query_forward=True))
    dump(out/'FIRST_COMPLETE.json',dict(status='PASS',pools=list(POOLS), reference_rows=79069,
         query_rows=sum(v['rows'] for v in summary.values()), slurm_job_id=os.environ['SLURM_JOB_ID'],
         package_manifest_sha256=sha(HERE/'PACKAGE_MANIFEST.json'), threshold_sha256=threshold_sha))
    progress('EVALUATION_COMPLETE',1,1,force=True)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('phase',choices=('first',))
    a.add_argument('--project',type=Path,default=ROOT)
    a.add_argument('--out',type=Path,required=True)
    args=a.parse_args()
    out=args.out.resolve()
    progress=Progress(out,args.phase,rss_limit_mib=int(os.environ.get('ROUND1_MEMORY_MIB','8192'))-384)
    try:
        verify_package(HERE)
        runtime(args.project,out)
        execute(args.project,out,progress)
        progress.finish()
    except Exception as e:
        dump(out/'STOP_first.json',dict(status='FAIL',stage=getattr(progress,'current','STARTUP'),
             error=str(e),traceback=traceback.format_exc()))
        raise


if __name__=='__main__':
    main()
