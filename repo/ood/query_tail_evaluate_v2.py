"""Source-normal calibration and fixed joint gates; no winner selection."""
from pathlib import Path
import math
import numpy as np
import query_tail_core_v2 as k
import query_tail_train_v2 as t
from continuous_evaluate_v3 import report
c = k.c
SUFFIXES = ('27', '127', '227', 'ensemble')


def baseline(base, role, rows):
    base = Path(base)
    path = base/'calibration/base_logits.npz' if role == 'CAL' else base/role/'scores.npz'
    with np.load(path, allow_pickle=False) as f:
        result = {'RECENT_'+s:f['RECENT_'+s].copy() for s in SUFFIXES}
    c.require(all(v.shape == (len(rows),) and np.isfinite(v).all() for v in result.values()), 'R0_SHAPE')
    c.require(np.array_equal(np.stack([result['RECENT_'+s] for s in SUFFIXES[:3]]).mean(0, dtype=np.float64), result['RECENT_ensemble']), 'R0_ENSEMBLE')
    if role != 'CAL':
        tau = c.read(base/'calibration/thresholds.json')['tau']['RECENT']
        with np.load(base/role/'decisions.npz', allow_pickle=False) as f:
            c.require(f['uid'].tolist() == [r['uid'] for r in rows], 'R0_UID_ORDER')
            for s in SUFFIXES: c.require(np.array_equal(result['RECENT_'+s] > tau[s], f['RECENT_'+s]), 'R0_ORIGINAL_DECISION')
    return result


def calibrate(rows, scores):
    c.require(all(r['partition'] == 'LEARN' and r['fit_role'] == 'CAL' for r in rows), 'CAL_ROLE')
    normal = np.asarray([i for i,r in enumerate(rows) if r['label'] == 0], dtype=np.int64)
    return {name:k.threshold(value[normal], [rows[int(i)] for i in normal]) for name,value in scores.items()}


def regressions(rows, decisions, pool, limit=.001):
    groups = {}; result = []
    if pool == 'CAL':
        for name in ('TCP', 'UDP', 'Hydra'):
            groups[name] = [i for i,r in enumerate(rows) if r['label'] == 1 and r['activity'] == name]
        c.require(all(groups.values()), 'CAL_ACTIVITY_GROUP_MISSING')
        attacks = [i for i,r in enumerate(rows) if r['label'] == 1]
        w = np.zeros(len(rows)); w[attacks] = k.class_weights([rows[i] for i in attacks])
    else:
        for proto in sorted({r['protocol'] for r in rows if r['label'] == 1}):
            groups[str(proto)] = [i for i,r in enumerate(rows) if r['label'] == 1 and r['protocol'] == proto]
        w = np.asarray([1/r['label_metric_weight_denominator'] for r in rows])
    for name, ix in groups.items():
        mass = math.fsum(w[ix])
        for suffix in SUFFIXES:
            old, new = decisions['RECENT_'+suffix][ix], decisions['QUERY_TAIL_'+suffix][ix]
            a = math.fsum(w[i]*int(decisions['RECENT_'+suffix][i]) for i in ix)/mass
            b = math.fsum(w[i]*int(decisions['QUERY_TAIL_'+suffix][i]) for i in ix)/mass
            result.append(dict(pool=pool, group=name, suffix=suffix, rows=len(ix), baseline_TP=int(old.sum()), candidate_TP=int(new.sum()),
                               baseline_weighted_recall=a, candidate_weighted_recall=b, drop=a-b, passed=a-b <= limit))
    return result


def gate(design, reports, pool):
    rule = design['gates']['common_inherited']; r = reports['QUERY_TAIL_ensemble']; reasons = []
    if r['overall']['attack']['weighted_rate'] < rule['attack_recall_ensemble_each_pool_min']: reasons.append('ATTACK_BELOW_99')
    if r['overall']['normal']['weighted_rate'] > rule['normal_weighted_FPR_each_pool_max']: reasons.append('NORMAL_FPR_GT_1PCT')
    if pool == 'CIC_DEV' and r['overall']['attack']['rate'] < rule['CIC_DEV_historical_Q_recall']-rule['CIC_DEV_max_drop_from_historical_Q_percentage_points']/100:
        reasons.append('HISTORICAL_Q_REGRESSION')
    for g in r['groups']['device']:
        for label, limit, lower in [('attack', rule['attack_recall_ensemble_each_device_min'], True), ('normal', rule['normal_weighted_FPR_each_device_max'], False)]:
            v = g['metrics'][label]['weighted_rate']
            if v is not None and (v < limit if lower else v > limit): reasons.append('DEVICE_'+label+':'+g['group']['device'])
    for suffix in SUFFIXES[:3]:
        if reports['QUERY_TAIL_'+suffix]['overall']['attack']['weighted_rate'] < rule['attack_recall_each_seed_each_pool_min']: reasons.append('SEED_ATTACK_'+suffix)
    return dict(passed=not reasons, reasons=reasons)


