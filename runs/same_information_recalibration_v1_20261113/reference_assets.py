"""Read the three accepted reference banks without opening evaluation queries."""
import gc
import sys
from pathlib import Path

import numpy as np

from common_round1 import require, load, read_rows, sha, uid_sha
from calibration import four


def verify(path, spec):
    require(path.is_file() and ('bytes' not in spec or path.stat().st_size == spec['bytes'])
            and sha(path) == spec['sha256'], 'ASSET_SHA:' + str(path))
    return path


def uids(rows):
    return [r['uid'] for r in rows]


def pack(rows_path, array_path):
    rows = read_rows(rows_path)
    with np.load(array_path, allow_pickle=False) as a:
        require(a['uid'].tolist() == uids(rows), 'REFERENCE_PACK_UID:' + str(array_path))
        return rows, a['e3'], a['q14']


def context(path, rows):
    with np.load(path, allow_pickle=False) as a:
        require(a['uid'].tolist() == uids(rows), 'CONTEXT_UID:' + str(path))
        c = a['features']
    require(c.shape == (len(rows), 8) and c.dtype.kind == 'f' and np.isfinite(c).all() and
            (c >= 0).all(), 'CONTEXT_SHAPE:' + str(path))
    return c


def edge_refs(store, config, progress, metadata_only):
    index_path = store.get('EDGE:encoded_complete')
    index = load(index_path)
    plan = read_rows(store.get('EDGE:reference_rows'))
    expected = {r['uid']: r for r in plan}
    require(len(plan) == len(expected) == config['reference']['EDGE']['commission_rows'], 'EDGE_REF_PLAN')
    specs = [(item, [i for i, uid in enumerate(item['uids']) if uid in expected])
             for item in index['batches']]
    specs = [(item, take) for item, take in specs if take]
    rows, zs, qs = [], [], []
    for i, (item, take) in enumerate(specs, 1):
        name = item['batch_id']
        require(Path(name).name == name, 'EDGE_BATCH_PATH')
        chosen = [item['uids'][j] for j in take]
        if metadata_only:
            rows.extend(expected[u] for u in chosen)
            continue
        folder = index_path.parent / 'batches' / name
        m = load(verify(folder / 'MANIFEST.json', dict(sha256=item['manifest_sha256'])))
        require(m['uids'] == item['uids'] and m['binding_sha256'] == index['binding_sha256']
                and m['batch_id'] == name and m['status'] == 'COMMITTED', 'EDGE_BATCH_IDENTITY')
        files = ['rows.json', 'E3.npy', 'q14.npy', 'uids.json']
        require(set(m['files']) == set(files), 'EDGE_BATCH_FIELDS')
        files = {f: verify(folder / f, m['files'][f]) for f in files}
        r = load(files['rows.json'])
        require(uids(r) == load(files['uids.json']) == item['uids'], 'EDGE_BATCH_ROWS')
        identity = ('uid', 'device', 'partition', 'capture_id', 'component_id', 'owner', 'frame',
                    'timestamp_ns', 'label', 'protocol', 'source_sha256', 'use', 'reference_end', 'bank_end_frame')
        require(all(all(r[j][k] == expected[u][k] for k in identity) for u,j in zip(chosen,take)),
                'EDGE_REFERENCE_METADATA_MISMATCH')
        rows.extend(r[j] for j in take)
        zs.append(np.load(files['E3.npy'], allow_pickle=False)[take])
        qs.append(np.load(files['q14.npy'], allow_pickle=False)[take])
        progress('LOAD_EDGE_REFERENCE_BATCHES', i, len(specs))
    require(set(uids(rows)) == set(expected), 'EDGE_REFERENCE_COVERAGE')
    return rows, None if metadata_only else np.concatenate(zs), None if metadata_only else np.concatenate(qs)


