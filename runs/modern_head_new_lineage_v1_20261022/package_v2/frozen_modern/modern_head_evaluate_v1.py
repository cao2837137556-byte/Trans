"""Fixed three-family comparison using the official metrics and inherited gates.

Every threshold is sealed from source CAL normals before target prediction.
All families/seeds are reported; this module never chooses a winner or modifies
the reference module. FIT scores are retained for subsequent source-only scales.
"""
from pathlib import Path
import copy
import time

import numpy as np
import query_tail_core_v2 as k
import query_tail_evaluate_v2 as official
from continuous_evaluate_v3 import report

c = k.c
FAMILIES = ('MLP_QUERY_BCE', 'TabM', 'LightGBM')
ONBOARDING_FAMILIES = ('TabM', 'LightGBM')
SUFFIXES = official.SUFFIXES
REGRESSION_SCOPE = 'Each seed and ensemble of every family: MLP_QUERY_BCE, TabM, LightGBM'


def modern_gates(inherited):
    """Change the scope description only; preserve every numeric acceptance rule."""
    gates = copy.deepcopy(inherited['gates'])
    gates['additional_regression']['applies_to'] = REGRESSION_SCOPE
    return gates


def validate_config(config, inherited=None):
    c.require(config.get('schema') == 'modern-head-comparison-v1' and
              tuple(config.get('families', ())) == FAMILIES and
              tuple(config.get('seeds', ())) == c.SEEDS and
              tuple(config.get('onboarding_families', ())) == ONBOARDING_FAMILIES,
              'MODERN_COMPARISON_SCOPE')
    c.require(type(config.get('synthetic_only')) is bool, 'MODERN_SYNTHETIC_FLAG')
    if inherited is not None:
        c.require(config.get('gates') == modern_gates(inherited), 'MODERN_INHERITED_GATES')


def ensemble(seed_scores):
    c.require(len(seed_scores) == 3 and all(np.asarray(s).ndim == 1 for s in seed_scores),
              'MODERN_ENSEMBLE_SCHEMA')
    c.require(len({np.asarray(s).shape for s in seed_scores}) == 1 and
              all(np.isfinite(s).all() for s in seed_scores), 'MODERN_ENSEMBLE_FINITE')
    result = np.stack(seed_scores).mean(0, dtype=np.float64)
    c.require(np.isfinite(result).all(), 'MODERN_ENSEMBLE_FINITE')
    return result


def calibrate(rows, scores):
    c.require(len({r['uid'] for r in rows}) == len(rows), 'MODERN_CAL_UID')
    c.require(all(np.asarray(v).shape == (len(rows),) and np.isfinite(v).all()
                  for v in scores.values()), 'MODERN_CAL_SCORE_SCHEMA')
    return official.calibrate(rows, scores)


def regressions(rows, decisions, pool, family, limit=.001):
    """Rename the candidate only; the official weight arithmetic is unchanged."""
    c.require(family in FAMILIES and limit == .001, 'MODERN_REGRESSION_CONTRACT')
    mapped = {'RECENT_'+s: decisions['RECENT_'+s] for s in SUFFIXES}
    mapped.update({'QUERY_TAIL_'+s: decisions[family+'_'+s] for s in SUFFIXES})
    return [dict(item, family=family) for item in official.regressions(rows, mapped, pool, limit)]


def gate(config, reports, pool, family):
    c.require(family in FAMILIES, 'MODERN_FAMILY')
    mapped = {'QUERY_TAIL_'+s: reports[family+'_'+s] for s in SUFFIXES}
    return official.gate(config, mapped, pool)


def comparison_summary(reports):
    """Compact comparison rows accompany, and never replace, full reports."""
    answer = {}
    for family in FAMILIES:
        r = reports[family+'_ensemble']
        devices = r['groups']['device']
        normal = [(d['metrics']['normal']['weighted_rate'], d['group']['device']) for d in devices
                  if d['metrics']['normal']['weighted_rate'] is not None]
        attacks = [(d['metrics']['attack']['weighted_rate'], d['group']['device']) for d in devices
                   if d['metrics']['attack']['weighted_rate'] is not None]
        ranges = {}
        for label in ('normal', 'attack'):
            values = [reports[family+'_'+s]['overall'][label]['weighted_rate'] for s in SUFFIXES[:3]]
            ranges[label] = dict(min=min(values), max=max(values), range=max(values)-min(values))
        answer[family] = dict(ensemble=r['overall'], seed_ranges=ranges,
            worst_device_fpr=dict(value=max(normal)[0], device=max(normal)[1]) if normal else None,
            worst_device_recall=dict(value=min(attacks)[0], device=min(attacks)[1]) if attacks else None)
    return answer


