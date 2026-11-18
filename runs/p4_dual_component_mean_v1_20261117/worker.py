"""Run the real preflight or the paired formal replay on a Slurm compute node."""
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import traceback

import numpy as np

from reports import A, B, HEADS, POOLS, TOL, headline, matched, paper_text, require

HERE = Path(__file__).resolve().parent


def bind_runtime(project, target, phase):
    from hashlib import sha256
    manifest = json.loads((HERE/'PACKAGE_MANIFEST.json').read_bytes())
    for name, pin in manifest['files'].items():
        require(sha256((HERE/name).read_bytes()).hexdigest() == pin, 'DELIVERED_SHA:' + name)
    cfg = json.loads((HERE/'FROZEN.json').read_bytes())
    old = project/cfg['runtime_package']
    previous = old/'PACKAGE_MANIFEST.json'
    require(sha256(previous.read_bytes()).hexdigest() == cfg['runtime_manifest_sha256'], 'RUNTIME_MANIFEST_SHA')
    for name, pin in json.loads(previous.read_bytes())['files'].items():
        require(sha256((old/name).read_bytes()).hexdigest() == pin, 'PRIOR_PACKAGE_SHA:' + name)
    sys.path.insert(1, str(old))
    sys.path.append(str(old/'repo/ood'))
    from common_round1 import PYTHON, NUMPY_RUNTIME, artifact, dump
    from runtime_support import TSHARK_SHA
    require(os.environ.get('SLURM_JOB_ID','').isdigit() and os.environ.get('SLURMD_NODENAME') and
            sys.platform.startswith('linux') and not sys.flags.optimize and sys.version_info[:2] == (3,11)
            and Path(sys.executable).resolve() == PYTHON.resolve() and np.__version__ == '2.0.1' and
            Path(np.__file__).resolve().is_relative_to((project/NUMPY_RUNTIME).resolve()), 'FROZEN_COMPUTE_RUNTIME')
    tshark = Path(shutil.which('tshark') or '')
    require(tshark.is_file() and artifact(tshark)['sha256'] == TSHARK_SHA, 'DECODER_RUNTIME')
    dump(target/('RUNTIME_'+phase+'.json'), dict(job_id=os.environ['SLURM_JOB_ID'],
         node=os.environ['SLURMD_NODENAME'], python=sys.version, numpy=np.__version__,
         package=artifact(HERE/'PACKAGE_MANIFEST.json'), runtime=artifact(previous), tshark_sha256=TSHARK_SHA))
    return old, cfg, tshark