def evaluate(root, base, run, design, metadata, indices, arrays, norm, progress):
    run, base = Path(run), Path(base); models = {}
    for arm in k.ARMS:
        for seed in c.SEEDS: models[(arm, seed)] = t.load(run/'endpoints'/(arm+'_'+str(seed)), arm, seed, design)
    thresholds = None; pool_gates = {}; checks = []
    for pool in ('CAL', 'CIC_DEV', 'UNSW_DEV'):
        role = 'LEARN' if pool == 'CAL' else pool
        ix = indices['CAL'] if pool == 'CAL' else np.arange(len(metadata[role]), dtype=np.int64)
        rows = [metadata[role][int(i)] for i in ix]
        q = np.load(run/'prepared'/(role+'_q.npy'), mmap_mode='r', allow_pickle=False)
        scores = baseline(base, pool, rows)
        for arm in k.ARMS:
            for seed in c.SEEDS:
                progress.stage = 'K_SCORE_'+pool+'_'+arm+'_'+str(seed)
                scores[arm+'_'+str(seed)] = k.scores(models[(arm, seed)], arrays[role], q, ix, norm, 768 if arm == 'RECENT_TAIL' else 782, progress)
            scores[arm+'_ensemble'] = np.stack([scores[arm+'_'+str(s)] for s in c.SEEDS]).mean(0, dtype=np.float64)
        if pool == 'CAL':
            thresholds = calibrate(rows, scores)
            original = c.read(base/'calibration/thresholds.json')['tau']['RECENT']
            c.require(all(thresholds['RECENT_'+s] == original[s] for s in SUFFIXES), 'R0_SOURCE_CAL_REPRODUCTION')
            c.write(run/'thresholds.json', dict(cuts=thresholds, source='ORIGINAL_SOURCE_CAL_NORMAL_ONLY', budget=.01,
                    comparator='strict >', normal_uid_sha256=c.uid_sha(r['uid'] for r in rows if r['label'] == 0), normal_rows=sum(r['label'] == 0 for r in rows)))
        decisions = {name:v > thresholds[name] for name,v in scores.items()}
        progress.stage = 'K_REPORT_'+pool
        reports = {}
        for j,(name,pred) in enumerate(decisions.items()):
            reports[name] = report(rows, pred, decisions['RECENT_'+name.rsplit('_', 1)[1]])
            progress.tick(j+1, len(decisions))
        out = run/pool; out.mkdir(exist_ok=False)
        c.save_arrays(out/'scores.npz', uid=np.asarray([r['uid'] for r in rows]), **scores)
        c.save_arrays(out/'decisions.npz', uid=np.asarray([r['uid'] for r in rows]), **decisions)
        c.write(out/'reports.json', reports)
        if pool != 'CAL': pool_gates[pool] = gate(design, reports, pool)
        if pool in ('CAL', 'CIC_DEV'): checks.extend(regressions(rows, decisions, pool))
        c.seal(out); c.verify(out)
    decision = dict(primary='QUERY_TAIL', common_gates=pool_gates, attack_group_protection=checks,
                    core_capability_pass=all(x['passed'] for x in pool_gates.values()) and all(x['passed'] for x in checks),
                    reference_veto_zero_added_misses='NOT_TESTED', reference_adaptation_gain='NOT_TESTED',
                    independent_ID='NOT_RUN', historical_holdout='CLOSED', evidence='CONSUMED_DEVELOPMENT_ONLY',
                    automatic_promotion=False, retries=0)
    c.write(run/'decision.json', decision)
    c.write(run/'K_COMPLETE.json', dict(status='COMPLETE', decision_sha256=c.sha(run/'decision.json')))
    return decision
