"""Causal reference selection and fixed inputs for learned onboarding V1.

This module performs no I/O, fitting, or inference. Ordered UID joins and the
historical replay exception are checked before any reference computation.
"""

import math
import sys
from pathlib import Path

import numpy as np


PROTOCOLS = (6, 17)
PARTITIONS = ('LEARN', 'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION', 'HOLDOUT')
QUERY_BATCH = 256
REFERENCE_BLOCK = 64


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _check_rows(rows, reference=False):
    seen = set()
    for row in rows:
        uid = row.get('uid')
        require(isinstance(uid, str) and uid and uid not in seen,
                'EMPTY_OR_DUPLICATE_UID')
        seen.add(uid)
        require(row.get('partition') in PARTITIONS and
                row.get('protocol') in PROTOCOLS, 'ROLE_OR_PROTOCOL')
        require(all(isinstance(row.get(k), str) and row[k] for k in
                    ('device', 'component_id', 'capture_id')), 'METADATA_IDENTITY')
        require(type(row.get('frame')) is int and row['frame'] > 0 and
                type(row.get('timestamp')) in (int, float) and
                math.isfinite(row['timestamp']), 'METADATA_TIME_FRAME')
        require('use' in row, 'MISSING_ROLE')
        if reference:
            require(row['use'] == 'REFERENCE' and row.get('label') == 0,
                    'REFERENCE_ROLE')
            end = row.get('reference_end')
            require(type(end) in (int, float) and math.isfinite(end) and
                    row['timestamp'] <= end, 'REFERENCE_END')
            if 'bank_end_frame' in row:
                require(type(row['bank_end_frame']) is int and
                        row['bank_end_frame'] >= row['frame'],
                        'COMPLETE_BANK_FRAME_END')
        else:
            require(row['use'] != 'REFERENCE', 'QUERY_ROLE')


def _joined(rows, e3, q14, feature_uids, q_uids):
    expected = [r['uid'] for r in rows]
    require(feature_uids is not None and q_uids is not None,
            'ORDERED_UIDS_REQUIRED')
    require(list(feature_uids) == expected and list(q_uids) == expected,
            'BROKEN_FEATURE_UID_JOIN')
    e3, q14 = np.asarray(e3), np.asarray(q14)
    require(e3.shape == (len(rows), 768) and q14.shape == (len(rows), 14),
            'FEATURE_SHAPE')
    require(e3.dtype.kind in 'fiu' and q14.dtype.kind in 'fiu',
            'FEATURE_DTYPE')
    for start in range(0, len(rows), QUERY_BATCH):
        x, q = e3[start:start + QUERY_BATCH], q14[start:start + QUERY_BATCH]
        require(np.isfinite(x).all() and np.isfinite(q).all(),
                'NONFINITE_FEATURE')
        require(np.all((q >= 0) & (q <= 1)), 'Q14_RANGE')
    return e3, np.asarray(q14, dtype=np.float64)


def _normalizer(normalizer):
    require(len(normalizer) == 2, 'NORMALIZER_SCHEMA')
    mean, scale = (np.asarray(x, dtype=np.float64).copy() for x in normalizer)
    require(mean.shape == scale.shape == (768,) and
            np.isfinite(mean).all() and np.isfinite(scale).all() and
            np.all(scale > 0), 'NORMALIZER_SCHEMA')
    return mean, scale


def _unit(e3, normalizer):
    mean, scale = normalizer
    x = (np.asarray(e3, dtype=np.float64) - mean) / scale
    norm = np.linalg.norm(x, axis=1)
    require(np.isfinite(x).all() and np.isfinite(norm).all() and
            np.all(norm > 0), 'NONFINITE_OR_ZERO_NORM_E3')
    return x / norm[:, None]


