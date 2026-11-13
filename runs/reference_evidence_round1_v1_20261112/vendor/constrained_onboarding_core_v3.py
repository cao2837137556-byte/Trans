"""Fixed, source-calibrated normal-reference correction; no I/O or model training.

Arrays are joined by explicit ordered UIDs. The caller additionally verifies the
RECENT feature version, q14 adapter receipt, and original source normalizer hash.
This module never infers provenance from a feature shape or a successful test.
"""
import hashlib
import math
from collections import defaultdict

import numpy as np
from indexed_features_v1 import matrix, IndexedMatrix

from legacy_qref_data_v1 import class_weights, weights as training_weights


SEEDS = (27, 127, 227)
PROTOCOLS = (6, 17)
LAMBDAS = (0.0, 0.05, 0.1, 0.25)
# HOLDOUT is an input role only, for the already-consumed three-device replay.
# This math module never loads data; the runner restricts the named replay pool.
PARTITIONS = ('LEARN', 'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION', 'HOLDOUT')
BLOCK_ROWS = 1024
PAIR_BUDGET = 65536


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _uid_hash(uids):
    return hashlib.sha256(('\n'.join(uids) + '\n').encode('utf-8')).hexdigest()


def _rows(rows, reference=False):
    seen = set()
    for r in rows:
        require(isinstance(r.get('uid'), str) and r['uid'] and r['uid'] not in seen,
                'EMPTY_OR_DUPLICATE_UID')
        seen.add(r['uid'])
        require(r.get('partition') in PARTITIONS and r.get('protocol') in PROTOCOLS,
                'ROLE_OR_PROTOCOL')
        require(all(isinstance(r.get(f), str) and r[f] for f in
                    ('device', 'component_id', 'capture_id')), 'METADATA_IDENTITY')
        require(isinstance(r.get('timestamp'), (int, float)) and
                math.isfinite(r['timestamp']) and type(r.get('frame')) is int and
                r['frame'] > 0, 'METADATA_TIME_FRAME')
        require('use' in r, 'MISSING_ROLE')
        if reference:
            require(r['use'] == 'REFERENCE' and r.get('label') == 0, 'REFERENCE_ROLE')
            require(isinstance(r.get('reference_end'), (int, float)) and
                    math.isfinite(r['reference_end']) and
                    r['timestamp'] <= r['reference_end'], 'REFERENCE_END')
        else:
            require(r['use'] != 'REFERENCE', 'QUERY_ROLE')


def _joined(rows, e3, q14, feature_uids, q_uids):
    require(feature_uids is not None and q_uids is not None, 'ORDERED_UIDS_REQUIRED')
    expected = [r['uid'] for r in rows]
    require(list(feature_uids) == expected and list(q_uids) == expected,
            'BROKEN_FEATURE_UID_JOIN')
    e3, q14 = matrix(e3), matrix(q14)
    require(e3.shape == (len(rows), 768) and q14.shape == (len(rows), 14),
            'FEATURE_SHAPE')
    require(e3.dtype.kind in 'fiu' and q14.dtype.kind in 'fiu', 'FEATURE_DTYPE')
    for start in range(0, len(rows), BLOCK_ROWS):
        z, q = e3[start:start + BLOCK_ROWS], q14[start:start + BLOCK_ROWS]
        require(np.isfinite(z).all() and np.isfinite(q).all(), 'NONFINITE_FEATURE')
        require(np.all((q >= 0) & (q <= 1)), 'Q14_RANGE')
    return e3, q14


def _normalizer(normalizer):
    require(len(normalizer) == 2, 'NORMALIZER_SCHEMA')
    mean, scale = (np.asarray(v, dtype=np.float64).copy() for v in normalizer)
    require(mean.shape == scale.shape == (768,) and np.isfinite(mean).all() and
            np.isfinite(scale).all() and np.all(scale > 0), 'NORMALIZER_SCHEMA')
    return mean, scale


def _unit(e3, normalizer):
    mean, scale = normalizer
    x = (np.asarray(e3, dtype=np.float64) - mean) / scale
    norms = np.linalg.norm(x, axis=1)
    require(np.isfinite(x).all() and np.isfinite(norms).all() and np.all(norms > 0),
            'NONFINITE_OR_ZERO_NORM_E3')
    return x / norms[:, None]


