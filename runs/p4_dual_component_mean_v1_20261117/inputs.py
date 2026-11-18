"""Bind the development-bank assets, query order and the original per-query weights."""
from hashlib import sha256

import numpy as np

from common_round1 import load, read_rows, require, uid_sha
from evaluation import load_query
from reference_assets import bank as accepted_bank, verify
from reference_inputs import normalized_context
from runtime_support import Store
from vendor import constrained_onboarding_core_v3 as core


def store_for(project, contract):
    store = Store(project, ('reference', 'query', 'runtime', 'raw_or_index', 'evaluation'))
    store.specs.update(contract['additional_pins'])
    for pool, witness in contract['metadata_sha'].items():
        store.specs[pool + ':query_context_uids']['sha256'] = witness
    return store


def edge_features(store, rows, ids, q):
    path = store.get('EDGE:encoded_complete')
    index = load(path)
    positions = {uid: i for i, uid in enumerate(ids)}
    seen = np.zeros(len(ids), bool)
    z = np.empty((len(ids), 768), dtype=np.float32)
    for batch in index['batches']:
        chosen = [(j, positions[u]) for j, u in enumerate(batch['uids']) if u in positions]
        if not chosen:
            continue
        folder = path.parent / 'batches' / batch['batch_id']
        manifest = load(verify(folder/'MANIFEST.json', dict(sha256=batch['manifest_sha256'])))
        require(manifest['uids'] == batch['uids'] and manifest['status'] == 'COMMITTED' and
                manifest['binding_sha256'] == index['binding_sha256'], 'EDGE_BATCH_BINDING')
        files = {k: verify(folder/k, pin) for k, pin in manifest['files'].items()}
        metadata = load(files['rows.json'])
        require([r['uid'] for r in metadata] == load(files['uids.json']) == batch['uids'], 'EDGE_BATCH_UIDS')
        src, dst = np.asarray(chosen).T
        require(not seen[dst].any() and len(set(dst)) == len(dst), 'EDGE_DUPLICATE_ENCODED_QUERY')
        require(all(all(metadata[j][k] == rows[i][k] for k in
                        ('uid', 'component_id', 'frame', 'capture_id', 'protocol', 'label', 'source_sha256'))
                    for j, i in chosen), 'EDGE_ENCODED_METADATA')
        own_q = np.load(files['q14.npy'], allow_pickle=False)
        require(np.array_equal(own_q[src], q[dst]), 'EDGE_ENCODED_Q14')
        z[dst] = np.load(files['E3.npy'], allow_pickle=False)[src]
        seen[dst] = True
    require(seen.all(), 'EDGE_ENCODED_QUERY_COVERAGE')
    with np.load(store.get('EDGE:query_physical'), allow_pickle=False) as a:
        require(a['uid'].tolist() == ids, 'EDGE_PHYSICAL_UID_ORDER')
        x = a['context']
    return z, x


def load_pool(store, pool, cfg, contract, norms, progress):
    refs, rz, rq, rc = accepted_bank(store, cfg, pool, progress)
    rows, ids, raw, p4, q, active, views, expansion, population = load_query(store, cfg, pool, refs)
    require(uid_sha(ids) == contract['query_uid_sha256'][pool], 'ACCEPTED_QUERY_ORDER:' + pool)
    with np.load(store.get(pool + ':query_array'), allow_pickle=False) as a:
        saved = a['support3']
        fields = {'query': a.files}
    with np.load(store.get(pool + ':accepted_geometry'), allow_pickle=False) as a:
        require(a['uid'].tolist() == ids and np.array_equal(saved, a['support3'])
                and np.array_equal(raw, a['RAW']), 'ACCEPTED_GEOMETRY_UID_SUPPORT_RAW:' + pool)
        fields['geometry'] = a.files
    require(saved.shape == (len(ids),) and saved.dtype == np.float64 and
            ((0 <= saved) & (saved <= 1)).all() and np.all(saved[~active] == 0), 'SUPPORT3_SCHEMA')
    if pool == 'EDGE':
        z, x = edge_features(store, rows, ids, q)
    else:
        with np.load(store.get(pool + ':query_context_uids'), allow_pickle=False) as a:
            tags = a['uid']
            require(tags.dtype in (np.dtype('S64'), np.dtype('U64')) and
                    np.array_equal(tags.astype('U64'), ids), 'QUERY_CONTEXT_UID_DECODE_AND_ORDER')
        z = np.load(store.get(pool + ':query_e3'), mmap_mode='r', allow_pickle=False)[:, :768]
        own_q = np.load(store.get(pool + ':query_q'), mmap_mode='r', allow_pickle=False)
        require(np.array_equal(q, own_q), 'QUERY_Q14_CACHE')
        x = np.load(store.get(pool + ':query_context'), mmap_mode='r', allow_pickle=False)
    require(z.shape == (len(ids), 768) and x.shape == (len(ids), 8), 'QUERY_FEATURE_SHAPES')
    ref_ids = [r['uid'] for r in refs]
    bank = core.ReferenceBank(refs, rz, rq, norms[0], feature_uids=ref_ids,
                              q_uids=ref_ids, allow_prebank_history=True)
    return dict(rows=rows, ids=ids, z=z, q=q, x=normalized_context(x, norms[1]), bank=bank,
                rc=normalized_context(rc, norms[1]), raw=raw, p4=p4,
                saved=saved, active=active, views=views, expansion=expansion, population=population,
                cache_fields=fields), (refs, rz, rq, rc)