def pick_slice(d):
    import analysis_core as ac
    buckets = {}
    guard = ac.guard(d['q'])
    for i, row in enumerate(d['rows']):
        key = (row['device'], row['protocol'], row.get('source_role'), row['label'],
               d['active'][i], guard[i], d['saved'][i] > 0)
        buckets.setdefault(key, []).append(i)
    return np.asarray(sorted({ii[j] for ii in buckets.values()
                             for j in (0, len(ii)//2, len(ii)-1)}), dtype=np.int64)


def subset(d, ix):
    return dict(d, rows=[d['rows'][i] for i in ix], ids=[d['ids'][i] for i in ix],
                **{k: d[k][ix] for k in ('z','q','x','raw','p4','saved','active')},
                expansion=None if d['expansion'] is None else d['expansion'][ix],
                views={v:(np.flatnonzero(np.isin(ix, ii)), w[ix]) for v,(ii,w) in d['views'].items()})


def evaluated(pool, d, pa, pb, extra_groups):
    import analysis_core as ac
    from evaluation import by_protocol
    masks = [None]
    if extra_groups:
        masks.append(by_protocol(d['rows']))
    metrics = [dict(config=arm, **r) for group in masks for arm, pred in ((A,pa),(B,pb))
               for r in ac.metrics(pool, d['rows'], pred, d['views'], d['q'], d['expansion'],
                                   d['population'], group_masks=group)]
    pairs = [dict(left=A, right=B, **r) for group in masks for r in
             ac.paired(pool, d['rows'], pa, pb, d['views'], d['q'], d['expansion'], group_masks=group)]
    matched(metrics, pairs)
    return metrics, pairs


def frozen_baseline(pool, d, method, expected):
    import analysis_core as ac
    from evaluation import baseline_parity
    from vendor import p4_worker
    cuts = method['cuts']
    restored = p4_worker.correct(d['raw'], d['saved'], d['q'], method['scales'], True, power=4)
    require(np.max(np.abs(restored - d['p4']), initial=0) <= TOL and
            np.array_equal(restored > cuts, d['p4'] > cuts), 'CACHED_A_SCORE_DECISIONS:' + pool)
    records = [dict(config=arm, **r) for arm, values in (('RAW',d['raw']), (A,restored))
               for r in ac.metrics(pool, d['rows'], values > cuts, d['views'], d['q'],
                                   d['expansion'], d['population'])]
    verified = baseline_parity(records, expected, pool)
    return dict(metric_rows=verified, weak_metric_rows=sum(r['config'] == A for r in records),
                max_abs_score_error=float(np.max(np.abs(restored-d['p4']))), decision_differences=0)


def score_arms(d, geo, method):
    import analysis_core as ac
    from vendor import p4_worker
    scores = [p4_worker.correct(d['raw'], geo[arm], d['q'], method['scales'], True, power=4)
              for arm in ('weak','mean')]
    sa, sb = scores
    pa, pb = [x > method['cuts'] for x in scores]
    protected = ac.guard(d['q'])
    fallback = protected | ~geo['gate']
    require(not np.any(geo['gate'] & ~d['active']) and np.array_equal(sa[fallback],d['raw'][fallback])
            and np.array_equal(sb[fallback],d['raw'][fallback]), 'OPENING_GUARD_OR_FALLBACK')
    require(np.isfinite(sa).all() and np.isfinite(sb).all() and np.all(sb <= sa) and not np.any(pb & ~pa),
            'ROW_AND_HEAD_ALARM_SUBSET')
    delta = float(np.max(np.abs(geo['weak'] - d['saved']), initial=0))
    score_delta = float(np.max(np.abs(sa - d['p4']), initial=0))
    require(delta <= TOL and score_delta <= TOL and np.array_equal(pa, d['p4'] > method['cuts']),
            f'REPLAYED_A_PARITY:s={delta},score={score_delta}')
    return sa, sb, pa, pb, dict(max_abs_support_error=delta, max_abs_score_error=score_delta,
                                decision_differences_by_head=[0]*4, subset_violations_by_head=[0]*4,
                                bypass_changes_by_head=[0]*4)


def independent_scores(d, s, method):
    import analysis_core as ac
    guard = ac.guard(d['q'])
    corrected = d['raw'][:,:3].copy()
    for i in np.flatnonzero(~guard):
        for j, span in enumerate(method['scales']):
            corrected[i,j] -= (0.25 * span) * (1.0 - (1.0 - float(s[i])) ** 4)
    return np.column_stack((corrected, corrected.mean(axis=1, dtype=np.float64)))


def witness(out, pool, d, ix, geo, values, method, geometry):
    from common_round1 import artifact
    from geometry import direct
    a, b, error = direct(d['rows'], d['z'], d['q'], d['x'], d['bank'], d['rc'], geometry, geo)
    sa, sb, pa, pb, parity = values
    oracle = [independent_scores(d, s, method) for s in (a,b)]
    require(all(np.allclose(x, y, atol=TOL, rtol=0) and np.array_equal(x > method['cuts'], p)
                for x,y,p in zip(oracle, (sa,sb), (pa,pb))), 'DIRECT_G4_SCORES_AND_DECISIONS')
    metrics, pairs = evaluated(pool, d, pa, pb, False)
    require(evaluated(pool, d, *(x > method['cuts'] for x in oracle), False) == (metrics, pairs),
            'DIRECT_REAL_SLICE_EVALUATION')
    path = out/'artifacts'/(pool+'_slice.npz')
    np.savez(path, ix=ix, uid=np.asarray(d['ids']), m=geo['m'], gate=geo['gate'], sa=sa, sb=sb, pa=pa, pb=pb)
    return dict(status='PASS', rows=len(ix), metrics=len(metrics), paired_cells=len(pairs),
                pair_evaluations=geo['pairs'], admitted=int(geo['gate'].sum()), direct_max_distance_error=error,
                archive_parity=parity, values=artifact(path))


def formal_outputs(out, pool, d, geo, values, proof):
    import analysis_core as ac
    from common_round1 import artifact, uid_sha, verify_artifact, write_rows
    sa, sb, pa, pb, parity = values
    path = verify_artifact(out/'artifacts', proof['values'])
    with np.load(path, allow_pickle=False) as p:
        ix = p['ix']
        require(np.array_equal(p['uid'], np.asarray(d['ids'])[ix]) and
                np.array_equal(p['gate'],geo['gate'][ix]) and
                np.allclose(p['m'],geo['m'][ix],atol=TOL,rtol=0) and
                np.allclose(p['sa'],sa[ix],atol=TOL,rtol=0) and np.allclose(p['sb'],sb[ix],atol=TOL,rtol=0)
                and np.array_equal(p['pa'],pa[ix]) and np.array_equal(p['pb'],pb[ix]),
                'FORMAL_TO_REAL_PREFLIGHT:' + pool)
    metrics, pairs = evaluated(pool, d, pa, pb, True)
    changed = np.flatnonzero((pa != pb).any(axis=1))
    guarded = ac.guard(d['q'])
    require(not np.any(guarded[changed]) and np.all(geo['gate'][changed]), 'WITHDRAWAL_OUTSIDE_SHARED_GATE')
    if pool == 'UNSW_DEV':
        attacks = np.array([r['label'] == 1 for r in d['rows']])
        require(guarded[attacks].all() and np.array_equal(pa[attacks],pb[attacks]), 'UNSW_ATTACK_BYPASS')
    path = out/'artifacts'/(pool+'_changed.jsonl.gz')
    count = write_rows(path, (dict(uid=d['ids'][i], row=int(i), label=d['rows'][i]['label'],
        device=d['rows'][i]['device'], protocol=d['rows'][i]['protocol'], group=d['rows'][i].get('source_role'),
        post_window=bool(d['active'][i]), guard=bool(guarded[i]), heads=list(HEADS), weak=pa[i].tolist(),
        mean=pb[i].tolist(), distances=geo['m'][i].tolist(), support=[geo['weak'][i],geo['mean'][i]],
        reference_uids=[d['bank'].rows[j]['uid'] for j in geo['donors'][i]],
        component_ids=[d['bank'].rows[j]['component_id'] for j in geo['donors'][i]]) for i in changed))
    arrays = out/'artifacts'/(pool+'_paired.npz')
    np.savez(arrays, uid=np.asarray(d['ids']), m1=geo['m'][:,0], m2=geo['m'][:,1], bank_rows=geo['donors'],
             opening=geo['opening'], geometry_ready=geo['geometry_ready'], legal_components=geo['legal_component_count'],
             admitted=geo['gate'], weak=geo['weak'], mean=geo['mean'], scores_a=sa, scores_b=sb, alarms_a=pa, alarms_b=pb)
    return metrics, pairs, dict(changed=dict(path=str(path),**artifact(path,count)),
            paired_arrays=dict(path=str(arrays),**artifact(arrays,len(d['ids']))),
            query_uid_order_sha256=uid_sha(d['ids']), reference_uid_order_sha256=uid_sha(
                [r['uid'] for r in d['bank'].rows]), rows=len(d['ids']), admitted=int(geo['gate'].sum()),
            reference_pairs=geo['pairs'], reproduced_A=parity, extra_withdrawals_by_head=(pa & ~pb).sum(0).tolist())


def run(phase, project, out):
    old, contract, tshark = bind_runtime(project, out, phase)
    from common_round1 import artifact, dump, load, sha, table
    from geometry import top_two
    from inputs import load_pool, raw_slice, store_for
    from runtime_support import Progress
    from boundary_checks import run as check_boundaries
    progress = Progress(out,phase)
    (out/'artifacts').mkdir(exist_ok=True)
    cfg, geom = load(old/'CONFIG.json'), load(old/'GEOMETRY.json')
    expected = load(old/'EXPECTED_BASELINE.json')
    method = cfg['method']
    require(method == contract['method'] and all(geom['method'][k] == v for k,v in method.items())
            and method['p'] == 4 and method['lambda_value'] == .25 and tuple(method['heads']) == HEADS
            and method['guard'] == 'SYN_AND_NOT_ACK_ALL_DEVICES' and all(s > 0 for s in method['scales'])
            and cfg['reference'] == contract['reference'] and cfg['query'] == contract['query'], 'TABLE9_FREEZE')
    package_sha = sha(HERE/'PACKAGE_MANIFEST.json')
    pre = None
    if phase == 'formal':
        pre = load(out/'PREFLIGHT.json')
        require(pre['status'] == 'PASS' and pre['package_sha256'] == package_sha and
                pre['job_id'] == load(out/'JOB_preflight.json')['job_id'] and
                pre['inputs_sha256'] == sha(out/'INPUTS_preflight.json'), 'FORMAL_PREFLIGHT_BINDING')
    store = store_for(project, contract)
    for h in HEADS[:3]:
        store.get('head_'+h)
    norms = []
    for key, width in (('e3_normalizer',768),('context_normalizer',8)):
        with np.load(store.get(key), allow_pickle=False) as a:
            mean, scale = a['mean'], a['scale']
            require(mean.shape == scale.shape == (width,) and (scale > 0).all() and np.isfinite(mean).all()
                    and np.isfinite(scale).all(), 'FROZEN_NORMALIZER')
            norms.append((mean,scale))
    raw_proof = None
    receipts, baselines, schemas, all_metrics, all_pairs = {}, {}, {}, [], []
    boundaries = check_boundaries()
    for pool in POOLS:
        with progress.measure('CHECK_INPUTS_'+pool):
            d, frozen = load_pool(store, pool, cfg, contract, norms, progress)
            schemas[pool] = d['cache_fields']
            baselines[pool] = frozen_baseline(pool, d, method, expected)
        if phase == 'preflight':
            if pool == 'CIC_DEV':
                with progress.measure('RAW_DECODE_AND_ENCODER'):
                    raw_proof = raw_slice(store, frozen, norms, d, out, tshark, progress)
            ix = pick_slice(d)
            d = subset(d, ix)
        del frozen
        with progress.measure('REPLAY_'+pool):
            geo = top_two(d['rows'], d['z'], d['q'], d['x'], d['bank'], d['rc'], geom, progress)
            values = score_arms(d, geo, method)
        with progress.measure('EVALUATE_'+pool):
            if phase == 'preflight':
                receipts[pool] = witness(out, pool, d, ix, geo, values, method, geom)
            else:
                m, p, receipts[pool] = formal_outputs(out,pool,d,geo,values,pre['pools'][pool])
                all_metrics.extend(m)
                all_pairs.extend(p)
        del d, geo, values
        gc.collect()
    inputs = out/('INPUTS_'+phase+'.json')
    dump(inputs, dict(assets=store.checked, baseline=baselines, caches=schemas, distance_source=
        'Recomputed joint per-reference distances on frozen encodings; componentwise minimum before ranks.'))
    job = os.environ['SLURM_JOB_ID']
    if phase == 'preflight':
        require(raw_proof and all(v['admitted'] > 0 for v in receipts.values()), 'REAL_SLICE_POSITIVE_COVERAGE')
        receipt = dict(status='PASS', job_id=job, package_sha256=package_sha, inputs_sha256=sha(inputs),
                       real_frontend=raw_proof, pools=receipts, boundaries=boundaries)
        dump(out/'PREFLIGHT.json',receipt)
        require(load(out/'PREFLIGHT.json') == receipt,'REAL_PREFLIGHT_RECEIPT_READBACK')
    else:
        heads = headline(all_metrics,all_pairs)
        table(out,'METRICS',all_metrics)
        table(out,'PAIRED',all_pairs)
        table(out,'HEADLINE',heads)
        dump(out/'ARTIFACTS.json',receipts)
        (out/'RESULTS_FOR_PAPER.md').write_text(paper_text(heads,pre['job_id'],job,all_pairs), encoding='utf-8')
        names = ('METRICS.json','PAIRED.json','HEADLINE.json','HEADLINE.csv','METRICS.csv','PAIRED.csv',
                 'ARTIFACTS.json','RESULTS_FOR_PAPER.md','PREFLIGHT.json','INPUTS_formal.json','INPUTS_preflight.json')
        dump(out/'SCIENCE.json',dict(status='PASS', job_id=job, preflight_job=pre['job_id'], rows=sum(
             r['rows'] for r in receipts.values()), heads=list(HEADS), arms=[A,B], package_sha256=package_sha,
             baseline=baselines, outputs={n:artifact(out/n) for n in names}))
    progress('PHASE_COMPLETE',1,1,force=True)


if __name__ == '__main__':
    phase, project, target = sys.argv[1:]
    out = Path(target)
    try:
        require(phase in ('preflight','formal'), 'PHASE')
        run(phase, Path(project), out)
    except Exception as error:
        path = out/('FAILURE_'+phase+'.json')
        path.write_text(json.dumps(dict(error=str(error), traceback=traceback.format_exc(),
                             job_id=os.environ.get('SLURM_JOB_ID')),indent=2), encoding='utf-8')
        raise
