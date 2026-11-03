"""Frozen local-reference geometry; distances are shared by D0 and L.

This module has no file/data discovery and never fits a detection head.  The
caller binds the saved identities and supplies a counter for every distance
pair actually issued.  Reference metadata validation and query replay checks
are delegated to the frozen V3 core, while both supports use one distance pass.
"""
from collections import defaultdict
import hashlib

import numpy as np


def _ratio_columns(distance, radii):
    """Vector-radius equivalent of V3 _ratio, including exact zero semantics."""
    radii = np.asarray(radii, dtype=np.float64)[None, :]
    answer = np.full(distance.shape, np.inf, dtype=np.float64)
    np.divide(distance, radii, out=answer, where=radii != 0)
    answer[(radii == 0) & (distance == 0)] = 0.0
    return answer


class DualBank:
    """One frozen bank and one shared distance pass for D0/local supports.

    ``geometry=None`` is supported only for the old ``fit_geometry`` raw-distance
    adapter: ``core.fit_geometry(..., source_bank=DualBank(..., None))``.
    Explicit feature UID lists are passed to V3 when supplied.  If omitted, the
    caller asserts that these already-validated arrays follow ``rows`` order.
    """

    def __init__(self, rows, e3, q14, normalizer, geometry, counter=None,
                 allow_prebank_history=True, core=None, checkpoint=None,
                 feature_uids=None, q_uids=None, allowed_partitions=None):
        if core is None:
            from .legacy import get_core
            core = get_core()
        self.core = core
        self.counter = counter or (lambda count: None)
        self.checkpoint = checkpoint or (lambda *args, **kwargs: None)
        ordered = [r['uid'] for r in rows]
        self.base = core.ReferenceBank(
            rows, e3, q14, normalizer,
            feature_uids=ordered if feature_uids is None else feature_uids,
            q_uids=ordered if q_uids is None else q_uids,
            allowed_partitions=allowed_partitions,
            allow_prebank_history=allow_prebank_history)
        for name in ('rows', 'normalizer', 'z', 'q14', 'groups', 'ends',
                     'frame_ends', 'by_uid', 'keys'):
            setattr(self, name, getattr(self.base, name))
        self.geometry = geometry
        self.local_rho_z = np.full(len(rows), np.nan, dtype=np.float64)
        self.local_rho_q = np.full(len(rows), np.nan, dtype=np.float64)
        self.local_ready = np.zeros(len(rows), dtype=bool)
        self.local_dependencies = [tuple() for _ in rows]
        self.local_neighbor_uids = [tuple() for _ in rows]
        self.scale_summary = []
        self.has_2c_expansion = False
        if geometry is not None:
            for protocol in core.PROTOCOLS:
                core._radius(geometry, protocol)
            self._prepare_local()

    def roster(self):
        return self.base.roster()

    def scale_arrays(self):
        """Auditable reference-order scales; NPZ-safe without object/pickle."""
        width = max([1] + [len(row['uid']) for row in self.rows])
        neighbors = np.full((len(self.rows), 5), '', dtype='<U%d' % width)
        for i in np.flatnonzero(self.local_ready):
            self.core.require(len(self.local_neighbor_uids[i]) == 5,
                              'LOCAL_SCALE_AUDIT_NEIGHBORS')
            neighbors[i] = self.local_neighbor_uids[i]
        return dict(uid=np.asarray([row['uid'] for row in self.rows], dtype='<U%d' % width),
                    ready=self.local_ready.copy(), rho_z=self.local_rho_z.copy(),
                    rho_q=self.local_rho_q.copy(), neighbor_uids=neighbors)

    def _distance(self, left_z, left_q, right_z, right_q):
        self.checkpoint('geometry.distance_block')
        self.counter(int(len(left_z)) * int(len(right_z)))
        dz = np.clip(1.0 - left_z @ right_z.T, 0.0, 2.0)
        delta = left_q[:, None, :] - right_q[None, :, :]
        dq = np.sqrt(np.mean(delta * delta, axis=2))
        self.core.require(np.isfinite(dz).all() and np.isfinite(dq).all() and
                          np.all(dz >= 0) and np.all(dq >= 0),
                          'NONFINITE_OR_NEGATIVE_DISTANCE')
        return dz, dq

    @staticmethod
    def _vector_ids(z, q):
        """Hash buckets plus exact equality, so even hash collisions are safe."""
        buckets, ids, representatives = defaultdict(list), [], []
        for i in range(len(z)):
            a, b = z[i].copy(), q[i].copy()
            a[a == 0] = 0.0
            b[b == 0] = 0.0
            digest = hashlib.sha256(a.tobytes() + b.tobytes()).digest()
            match = None
            for previous in buckets[digest]:
                if np.array_equal(z[i], z[previous]) and np.array_equal(q[i], q[previous]):
                    match = ids[previous]
                    break
            if match is None:
                match = len(representatives)
                representatives.append(i)
                buckets[digest].append(i)
            ids.append(match)
        return np.asarray(ids, dtype=np.int64)

    def _prepare_local(self):
        """Compute each unordered reference pair once, bank by bank."""
        for key in self.keys:
            self.checkpoint('geometry.reference_bank_prepare')
            ix = np.asarray(self.groups[key], dtype=np.int64)  # UID order
            refs = [self.rows[i] for i in ix]
            radii = self.core._radius(self.geometry, key[2])
            summary = dict(key=list(key), references=len(ix), ready=0,
                           distinct_components=len({r['component_id'] for r in refs}),
                           two_component_expansion=False)
            if radii is None:
                summary['status'] = 'NO_SOURCE_GEOMETRY_SUPPORT'
                self.scale_summary.append(summary)
                continue
            n = len(ix)
            grouped = defaultdict(list)
            for local, row in enumerate(refs):
                grouped[(row['capture_id'], row['component_id'])].append(local)
            blocks = np.empty(n, dtype=np.int64)
            block_count = 0
            for group in sorted(grouped):
                ordered = sorted(grouped[group], key=lambda i: (
                    refs[i]['timestamp'], refs[i]['frame'], refs[i]['uid']))
                count = min(8, len(ordered))
                for rank, index in enumerate(ordered):
                    blocks[index] = block_count + count * rank // len(ordered)
                block_count += count
            summary['time_blocks'] = block_count
            if block_count < 6:
                summary['status'] = 'LOCAL_SCALE_NOT_READY'
                self.scale_summary.append(summary)
                continue
            z, q = self.z[ix], self.q14[ix]
            vector_ids = self._vector_ids(z, q)
            # These are per-block sufficient statistics, never a pair matrix.
            # Keep both axes for the same representative; no second distance pass.
            best_joint = np.full((n, block_count), np.inf, dtype=np.float64)
            best_z = np.full((n, block_count), np.nan, dtype=np.float64)
            best_q = np.full((n, block_count), np.nan, dtype=np.float64)
            best_index = np.full((n, block_count), -1, dtype=np.int32)
            self.checkpoint('geometry.reference_neighbor_state')

            def update(left, right, dz, dq):
                joint = np.maximum(self.core._ratio(dz, radii[0]),
                                   self.core._ratio(dq, radii[1]))
                for block in np.unique(blocks[right]):
                    columns = np.flatnonzero(blocks[right] == block)
                    chosen_column = columns[np.argmin(joint[:, columns], axis=1)]
                    representative = right[chosen_column]
                    values = joint[np.arange(len(left)), chosen_column]
                    old_values = best_joint[left, block]
                    old_index = best_index[left, block]
                    take = ((values < old_values) |
                            ((values == old_values) &
                             ((old_index < 0) | (representative < old_index))))
                    selected_left = left[take]
                    selected_col = chosen_column[take]
                    best_joint[selected_left, block] = values[take]
                    best_index[selected_left, block] = representative[take]
                    best_z[selected_left, block] = dz[np.flatnonzero(take), selected_col]
                    best_q[selected_left, block] = dq[np.flatnonzero(take), selected_col]

            width = 64
            for start in range(0, n, width):
                left = np.arange(start, min(n, start + width), dtype=np.int64)
                # Diagonal tile: no self or duplicate lower-triangle work.
                for position in range(len(left)):
                    a, b = left[position:position + 1], left[position + 1:]
                    if len(b):
                        dz, dq = self._distance(z[a], q[a], z[b], q[b])
                        update(a, b, dz, dq)
                        update(b, a, dz.T, dq.T)
                for other in range(start + width, n, width):
                    right = np.arange(other, min(n, other + width), dtype=np.int64)
                    dz, dq = self._distance(z[left], q[left], z[right], q[right])
                    update(left, right, dz, dq)
                    update(right, left, dz.T, dq.T)
            for center in range(n):
                # First select each block's nearest position, then deduplicate.
                # Do not substitute a block's second position after deduplication.
                candidates = [b for b in range(block_count)
                              if b != blocks[center] and best_index[center, b] >= 0
                              and vector_ids[best_index[center, b]] != vector_ids[center]]
                by_vector = {}
                for block in candidates:
                    representative = int(best_index[center, block])
                    identity = int(vector_ids[representative])
                    previous = by_vector.get(identity)
                    if previous is None or representative < int(best_index[center, previous]):
                        by_vector[identity] = block
                candidates = sorted(by_vector.values(), key=lambda b: (
                    best_joint[center, b], refs[int(best_index[center, b])]['uid']))
                if len(candidates) < 5 or best_joint[center, candidates[4]] > 2:
                    continue
                chosen = candidates[:5]
                rho_z = min(float(np.max(best_z[center, chosen])), 2 * radii[0], 2.0)
                rho_q = min(float(np.max(best_q[center, chosen])), 2 * radii[1])
                self.core.require(np.isfinite(rho_z) and np.isfinite(rho_q) and
                                  rho_z >= 0 and rho_q >= 0, 'LOCAL_RADIUS_INVALID')
                global_index = int(ix[center])
                dependencies = tuple(int(ix[int(best_index[center, b])]) for b in chosen)
                self.local_rho_z[global_index] = rho_z
                self.local_rho_q[global_index] = rho_q
                self.local_ready[global_index] = True
                self.local_dependencies[global_index] = dependencies
                self.local_neighbor_uids[global_index] = tuple(self.rows[i]['uid'] for i in dependencies)
                if summary['distinct_components'] >= 2 and (rho_z > radii[0] or rho_q > radii[1]):
                    summary['two_component_expansion'] = True
            summary['ready'] = int(self.local_ready[ix].sum())
            summary['status'] = 'READY' if summary['ready'] else 'LOCAL_SCALE_NOT_READY'
            self.has_2c_expansion |= summary['two_component_expansion']
            self.scale_summary.append(summary)
            del best_joint, best_z, best_q, best_index
            self.checkpoint('geometry.reference_bank_complete')

    def _empty(self, size):
        return dict(d0=np.zeros(size), local=np.zeros(size),
                    eligible_d0=np.zeros(size, dtype=bool),
                    eligible_local=np.zeros(size, dtype=bool),
                    localready=np.zeros(size, dtype=bool),
                    branch=np.full(size, 'OTHER', dtype=object),
                    geometry_supported=np.zeros(size, dtype=bool),
                    reason=np.full(size, 'NO_REFERENCE_BANK', dtype=object),
                    second_dz=np.full(size, np.inf), second_dq=np.full(size, np.inf),
                    second_joint=np.full(size, np.inf), local_second_joint=np.full(size, np.inf),
                    matched_reference_uids=np.full((size, 2), None, dtype=object),
                    local_matched_reference_uids=np.full((size, 2), None, dtype=object),
                    matched_components=np.full((size, 2), None, dtype=object),
                    same_component=np.zeros(size, dtype=bool),
                    legal_component_count=np.zeros(size, dtype=np.int64),
                    legal_position_count=np.zeros(size, dtype=np.int64),
                    bank_end_frame=np.full(size, None, dtype=object), bank_end=np.full(size, np.nan))

    @staticmethod
    def _aliases(result):
        result.update(a0=result['d0'], aL=result['local'],
                      eligible0=result['eligible_d0'], eligibleL=result['eligible_local'],
                      support=result['d0'], eligible=result['eligible_d0'])
        return result

    def _evaluate_group(self, result, rows, e3, q14, query_ix, reference_ix,
                        geometry, raw_distances=False):
        if not reference_ix:
            return
        reference_ix = sorted(reference_ix, key=lambda i: self.rows[i]['uid'])
        refs = [self.rows[i] for i in reference_ix]
        donors = {(r['partition'], r['device'], r['protocol']) for r in refs}
        self.core.require(len(donors) == 1, 'MIXED_DONOR_BANK')
        donor = next(iter(donors))
        self.core.require(all(rows[i]['partition'] == donor[0] and
                              rows[i]['protocol'] == donor[2] for i in query_ix),
                          'DONOR_PROTOCOL_PARTITION')
        end = self.ends[donor[:2]]
        original_component_count = len({self.rows[j]['component_id']
                                        for j in self.groups[donor]})
        components = [r['component_id'] for r in refs]
        radii = (1.0, 1.0) if raw_distances else self.core._radius(geometry, donor[2])
        result['bank_end'][query_ix] = end
        result['geometry_supported'][query_ix] = radii is not None
        patterns = defaultdict(list)
        for i in query_ix:
            row = rows[i]
            frame_end = self.frame_ends.get(donor[:2] + (row['capture_id'],))
            result['bank_end_frame'][i] = frame_end
            if row['uid'] in self.by_uid:
                result['reason'][i] = 'HISTORY_REPLAY_MUST_REMAIN_HEAD_ONLY'
                continue
            if not end < row['timestamp']:
                result['reason'][i] = 'BANK_NOT_YET_AVAILABLE'
                continue
            if frame_end is not None and row['frame'] <= frame_end:
                result['reason'][i] = 'BANK_FRAME_NOT_YET_AVAILABLE'
                continue
            legal = tuple(j for j, r in enumerate(refs)
                          if r['capture_id'] != row['capture_id'] or r['frame'] < row['frame'])
            count = len({components[j] for j in legal})
            result['legal_component_count'][i] = count
            result['legal_position_count'][i] = len(legal)
            result['same_component'][i] = row['component_id'] in {components[j] for j in legal}
            eligible0 = count >= 2
            one_component = (original_component_count == 1 and count == 1
                             and len(legal) >= 8)
            if not eligible0 and (raw_distances or not one_component):
                result['reason'][i] = 'FEWER_THAN_TWO_LEGAL_COMPONENTS'
                continue
            result['eligible_d0'][i] = eligible0
            result['eligible_local'][i] = eligible0
            result['branch'][i] = '2C_ZERO' if eligible0 else '1C'
            result['reason'][i] = ('NO_SOURCE_GEOMETRY_SUPPORT' if radii is None
                                    else 'ELIGIBLE_ZERO_SUPPORT')
            patterns[legal].append(i)
        for legal, ix in patterns.items():
            indices = np.asarray([reference_ix[j] for j in legal], dtype=np.int64)
            comp = [components[j] for j in legal]
            is_2c = len(set(comp)) >= 2
            legal_set = set(indices.tolist())
            ready = np.asarray([self.local_ready[j] and
                                all(dependency in legal_set for dependency in self.local_dependencies[j])
                                for j in indices], dtype=bool)
            new_components = [comp[j] for j in np.flatnonzero(ready)]
            local_ok = (not raw_distances and radii is not None and
                        (len(set(new_components)) >= 2 if is_2c else int(ready.sum()) >= 2))
            chunk_size = max(1, min(self.core.BLOCK_ROWS, self.core.PAIR_BUDGET // len(indices)))
            for start in range(0, len(ix), chunk_size):
                use = np.asarray(ix[start:start + chunk_size], dtype=np.int64)
                z = self.core._unit(e3[use], self.normalizer)
                q = np.asarray(q14[use], dtype=np.float64)
                dz, dq = self._distance(z, q, self.z[indices], self.q14[indices])
                if is_2c:
                    result['second_dz'][use], _ = self.core._second_distinct(dz, comp)
                    result['second_dq'][use], _ = self.core._second_distinct(dq, comp)
                    if radii is not None:
                        joint = np.maximum(self.core._ratio(dz, radii[0]), self.core._ratio(dq, radii[1]))
                        second, best = self.core._second_distinct(joint, comp)
                        result['second_joint'][use] = second
                        result['d0'][use] = np.clip(1.0 - second, 0.0, 1.0)
                        result['matched_reference_uids'][use] = np.asarray(
                            [self.rows[j]['uid'] for j in indices], dtype=object)[best]
                        result['matched_components'][use] = np.asarray(comp, dtype=object)[best]
                    positive = result['d0'][use] > 0
                    result['branch'][use[positive]] = '2C_POS'
                result['local'][use] = result['d0'][use]
                if local_ok:
                    ready_indices = indices[ready]
                    joint = np.maximum(_ratio_columns(dz[:, ready], self.local_rho_z[ready_indices]),
                                       _ratio_columns(dq[:, ready], self.local_rho_q[ready_indices]))
                    if is_2c:
                        second, best = self.core._second_distinct(joint, new_components)
                    else:
                        best = np.argsort(joint, axis=1, kind='stable')[:, :2]
                        second = np.take_along_axis(joint, best[:, 1:2], axis=1).ravel()
                    result['local_second_joint'][use] = second
                    result['local_matched_reference_uids'][use] = np.asarray(
                        [self.rows[j]['uid'] for j in ready_indices], dtype=object)[best]
                    result['local'][use] = np.maximum(result['d0'][use], np.clip(1.0 - second, 0.0, 1.0))
                    result['localready'][use] = True
                    result['eligible_local'][use] = True
                    result['reason'][use] = 'LOCAL_GEOMETRY_READY'
        self.checkpoint('geometry.query_group_complete')

    def own(self, rows, e3, q14, geometry=None, *, feature_uids=None, q_uids=None,
            override=None, _raw_distances=False):
        geometry = self.geometry if geometry is None else geometry
        if not _raw_distances:
            self.core.require(geometry is not None, 'GEOMETRY_REQUIRED')
            self.core.require(geometry is self.geometry, 'LOCAL_GEOMETRY_IDENTITY_CHANGED')
            for protocol in self.core.PROTOCOLS:
                self.core._radius(geometry, protocol)
        uids = [r['uid'] for r in rows]
        e3, q14 = self.base._queries(rows, e3, q14,
                                      uids if feature_uids is None else feature_uids,
                                      uids if q_uids is None else q_uids)
        result, groups = self._empty(len(rows)), defaultdict(list)
        for i, row in enumerate(rows):
            groups[(row['partition'], row['device'], row['protocol'])].append(i)
        if override is not None:
            self.core.require(isinstance(override, dict), 'OVERRIDE_SCHEMA')
            for key, ids in override.items():
                self.core.require(isinstance(key, tuple) and len(key) == 3 and
                                  len(ids) == len(set(ids)) and all(u in self.by_uid for u in ids),
                                  'OVERRIDE_UID')
        for key, ix in groups.items():
            reference_ix = (self.groups.get(key, []) if override is None else
                            [self.by_uid[u] for u in override.get(key, [])])
            self._evaluate_group(result, rows, e3, q14, ix, reference_ix,
                                 geometry, raw_distances=_raw_distances)
        result['query_uid_sha256'] = self.core._uid_hash(uids)
        return self._aliases(result)

    def matrix(self, rows, e3, q14, geometry=None, *, feature_uids=None, q_uids=None):
        self.core.require(all(r['partition'] == 'LEARN' for r in self.rows) and
                          all(r.get('partition') == 'LEARN' for r in rows), 'SOURCE_DONORS_ONLY')
        geometry = self.geometry if geometry is None else geometry
        self.core.require(geometry is self.geometry and geometry is not None,
                          'LOCAL_GEOMETRY_IDENTITY_CHANGED')
        uids = [r['uid'] for r in rows]
        e3, q14 = self.base._queries(rows, e3, q14,
                                      uids if feature_uids is None else feature_uids,
                                      uids if q_uids is None else q_uids)
        n, k = len(rows), len(self.keys)
        result = {name: np.repeat(value[:, None, ...], k, axis=1)
                  for name, value in self._empty(n).items()}
        for donor_index, key in enumerate(self.keys):
            ix = [i for i, row in enumerate(rows) if row['protocol'] == key[2]]
            column = self._empty(n)
            self._evaluate_group(column, rows, e3, q14, ix, self.groups[key], geometry)
            for name, value in column.items():
                result[name][:, donor_index, ...] = value
        result['roster'] = self.roster()
        result['query_uid_sha256'] = self.core._uid_hash(uids)
        return self._aliases(result)


LocalReferenceBank = DualBank
