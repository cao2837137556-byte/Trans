"""Fixed k=5 nearest-neighbour distance on frozen standardized unit E3.

No fitting, source selection, threshold search, or I/O occurs in this module.
The detector has one distance score, not four independent learned heads.
"""
import math
from collections import defaultdict

import numpy as np

K = 5
BLOCK_ROWS = 128
MAX_BLOCK_PAIRS = 262144


def require(value, message):
    if not value:
        raise ValueError(message)


def unit(e3, normalizer):
    mean, scale = (np.asarray(x, dtype=np.float64) for x in normalizer)
    require(mean.shape == scale.shape == (768,) and np.all(scale > 0), 'NORMALIZER')
    z = (np.asarray(e3, dtype=np.float64) - mean) / scale
    require(z.ndim == 2 and z.shape[1] == 768 and np.isfinite(z).all(), 'E3')
    norm = np.linalg.norm(z, axis=1)
    require(np.all(norm > 0), 'ZERO_E3_NORM')
    return z / norm[:, None]


class KNN5Bank:
    def __init__(self, rows, e3, normalizer, *, feature_uids):
        require(list(feature_uids) == [r['uid'] for r in rows], 'REFERENCE_UID_JOIN')
        require(len(feature_uids) == len(set(feature_uids)), 'DUPLICATE_REFERENCE_UID')
        self.rows = [dict(r) for r in rows]
        self.uids = set(feature_uids)
        self.normalizer = normalizer
        self.z = unit(e3, normalizer)
        require(len(self.z) == len(rows), 'REFERENCE_SHAPE')
        self.groups = defaultdict(list)
        self.ends = {}
        self.frame_ends = {}
        self.reference_frame_max = {}
        for i, row in enumerate(rows):
            require(row['use'] == 'REFERENCE' and row['label'] == 0, 'REFERENCE_ROLE')
            require(row['protocol'] in (6, 17), 'REFERENCE_PROTOCOL')
            key = (row['partition'], row['device'])
            end = row['reference_end']
            require(math.isfinite(end) and row['timestamp'] <= end, 'REFERENCE_TIME')
            require(self.ends.setdefault(key, end) == end, 'INCOMPLETE_BANK_END')
            self.groups[key + (row['protocol'],)].append(i)
            capture_key = key + (row['protocol'], row['capture_id'])
            self.reference_frame_max[capture_key] = max(self.reference_frame_max.get(capture_key,0),row['frame'])
            if 'bank_end_frame' in row:
                end_frame = row['bank_end_frame']
                require(type(end_frame) is int and end_frame >= row['frame'], 'BANK_END_FRAME')
                require(self.frame_ends.setdefault(key+(row['capture_id'],), end_frame) == end_frame,
                        'INCOMPLETE_BANK_FRAME_END')
        for indices in self.groups.values():
            indices.sort(key=lambda j: self.rows[j]['uid'])
        self.groups = {k:tuple(v) for k,v in self.groups.items()}

    def distances(self, rows, e3, *, feature_uids, donor=None, progress=None):
        """Use own bank; optional donor is source-LEARN calibration only.

        Distances are NaN for RAW fallback rows. Repeated observations from the
        same component are legitimate neighbours for this standard point-kNN
        comparator; C5's two-component support criterion is not imposed here.
        """
        require(list(feature_uids) == [r['uid'] for r in rows], 'QUERY_UID_JOIN')
        require(len(feature_uids) == len(set(feature_uids)), 'DUPLICATE_QUERY_UID')
        require(len(e3) == len(rows), 'QUERY_SHAPE')
        require(all(r['use'] != 'REFERENCE' for r in rows), 'QUERY_ROLE')
        if donor is not None:
            require(donor in self.groups and donor[0] == 'LEARN' and
                    all(r['partition'] == 'LEARN' for r in rows), 'SOURCE_DONOR_ONLY')
        answer = np.full(len(rows), np.nan, dtype=np.float64)
        reasons = np.full(len(rows), 'NO_SAME_PROTOCOL_BANK', dtype='<U40')
        grouped = defaultdict(list)
        for i, row in enumerate(rows):
            if row['uid'] in self.uids:
                reasons[i] = 'REFERENCE_QUERY_REPLAY_RAW'
                continue
            key = donor or (row['partition'], row['device'], row['protocol'])
            if row['protocol'] != key[2]:
                continue
            indices = self.groups.get(key, [])
            if not indices:
                continue
            end = self.ends[key[:2]]
            if not end < row['timestamp']:
                reasons[i] = 'BANK_NOT_YET_AVAILABLE'
                continue
            end_frame = self.frame_ends.get(key[:2]+(row['capture_id'],))
            if end_frame is not None and row['frame'] <= end_frame:
                reasons[i] = 'BANK_FRAME_NOT_YET_AVAILABLE'
                continue
            max_frame = self.reference_frame_max.get(key+(row['capture_id'],),0)
            legal = indices if row['frame'] > max_frame else tuple(
                j for j in indices if self.rows[j]['capture_id'] != row['capture_id']
                or self.rows[j]['frame'] < row['frame'])
            if len(legal) < K:
                reasons[i] = 'FEWER_THAN_FIVE_LEGAL_POINTS'
                continue
            grouped[legal].append(i)
        pairs = 0
        for legal, ix in grouped.items():
            bank_z = self.z[np.asarray(legal)]
            block = max(1, min(BLOCK_ROWS, MAX_BLOCK_PAIRS // len(legal)))
            for start in range(0, len(ix), block):
                take = np.asarray(ix[start:start+block], dtype=np.int64)
                z = unit(e3[take], self.normalizer)
                # ||u-v||_2^2 = 2-2*cos(u,v) for unit-normalized vectors.
                squared = np.clip(2.-2.*(z @ bank_z.T), 0., 4.)
                kth = np.partition(squared, K-1, axis=1)[:, K-1]
                answer[take] = np.sqrt(kth)
                reasons[take] = 'KNN5_SCORED'
                pairs += len(take)*len(legal)
                if progress is not None:
                    progress(pairs)
        return dict(distance=answer, reason=reasons, pairs=pairs)


def source_cuts(normal_distance, raw_normal_decisions, normal_weights):
    """Match each RAW source-normal weighted FPR, with conservative ties.

    RAW fallback mass is held fixed. Among distinct finite observed distances,
    choose the smallest strict-> cut whose total weighted FPR is <= the RAW
    target. If every supported row fits the target, use nextafter(min,-inf).
    This is an operating-point calibration; attacks cannot select thresholds.
    """
    distance = np.asarray(normal_distance, dtype=np.float64)
    raw = np.asarray(raw_normal_decisions, dtype=bool)
    weight = np.asarray(normal_weights, dtype=np.float64)
    require(distance.ndim == 1 and raw.shape == (len(distance), 4) and
            weight.shape == distance.shape and np.isfinite(weight).all() and
            np.all(weight > 0), 'CALIBRATION_SHAPE')
    finite = np.isfinite(distance)
    cuts, details = [], []
    total = math.fsum(weight)
    values = np.unique(distance[finite])
    for head in range(4):
        target = math.fsum(weight[raw[:, head]])
        fallback = math.fsum(weight[(~finite) & raw[:, head]])
        budget = target - fallback
        require(budget >= 0, 'NEGATIVE_FINITE_FPR_BUDGET')
        cut = None
        if len(values):
            finite_mass = math.fsum(weight[finite])
            if finite_mass <= budget:
                cut = float(np.nextafter(values[0], -np.inf))
            else:
                # Stable grouping followed by fsum makes ties explicit and
                # avoids a search over candidate methods or external scores.
                order = np.argsort(distance[finite], kind='stable')
                sorted_distance = distance[finite][order]
                sorted_weight = weight[finite][order]
                starts = np.r_[0, np.flatnonzero(np.diff(sorted_distance))+1]
                masses = [math.fsum(sorted_weight[a:b]) for a,b in
                          zip(starts, np.r_[starts[1:],len(order)])]
                reverse = np.cumsum(np.asarray(masses[::-1], dtype=np.float64))
                tail = np.r_[reverse[-2::-1], 0.]
                legal = np.flatnonzero(tail <= budget)
                require(len(legal) > 0, 'NO_CONSERVATIVE_NORMAL_CUT')
                chosen = int(legal[0])
                while math.fsum(masses[chosen+1:]) > budget:
                    chosen += 1
                while chosen > 0 and math.fsum(masses[chosen:]) <= budget:
                    chosen -= 1
                cut = float(sorted_distance[starts[chosen]])
        cuts.append(cut)
        achieved = fallback if cut is None else fallback + math.fsum(weight[finite & (distance > cut)])
        require(achieved <= target + 1e-15*total, 'SOURCE_FPR_MATCH_OVERSHOOT')
        details.append(dict(target_weighted_fpr=target/total, achieved_weighted_fpr=achieved/total,
                            fallback_fp_mass=fallback, finite_tail_budget=budget,
                            tie_gap=(target-achieved)/total, cut=cut))
    return dict(cuts=cuts, working_points=details)


def decisions(distance, raw_decisions, cuts):
    score = np.asarray(distance, dtype=np.float64)
    raw = np.asarray(raw_decisions, dtype=bool)
    require(raw.shape == (len(score), 4) and len(cuts) == 4, 'DECISION_SHAPE')
    result = raw.copy()
    finite = np.isfinite(score)
    for j, cut in enumerate(cuts):
        if cut is not None:
            require(math.isfinite(cut), 'NONFINITE_CUT')
            result[finite, j] = score[finite] > cut
    return result
