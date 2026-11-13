"""Check local frozen query identities and weight schema without loading absent HPC scores."""
from collections import Counter
from pathlib import Path

import numpy as np

from common_round1 import HERE, Inputs, config_at, dump, load, read_rows, require, uid_sha
from evaluation import compare_tables, evaluation_rows
from vendor import analysis_core as prod


def main():
    root = HERE.parents[1]
    cfg = config_at()
    pins = load(HERE / 'INPUT_PINS.json')
    local = Inputs(root, pins, ('query',), local=True)
    report = local.verify()
    for name in ('prepared_rows', 'query_e3', 'query_q', 'query_view_witness'):
        require(name in report['checked'], 'LOCAL_QUERY_ASSET:' + name)
    rows = read_rows(local.get('prepared_rows'))
    ids = [r['uid'] for r in rows]
    require(len(ids) == len(set(ids)) == 148316 and uid_sha(ids) == cfg['query_identity']['uid_sha256'],
            'LOCAL_QUERY_IDENTITY')
    path = 'runs/dense_reference_matrix_v1_20261027/preparation/frozen_final/UNSW_DEV_query_uids.json'
    require(load(root / path) == ids, 'LOCAL_E3_Q14_UID_BINDING')
    z = np.load(local.get('query_e3'), mmap_mode='r', allow_pickle=False)
    q = np.load(local.get('query_q'), mmap_mode='r', allow_pickle=False)
    require(z.shape == (len(ids), 794) and q.shape == (len(ids), 14) and
            z.dtype == q.dtype == np.float32, 'LOCAL_ENCODED_SCHEMA')
    for start in range(0, len(rows), 4096):
        zz, qq = z[start:start + 4096], q[start:start + 4096]
        require(np.isfinite(zz).all() and np.isfinite(qq).all() and ((qq >= 0) & (qq <= 1)).all(),
                'LOCAL_FEATURE_FINITE_AND_RANGE')
    windows = {(w['partition'], w['device']): w for w in cfg['windows']}
    primary = []
    for i, r in enumerate(rows):
        w = windows[(r['partition'], r['device'])]
        if r['timestamp'] > w['reference_end'] and (r['capture_id'] != w['capture_id'] or r['frame'] > w['frame_end']):
            primary.append(i)
    with np.load(local.get('query_view_witness'), allow_pickle=False) as a:
        require(a['uid'].tolist() == ids and a['primary_indices'].tolist() == primary,
                'LOCAL_FROZEN_VIEW_IDENTITY')
        w = np.zeros(len(rows), dtype=np.float64)
        w[primary] = a['primary_weights']
        views = {'full': (np.arange(len(rows)), a['full_weights']),
                 'post_window_primary': (np.asarray(primary), w)}
    labels = np.asarray([r['label'] for r in rows])
    require(prod.guard(q)[labels == 1].all(), 'LOCAL_UNSW_ATTACK_GUARD')
    expected = load(HERE / 'evidence/BASELINE_EXPECTED.json')['metrics']
    # The metrics schema can be verified on real weights without fabricating scores.
    # A zero mask checks denominators only and is never written as a result.
    d = dict(rows=rows, q=q, views=views)
    pred = np.zeros((len(rows), 4), dtype=bool)
    actual = evaluation_rows(d, pred)
    expected_denom = [{k: r[k] for k in ('pool', 'view', 'head', 'group', 'guard_stratum',
                    'rows', 'weighted_denominator')} for r in expected if r['config'] == 'RAW']
    n = compare_tables(actual, expected_denom, extra_groups=True)
    result = dict(status='PASS', scope='local cache identity, window index, weighting denominators',
                  actual_query_rows=len(rows), primary_rows=len(primary),
                  full_label_counts=Counter(str(x) for x in labels),
                  primary_label_counts=Counter(str(x) for x in labels[primary]),
                  query_uid_sha256=uid_sha(ids), actual_p4_metrics_recomputed=False,
                  baseline_weight_rows_checked=n, attacks_all_syn_guarded=True,
                  local_pins=report['checked'], hpc_only_unverified=sorted(report['failures']))
    dump(HERE / 'LOCAL_QUERY_AUDIT.json', result)
    print('LOCAL_REAL_QUERY_INPUTS', len(rows), 'PRIMARY', len(primary), 'WEIGHT_ROWS', n)


if __name__ == '__main__':
    main()