def raw_slice(store, frozen, norms, pool_data, out, tshark, progress):
    """Rebuild one complete original encoder batch from its three small real captures."""
    import torch
    import legacy_reference_sample_prepare_v1 as legacy
    import continuous_input_v3 as inp
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from hnr.encoding import new_encoder
    from reference_features import encoder_config
    from reference_frontend import short_capture
    from runtime_support import HERE as frozen_package
    from vendor import physical

    refs, rz, rq, rc = frozen
    indices = {r['uid']: i for i, r in enumerate(refs)}
    proof = read_rows(frozen_package/'tensor/HEIM.jsonl.gz')
    records = [r for r in proof if r['shape'] == [6, 13, 1]]
    ids = [r['uid'] for r in records]
    require(len(ids) == 3 and ids == sorted(ids), 'ORIGINAL_THREE_ROW_E3_BATCH')
    wanted = {refs[indices[u]]['capture_id'] for u in ids}
    folder = out/'artifacts'/'frontend_slice'
    folder.mkdir(parents=True, exist_ok=False)
    cfg = load(frozen_package/'REFERENCE_SOURCES.json')
    entries = {}
    nframes = 0
    raw_pins = {}
    class FilePin:
        @staticmethod
        def pin(path, digest):
            return verify(path, dict(sha256=digest))
    for spec in cfg['short']:
        if spec['capture_id'] not in wanted:
            continue
        path = store.get(spec['asset'])
        require(store.checked[spec['asset']]['sha256'] == spec['sha256'], 'RAW_CAPTURE_SHA')
        decoded, _ = short_capture(dict(spec, raw=dict(path=str(path), sha256=spec['sha256'])), folder,
                                   legacy.old.legacy_runtime(), tshark, cfg['cic_known_macs'])
        picks = [e for e in decoded if e['uid'] in ids]
        physical_x, _ = physical.replay([e['row'] for e in picks], path, spec['sha256'],
                                       FilePin, progress, oracle=True)
        for e, x in zip(picks, physical_x['features']):
            i = indices[e['uid']]
            require(e['row']['component_id'] == refs[i]['component_id'] and
                    np.array_equal(x, rc[i]) and np.array_equal(np.asarray(e['q14'], np.float32), rq[i]),
                    'REDECODED_REFERENCE_IDENTITY_Q14_CONTEXT')
            entries[e['uid']] = e
        nframes += spec['expected_packets']
        raw_pins[spec['capture_id']] = spec['sha256']
    require(set(entries) == set(ids), 'FRONTEND_SLICE_COVERAGE')
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    encoder, identity = new_encoder(encoder_config(store))
    embed, _, model, tokenizer, collator = encoder
    examples = []
    for uid in ids:
        body = entries[uid]['body']
        example = tokenize(tokenizer, body['flow'])
        inp.verify_tokenized(body['flow'], body['provenance'], example)
        examples.append(example)
    batch = collator(examples)
    verify_batch(examples, batch)
    require([tensor_hash(batch, i) for i in range(len(ids))] == [r['tensor_sha256'] for r in records],
            'FRONTEND_PRODUCTION_TENSOR_SHA')
    e3 = embed.core.e3_forward_batches(model, [batch], 'cpu')
    ix = [indices[u] for u in ids]
    require(e3.dtype == np.float32 and e3.shape == (len(ix), 768) and np.isfinite(e3).all(),
            'FRONTEND_NEW_E3_SHAPE')
    cached_hash = [sha256(v.tobytes()).hexdigest() for v in rz[ix]]
    require(cached_hash == [r['feature_sha256'] for r in records], 'FROZEN_E3_WITNESS_SHA')
    # Use the actual new forward in the preflight bank. Worker compares this path to
    # the archived decisions and to the full frozen-bank replay at scientific tolerance.
    pool_data['bank'].z[ix] = core._unit(e3, norms[0])
    return dict(captures=raw_pins, decoded_frames=nframes, uids=ids, encoder=identity,
                tensor_sha256=[r['tensor_sha256'] for r in records], cached_e3_sha256=cached_hash,
                fresh_e3_sha256=[sha256(v.tobytes()).hexdigest() for v in e3],
                max_e3_difference=float(np.max(np.abs(e3 - rz[ix]))),
                actual_forwards=len(ix), actual_vectors_used_in_preflight_bank=True)