def _possible(indices, rows, selected_components, need_rows, need_components):
    if need_rows < 0 or need_components < 0:
        return False
    capacities = {}
    for ix in indices:
        component = rows[ix]['component_id']
        capacities[component] = capacities.get(component, 0) + 1
    reachable = {(0, 0)}
    for component, capacity in capacities.items():
        increment = 0 if component in selected_components else 1
        next_reachable = set()
        for count, distinct in reachable:
            for take in range(min(capacity, need_rows - count) + 1):
                new_distinct = distinct + (increment if take else 0)
                if new_distinct <= need_components:
                    next_reachable.add((count + take, new_distinct))
        reachable = next_reachable
    return (need_rows, need_components) in reachable


class ReferenceBank:
    """One immutable collection of complete device banks and their cutoffs."""

    def __init__(self, rows, e3, q14, normalizer, *, feature_uids,
                 q_uids, allow_target_prebank=False):
        self.rows = [dict(r) for r in rows]
        _check_rows(self.rows, reference=True)
        self.normalizer = _normalizer(normalizer)
        e3, q14 = _joined(self.rows, e3, q14, feature_uids, q_uids)
        self.z = np.empty((len(rows), 768), dtype=np.float64)
        for start in range(0, len(rows), QUERY_BATCH):
            stop = min(start + QUERY_BATCH, len(rows))
            self.z[start:stop] = _unit(e3[start:stop], self.normalizer)
        self.q14 = q14.copy()
        self.by_uid = {}
        self.groups = {}
        self.ends = {}
        self.frame_ends = {}
        self.allow_target_prebank = bool(allow_target_prebank)
        frame_presence = {}
        for ix, row in enumerate(self.rows):
            device_key = (row['partition'], row['device'])
            key = device_key + (row['protocol'],)
            end = self.ends.setdefault(device_key, row['reference_end'])
            require(end == row['reference_end'], 'COMPLETE_BANK_END_MISMATCH')
            frame_key = device_key + (row['capture_id'],)
            present = 'bank_end_frame' in row
            require(frame_presence.setdefault(frame_key, present) == present,
                    'INCOMPLETE_BANK_FRAME_END')
            if present:
                frame_end = self.frame_ends.setdefault(
                    frame_key, row['bank_end_frame'])
                require(frame_end == row['bank_end_frame'],
                        'COMPLETE_BANK_FRAME_END_MISMATCH')
            self.groups.setdefault(key, []).append(ix)
            self.by_uid[row['uid']] = ix
        for indices in self.groups.values():
            indices.sort(key=lambda i: self.rows[i]['uid'])
        self.keys = sorted(self.groups)

    def _query_audits(self, rows):
        _check_rows(rows)
        audits = [None] * len(rows)
        for i, row in enumerate(rows):
            ref_ix = self.by_uid.get(row['uid'])
            if ref_ix is None:
                continue
            require(row['partition'] != 'LEARN' and self.allow_target_prebank,
                    'QUERY_IS_REFERENCE')
            module_dir = Path(__file__).resolve().parents[3] / 'repo' / 'ood'
            if str(module_dir) not in sys.path:
                sys.path.insert(0, str(module_dir))
            from causal_reference_overlap_v1 import require_prebank_history
            audits[i] = require_prebank_history(row, self.rows[ref_ix])
        return audits

    def _queries(self, rows, e3, q14, feature_uids, q_uids):
        audits = self._query_audits(rows)
        e3, q14 = _joined(rows, e3, q14, feature_uids, q_uids)
        z = np.empty((len(rows), 768), dtype=np.float64)
        for start in range(0, len(rows), QUERY_BATCH):
            stop = min(start + QUERY_BATCH, len(rows))
            z[start:stop] = _unit(e3[start:stop], self.normalizer)
        return z, q14, audits

    def qualification(self, rows):
        """Metadata-only own-bank eligibility for a sealed WRONG control plan."""
        rows = list(rows)
        audits = self._query_audits(rows)
        out = self._empty(len(rows))
        for i, row in enumerate(rows):
            if audits[i] is not None:
                out['prebank_audit'][i] = audits[i]
                out['reason'][i] = 'PREBANK_HISTORY_HEAD_ONLY'
                continue
            key = (row['partition'], row['device'], row['protocol'])
            out['bank_key'][i] = key
            legal, end, frame_end, reason = self._legal(row, key)
            if end is not None:
                out['bank_end'][i], out['bank_end_frame'][i] = end, frame_end
            if reason is not None:
                out['reason'][i] = reason
                continue
            count = len({self.rows[j]['component_id'] for j in legal})
            out['legal_reference_count'][i], out['legal_component_count'][i] = len(legal), count
            out['eligible'][i] = count >= 2
            out['reason'][i] = 'ELIGIBLE' if count >= 2 else 'FEWER_THAN_TWO_LEGAL_COMPONENTS'
        return out

    def _legal(self, row, key, allowed_uids=None):
        require(row['partition'] == key[0] and row['protocol'] == key[2],
                'DONOR_PROTOCOL_PARTITION')
        if key not in self.groups:
            return None, None, None, 'NO_REFERENCE_BANK'
        end = self.ends[key[:2]]
        frame_end = self.frame_ends.get(key[:2] + (row['capture_id'],))
        if not end < row['timestamp']:
            return [], end, frame_end, 'BANK_NOT_YET_AVAILABLE'
        if frame_end is not None and row['frame'] <= frame_end:
            return [], end, frame_end, 'BANK_FRAME_NOT_YET_AVAILABLE'
        indices = self.groups[key]
        if allowed_uids is not None:
            require(len(allowed_uids) == len(set(allowed_uids)) and
                    all(uid in self.by_uid and self.by_uid[uid] in indices
                        for uid in allowed_uids), 'REFERENCE_SUBSET_UID')
            allowed = set(allowed_uids)
            indices = [i for i in indices if self.rows[i]['uid'] in allowed]
        legal = [i for i in indices if
                 self.rows[i]['capture_id'] != row['capture_id'] or
                 self.rows[i]['frame'] < row['frame']]
        return legal, end, frame_end, None

    @staticmethod
    def _empty(size):
        return dict(eligible=np.zeros(size, dtype=bool),
                    reason=np.full(size, 'NO_REFERENCE_BANK', dtype=object),
                    legal_reference_count=np.zeros(size, dtype=np.int64),
                    legal_component_count=np.zeros(size, dtype=np.int64),
                    matched_reference_uids=np.full((size, 2), None, dtype=object),
                    matched_components=np.full((size, 2), None, dtype=object),
                    dz=np.full((size, 2), np.inf, dtype=np.float64),
                    dq=np.full((size, 2), np.inf, dtype=np.float64),
                    d=np.full((size, 2), np.inf, dtype=np.float64),
                    qref=np.zeros((size, 2, 14), dtype=np.float64),
                    bank_end=np.full(size, np.nan, dtype=np.float64),
                    bank_end_frame=np.full(size, None, dtype=object),
                    bank_key=np.full(size, None, dtype=object),
                    prebank_audit=np.full(size, None, dtype=object))

    def trace(self, query_rows, e3, q14, *, feature_uids, q_uids,
              donor_keys=None, reference_uids=None, query_batch=QUERY_BATCH,
              reference_block=REFERENCE_BLOCK):
        """Trace own or explicit donor banks; subsets retain complete cutoffs."""
        rows = list(query_rows)
        z, q14, audits = self._queries(rows, e3, q14, feature_uids, q_uids)
        n = len(rows)
        require(type(query_batch) is int and query_batch > 0 and
                type(reference_block) is int and reference_block > 0, 'TRACE_BATCH_SIZE')
        if donor_keys is not None:
            require(len(donor_keys) == n, 'DONOR_KEYS_LENGTH')
        if reference_uids is not None:
            require(len(reference_uids) == n, 'REFERENCE_SUBSETS_LENGTH')
        out = self._empty(n)
        for start in range(0, n, query_batch):
            for i in range(start, min(start + query_batch, n)):
                row = rows[i]
                if audits[i] is not None:
                    out['prebank_audit'][i] = audits[i]
                    out['reason'][i] = 'PREBANK_HISTORY_HEAD_ONLY'
                    continue
                if donor_keys is not None and donor_keys[i] is None:
                    out['reason'][i] = 'NO_EXACT_WRONG_BANK'
                    continue
                key = ((row['partition'], row['device'], row['protocol'])
                       if donor_keys is None else tuple(donor_keys[i]))
                require(len(key) == 3, 'DONOR_KEY_SCHEMA')
                out['bank_key'][i] = key
                subset = None if reference_uids is None else reference_uids[i]
                legal, end, frame_end, reason = self._legal(row, key, subset)
                if end is not None:
                    out['bank_end'][i] = end
                    out['bank_end_frame'][i] = frame_end
                if reason is not None:
                    out['reason'][i] = reason
                    continue
                components = {self.rows[j]['component_id'] for j in legal}
                out['legal_reference_count'][i] = len(legal)
                out['legal_component_count'][i] = len(components)
                if len(components) < 2:
                    out['reason'][i] = 'FEWER_THAN_TWO_LEGAL_COMPONENTS'
                    continue
                # UID-sorted iteration and strict less-than updates make ties stable.
                best = {}
                for offset in range(0, len(legal), reference_block):
                    block = legal[offset:offset + reference_block]
                    ref_z = self.z[block]
                    dz = np.clip(1.0 - np.sum(ref_z * z[i], axis=1), 0.0, 2.0)
                    delta = self.q14[block] - q14[i]
                    dq = np.sqrt(np.mean(delta * delta, axis=1))
                    distances = np.maximum(dz / 2.0, dq)
                    for j, ref_ix in enumerate(block):
                        ref = self.rows[ref_ix]
                        component = ref['component_id']
                        candidate = (float(distances[j]), ref['uid'], component,
                                     ref_ix, float(dz[j]), float(dq[j]))
                        previous = best.get(component)
                        if previous is None or candidate[:2] < previous[:2]:
                            best[component] = candidate
                chosen = sorted(best.values(), key=lambda item: item[:3])[:2]
                out['eligible'][i] = True
                out['reason'][i] = 'ELIGIBLE'
                for k, item in enumerate(chosen):
                    distance, uid, component, ref_ix, dz, dq = item
                    out['matched_reference_uids'][i, k] = uid
                    out['matched_components'][i, k] = component
                    out['d'][i, k] = distance
                    out['dz'][i, k] = dz
                    out['dq'][i, k] = dq
                    out['qref'][i, k] = self.q14[ref_ix]
        return out

    def plan_wrong(self, query_rows, own_trace):
        """Metadata-only lexicographically first exact N-row/C-component control."""
        rows = list(query_rows)
        require(len(own_trace['eligible']) == len(rows), 'OWN_TRACE_LENGTH')
        keys, subsets, reasons = [], [], []
        for i, row in enumerate(rows):
            keys.append(None)
            subsets.append(None)
            reasons.append('OWN_INELIGIBLE')
            if not own_trace['eligible'][i]:
                continue
            n = int(own_trace['legal_reference_count'][i])
            c = int(own_trace['legal_component_count'][i])
            for key in self.keys:
                if (key[0] != row['partition'] or key[1] == row['device'] or
                        key[2] != row['protocol']):
                    continue
                legal, _, _, reason = self._legal(row, key)
                if reason is not None or not _possible(legal, self.rows, set(), n, c):
                    continue
                selected, selected_components = [], set()
                for pos, ref_ix in enumerate(legal):
                    if len(selected) == n:
                        break
                    component = self.rows[ref_ix]['component_id']
                    new_components = selected_components | {component}
                    if _possible(legal[pos + 1:], self.rows, new_components,
                                 n - len(selected) - 1, c - len(new_components)):
                        selected.append(ref_ix)
                        selected_components = new_components
                require(len(selected) == n and len(selected_components) == c,
                        'WRONG_SUBSET_INTERNAL')
                keys[i] = key
                subsets[i] = tuple(self.rows[j]['uid'] for j in selected)
                reasons[i] = 'MATCHED'
                break
            if keys[i] is None:
                reasons[i] = 'NO_EXACT_WRONG_BANK'
        return dict(donor_keys=keys, reference_uids=subsets, reason=reasons)


