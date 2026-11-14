"""Replay frozen query scores after the calibration artifact is sealed."""
from pathlib import Path
from collections import defaultdict

import numpy as np

import analysis_core as ac
from calibration import RAW, P4, WITH_GUARD, NO_GUARD, ARMS, predictions
from common_round1 import load, read_rows, require, sha, uid_sha, table, write_rows, artifact

LABELS = ('NORMAL', 'ATTACK')


def after_open(rows, cfg, pool):
    if pool == 'EDGE':
        active = np.array([r['timestamp_ns'] > cfg['edge_cutoff'] and
            (r['source_role'] != 'NORMAL' or r['frame'] > cfg['edge_last_frame']) for r in rows])
        require(active.all(), 'EDGE_WINDOW')
        return active
    windows = {(w['partition'],w['device']):w for w in cfg['windows'][pool]}
    active = []
    for r in rows:
        w = windows[(r['partition'],r['device'])]
        active.append(r['timestamp'] > w['reference_end'] and
                      (r['capture_id'] != w['capture_id'] or r['frame'] > w['frame_end']))
    return np.asarray(active, dtype=bool)


def load_query(store, cfg, pool, references):
    prefix = pool + ':query_'
    rows = read_rows(store.get(prefix + 'rows'))
    uids = [r['uid'] for r in rows]
    n, npost, overlap = cfg['query_counts'][pool]
    require(len(rows) == len(set(uids)) == n and all(r['use'] != 'REFERENCE' and r['label'] in (0,1)
                                                   for r in rows), 'QUERY_ROLES:' + pool)
    active = after_open(rows,cfg,pool)
    require(int(active.sum()) == npost, 'QUERY_OPEN_COUNT')
    # Prebank overlaps are old full-view RAW fallback observations only.
    rr = {r['uid']:r for r in references}
    matched = [(r,rr[r['uid']],a) for r,a in zip(rows,active) if r['uid'] in rr]
    require(len(matched) == overlap and all(not a and r['label'] == 0 and
                all(r[k] == v[k] for k in ('source_sha256','frame','owner','capture_id','component_id',
                                          'device','partition','protocol','timestamp'))
                for r,v,a in matched), 'QUERY_REFERENCE_TEMPORAL_OVERLAP')
    views = {}
    qconfig = cfg['query'][pool]
    with np.load(store.get(prefix + 'array'), allow_pickle=False) as a:
        require(a['uid'].tolist() == uids, 'QUERY_ARRAY_UIDS')
        q = a['q']
        for view in qconfig['views']:
            index, weight = a[view + '_ix'], a[view + '_weight']
            expected = np.arange(n) if view == 'full' else np.flatnonzero(active)
            require(index.dtype.kind in 'iu' and index.ndim == 1 and
                    len(np.unique(index)) == len(index) and np.array_equal(np.sort(index),expected) and
                    weight.shape == (n,) and np.isfinite(weight).all() and
                    (weight[index] > 0).all(), 'FROZEN_VIEW_WEIGHT:' + view)
            views[view] = index, weight
        expansion = a['expansion'] if 'expansion' in a.files else None
    pop = qconfig['population']
    require((expansion is None) == (pop is None) and
            (expansion is None or (expansion.shape == (n,) and np.isfinite(expansion).all() and
                                   (expansion > 0).all())), 'EDGE_HT_INPUT')
    require(q.shape == (n,14) and np.isfinite(q).all() and ((0 <= q)&(q <= 1)).all(), 'QUERY_Q14')
    with np.load(store.get(prefix + 'scores'), allow_pickle=False) as a:
        require(a['uid'].tolist() == uids, 'QUERY_SCORE_UIDS')
        raw,p4 = a[RAW],a[P4]
    for x in (raw,p4):
        require(x.shape == (n,4) and x.dtype == np.float64 and np.isfinite(x).all() and
                np.array_equal(x[:,3],np.stack([x[:,j] for j in range(3)]).mean(0,dtype=np.float64)),
                'FROZEN_SCORE_SCHEMA')
    require(np.array_equal(p4[~active | ac.guard(q)],raw[~active | ac.guard(q)]), 'FROZEN_P4_RAW_REGION')
    return rows, uids, raw, p4, q, active, views, expansion, pop


