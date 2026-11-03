"""Conditional main CAL and one frozen A/B evaluation; never refits a parameter."""
import gzip
import json
import math
from pathlib import Path

import numpy as np

from .common import SPEC_SHA, array_sha, read_json, require, resolve_asset, sha, uid_sha
from .legacy import load_legacy
from .runtime import verify_predecessor


def _save(output, name, runtime, **arrays):
    path = Path(output)/name
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), 'OUTPUT_ALREADY_EXISTS:' + name)
    require(all(np.asarray(v).dtype.kind != 'O' for v in arrays.values()), 'OUTPUT_OBJECT_ARRAY')
    np.savez_compressed(path, **arrays)
    runtime.checkpoint('SAVE_ARRAYS', file=name)


def _dual_own(rows, normals, attacks, normal_result, attack_matrix, arm):
    """Match own donor by identity; lack of an eligible bank means RAW fallback."""
    out, eligible = np.zeros(len(rows)), np.zeros(len(rows), dtype=bool)
    out[normals], eligible[normals] = normal_result[arm], normal_result['eligible_' + arm]
    keys = {(r['partition'], r['device'], r['protocol']): j for j, r in enumerate(attack_matrix['roster'])}
    for local, index in enumerate(attacks):
        row = rows[int(index)]
        column = keys.get((row['partition'], row['device'], row['protocol']))
        if column is not None:
            out[index] = attack_matrix[arm][local, column]
            eligible[index] = attack_matrix['eligible_' + arm][local, column]
    return out, eligible


def _cal_component_isolation(rows, references):
    ref = {(r['device'], r['component_id']) for r in references}
    require(not ref.intersection((r['device'], r['component_id']) for r in rows),
            'MAIN_CAL_REFERENCE_COMPONENT_OVERLAP')