def weighted_quantile(values, weights, probability):
    """Lowest observed value attaining the normalized cumulative mass."""
    x, w = np.asarray(values, dtype=np.float64), np.asarray(weights, dtype=np.float64)
    require(x.ndim == w.ndim == 1 and len(x) == len(w) > 0 and
            np.isfinite(x).all() and np.isfinite(w).all() and np.all(w > 0) and
            0 <= probability <= 1, 'QUANTILE_INPUT')
    order = np.argsort(x, kind='stable')
    cumulative = np.cumsum(w[order] / math.fsum(w), dtype=np.float64)
    cumulative[-1] = 1.0
    index = min(int(np.searchsorted(cumulative, probability, side='left')), len(x)-1)
    return float(x[order[index]])


def _radius(geometry, protocol):
    require(isinstance(geometry, dict) and 'protocols' in geometry, 'GEOMETRY_SCHEMA')
    protocols = geometry['protocols']
    item = protocols.get(str(protocol), protocols.get(protocol))
    require(item is not None, 'GEOMETRY_PROTOCOL_MISSING')
    require(item.get('status') in ('READY', 'NO_SOURCE_GEOMETRY_SUPPORT'), 'GEOMETRY_STATUS')
    if item['status'] != 'READY':
        return None
    radii = float(item['rho_z']), float(item['rho_q'])
    require(all(math.isfinite(v) and v >= 0 for v in radii), 'GEOMETRY_RADIUS')
    return radii


def _ratio(distance, radius):
    if radius == 0:
        return np.where(distance == 0, 0.0, np.inf)
    return distance / radius


def _second_distinct(distance, components):
    """Return first/second distinct-component representatives with UID-stable ties."""
    groups = defaultdict(list)
    for i, component in enumerate(components):
        groups[component].append(i)
    require(len(groups) >= 2, 'SECOND_COMPONENT_REQUIRED')
    minima, representatives = [], []
    for ix in groups.values():
        local = np.argmin(distance[:, ix], axis=1)
        representative = np.asarray(ix)[local]
        minima.append(distance[np.arange(len(distance)), representative])
        representatives.append(representative)
    reduced = np.stack(minima, axis=1)
    chosen = np.argsort(reduced, axis=1, kind='stable')[:, :2]
    representatives = np.stack(representatives, axis=1)
    best = np.take_along_axis(representatives, chosen, axis=1)
    return np.take_along_axis(reduced, chosen[:, 1:2], axis=1).ravel(), best


