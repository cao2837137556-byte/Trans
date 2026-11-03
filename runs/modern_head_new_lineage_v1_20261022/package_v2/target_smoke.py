"""Bounded target-runtime source-FIT engineering test, never scientific results."""
import argparse
import copy
import time
from pathlib import Path
import package_io as io


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); config = io.package()
    import modern_adapter as adapter
    from modern_service import Progress, tree_rss
    import numpy as np
    context = adapter.boot(config)
    output = Path(args.output).resolve()
    protected = [Path(config['source_config'][k]).resolve() for k in ('cache', 'head_run', 'query_root', 'lineage_root')]
    protected += [io.ROOT, Path(config['onboarding_package']).resolve(), Path(config['run']).resolve()]
    io.require(not output.exists() and all(not output.is_relative_to(p) and not p.is_relative_to(output) for p in protected), 'SMOKE_OUTPUT_SCOPE')
    output.mkdir(parents=True)
    oldrun, cache, marker, binding = adapter.source_state(config, context)
    receipt = io.read(oldrun / 'compact_metadata_receipt.json')
    rows = context['modules']['training_metadata_v1'].Rows(oldrun / 'training_metadata',
        expected_source_sha256=receipt['source_sha256'],
        expected_uid_sha256=context['design']['data']['uid_sha256']['LEARN'])
    selected = {0: [], 1: []}
    with np.load(oldrun / 'prepared/FIT.npz', allow_pickle=False) as saved:
        fit = saved['indices'].copy()
    for i in fit:
        label = rows[int(i)]['label']
        if len(selected[label]) < 32: selected[label].append(int(i))
        if all(len(v) == 32 for v in selected.values()): break
    io.require(all(len(v) == 32 for v in selected.values()), 'SMOKE_SOURCE_CLASSES')
    ix = np.asarray(sorted(selected[0]+selected[1]), dtype=np.int64)
    values = np.load(context['c'].pin(cache / 'features/LEARN.npy', binding['feature_files']['LEARN.npy']), mmap_mode='r', allow_pickle=False)
    q = np.load(oldrun / 'prepared/LEARN_q.npy', mmap_mode='r', allow_pickle=False)
    with np.load(oldrun / 'prepared/normalizer.npz', allow_pickle=False) as saved:
        norm = saved['mean'].copy(), saved['scale'].copy()
    tiny = copy.deepcopy(context['contract']); tiny['synthetic_only'] = True
    tiny['training']['epochs'] = 1; tiny['training']['batch_size'] = 64
    tiny['training']['lightgbm']['num_boost_round'] = 3
    checks = {}
    try:
        for family in adapter.FAMILIES:
            started = time.monotonic(); progress = Progress(output / (family + '_progress.json'))
            model = context['train'].train(tiny, rows, values, q, norm, ix, family, 27,
                output / family, progress, synthetic=True)
            before = context['models'].scores(model, family, values, q, ix, norm)
            del model
            model = context['train'].load(output / family, family, 27, tiny)
            after = context['models'].scores(model, family, values, q, ix, norm)
            io.require(before.dtype == after.dtype and np.array_equal(before, after), 'SMOKE_REPLAY:' + family)
            checks[family] = dict(status='PASS', samples=len(ix), score_replay='BITWISE_IDENTICAL',
                seconds=time.monotonic()-started, endpoint_sha256=io.sha(output / family / 'endpoint.json'),
                current_tree_rss_bytes=tree_rss())
            del model
        io.write(output / 'SMOKE_COMPLETE.json', dict(status='PASS', engineering_only=True,
            scope='64 existing source FIT rows, balanced classes; 1 epoch / 3 tree rounds; no target data',
            production_recipe_changed=False, runtime=adapter.runtime(), checks=checks,
            source_query_complete_sha256=config['source_config']['head_complete_sha256']))
        print('TARGET_SMOKE_PASS', flush=True)
    finally:
        rows.close()


if __name__ == '__main__': main()