def make_features(rows, q14, scores, centers, scales, trace,
                  query_only=False):
    """Return fixed float32 inputs with all reference slots masked on demand."""
    n = len(rows)
    q = np.asarray(q14, dtype=np.float64)
    score = np.asarray(scores, dtype=np.float64)
    center = np.broadcast_to(np.asarray(centers, dtype=np.float64), (n,))
    scale = np.broadcast_to(np.asarray(scales, dtype=np.float64), (n,))
    require(q.shape == (n, 14) and score.shape == (n,) and
            np.isfinite(q).all() and np.all((q >= 0) & (q <= 1)) and
            np.isfinite(score).all() and np.isfinite(center).all() and
            np.isfinite(scale).all() and np.all(scale >= 0), 'FEATURE_INPUT')
    require(trace['qref'].shape == (n, 2, 14) and
            trace['dz'].shape == trace['dq'].shape == (n, 2) and
            len(trace['eligible']) == n, 'TRACE_SHAPE')
    output = np.zeros((n, 50), dtype=np.float32)
    output[:, :14] = q
    eligible = np.asarray(trace['eligible'], dtype=bool)
    if np.any(eligible):
        require(np.isfinite(trace['qref'][eligible]).all() and
                np.isfinite(trace['dz'][eligible]).all() and
                np.isfinite(trace['dq'][eligible]).all(), 'TRACE_NONFINITE')
        diff = q[eligible, None, :] - trace['qref'][eligible]
        output[eligible, 14:28] = np.mean(diff, axis=1)
        output[eligible, 28:42] = np.mean(np.abs(diff), axis=1)
        output[eligible, 42:44] = trace['dz'][eligible] / 2.0
        output[eligible, 44:46] = trace['dq'][eligible]
        count = np.asarray(trace['legal_component_count'], dtype=np.int64)
        output[eligible, 47] = np.minimum(np.log2(count[eligible]) / 6.0, 1.0)
    good_scale = scale > 0
    output[good_scale, 46] = np.clip(
        (score[good_scale] - center[good_scale]) / scale[good_scale], -8, 8) / 8
    for i, row in enumerate(rows):
        require(row.get('protocol') in PROTOCOLS, 'FEATURE_PROTOCOL')
        output[i, 48 if row['protocol'] == 6 else 49] = 1.0
    if query_only:
        output[:, 14:46] = 0
        output[:, 47] = 0
    return output


def apply_correction(scores, a, eligible, scales, lambda_value):
    """Subtract in float64; fallback entries retain their original bits."""
    source = np.asarray(scores)
    require(source.ndim == 1 and source.dtype.kind == 'f' and
            np.isfinite(source).all(), 'SCORE_INPUT')
    n = len(source)
    strengths = np.asarray(a, dtype=np.float64)
    mask = np.asarray(eligible, dtype=bool)
    scale = np.broadcast_to(np.asarray(scales, dtype=np.float64), (n,))
    require(strengths.shape == mask.shape == (n,) and
            np.isfinite(strengths).all() and np.all((strengths >= 0) & (strengths <= 1)) and
            np.isfinite(scale).all() and np.all(scale >= 0) and
            type(lambda_value) in (int, float) and
            math.isfinite(lambda_value) and lambda_value in (0., .05, .1, .25),
            'CORRECTION_INPUT')
    result = source.astype(np.float64, copy=True)
    active = mask & (scale > 0) & (lambda_value > 0)
    result[active] -= float(lambda_value) * scale[active] * strengths[active]
    return result
