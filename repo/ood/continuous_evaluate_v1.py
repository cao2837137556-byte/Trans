"""Single source calibration, paired fixed development evaluation and controls."""
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
import continuous_common_v1 as c
import continuous_model_v1 as m
from legacy_qref_evaluate_v1 import measure, paired
from legacy_qref_model_v1 import veto, protected_cut


def logits(models, values, rows, norm, progress):
    output = {str(s): [] for s in c.SEEDS}
    with torch.inference_mode():
        for start in range(0, len(rows), 256):
            z = m.normalized(values, slice(start, start+256), norm)
            for seed in c.SEEDS:
                output[str(seed)].append(models[seed](z).flatten().numpy())
            progress.tick(start+len(z), len(rows))
    output = {k: np.concatenate(v) for k, v in output.items()}
    output['ensemble'] = np.stack(list(output.values())).mean(0, dtype=np.float64)
    c.require(all(np.isfinite(v).all() for v in output.values()), 'LOGIT_NONFINITE')
    return output


def similarities(models, values, rows, norm, bank, design, progress, override=None):
    result = {str(s): [] for s in c.SEEDS}; result['RAW'] = []; validity = []
    with torch.inference_mode():
        for start in range(0, len(rows), 256):
            rr = rows[start:start+256]; z = m.normalized(values, slice(start, start+256), norm)
            common = None
            for key, model in [(str(s), models[s]) for s in c.SEEDS] + [('RAW', m.Raw())]:
                scores, valid = bank.own(z, rr, model, design, override=override)
                c.require(common is None or torch.equal(common, valid), 'REFERENCE_MASK_DIFFERENCE')
                common = valid; result[key].append(scores.numpy())
            validity.append(common.numpy()); progress.tick(start+len(rr), len(rows))
    result = {k: np.concatenate(v) for k, v in result.items()}
    result['ensemble'] = np.stack([result[str(s)] for s in c.SEEDS]).mean(0, dtype=np.float64)
    return result, np.concatenate(validity)


def calibrate(design, classifiers, metrics, data, norms, bank, out, progress):
    out = Path(out); out.mkdir(exist_ok=False)
    rows = data['rows']; normal = [i for i, r in enumerate(rows) if r['label'] == 0]
    attack = [i for i, r in enumerate(rows) if r['label'] == 1]
    c.require(all(r['partition'] == 'LEARN' and r['fit_role'] == 'CAL' for r in rows), 'CAL_ROLE')
    c.require(len(normal) == design['data']['CAL']['normal'] and len(attack) == design['data']['CAL']['attack'], 'CAL_COUNTS')
    c.require(all(r['partition'] == 'LEARN' for r in bank.rows), 'CAL_SOURCE_BANK_ONLY')
    tau = {}; logit_output = {}
    for arm in c.ARMS:
        result = logits(classifiers[arm], data[arm], rows, norms[arm], progress)
        tau[arm] = {key: m.threshold(values[normal], [rows[i] for i in normal]) for key, values in result.items()}
        logit_output.update({arm+'_'+key: v for key, v in result.items()})
    chunks = {str(s): [] for s in c.SEEDS}; chunks.update(RAW=[], ensemble=[])
    pairs = []; all_models = {str(s): metrics[s] for s in c.SEEDS}; all_models['RAW'] = m.Raw()
    with torch.inference_mode():
        for start in range(0, len(attack), 256):
            ix = attack[start:start+256]; rr = [rows[i] for i in ix]
            z = m.normalized(data['RECENT_STATE'], np.asarray(ix), norms['RECENT_STATE'])
            mats = {}; common = None
            for key, model in all_models.items():
                matrix, mask = bank.matrix(z, rr, model, design, minimum=2)
                c.require(common is None or torch.equal(mask, common), 'CAL_BANK_MASK')
                common = mask; mats[key] = matrix.numpy()
            c.require(bool(common.any(1).all()), 'CAL_ATTACK_WITHOUT_ANY_LEGAL_BANK')
            mats['ensemble'] = np.stack([mats[str(s)] for s in c.SEEDS]).mean(0, dtype=np.float64)
            for key, matrix in mats.items():
                chunks[key].append(matrix[common.numpy()])
            qi, bi = np.nonzero(common.numpy())
            pairs.extend((ix[int(q)], int(b)) for q, b in zip(qi, bi))
            progress.tick(start+len(ix), len(attack))
    c.require(len(pairs) == design['data']['CAL']['attack_donor_pairs'], 'CAL_PAIR_DENOMINATOR')
    arrays = {key: np.concatenate(v) for key, v in chunks.items()}
    cuts = {key: protected_cut(v) for key, v in arrays.items()}
    c.save_arrays(out/'base_logits.npz', **logit_output)
    c.save_arrays(out/'reference_scores.npz', pairs=np.asarray(pairs), **arrays)
    c.write(out/'thresholds.json', dict(tau=tau, cuts=cuts, source_CAL_only=True,
        design_digest=c.digest(design), normal_rows=len(normal), attack_rows=len(attack), pairs=len(pairs)))
    c.seal(out); c.verify(out)
    with np.load(out/'reference_scores.npz', allow_pickle=False) as saved:
        c.require(all(not (saved[k] > cut).any() for k, cut in cuts.items()), 'CAL_PROTECTION_REAPPLY')
    return tau, cuts


