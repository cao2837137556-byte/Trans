"""Local explicit CLI; no scheduler or automatic experiment retries."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time

for thread_key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[thread_key] = '4'

import numpy as np
import torch

import common as c
import pipeline


def resource_plan(source, output):
    """Estimate changed-stage working sets; a ceiling is not an ETA."""
    fit = len(source['fit_indices']); n = len(source['rows'])
    refs = source['references']['rows']
    keys = {(r['partition'], r['device'], r['protocol']) for r in refs}
    groups = [sum(source['rows'][int(i)]['device'] in g for i in source['fit_indices']) for g in c.GROUPS]
    aux_updates = [40*((count+255)//256) for count in groups]
    # Conservative full touched source mapping + metadata + compact geometry + torch buffers.
    mmap_bytes = n*794*4 + n*14*4
    geometry_bytes = fit*len(keys)*(2*(2*2+2*2*8)+1+4+1)
    metadata_estimate = n*2200
    task_estimate = fit*2*1350
    mining_reserve = fit*2*160
    runtime_reserve = 1024**3
    peak = mmap_bytes+geometry_bytes+metadata_estimate+task_estimate+mining_reserve+runtime_reserve
    output_estimate = geometry_bytes+600*1024**2
    existing = Path(output).resolve()
    while not existing.exists():
        existing = existing.parent
    free = shutil.disk_usage(existing).free
    status = 'ESTIMATE_READY_SYNTHETIC_TIMING_PENDING'
    if peak > 8*1024**3 or output_estimate > 2*1024**3 or free < 2*output_estimate:
        status = 'RESOURCE_NOT_READY'
    return c.record('learned-onboarding-resource-plan-v1', status=status,
        runtime=c.environment(),
        estimates_only=True, synthetic_timing_complete=False,
        fit_rows=fit, source_banks=len(keys), auxiliary_group_rows=groups,
        auxiliary_updates=aux_updates, module_updates=12000,
        touched_mmap_bytes=mmap_bytes, compact_geometry_bytes=geometry_bytes,
        estimated_metadata_bytes=metadata_estimate, runtime_reserve_bytes=runtime_reserve,
        estimated_task_metadata_bytes=task_estimate, mining_reserve_bytes=mining_reserve,
        task_bank_storage='lazy BankCandidates; geometry mmap; streaming JSONL export',
        estimated_peak_rss=peak, estimated_output_bytes=output_estimate,
        disk_free_bytes=free, rss_guard_bytes=8*1024**3,
        environment_memory_ceiling_bytes=16*1024**3, output_limit_bytes=2*1024**3,
        training_stop_ceiling_hours=10, cpu_threads=4, heavy_workers=1,
        measured_training_seconds=None,
        io_estimates=dict(source_array_bytes=mmap_bytes, source_scoring_rows=n,
            source_geometry_candidate_pairs=fit*len(keys)*2,
            source_geometry_equivalence_multiplier=2,
            target_rows_not_loaded=True, target_scoring_seconds=None,
            note='IO/geometry/evaluation wall-time not measured; synthetic timing is training-compute only'))


def synthetic_timing(plan):
    """Registered 50 warmup + 200 synthetic update timing, no real-data fit."""
    import learning
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    rng = np.random.Generator(np.random.PCG64(27))
    measured = {}
    for name, width in (('auxiliary', 782), ('module', 50)):
        model = learning._old_classifier() if width == 782 else learning.correction_model()
        opt = torch.optim.AdamW(model.parameters(), lr=.0003 if width == 782 else .001,
                               weight_decay=.0001, foreach=False)
        x = torch.from_numpy(rng.normal(size=(256, width)).astype(np.float32))
        y = torch.from_numpy(rng.integers(0, 2, size=256).astype(np.float32))
        start = None
        for step in range(250):
            if step == 50:
                start = time.perf_counter()
            opt.zero_grad(set_to_none=True)
            out = model(x).flatten()
            loss = (torch.nn.functional.binary_cross_entropy_with_logits(out, y) if width == 782
                    else (out-y).square().mean())
            loss.backward(); opt.step()
        measured[name] = (time.perf_counter()-start)/200
    aux_times = [measured['auxiliary']*updates for updates in plan['auxiliary_updates']]
    # Module timing multiplier covers the maximum six source donor banks and per-query losses.
    module_time = measured['module']*12000*6
    plan = dict(plan, synthetic_timing_complete=True, runtime=c.environment(),
                synthetic_step_seconds=measured, auxiliary_training_seconds_estimate=aux_times,
                module_training_seconds_estimate=module_time,
                timing_scope='synthetic compute only; source IO, geometry and evaluation separately estimated')
    if plan['status'] != 'RESOURCE_NOT_READY':
        plan['status'] = ('READY' if max(aux_times) <= 4*3600 and module_time <= 2*3600 and
                          sum(aux_times)+module_time <= 10*3600 else 'RESOURCE_NOT_READY')
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'validate-source', 'preflight', 'fit', 'calibrate', 'evaluate'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-assets', type=Path, required=True)
    parser.add_argument('--fit-dir', type=Path)
    parser.add_argument('--calibration-dir', type=Path)
    parser.add_argument('--target-manifest', type=Path)
    parser.add_argument('--target-manifest-sha256')
    parser.add_argument('--preflight-receipt', type=Path)
    parser.add_argument('--execution-slot', choices=('exclusive-local', 'exclusive-existing-remote'))
    args = parser.parse_args(argv)
    stage = args.stage
    may_write_exception = False
    try:
        c.check_spec()
        output = args.output.resolve()
        here = Path(__file__).resolve().parents[1]
        c.require(any(root in output.parents for root in (here/'results', here/'validation')),
                  'OUTPUT_OUTSIDE_STAGE_ROOTS')
        inputs = [p.resolve() for p in (args.source_assets, args.config, args.fit_dir,
                  args.calibration_dir, args.preflight_receipt, args.target_manifest) if p is not None]
        c.require(all(output != p and output not in p.parents and p not in output.parents
                      for p in inputs), 'OUTPUT_INPUT_PATH_OVERLAP')
        c.require(not output.exists(), 'OUTPUT_ALREADY_EXISTS:'+str(output))
        may_write_exception = True
        config = c.read(args.config)
        c.require(config['schema'] == 'learned-onboarding-local-config-v1' and
                  config['spec_sha256'] == c.SPEC_SHA256, 'CONFIG_SPEC')
        # This explicit assertion records the caller's execution context; it never probes or changes remote jobs.
        if stage in ('fit', 'calibrate', 'evaluate', 'preflight'):
            c.require(args.execution_slot is not None, 'EXCLUSIVE_EXECUTION_SLOT_REQUIRED')
        from source_inputs import prepare_source
        source = prepare_source(config=config.get('source', {}), output_dir=args.source_assets,
                                validate_only=stage in ('prepare', 'validate-source', 'preflight'))
        if stage == 'prepare':
            out = c.fresh(args.output)
            c.write(out/'source_prepare.json', c.record('learned-onboarding-source-prepare-v1',
                status='SOURCE_IDENTITIES_VERIFIED', input_binding=source['binding'],
                source_rows=len(source['rows']), reference_rows=len(source['references']['rows']),
                training_started=False, target_queries_read=0))
            c.seal(out)
            return 0
        if stage == 'validate-source':
            out = c.fresh(args.output)
            isolation = pipeline.source_isolation(source['rows'], source['fit_indices'],
                source['cal_indices'], source['references'])
            fi = source['fit_indices']
            coverage = pipeline.source_coverage([source['rows'][int(i)] for i in fi],
                pipeline.IndexedRows(source['e3'], fi), pipeline.IndexedRows(source['q14'], fi),
                source['references'], source['normalizer'])
            c.write(out/'isolation.json', isolation); c.write(out/'source_task_receipt.json', coverage)
            c.write(out/'resource_plan.json', resource_plan(source, out))
            c.seal(out)
            return 0
        if stage == 'preflight':
            out = c.fresh(args.output)
            plan = synthetic_timing(resource_plan(source, out))
            plan['input_binding_digest'] = c.digest(source['binding'])
            plan['config_sha256'] = c.sha(args.config)
            plan['execution_slot'] = args.execution_slot
            c.write(out/'resource_plan.json', plan); c.seal(out)
            c.require(plan['status'] == 'READY', 'RESOURCE_NOT_READY')
            return 0
        c.require(args.preflight_receipt is not None, 'PREFLIGHT_RECEIPT_REQUIRED')
        plan = c.read(args.preflight_receipt)
        c.require(plan['status'] == 'READY' and plan['spec_sha256'] == c.SPEC_SHA256 and
                  plan['input_binding_digest'] == c.digest(source['binding']) and
                  plan['config_sha256'] == c.sha(args.config) and
                  plan['execution_slot'] == args.execution_slot, 'PREFLIGHT_IDENTITY')
        c.verify_seal(args.preflight_receipt.parent)
        guard = c.Guard(args.output, budget_folder=here/'results')
        if stage == 'fit':
            pipeline.fit_source(source, args.output, guard=guard)
        elif stage == 'calibrate':
            c.require(args.fit_dir is not None, 'FIT_DIR_REQUIRED')
            pipeline.calibrate_source(source, args.fit_dir, args.output, guard=guard)
        else:
            c.require(args.fit_dir is not None and args.calibration_dir is not None and
                      args.target_manifest is not None and args.target_manifest_sha256,
                      'EVALUATION_INPUTS_REQUIRED')
            from bundle_io import load_targets
            loader = lambda: load_targets(args.target_manifest,
                expected_sha256=args.target_manifest_sha256,
                source_binding_digest=c.digest(source['binding']), cut=source['cut'],
                normalizer_sha256=source['binding']['normalizer_sha256'],
                source_binding=source['binding'])
            pipeline.evaluate_targets(source, args.fit_dir, args.calibration_dir, loader,
                                      args.output, guard=guard)
        return 0
    except Exception as error:
        # Existing output is never resumed; errors in input/identity/resource retain their stage evidence.
        if may_write_exception and not (args.output/'SEAL.json').exists():
            pipeline.write_exception(args.output, stage, error)
        print(type(error).__name__+': '+str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