def bank(store, cfg, pool, progress, *, local_partial=False):
    prefix = pool + ':'
    if pool == 'EDGE':
        rows, z, q = edge_refs(store, cfg, progress, local_partial)
        if local_partial:
            x = None
        else:
            x = context(store.get(prefix + 'dense_context'), rows)
        require(all(r['timestamp_ns'] <= cfg['edge_cutoff'] and
                    r['frame'] <= cfg['edge_last_frame'] and
                    r['bank_end_frame'] == cfg['edge_last_frame'] for r in rows), 'EDGE_REFERENCE_WINDOW')
    else:
        rows, z, q = pack(store.get(prefix + 'dense_rows'), store.get(prefix + 'dense_e3'))
        dense = cfg['reference'][pool]
        require(len(rows) == dense['commission_rows'] and uid_sha(uids(rows)) == dense['commission_uid_sha256'],
                'DENSE_REFERENCE_IDENTITY:' + pool)
        if not local_partial:
            x0 = context(store.get(prefix + 'dense_context'), rows)
        past, zp, qp = [], [], []
        for spec in cfg['history_packs'][pool]:
            r, za, qa = pack(store.get(spec['rows']), store.get(spec['arrays']))
            ids = [i for i, v in enumerate(r) if not spec.get('device') or v['device'] == spec['device']]
            require('count' not in spec or len(ids) == spec['count'], 'HISTORY_COUNT')
            past.extend(r[i] for i in ids)
            zp.append(za[ids])
            qp.append(qa[ids])
        x = None if local_partial else np.concatenate((x0, context(store.get(prefix + 'history_context'), past)))
        require(all(r['timestamp'] <= r['reference_end'] for r in past), 'HISTORY_CUTOFF')
        if pool == 'UNSW_DEV':
            require(all(r['history_role'] == 'HIST_REF' and r['frame'] <= r['bank_end_frame'] for r in past),
                    'UNSW_HIST_REF')
        windows = {(r['partition'], r['device']): r for r in cfg['windows'][pool]}
        require(all((r['partition'], r['device']) in windows and
                    r['reference_end'] == windows[(r['partition'], r['device'])]['reference_end'] and
                    r['bank_end_frame'] == windows[(r['partition'], r['device'])]['frame_end']
                    for r in rows), 'FROZEN_DENSE_WINDOW')
        rows.extend(dict(r, historical_reference_end=r['reference_end'],
                         reference_end=windows[(r['partition'], r['device'])]['reference_end']) for r in past)
        z, q = np.concatenate([z, *zp]), np.concatenate([q, *qp])
    ident = cfg['reference'][pool]['full_bank']
    ids = uids(rows)
    require(len(ids) == len(set(ids)) == ident['rows'] and uid_sha(ids) == ident['uid_sha256'],
            'FROZEN_REFERENCE_IDENTITY:' + pool)
    require(all(r['label'] == 0 and r['use'] == 'REFERENCE' and all(r.get(k) for k in
                ('partition','device','capture_id','component_id')) and
                r['timestamp'] <= r['reference_end'] and
                ('bank_end_frame' not in r or r['frame'] <= r['bank_end_frame']) for r in rows),
            'REFERENCE_NORMAL_IDENTITY:' + pool)
    physical = [(r['source_sha256'], r['frame'], r['owner']) for r in rows]
    require(len(set(physical)) == len(ids), 'DUPLICATE_PHYSICAL_REFERENCE:' + pool)
    if z is not None:
        require(z.shape == (len(ids), 768) and z.dtype == np.float32 and np.isfinite(z).all() and
                q.shape == (len(ids),14) and q.dtype == np.float32 and np.isfinite(q).all() and
                ((0 <= q) & (q <= 1)).all(), 'REFERENCE_FEATURE_SCHEMA:' + pool)
    return rows, z, q, x


def model_setup(store, cfg):
    import torch
    require(torch.__version__.split('+')[0] == '2.5.1', 'FROZEN_TORCH_VERSION')
    module_paths = {m: store.get('model:' + m).resolve() for m in cfg['model_modules']}
    require(len({p.parent for p in module_paths.values()}) == 1, 'MODEL_MODULE_PATHS')
    sys.path.insert(0, str(module_paths['context_core'].parent))
    try:
        import context_core as core
    finally:
        sys.path.pop(0)
    require(all(Path(sys.modules[n].__file__).resolve() == p for n,p in module_paths.items()),
            'MODEL_IMPORT_SOURCE_PIN')
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    nets = []
    for seed in cfg['method']['heads'][:3]:
        net = core.classifier(int(seed), 790)
        with np.load(store.get('head_' + seed), allow_pickle=False) as a:
            net.load_state_dict({key: torch.from_numpy(a[key].copy()) for key in a.files})
        nets.append(net.eval().requires_grad_(False))
    def normalizer(name, width):
        with np.load(store.get(name), allow_pickle=False) as a:
            mean, scale = a['mean'], a['scale']
        require(mean.shape == scale.shape == (width,) and np.isfinite(mean).all() and
                np.isfinite(scale).all() and (scale > 0).all(), 'FROZEN_NORMALIZER:' + name)
        return mean, scale
    return core, nets, normalizer('e3_normalizer', 768), normalizer('context_normalizer', 8)


def forward(model, z, q, physical, indices, progress, stage):
    core, nets, norm, (mean, scale) = model
    ctx = ((np.log1p(physical) - mean) / scale).astype(np.float32)
    require(np.isfinite(ctx).all(), 'REFERENCE_CONTEXT_NORMALIZATION')
    class Tick:
        def __init__(self, col):
            self.col = col
        def tick(self, done, total):
            progress(stage, self.col * total + done, 3 * total)
    result = four(np.column_stack([core.scores(net, (z, ctx), q, indices, norm, 790, Tick(j))
                                   for j,net in enumerate(nets)]))
    del ctx
    gc.collect()
    return result
