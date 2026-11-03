"""Isolated source-FIT hot-batch timing; no experimental endpoint or selection."""
import argparse
import math
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    package = Path(args.package).resolve(); sys.path.insert(0, str(package))
    import package_io as io
    import modern_adapter as adapter
    config = io.package(); context = adapter.boot(config)
    import numpy as np
    import torch
    import resource
    out = Path(args.output).resolve()
    forbidden = [Path(config['source_config'][k]).resolve() for k in ('cache', 'head_run', 'query_root', 'lineage_root')]
    forbidden += [package, Path(config['onboarding_package']).resolve(), Path(config['run']).resolve()]
    io.require(not out.exists() and all(not out.is_relative_to(p) and not p.is_relative_to(out) for p in forbidden), 'BENCHMARK_OUTPUT_SCOPE')
    oldrun, cache, marker, binding = adapter.source_state(config, context)
    compact = io.read(oldrun / 'compact_metadata_receipt.json')
    rows = context['modules']['training_metadata_v1'].Rows(oldrun / 'training_metadata',
        expected_source_sha256=compact['source_sha256'],
        expected_uid_sha256=context['design']['data']['uid_sha256']['LEARN'])
    k = context['modules']['query_tail_core_v2']; models = context['models']
    try:
        with np.load(oldrun / 'prepared/FIT.npz', allow_pickle=False) as saved:
            fit = saved['indices'].copy()
        with np.load(oldrun / 'prepared/normalizer.npz', allow_pickle=False) as saved:
            norm = saved['mean'].copy(), saved['scale'].copy()
        io.require(len(fit) == 617908 and len(set(fit[:256])) == 256, 'FULL_FIT_AND_BATCH')
        values = np.load(io.pin(cache / 'features/LEARN.npy', binding['feature_files']['LEARN.npy']), mmap_mode='r', allow_pickle=False)
        q = np.load(oldrun / 'prepared/LEARN_q.npy', mmap_mode='r', allow_pickle=False)
        ix = fit[:256]
        full_weights = k.weights(context['train'].IndexRows(rows, fit))
        batch_weights = full_weights[:256]
        labels = torch.from_numpy(np.asarray([rows[int(i)]['label'] for i in ix], dtype=np.float32))
        model = models.classifier('TabM', 27, context['contract'])
        model.train()
        kwargs = dict(context['contract']['training']['optimizer_tabm']); kwargs['betas'] = tuple(kwargs['betas'])
        optimizer = torch.optim.AdamW(model.parameters(), **kwargs)
        times = []
        for step in range(10):
            started = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            predicted = model(k.normalized(values, q, ix, norm, 782))
            loss = models.tabm_weighted_bce(predicted, labels, batch_weights, len(fit))
            io.require(bool(torch.isfinite(loss)), 'BENCHMARK_NONFINITE_LOSS')
            loss.backward()
            io.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()), 'BENCHMARK_GRADIENT')
            optimizer.step()
            io.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), 'BENCHMARK_PARAMETER')
            elapsed = time.perf_counter() - started
            if step >= 2: times.append(elapsed)
            print('TABM_BATCH step=%d/10 seconds=%.6f measured=%s' % (step+1, elapsed, step>=2), flush=True)
        updates = 40 * math.ceil(len(fit) / 256)
        io.write(out, dict(status='PASS', engineering_only=True, scientific_endpoint_created=False,
            immutable_package_manifest_sha256=io.sha(package / 'code_manifest.json'),
            benchmark_source_sha256=io.sha(Path(__file__)), seed=27, threads=4,
            source_fit_rows=len(fit), batch_size=256, members=32, blocks=3, width=512,
            warmup_steps=2, measured_steps=8, seconds_per_step=times,
            mean_seconds=float(np.mean(times)), min_seconds=float(np.min(times)), max_seconds=float(np.max(times)),
            timing_boundary='batch normalization, forward, weighted loss, finite checks, backward, AdamW and finite parameters',
            repeated_batch='first256 sourceFIT positions, fixed order, hot cache; optimistic I/O cost',
            arithmetic_only_three_TabM_training_hours=dict(
                mean=3*updates*float(np.mean(times))/3600,
                observed_batch_min=3*updates*float(np.min(times))/3600,
                observed_batch_max=3*updates*float(np.max(times))/3600),
            not_total_job_ETA=True, excludes='cold/random FIT reads, epoch/checkpoint writing, other heads, scoring, replay and paired onboarding',
            process_lifetime_max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            rss_scope='Linux child-process lifetime peak including source validation/metadata; not full training or cgroup peak',
            runtime=adapter.runtime()))
    finally:
        rows.close()


if __name__ == '__main__': main()