def report(rows, pred, base):
    result = dict(overall=measure(rows, pred), paired=paired(rows, pred, base), groups={})
    for fields in [('device',), ('device', 'protocol'), ('device', 'attack_rate'),
                   ('device', 'activity'), ('device', 'component_id')]:
        groups = defaultdict(list)
        for i, r in enumerate(rows):
            groups[tuple(str(r.get(k, 'NA')) for k in fields)].append(i)
        result['groups']['/'.join(fields)] = [dict(group=dict(zip(fields, key)),
            metrics=measure([rows[i] for i in ix], pred[ix]),
            paired=paired([rows[i] for i in ix], pred[ix], base[ix])) for key, ix in sorted(groups.items())]
    component = result['groups']['device/component_id']
    result['component_macro'] = {label: float(np.mean([g['metrics'][label]['rate'] for g in component
        if g['metrics'][label]['rate'] is not None])) if any(g['metrics'][label]['rate'] is not None for g in component) else None
        for label in ('normal', 'attack')}
    result['component_count']=len(component)
    del result['groups']['device/component_id']  # UID metadata/decisions allow replay; avoid millions of duplicate JSON cells.
    return result


def gate(design, reports, pool):
    r = reports['RECENT_STATE_LEARNED_ensemble']; b = reports['RECENT_STATE_ensemble']; why = []
    if r['overall']['attack']['rate'] < .99: why.append('ATTACK_BELOW_99')
    if pool == 'CIC_DEV' and r['overall']['attack']['rate'] < 79045/79056-.001: why.append('SOURCE_REGRESSION_GT_0_1PP')
    if r['overall']['normal']['weighted_rate'] > .01: why.append('NORMAL_FPR_GT_1PCT')
    for g in r['groups']['device']:
        for label, limit, lower in [('attack', .97, True), ('normal', .02, False)]:
            value = g['metrics'][label]['rate' if lower else 'weighted_rate']
            if value is not None and ((value < limit) if lower else (value > limit)):
                why.append('DEVICE_'+label.upper()+':'+g['group']['device'])
    for suffix in ['ensemble'] + [str(s) for s in c.SEEDS]:
        v = reports['RECENT_STATE_LEARNED_'+suffix]
        if v['paired']['new_attack_misses']: why.append('LEARNED_ADDED_MISSES_'+suffix)
        if suffix != 'ensemble' and v['overall']['attack']['rate'] < .97: why.append('SEED_ATTACK_BELOW_97_'+suffix)
    baseline_fpr = b['overall']['normal']['weighted_rate']
    gain = None if baseline_fpr == 0 else 1-r['overall']['normal']['weighted_rate']/baseline_fpr
    adaptation = gain is not None and gain >= .30
    raw = reports['RECENT_STATE_RAW_ensemble']
    learned_over_raw = r['overall']['normal']['weighted_rate'] < raw['overall']['normal']['weighted_rate'] and r['paired']['new_attack_misses'] <= raw['paired']['new_attack_misses']
    return dict(core_capability_pass=not why, reasons=why, adaptation_gain= gain,
        adaptation_gain_pass=adaptation, gain_status='NO_ROOM_FOR_GAIN' if gain is None else 'MEASURED',
        learned_over_raw=learned_over_raw,
        raw_zero_added_attack_misses=all(reports['RECENT_STATE_RAW_'+s]['paired']['new_attack_misses']==0 for s in ['ensemble','27','127','227']),
        independent_ID='NOT_RUN',
        evidence='CONSUMED_DEVELOPMENT_ONLY', automatic_promotion=False)