class ReferenceBank:
    """A fixed bank retaining the complete device cutoff, including donor subsets.

    Source donor use is available only through matrix(). Own-bank inference is
    partition/device/protocol isolated. Explicit overrides are diagnostic controls;
    their time/protocol/count matching is validated by the control-plan caller.
    """

    def __init__(self, rows, e3, q14, normalizer, *, feature_uids=None, q_uids=None,
                 allowed_partitions=None, allow_prebank_history=False):
        self.allow_prebank_history=allow_prebank_history
        self.rows = [dict(r) for r in rows]
        _rows(self.rows, reference=True)
        if allowed_partitions is not None:
            require(all(r['partition'] in allowed_partitions for r in self.rows),
                    'REFERENCE_PARTITION')
        self.normalizer = _normalizer(normalizer)
        e3, q14 = _joined(self.rows, e3, q14, feature_uids, q_uids)
        self.z = _unit(e3[:] if isinstance(e3, IndexedMatrix) else e3, self.normalizer)
        self.q14 = np.asarray(q14[:] if isinstance(q14, IndexedMatrix) else q14, dtype=np.float64).copy()
        self.groups, self.ends, self.frame_ends, self.by_uid = {}, {}, {}, {}
        for i, r in enumerate(self.rows):
            device_key = (r['partition'], r['device'])
            require(self.ends.setdefault(device_key, r['reference_end']) ==
                    r['reference_end'], 'COMPLETE_BANK_END_MISMATCH')
            if 'bank_end_frame' in r:
                frame_end = r['bank_end_frame']
                require(type(frame_end) is int and frame_end >= r['frame'],
                        'COMPLETE_BANK_FRAME_END')
                capture_key = device_key + (r['capture_id'],)
                require(self.frame_ends.setdefault(capture_key, frame_end) == frame_end,
                        'COMPLETE_BANK_FRAME_END_MISMATCH')
            self.groups.setdefault(device_key + (r['protocol'],), []).append(i)
            self.by_uid[r['uid']] = i
        self.keys = sorted(self.groups)
        for key in self.keys:
            self.groups[key].sort(key=lambda i: self.rows[i]['uid'])

    def roster(self):
        return [dict(partition=key[0], device=key[1], protocol=key[2],
                     reference_end=self.ends[key[:2]],
                     bank_end_frames={capture_key[2]: end for capture_key, end in self.frame_ends.items()
                                      if capture_key[:2] == key[:2]},
                     reference_uids=[self.rows[i]['uid'] for i in self.groups[key]],
                     distinct_components=len({self.rows[i]['component_id']
                                              for i in self.groups[key]}))
                for key in self.keys]

    def _queries(self, rows, e3, q14, feature_uids, q_uids):
        _rows(rows)
        overlap=[r for r in rows if r['uid'] in self.by_uid]
        require(not overlap or self.allow_prebank_history, 'QUERY_IS_REFERENCE')
        if overlap:
            from causal_reference_overlap_v1 import require_prebank_history
            for r in overlap:require_prebank_history(r,self.rows[self.by_uid[r['uid']]])
        e3, q14 = _joined(rows, e3, q14, feature_uids, q_uids)
        # Even unsupported queries must fail on corrupt/zero normalized E3.
        for start in range(0, len(rows), BLOCK_ROWS):
            _unit(e3[start:start + BLOCK_ROWS], self.normalizer)
        return e3, q14

    @staticmethod
    def _empty(size):
        return dict(support=np.zeros(size, dtype=np.float64),
                    eligible=np.zeros(size, dtype=bool),
                    geometry_supported=np.zeros(size, dtype=bool),
                    reason=np.full(size, 'NO_REFERENCE_BANK', dtype=object),
                    second_dz=np.full(size, np.inf), second_dq=np.full(size, np.inf),
                    second_joint=np.full(size, np.inf),
                    matched_reference_uids=np.full((size, 2), None, dtype=object),
                    matched_components=np.full((size, 2), None, dtype=object),
                    same_component=np.zeros(size, dtype=bool),
                    legal_component_count=np.zeros(size, dtype=np.int64),
                    bank_end_frame=np.full(size, None, dtype=object),
                    bank_end=np.full(size, np.nan))

    def _evaluate_group(self, result, rows, e3, q14, query_ix, reference_ix,
                        geometry, raw_distances=False):
        if not reference_ix:
            return
        reference_ix = sorted(reference_ix, key=lambda i: self.rows[i]['uid'])
        refs = [self.rows[i] for i in reference_ix]
        donor_keys = {(r['partition'], r['device'], r['protocol']) for r in refs}
        require(len(donor_keys) == 1, 'MIXED_DONOR_BANK')
        donor = next(iter(donor_keys))
        require(all(rows[i]['partition'] == donor[0] and
                    rows[i]['protocol'] == donor[2] for i in query_ix), 'DONOR_PROTOCOL_PARTITION')
        end = self.ends[donor[:2]]
        components = [r['component_id'] for r in refs]
        radii = (1., 1.) if raw_distances else _radius(geometry, donor[2])
        result['bank_end'][query_ix] = end
        result['geometry_supported'][query_ix] = radii is not None
        # Frame condition is query-specific, even when timestamps alone pass.
        patterns = defaultdict(list)
        for i in query_ix:
            frame_end = self.frame_ends.get(donor[:2] + (rows[i]['capture_id'],))
            result['bank_end_frame'][i] = frame_end
            if not end < rows[i]['timestamp']:
                result['reason'][i] = 'BANK_NOT_YET_AVAILABLE'
                continue
            if frame_end is not None and rows[i]['frame'] <= frame_end:
                result['reason'][i] = 'BANK_FRAME_NOT_YET_AVAILABLE'
                continue
            legal = tuple(j for j, r in enumerate(refs)
                          if r['capture_id'] != rows[i]['capture_id'] or
                          r['frame'] < rows[i]['frame'])
            count = len({components[j] for j in legal})
            result['legal_component_count'][i] = count
            result['same_component'][i] = rows[i]['component_id'] in {
                components[j] for j in legal}
            if count < 2:
                result['reason'][i] = 'FEWER_THAN_TWO_LEGAL_COMPONENTS'
                continue
            result['eligible'][i] = True
            result['reason'][i] = ('NO_SOURCE_GEOMETRY_SUPPORT' if radii is None
                                   else 'ELIGIBLE_ZERO_SUPPORT')
            # Preserve distances for missing source geometry too, for audit.
            patterns[legal].append(i)
        for legal, ix in patterns.items():
            indices = np.asarray([reference_ix[j] for j in legal])
            comp = [components[j] for j in legal]
            chunk_size = max(1, min(BLOCK_ROWS, PAIR_BUDGET // len(indices)))
            for start in range(0, len(ix), chunk_size):
                use = np.asarray(ix[start:start + chunk_size], dtype=np.int64)
                z = _unit(e3[use], self.normalizer)
                dz = np.clip(1. - z @ self.z[indices].T, 0., 2.)
                delta = (np.asarray(q14[use], dtype=np.float64)[:, None, :] -
                         self.q14[indices][None, :, :])
                dq = np.sqrt(np.mean(delta * delta, axis=2))
                result['second_dz'][use], _ = _second_distinct(dz, comp)
                result['second_dq'][use], _ = _second_distinct(dq, comp)
                if radii is None:
                    continue
                joint = np.maximum(_ratio(dz, radii[0]), _ratio(dq, radii[1]))
                second, best = _second_distinct(joint, comp)
                support = np.clip(1. - second, 0., 1.)
                result['second_joint'][use] = second
                result['support'][use] = support
                result['reason'][use[support > 0]] = 'SUPPORTED'
                uid_array = np.asarray([self.rows[j]['uid'] for j in indices], dtype=object)
                result['matched_reference_uids'][use] = uid_array[best]
                result['matched_components'][use] = np.asarray(comp, dtype=object)[best]

    def own(self, rows, e3, q14, geometry, *, feature_uids=None, q_uids=None,
            override=None, _raw_distances=False):
        """Own bank or an explicitly pre-registered diagnostic donor UID map."""
        e3, q14 = self._queries(rows, e3, q14, feature_uids, q_uids)
        if not _raw_distances:
            for protocol in PROTOCOLS:
                _radius(geometry, protocol)
        result = self._empty(len(rows))
        groups = defaultdict(list)
        for i, r in enumerate(rows):
            groups[(r['partition'], r['device'], r['protocol'])].append(i)
        if override is not None:
            require(isinstance(override, dict), 'OVERRIDE_SCHEMA')
            for key, uids in override.items():
                require(isinstance(key, tuple) and len(key) == 3 and
                        len(uids) == len(set(uids)) and all(u in self.by_uid for u in uids),
                        'OVERRIDE_UID')
        for key, ix in groups.items():
            reference_ix = (self.groups.get(key, []) if override is None else
                            [self.by_uid[u] for u in override.get(key, [])])
            self._evaluate_group(result, rows, e3, q14, ix, reference_ix, geometry,
                                 raw_distances=_raw_distances)
        # Replay rows remain in the report, but cannot be corrected or matched
        # to any reference, including a diagnostic donor override.
        overlap_ix=[i for i,r in enumerate(rows) if r['uid'] in self.by_uid]
        if overlap_ix:
            require(not np.any(result['eligible'][overlap_ix]) and
                    np.all(result['support'][overlap_ix]==0) and
                    all(x is None for x in result['matched_reference_uids'][overlap_ix].flat),
                    'HISTORY_REPLAY_MUST_REMAIN_HEAD_ONLY')
        return result

    def matrix(self, rows, e3, q14, geometry, *, feature_uids=None, q_uids=None):
        """Source-only same-protocol donor matrix in deterministic roster order."""
        require(all(r['partition'] == 'LEARN' for r in self.rows) and
                all(r.get('partition') == 'LEARN' for r in rows), 'SOURCE_DONORS_ONLY')
        e3, q14 = self._queries(rows, e3, q14, feature_uids, q_uids)
        for protocol in PROTOCOLS:
            _radius(geometry, protocol)
        n, k = len(rows), len(self.keys)
        support, eligible = np.zeros((n, k)), np.zeros((n, k), dtype=bool)
        same = np.zeros((n, k), dtype=bool)
        for j, key in enumerate(self.keys):
            ix = [i for i, r in enumerate(rows) if r['protocol'] == key[2]]
            result = self._empty(n)
            self._evaluate_group(result, rows, e3, q14, ix, self.groups[key], geometry)
            support[:, j], eligible[:, j] = result['support'], result['eligible']
            same[:, j] = result['same_component']
        return dict(support=support, eligible=eligible, same_component=same,
                    roster=self.roster(), query_uid_sha256=_uid_hash([r['uid'] for r in rows]))


def fit_geometry(rows, e3, q14, source_bank, *, feature_uids=None, q_uids=None):
    require(len(rows) > 0 and all(r.get('partition') == 'LEARN' and
            r.get('fit_role') == 'FIT' and r.get('label') == 0 for r in rows),
            'GEOMETRY_FIT_NORMAL_ONLY')
    require(all(r['partition'] == 'LEARN' for r in source_bank.rows), 'SOURCE_BANK_ONLY')
    raw = source_bank.own(rows, e3, q14, None, feature_uids=feature_uids,
                          q_uids=q_uids, _raw_distances=True)
    answer = dict(version='constrained-onboarding-geometry-v1', protocols={},
                  fit_normal_uid_sha256=_uid_hash([r['uid'] for r in rows]),
                  source_roster=source_bank.roster(),
                  quantile=0.9, weight_rule='class_weights within eligible protocol subset')
    for protocol in PROTOCOLS:
        ix = [i for i, r in enumerate(rows) if r['protocol'] == protocol and raw['eligible'][i]]
        if not ix:
            answer['protocols'][str(protocol)] = dict(status='NO_SOURCE_GEOMETRY_SUPPORT', rows=0)
            continue
        eligible = [rows[i] for i in ix]
        w = class_weights(eligible)
        answer['protocols'][str(protocol)] = dict(
            status='READY', rows=len(ix), devices=sorted({r['device'] for r in eligible}),
            eligible_uid_sha256=_uid_hash([r['uid'] for r in eligible]),
            rho_z=weighted_quantile(raw['second_dz'][ix], w, .9),
            rho_q=weighted_quantile(raw['second_dq'][ix], w, .9),
            weight_sum=float(math.fsum(w)))
    return answer


def _logits(logits, count, seed_order):
    require(tuple(seed_order) == SEEDS, 'FIXED_SEED_ORDER')
    if isinstance(logits, dict):
        normalized = {int(k): v for k, v in logits.items()}
        require(len(normalized) == len(logits) and set(normalized) == set(SEEDS), 'LOGIT_SEEDS')
        x = np.column_stack([normalized[s] for s in SEEDS]).astype(np.float64)
    else:
        x = np.asarray(logits, dtype=np.float64)
    require(x.shape == (count, 3) and np.isfinite(x).all(), 'LOGIT_SHAPE_FINITE')
    return x


def _scales(scales):
    if isinstance(scales, dict) and 'scales' in scales:
        scales = scales['scales']
    if isinstance(scales, dict):
        converted = {int(k): v for k, v in scales.items()}
        require(set(converted) == set(SEEDS) and len(converted) == len(scales), 'SCALE_SEEDS')
        scales = [converted[s] for s in SEEDS]
    result = np.asarray(scales, dtype=np.float64)
    require(result.shape == (3,) and np.isfinite(result).all() and np.all(result >= 0), 'SCALE_INPUT')
    return result


def fit_scales(rows, logits, seed_order=SEEDS):
    _rows(rows)
    require(len(rows) > 0 and all(r.get('partition') == 'LEARN' and r.get('fit_role') == 'FIT'
            and r.get('label') in (0, 1) for r in rows), 'SCALE_FIT_ONLY')
    x = _logits(logits, len(rows), seed_order)
    w = training_weights(rows)
    quantiles = [(weighted_quantile(x[:, j], w, .1), weighted_quantile(x[:, j], w, .9))
                 for j in range(3)]
    return dict(version='constrained-onboarding-scales-v1', seed_order=list(SEEDS),
                scales=[high-low for low, high in quantiles],
                q10=[low for low, _ in quantiles], q90=[high for _, high in quantiles],
                fit_uid_sha256=_uid_hash([r['uid'] for r in rows]), rows=len(rows),
                normal_weight=float(math.fsum(w[[r['label'] == 0 for r in rows]])),
                attack_weight=float(math.fsum(w[[r['label'] == 1 for r in rows]])))


def apply_correction(logits, support, scales, lambda_value, seed_order=SEEDS):
    a = np.asarray(support, dtype=np.float64)
    require(a.ndim == 1 and np.isfinite(a).all() and np.all((a >= 0) & (a <= 1)),
            'SUPPORT_RANGE')
    require(lambda_value in LAMBDAS, 'UNREGISTERED_LAMBDA')
    x, s = _logits(logits, len(a), seed_order), _scales(scales)
    result = x.copy()
    if lambda_value == 0:
        return result
    active = a > 0
    for j in range(3):
        if s[j] > 0:
            result[active, j] = x[active, j] - float(lambda_value) * s[j] * a[active]
    require(np.isfinite(result).all(), 'CORRECTION_NONFINITE')
    return result


def ordered_ensemble(logits, seed_order=SEEDS):
    count = len(next(iter(logits.values()))) if isinstance(logits, dict) else len(logits)
    x = _logits(logits, count, seed_order)
    # Preserve the legacy stack/axis layout as well as the addition order.
    # A row-major N x 3 reduction need not follow the same numerical path.
    with np.errstate(over='ignore', invalid='ignore'):
        result = np.stack([x[:, j] for j in range(3)]).mean(0, dtype=np.float64)
    require(np.isfinite(result).all(), 'ENSEMBLE_NONFINITE')
    return result


def _cuts(cuts):
    if isinstance(cuts, dict):
        converted = {int(k): v for k, v in cuts.items()}
        require(set(converted) == set(SEEDS) and len(converted) == len(cuts), 'CUT_SEEDS')
        cuts = [converted[s] for s in SEEDS]
    result = np.asarray(cuts, dtype=np.float64)
    require(result.shape == (3,) and np.isfinite(result).all(), 'CUT_INPUT')
    return result


def choose_lambda(cal_attack_rows, logits, cuts, ensemble_cut, scales, source_bank,
                  e3, q14, geometry, *, feature_uids=None, q_uids=None, seed_order=SEEDS):
    """Protect every originally detected CAL attack, seed and ordered ensemble.

    All registered original source banks are checked. The receipt distinguishes
    positive support from actual/cap-reachable withdrawals; source saturation is
    evidence about calibration power, never a target-safety guarantee.
    """
    rows = cal_attack_rows
    require(len(rows) > 0 and all(r.get('partition') == 'LEARN' and
            r.get('fit_role') == 'CAL' and r.get('label') == 1 for r in rows),
            'PROTECTION_CAL_ATTACK_ONLY')
    source_components = {r['component_id'] for r in source_bank.rows}
    require(not source_components.intersection(r['component_id'] for r in rows),
            'CAL_REFERENCE_COMPONENT_LEAKAGE')
    x, s, cut = _logits(logits, len(rows), seed_order), _scales(scales), _cuts(cuts)
    require(math.isfinite(float(ensemble_cut)), 'ENSEMBLE_CUT')
    matrix = source_bank.matrix(rows, e3, q14, geometry,
                                feature_uids=feature_uids, q_uids=q_uids)
    a, eligible = matrix['support'], matrix['eligible']
    base = x > cut
    base_ensemble_logits = ordered_ensemble(x)
    base_ensemble = base_ensemble_logits > ensemble_cut
    receipts, selected = [], 0.0
    for candidate in LAMBDAS:
        missed = [set() for _ in range(4)]
        missed_pairs = [0] * 4
        minimum_ratios = [None] * 4
        cap_reachable = [set() for _ in range(4)]
        for j in range(a.shape[1]):
            corrected = apply_correction(x, a[:, j], s, candidate)
            alarms = corrected > cut
            ensemble = ordered_ensemble(corrected) > ensemble_cut
            positive = eligible[:, j] & (a[:, j] > 0)
            decisions = [base[:, k] & ~alarms[:, k] & eligible[:, j] for k in range(3)]
            decisions.append(base_ensemble & ~ensemble & eligible[:, j])
            for k, changed in enumerate(decisions):
                indices = np.flatnonzero(changed)
                missed[k].update(int(i) for i in indices)
                missed_pairs[k] += len(indices)
                baseline_alarm = base[:, k] if k < 3 else base_ensemble
                margin = x[:, k]-cut[k] if k < 3 else base_ensemble_logits-ensemble_cut
                cap = candidate * (s[k] if k < 3 else float(np.mean(s)))
                cap_reachable[k].update(int(i) for i in np.flatnonzero(
                    positive & baseline_alarm & (margin <= cap)))
                if cap > 0 and np.any(positive & baseline_alarm):
                    ratio = float(np.min(margin[positive & baseline_alarm] / cap))
                    minimum_ratios[k] = (ratio if minimum_ratios[k] is None else
                                         min(minimum_ratios[k], ratio))
        ok = not any(missed)
        if ok:
            selected = candidate
        names = [str(s) for s in SEEDS] + ['ensemble']
        receipts.append(dict(lambda_value=candidate, passes=ok,
            new_miss_count={name: len(missed[k]) for k, name in enumerate(names)},
            new_miss_pair_count={name: missed_pairs[k] for k, name in enumerate(names)},
            newly_missed_uids={name: [rows[i]['uid'] for i in sorted(missed[k])]
                              for k, name in enumerate(names)},
            cap_reachable_detected_attack_count={name: len(cap_reachable[k]) for k, name in enumerate(names)},
            minimum_positive_support_margin_over_cap={name: minimum_ratios[k] for k, name in enumerate(names)}))
    any_support = np.any(a > 0, axis=1)
    bank_coverage = []
    for j, item in enumerate(matrix['roster']):
        legal_count = int(eligible[:, j].sum())
        status = ('FEWER_THAN_TWO_COMPONENTS' if item['distinct_components'] < 2 else
                  'NO_LEGAL_CAL_ATTACK_PAIRS' if legal_count == 0 else
                  'NO_SOURCE_GEOMETRY_SUPPORT' if _radius(geometry, item['protocol']) is None else
                  'LEGAL_PAIRS_NO_POSITIVE_SUPPORT' if not np.any(a[:, j] > 0) else
                  'LEGAL_PAIRS_WITH_SUPPORT')
        bank_coverage.append(dict(partition=item['partition'], device=item['device'],
                                  protocol=item['protocol'], status=status,
                                  eligible_pairs=legal_count,
                                  positive_support_pairs=int((a[:, j] > 0).sum())))
    coverage_status = ('NO_ELIGIBLE_PAIRS' if not np.any(eligible) else
                       'NO_POSITIVE_SUPPORT' if not np.any(any_support) else
                       'OBSERVED_WITH_SUPPORT')
    return dict(version='constrained-onboarding-source-protection-v1', selected_lambda=selected,
                seed_order=list(SEEDS), candidates=receipts, roster=matrix['roster'],
                coverage_status=coverage_status, bank_coverage=bank_coverage,
                candidate_pass_means='zero observed added CAL misses; never coverage or target safety',
                cal_attack_rows=len(rows), cal_attack_uid_sha256=matrix['query_uid_sha256'],
                eligible_pairs=int(eligible.sum()), positive_support_pairs=int((a > 0).sum()),
                attack_rows_with_support=int(any_support.sum()),
                attack_support_share=float(any_support.mean()),
                validity_matrix_sha256=hashlib.sha256(eligible.tobytes(order='C')).hexdigest(),
                source_zero_misses_is_target_guarantee=False)