def evaluate(root, parent, run, config, metadata, indices, arrays, q, norm, progress=None):
    import modern_head_models_v1 as models
    import modern_head_train_v1 as training
    root, parent, run = Path(root), Path(parent), Path(run)
    inherited = c.read(c.pin(root/'query_tail_design.json', k.DESIGN_SHA))
    validate_config(config, inherited)
    thresholds = None; pool_gates = {f: {} for f in FAMILIES}
    checks = {f: [] for f in FAMILIES}; timings = {}; summaries = {}
    # Target arrays are not scored until the CAL-only threshold file is written.
    for pool in ('CAL', 'CIC_DEV', 'UNSW_DEV', 'FIT'):
        role = 'LEARN' if pool in ('CAL', 'FIT') else pool
        ix = indices[pool] if role == 'LEARN' else np.arange(len(metadata[role]), dtype=np.int64)
        rows = [metadata[role][int(i)] for i in ix]
        c.require(len({r['uid'] for r in rows}) == len(rows), 'MODERN_POOL_UID')
        scores = official.baseline(parent, pool, rows) if pool != 'FIT' else {}
        for family in FAMILIES:
            for seed in c.SEEDS:
                if progress is not None:
                    progress.stage = 'MODERN_SCORE_'+pool+'_'+family+'_'+str(seed)
                started = time.monotonic()
                model = training.load(run/'endpoints'/(family+'_'+str(seed)), family, seed, config)
                value = models.scores(model, family, arrays[role], q[role], ix, norm, progress)
                c.require(value.shape == (len(rows),) and np.isfinite(value).all(), 'MODERN_SCORE_SCHEMA')
                scores[family+'_'+str(seed)] = value
                timings[pool+'_'+family+'_'+str(seed)] = dict(seconds=time.monotonic()-started,
                    rows=len(rows), boundary='endpoint load plus prediction; excludes metric reporting and output I/O')
                del model
            scores[family+'_ensemble'] = ensemble([scores[family+'_'+str(s)] for s in c.SEEDS])
        if pool == 'CAL':
            thresholds = calibrate(rows, scores)
            original = c.read(parent/'calibration/thresholds.json')['tau']['RECENT']
            c.require(all(thresholds['RECENT_'+s] == original[s] for s in SUFFIXES), 'MODERN_R0_CAL_REPRODUCTION')
            c.write(run/'thresholds.json', dict(cuts=thresholds, source='ORIGINAL_SOURCE_CAL_NORMAL_ONLY',
                budget=.01, comparator='strict >', normal_uid_sha256=c.uid_sha(r['uid'] for r in rows if r['label'] == 0),
                normal_rows=sum(r['label'] == 0 for r in rows), config_digest=c.digest(config),
                gates_digest=c.digest(config['gates']), seed_order=list(c.SEEDS),
                ensemble='np.stack(seed_vectors).mean(axis=0,dtype=float64)'))
        out = run/pool; out.mkdir(exist_ok=False)
        c.save_arrays(out/'scores.npz', uid=np.asarray([r['uid'] for r in rows]), **scores)
        if pool != 'FIT':
            decisions = {name: value > thresholds[name] for name, value in scores.items()}
            reports = {}
            for j, (name, pred) in enumerate(decisions.items()):
                reports[name] = report(rows, pred, decisions['RECENT_'+name.rsplit('_', 1)[1]])
                if progress is not None:
                    progress.stage = 'MODERN_REPORT_'+pool; progress.tick(j+1, len(decisions))
            c.save_arrays(out/'decisions.npz', uid=np.asarray([r['uid'] for r in rows]), **decisions)
            c.write(out/'reports.json', reports)
            for family in FAMILIES:
                if pool != 'CAL': pool_gates[family][pool] = gate(config, reports, pool, family)
                if pool in ('CAL', 'CIC_DEV'): checks[family].extend(regressions(rows, decisions, pool, family))
            summaries[pool] = comparison_summary(reports)
        c.seal(out); c.verify(out)
    candidates = {family: dict(common_gates=pool_gates[family], attack_group_protection=checks[family],
        core_capability_pass=all(v['passed'] for v in pool_gates[family].values()) and
                             all(v['passed'] for v in checks[family])) for family in FAMILIES}
    decision = dict(families=candidates, automatic_promotion=False, selected_family=None,
        onboarding_families=list(ONBOARDING_FAMILIES), onboarding_selection='FIXED_BEFORE_TARGET_RESULTS',
        reference_veto_zero_added_misses='NOT_TESTED', reference_adaptation_gain='NOT_TESTED',
        independent_ID='NOT_RUN', historical_holdout='CLOSED', evidence='CONSUMED_DEVELOPMENT_ONLY',
        config_digest=c.digest(config), retries=0)
    c.write(run/'comparison_summary.json', dict(pools=summaries, prediction_cost=timings,
        no_automatic_winner=True, evidence='CONSUMED_DEVELOPMENT_ONLY'))
    c.write(run/'decision.json', decision)
    c.write(run/'K_COMPLETE.json', dict(status='COMPLETE', config_digest=c.digest(config),
        decision_sha256=c.sha(run/'decision.json'), summary_sha256=c.sha(run/'comparison_summary.json')))
    return decision