def evaluate(design, classifiers, metrics, data, norms, bank, tau, cuts, controls, pool, out, progress):
    out = Path(out); out.mkdir(exist_ok=False)
    rows = data['rows']; predictions = {}; saved = {}; reports = {}
    for arm in c.ARMS:
        values = logits(classifiers[arm], data[arm], rows, norms[arm], progress)
        for suffix, values in values.items():
            name = arm+'_'+suffix; saved[name] = values; predictions[name] = values > tau[arm][suffix]
    sims, valid = similarities(metrics, data['RECENT_STATE'], rows, norms['RECENT_STATE'], bank, design, progress)
    for suffix in ['ensemble'] + [str(s) for s in c.SEEDS]:
        base = predictions['RECENT_STATE_'+suffix]
        for arm, key in [('LEARNED', suffix), ('RAW', 'RAW')]:
            name = 'RECENT_STATE_'+arm+'_'+suffix
            predictions[name] = veto(base, sims[key], valid, cuts[key]); saved[name+'_similarity'] = sims[key]
    for name, prediction in predictions.items():
        suffix = name.rsplit('_', 1)[1]
        reports[name] = report(rows, prediction, predictions['RECENT_STATE_'+suffix])
    control_reports = []
    for control in controls:
        if control['status'] != 'MATCHED':
            control_reports.append(control); continue
        ix = [i for i, r in enumerate(rows) if r['device'] == control['device'] and r['protocol'] == control['protocol']]
        rr = [rows[i] for i in ix]
        c.require(len(ix) == control['rows'] and c.uid_sha(r['uid'] for r in rr) == control['query_uid_sha256'], 'MATCHED_CONTROL_QUERY')
        for which in ('correct', 'wrong'):
            override = {(control['device'], control['protocol']): control[which+'_reference_uids']}
            chosen = [bank.rows[bank.by_uid[u]] for u in control[which+'_reference_uids']]
            c.require(len(chosen) == control['count'] and len({r['component_id'] for r in chosen}) == len(chosen), 'CONTROL_COUNT')
            owner = control['device'] if which == 'correct' else control['donor']
            c.require(all(r['device'] == owner and r['protocol'] == control['protocol'] for r in chosen), 'CONTROL_OWNER_PROTOCOL')
            c.require(all(r['reference_end'] < min(q['timestamp'] for q in rr) for r in chosen), 'CONTROL_FUTURE')
            ss, vv = similarities(metrics, data['RECENT_STATE'][np.asarray(ix)], rr, norms['RECENT_STATE'], bank, design, progress, override)
            cr = {}
            for suffix in ['ensemble'] + [str(s) for s in c.SEEDS]:
                base = predictions['RECENT_STATE_'+suffix][ix]
                pp = veto(base, ss[suffix], vv, cuts[suffix])
                cr[suffix] = report(rr, pp, base)
            control_reports.append(dict(device=control['device'], protocol=control['protocol'], which=which, reports=cr))
    c.save_arrays(out/'decisions.npz', uid=np.asarray([r['uid'] for r in rows]), valid_reference=valid, **predictions)
    c.save_arrays(out/'scores.npz', **saved)
    c.write(out/'reports.json', reports); c.write(out/'matched_controls.json', control_reports)
    c.write(out/'zero_vectors.json',{str(s):metrics[s].zero_counts for s in c.SEEDS})
    result = gate(design, reports, pool)
    c.write(out/'decision.json', result); c.seal(out); c.verify(out)
    return result