def main_calibration(root, output, runtime, legacy):
    from .geometry import DualBank
    from . import metrics
    dense, data, indexed = legacy['dense_source'], legacy['source_data'], legacy['indexed']
    identities = dense.source_identity_preflight(root)
    runtime.write_json('MAIN_INPUT_SEAL.json', identities)
    reference_rows = dense.load_rows(root/dense.DENSE/'references.jsonl.gz')
    with np.load(root/dense.DENSE/'bank.npz', allow_pickle=False) as saved:
        refs = {k: saved[k].copy() for k in ('uid', 'e3', 'q14')}
    with np.load(root/dense.OLD_REFS/'SOURCE_REFS.npz', allow_pickle=False) as saved:
        old_bank = {k: saved[k].copy() for k in ('uid', 'e3', 'q14')}
    dense.validate_bank(reference_rows, refs, read_json(root/dense.SOURCE_PLAN),
                        dense.load_rows(root/dense.OLD_REFS/'SOURCE_REFS.jsonl.gz'), old_bank)
    with np.load(root/dense.PREP/'CAL.npz', allow_pickle=False) as saved:
        indices = saved['indices'].copy()
    require(len(indices) == 148819 and np.array_equal(indices, np.sort(np.unique(indices))), 'MAIN_CAL_INDICES')
    positions, rows = set(indices.tolist()), []
    with gzip.open(root/dense.PREP/'LEARN.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for i, line in enumerate(stream):
            if i in positions:
                row = json.loads(line)
                require(row['source_index'] == i and row['fit_role'] == 'CAL', 'MAIN_CAL_ROLE')
                rows.append(row)
    require(len(rows) == len(indices), 'MAIN_CAL_ROWS')
    _cal_component_isolation(rows, reference_rows)
    with np.load(root/dense.TRACE, allow_pickle=False) as saved:
        require(saved['uid'].tolist() == [r['uid'] for r in rows], 'MAIN_CAL_UID_ORDER')
        logits, original_decisions = saved['original_logits'].copy(), saved['original_decisions'].copy()
    config, geometry, scales = (read_json(root/dense.CALIBRATION/(name+'.json'))
                                for name in ('cuts', 'geometry', 'scales'))
    cuts = np.asarray([*config['cuts'], config['ensemble_cut']], dtype=np.float64)
    require(config['seeds'] == [27,127,227] and not config['moved'], 'MAIN_CUT_BINDING')
    with np.load(root/dense.PREP/'normalizer.npz', allow_pickle=False) as saved:
        normalizer = (saved['mean'].copy(), saved['scale'].copy())
    features = np.load(root/dense.FEATURES, mmap_mode='r', allow_pickle=False)
    q = np.load(root/dense.PREP/'LEARN_q.npy', mmap_mode='r', allow_pickle=False)
    labels = np.asarray([r['label'] for r in rows])
    normals, attacks = np.flatnonzero(labels == 0), np.flatnonzero(labels == 1)
    require(len(normals) == 33147 and len(attacks) == 115672, 'MAIN_CAL_COUNTS')
    runtime.checkpoint('MAIN_LOCAL_RADII')
    bank = DualBank(reference_rows, refs['e3'], refs['q14'], normalizer, geometry,
                    core=legacy['core'], counter=runtime.add_pairs, checkpoint=runtime.checkpoint,
                    allow_prebank_history=False)
    _save(output, 'MAIN_LOCAL_SCALES.npz', runtime, **bank.scale_arrays())
    normal_rows = [rows[int(i)] for i in normals]
    attack_rows = [rows[int(i)] for i in attacks]
    def view(ix, values, columns=None):
        return indexed.IndexedMatrix(values, indices[ix], columns) if columns else indexed.IndexedMatrix(values, indices[ix])
    runtime.checkpoint('MAIN_CAL_DUAL_SUPPORT')
    normal_result = bank.own(normal_rows, view(normals, features, slice(0,768)), view(normals, q))
    attack_matrix = bank.matrix(attack_rows, view(attacks, features, slice(0,768)), view(attacks, q))
    own, masks, score, safety = {}, {}, {}, {}
    raw = np.column_stack((logits, metrics.ensemble(logits, mode='target')))
    require(np.array_equal(raw > cuts, original_decisions), 'MAIN_RAW_DECISION_PARITY')
    for arm in ('d0', 'local'):
        own[arm], masks[arm] = _dual_own(rows, normals, attacks, normal_result, attack_matrix, arm)
        score[arm] = metrics.apply_correction(logits, own[arm], scales['scales'], .25, mode='target')
        scenarios = metrics.scenario_scores(logits[attacks], attack_matrix[arm],
                    attack_matrix['eligible_' + arm], scales['scales'], .25, mode='target')
        safety[arm] = scenarios['safety']
        _save(output, 'MAIN_CAL_' + arm.upper() + '_ATTACK_SCENARIOS.npz', runtime,
              uid=np.asarray([r['uid'] for r in attack_rows]), support=attack_matrix[arm],
              eligible=attack_matrix['eligible_' + arm], donor=scenarios['donor'],
              safety=scenarios['safety'], raw=scenarios['raw'])
    measured = dict(own_corrected_logits_sha256=array_sha(score['d0'][:,:3]),
                    own_decisions_sha256=array_sha(score['d0'] > cuts),
                    eligible_matrix_sha256=array_sha(attack_matrix['eligible_d0']))
    runtime.write_json('MAIN_D0_PARITY.json', dict(measured=measured, expected=dense.ANCHORS))
    require(measured == dense.ANCHORS, 'MAIN_D0_NUMERIC_ANCHOR')
    checks = {arm: metrics.calibration_check(raw[attacks], safety[arm], cuts)
              for arm in ('d0', 'local')}
    _save(output, 'MAIN_CAL_SCORES.npz', runtime, uid=np.asarray([r['uid'] for r in rows]),
          raw=raw, d0=score['d0'], local=score['local'], support_d0=own['d0'],
          support_local=own['local'], eligible_d0=masks['d0'], eligible_local=masks['local'], cuts=cuts)
    runtime.write_json('MAIN_CAL_CHECK.json', checks)
    require(all(sha(root/k) == v for k,v in identities.items()), 'MAIN_INPUT_CHANGED')
    return dict(checks=checks, parameters=dict(cuts=cuts, geometry=geometry, scales=scales['scales'],
                                             normalizer=normalizer), identities=identities)


def _pin_manifest_assets(root, spec, identities):
    for section in ('query', 'dense_bank'):
        for value in spec[section].values():
            if isinstance(value, dict) and 'path' in value and 'sha256' in value:
                path = resolve_asset(root, value['path'])
                digest = sha(path)
                require(digest == value['sha256'], 'TARGET_MANIFEST_ASSET:' + str(path))
                identities[path.relative_to(root).as_posix()] = digest


def _baseline_report(rows, denominator, decisions):
    labels = np.asarray([r['label'] for r in rows])
    w = 1./np.asarray(denominator, dtype=np.float64)
    result = {}
    for j, suffix in enumerate(('27','127','227','ensemble')):
        normal, attack = labels == 0, labels == 1
        pred = decisions[:,j]
        result[suffix] = dict(FP=int(np.sum(normal & pred)), TP=int(np.sum(attack & pred)),
                             FN=int(np.sum(attack & ~pred)),
                             weighted_FPR=math.fsum(w[normal & pred])/math.fsum(w[normal]),
                             weighted_recall=math.fsum(w[attack & pred])/math.fsum(w[attack]))
    return result


def run_target(root, output, runtime, source_result):
    # Gate before importing target helpers or opening any A/B input.
    prior, receipt = verify_predecessor(source_result)
    root, output = Path(root).resolve(), Path(output).resolve()
    runtime.write_json('PREDECESSOR.json', dict(result_sha256=sha(source_result),
                       elapsed_seconds=receipt['elapsed_seconds'], scientific_status=prior['scientific_status']))
    legacy = load_legacy(root)
    main = main_calibration(root, output, runtime, legacy)
    if not all(c['pass'] for c in main['checks'].values()):
        return dict(status='COMPLETE', scientific_status='MAIN_CAL_SAFETY_FAIL',
                    spec_sha256=SPEC_SHA, target_evaluations=0, cal_checks=main['checks'])
    from .geometry import DualBank
    from . import metrics
    target = legacy['target_data']
    identity = target._verify_assets(root)
    identities = dict(identity['target_inputs'])
    manifest = read_json(root/target.MANIFEST)
    historical = read_json(root/target.MATRIX/'RESULT.json')
    params = main['parameters']
    primary, reports = {}, {}
    for spec in manifest['pools']:
        pool = spec['pool_id']
        require(pool in ('CIC_DEV', 'UNSW_DEV'), 'UNREGISTERED_TARGET_POOL')
        _pin_manifest_assets(root, spec, identities)
        runtime.checkpoint('TARGET_INPUTS', pool=pool)
        rows, phases, saved, denominator, post = target.load_pool(root, pool, spec)
        own = saved['own']
        require(np.array_equal(params['cuts'], np.r_[own['cuts'], own['ensemble_cut']]), 'TARGET_CUT_MISMATCH')
        ref_path = resolve_asset(root, spec['dense_bank']['rows']['path'])
        references = legacy['dense_source'].load_rows(ref_path)
        bank_path = resolve_asset(root, spec['dense_bank']['e3']['path'])
        with np.load(bank_path, allow_pickle=False) as z:
            refs = {k:z[k].copy() for k in ('uid','e3','q14')}
        require(len(references) == spec['dense_rows'] == len(refs['uid']) and
                [r['uid'] for r in references] == refs['uid'].tolist() and
                uid_sha(refs['uid']) == spec['dense_bank']['expected_ordered_uid_sha256'], 'TARGET_REFERENCE_UID_BINDING')
        query = spec['query']
        require(uid_sha(r['uid'] for r in rows) == query['feature_uid_sha256'] == query['q_uid_sha256'],
                'TARGET_QUERY_VECTOR_UID_BINDING')
        feature = np.load(resolve_asset(root, query['e3']['path']), mmap_mode='r', allow_pickle=False)
        q = np.load(resolve_asset(root, query['q14']['path']), mmap_mode='r', allow_pickle=False)
        bank = DualBank(references, refs['e3'], refs['q14'], params['normalizer'], params['geometry'],
                        core=legacy['core'], counter=runtime.add_pairs, checkpoint=runtime.checkpoint,
                        allow_prebank_history=True)
        _save(output, pool+'_LOCAL_SCALES.npz', runtime, **bank.scale_arrays())
        ix = np.arange(len(rows), dtype=np.int64)
        support = bank.own(rows, legacy['indexed'].IndexedMatrix(feature, ix, slice(0,768)), q)
        require(np.array_equal(support['d0'], own['support']) and
                np.array_equal(support['eligible_d0'], own['eligible']), 'TARGET_D0_SUPPORT_PARITY')
        raw = np.column_stack((own['raw_logits'], own['raw_ensemble_logits']))
        d0 = metrics.apply_correction(own['raw_logits'], support['d0'], params['scales'], .25, mode='target')
        local = metrics.apply_correction(own['raw_logits'], support['local'], params['scales'], .25, mode='target')
        require(np.array_equal(d0, np.column_stack((own['corrected_logits'], own['corrected_ensemble_logits']))),
                'TARGET_D0_SCORE_PARITY')
        views, parity = {}, {}
        for view, mask in (('full', np.ones(len(rows), bool)), ('post_window_primary', post)):
            vi = np.flatnonzero(mask)
            rr = [rows[int(i)] for i in vi]
            dd = denominator if view == 'full' else target.target_denominators(rr, pool)
            parity[view] = target.verify_d0_view(rr, dd, _baseline_report(rr, dd, own['corrected'][vi]),
                historical['pools'][pool]['arms']['R-DENSE']['0.1']['views'][view])
            views[view] = metrics.evaluate_population(name=pool, rows=rr, weights=1./dd.astype(np.float64),
                raw=raw[vi], d0=d0[vi], local=local[vi], cuts=params['cuts'], phases=phases[vi],
                branches=support['branch'][vi], mode='target', denominators=dd)
        _save(output, pool+'_SCORES.npz', runtime, uid=own['uid'], raw=raw, d0=d0, local=local,
              support_d0=support['d0'], support_local=support['local'], eligible_d0=support['eligible_d0'],
              eligible_local=support['eligible_local'], branch=np.asarray(support['branch'], dtype='<U8'), phase=phases, post_window=post)
        runtime.write_json(pool+'_REPORT.json', dict(views=views, D0_parity=parity))
        primary[pool] = views['post_window_primary']
        reports[pool] = {'report':pool+'_REPORT.json', 'sha256':sha(output/(pool+'_REPORT.json'))}
    require(set(primary) == {'CIC_DEV','UNSW_DEV'}, 'TARGET_COMPLETENESS')
    gate = metrics.target_gate(primary)
    runtime.write_json('TARGET_INPUT_SEAL.json', identities)
    require(all(sha(root/path) == digest for path,digest in identities.items()), 'TARGET_INPUT_DRIFT')
    return dict(status='COMPLETE', scientific_status='TARGET_GOAL_PASS' if gate['pass'] else 'TARGET_GOAL_FAIL',
                spec_sha256=SPEC_SHA, gate=gate, pools=reports, target_evaluations=2,
                new_training=0, new_encoding=0, new_head_forwards=0, independent_confirmation=False,
                third_pool_deferred=True, attribution_claim=False, automatic_retry=False)