def baseline_parity(metrics, expected, pool):
    def key(x):
        return tuple(x[k] for k in ('config','pool','view','head','group','guard_stratum'))
    a = {key(x):x for x in metrics if x['config'] in (RAW,P4)}
    e = [x for x in expected if x['pool'] == pool]
    require(e and set(a) == {key(x) for x in e}, 'BASELINE_METRIC_KEYS')
    for x in e:
        y = a[key(x)]
        require(x['rows'] == y['rows'] and x['alarm_count'] == y['alarm_count'] and
                all(abs(x[k]-y[k]) <= 2e-10 for k in x if k.endswith('rate') or
                    k in ('weighted_numerator','weighted_denominator','ht_alarm_total','ht_selected_expansion_total')),
                'BASELINE_METRIC_PARITY:' + str(key(x)))
    return len(e)


def by_protocol(rows):
    g = defaultdict(list)
    for i,r in enumerate(rows):
        label = LABELS[r['label']]
        g[f'protocol:{r["protocol"]} / {label}'].append(i)
        g[f'device:{r["device"]} / protocol:{r["protocol"]} / {label}'].append(i)
    return {k:np.isin(np.arange(len(rows)),ids) for k,ids in g.items()}


PAIRS = ((RAW,P4),(RAW,WITH_GUARD),(RAW,NO_GUARD),
         (P4,WITH_GUARD),(P4,NO_GUARD),(WITH_GUARD,NO_GUARD))


def evaluate(store, cfg, pool, references, fitted, baseline, out, progress):
    rows, uids, raw, p4, q, active, views, expansion, pop = load_query(store,cfg,pool,references)
    source_cuts = cfg['method']['cuts']
    picks = set(np.linspace(0,len(rows)-1,min(512,len(rows)),dtype=int))
    for region in (active,~active,ac.guard(q),~ac.guard(q)):
        picks.update(np.flatnonzero(region)[:8].tolist())
    sl = np.array(sorted(picks))
    p0 = predictions(raw[sl],p4[sl],q[sl],active[sl],source_cuts,fitted)
    require(set(p0) == set(ARMS) and all(len(x)==len(sl) for x in p0.values()), 'REAL_QUERY_SLICE')
    progress('QUERY_PREFLIGHT',len(sl),len(sl),pool=pool,force=True)
    pred = predictions(raw,p4,q,active,source_cuts,fitted)
    require(all(np.array_equal(p0[a],pred[a][sl]) for a in ARMS), 'REAL_QUERY_SLICE_PARITY')
    metrics = [dict(config=a,**x) for a in ARMS
               for x in ac.metrics(pool,rows,pred[a],views,q,expansion,pop)]
    baseline_rows = baseline_parity(metrics,baseline,pool)
    groups = by_protocol(rows)
    metrics.extend(dict(config=a,**x) for a in ARMS for x in
                   ac.metrics(pool,rows,pred[a],views,q,expansion,pop,group_masks=groups))
    pairs = [dict(left=l,right=r,**x) for l,r in PAIRS
             for g in (None,groups) for x in ac.paired(pool,rows,pred[l],pred[r],views,q,expansion,group_masks=g)]
    path = out / f'{pool}_CHANGED_UIDS.jsonl.gz'
    changed = np.flatnonzero(np.logical_or.reduce([np.any(pred[a] != pred[RAW],axis=1) for a in ARMS[1:]]))
    count = write_rows(path,(dict(uid=uids[i],label=rows[i]['label'],device=rows[i]['device'],
                                protocol=rows[i]['protocol'],guard=bool(q[i,0]==1 and q[i,2]==1 and q[i,5]==0),
                                decisions={a:pred[a][i].astype(int).tolist() for a in ARMS}) for i in changed))
    require(count == len(changed), 'CHANGED_UID_OUTPUT')
    progress('QUERY_EVALUATED',len(rows),len(rows),pool=pool,force=True)
    return metrics,pairs,dict(rows=len(rows),post_rows=int(active.sum()),query_uid_sha256=uid_sha(uids),
                              real_slice_rows=len(sl),baseline_metric_rows=baseline_rows,
                              changed_uid_index=artifact(path,count))
