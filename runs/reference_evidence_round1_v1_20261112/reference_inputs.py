"""Reference-only loader and selectors. The selector receives no query inputs."""
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib

import numpy as np

from common_round1 import (artifact, dump, read_rows, require, uid_sha, verify_artifact,
                           write_rows)
from vendor import constrained_onboarding_core_v3 as core
from vendor.history_context import union


def key(row):
    return row['partition'], row['device'], row['protocol']


def uids(rows):
    return [row['uid'] for row in rows]


@dataclass
class ReferenceAssets:
    rows: list
    z: np.ndarray
    q: np.ndarray
    raw_context: np.ndarray
    dense_count: int
    dense_bank: object
    full_bank: object
    norm: tuple
    context_norm: tuple
    identity: dict

    def bank(self, indices, *, retain_omitted_capture_cutoffs=False):
        rows = [self.rows[i] for i in indices]
        ids = uids(rows)
        candidate = core.ReferenceBank(rows, self.z[indices], self.q[indices], self.norm,
                                       feature_uids=ids, q_uids=ids, allow_prebank_history=True)
        policy = self.full_bank
        require(candidate.ends == policy.ends, 'BANK_END_POLICY_CHANGED')
        require(all(policy.frame_ends.get(k) == v for k, v in candidate.frame_ends.items()),
                'BANK_FRAME_CONFLICT')
        if retain_omitted_capture_cutoffs:
            # M can omit an entire capture. Enforce its original frame cutoff even then.
            candidate.frame_ends = policy.frame_ends.copy()
        require(candidate.frame_ends == policy.frame_ends, 'BANK_FRAME_POLICY_CHANGED')
        return candidate


def load_pack(store, rows_name, array_name):
    rows = read_rows(store.get(rows_name))
    with np.load(store.get(array_name), allow_pickle=False) as saved:
        require(saved['uid'].tolist() == uids(rows), 'BANK_FEATURE_UIDS:' + rows_name)
        return rows, saved['e3'], saved['q14']


def load_reference_metadata(store, config):
    dense = read_rows(store.get('dense_rows'))
    history = []
    for pack in config['history_packs']:
        history.extend(read_rows(store.get(pack['rows'])))
    return dense, history


def normalized_context(values, normalizer):
    mean, scale = normalizer
    # The production cache contains physical context, not already standardized context.
    require(values.shape[1:] == (8,) and np.isfinite(values).all() and (values >= 0).all(),
            'PHYSICAL_CONTEXT_SCHEMA')
    result = ((np.log1p(values) - mean) / scale).astype(np.float32)
    require(np.isfinite(result).all(), 'NORMALIZED_CONTEXT_SCHEMA')
    return result


def load_references(store, config):
    dense = load_pack(store, 'dense_rows', 'dense_arrays')
    packs = [load_pack(store, pack['rows'], pack['arrays']) for pack in config['history_packs']]
    require(len({(p[1].dtype.str, p[2].dtype.str) for p in [dense, *packs]}) == 1,
            'REFERENCE_FEATURE_DTYPE_DRIFT')
    history = ([r for p in packs for r in p[0]],
               np.concatenate([p[1] for p in packs]), np.concatenate([p[2] for p in packs]))
    require(all(r['history_role'] == 'HIST_REF' and r['use'] == 'REFERENCE' and
                r['label'] == 0 and r['timestamp'] <= r['reference_end'] and
                type(r['bank_end_frame']) is int and r['frame'] <= r['bank_end_frame']
                for r in history[0]), 'HIST_REF_PROVENANCE')
    rows, z, q = union(dense, history)
    with np.load(store.get('e3_normalizer'), allow_pickle=False) as a:
        norm = core._normalizer((a['mean'], a['scale']))
    with np.load(store.get('context_normalizer'), allow_pickle=False) as a:
        context_norm = a['mean'], a['scale']
    mean, scale = context_norm
    require(mean.shape == scale.shape == (8,) and np.isfinite(mean).all() and
            np.isfinite(scale).all() and np.all(scale > 0), 'CONTEXT_NORMALIZER_SCHEMA')
    contexts = []
    for name, group in [('dense_context', dense[0]), ('history_context', history[0])]:
        with np.load(store.get(name), allow_pickle=False) as a:
            require(a['uid'].tolist() == uids(group), 'BANK_CONTEXT_UIDS:' + name)
            values = a['features']
            require(values.shape == (len(group), 8) and values.dtype.kind == 'f' and
                    np.isfinite(values).all() and (values >= 0).all(), 'CONTEXT_VALUES:' + name)
            contexts.append(values)
    require(contexts[0].dtype == contexts[1].dtype, 'CONTEXT_DTYPE_DRIFT')
    ref = config['reference_identity']
    dense_ids = uids(dense[0])
    all_ids = uids(rows)
    require(dict(rows=len(dense_ids), uid_sha256=uid_sha(dense_ids)) == ref['dense'] and
            dict(rows=len(all_ids), uid_sha256=uid_sha(all_ids)) == ref['full'] and
            len(history[0]) == ref['history_rows'], 'REFERENCE_UID_ORDER')
    dense_bank = core.ReferenceBank(*dense, norm, feature_uids=dense_ids, q_uids=dense_ids,
                                    allow_prebank_history=True)
    full_bank = core.ReferenceBank(rows, z, q, norm, feature_uids=all_ids, q_uids=all_ids,
                                   allow_prebank_history=True)
    expected_ends = {(w['partition'], w['device']): w['reference_end'] for w in config['windows']}
    expected_frames = {(w['partition'], w['device'], w['capture_id']): w['frame_end']
                       for w in config['windows']}
    require(expected_ends == dense_bank.ends == full_bank.ends and
            expected_frames == dense_bank.frame_ends, 'FROZEN_WINDOWS_BINDING')
    require(all(full_bank.frame_ends.get(k) == v for k, v in expected_frames.items()),
            'FULL_COMMISSION_FRAME_POLICY')
    return ReferenceAssets(rows, z, q, np.concatenate(contexts), len(dense_ids),
                           dense_bank, full_bank, norm, context_norm, ref)


def signature(row, bank):
    frame_end = row.get('bank_end_frame')
    capture = row['partition'], row['device'], row['capture_id']
    effective = bank.frame_ends.get(capture)
    # Dropping a frame is valid for all possible queries, not only the fixed query list.
    covered = (type(frame_end) is int and effective == frame_end and row['frame'] <= frame_end)
    return (*key(row), row['component_id'], row['capture_id'], row['reference_end'],
            frame_end, effective, None if covered else row['frame'])


def select_m(rows, dense_count, config):
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row['device'], row['protocol'], i >= dense_count].append(i)
    salt = config['m']['salt'] + '\n'
    selected = []
    quota_record = []
    require({k[:2] for k in groups} == {(r['device'], r['protocol']) for r in config['m']['quotas']},
            'M_DEVICE_PROTOCOL_SCOPE')
    for quota in config['m']['quotas']:
        group = quota['device'], quota['protocol']
        dense_ids = groups[(*group, False)]
        require(len(dense_ids) == quota['dense'] + quota['history'], 'M_EQUAL_BUDGET_PER_GROUP')
        for is_hist, count in [(False, quota['dense']), (True, quota['history'])]:
            options = groups[(*group, is_hist)]
            require(len(options) >= count, 'M_QUOTA_UNAVAILABLE:' + str(group))
            order = sorted(options, key=lambda i: (
                hashlib.sha256((salt + rows[i]['uid']).encode('utf-8')).digest(), rows[i]['uid']
            ))
            selected.extend(order[:count])
        quota_record.append(dict(quota, source_dense=len(dense_ids), source_history=len(groups[(*group, True)])))
    selected = np.asarray(sorted(selected), dtype=np.int64)
    require(len(selected) == len(set(selected)) == 13247 and
            np.count_nonzero(selected < dense_count) == 10011, 'M_FIXED_CARDINALITY')
    return selected, quota_record


def deduplicate(assets):
    groups = defaultdict(list)
    parents = np.arange(len(assets.rows))
    arrays = assets.z, assets.q, assets.raw_context
    # Sort by UID so the first true match is the retained minimum UID.
    order = sorted(range(assets.dense_count, len(assets.rows)), key=lambda i: assets.rows[i]['uid'])
    for i in order:
        sig = signature(assets.rows[i], assets.full_bank)
        digest = hashlib.sha256()
        for a in arrays:
            require(np.isfinite(a[i]).all(), 'C0_NONFINITE_REFERENCE')
            digest.update(a.dtype.str.encode('ascii'))
            digest.update(a[i].tobytes())
        bucket = groups[(sig, digest.digest())]
        for parent in bucket:
            if all(a[i].dtype == a[parent].dtype and np.array_equal(a[i], a[parent]) for a in arrays):
                parents[i] = parent
                break
        else:
            bucket.append(i)
    kept = np.flatnonzero(parents == np.arange(len(parents)))
    return kept, parents


def groups_for_c1(assets, c0):
    groups = defaultdict(list)
    for i in c0:
        if i >= assets.dense_count:
            groups[signature(assets.rows[i], assets.full_bank)].append(int(i))
    return dict(sorted(groups.items(), key=lambda item: repr(item[0])))


def cardinality(assets, groups):
    all_groups = []
    counts = defaultdict(Counter)
    total = assets.dense_count
    for sig, indices in groups.items():
        n = len(indices)
        keep = (n + 1) // 2
        dev_proto = sig[1], sig[2]
        counts[dev_proto].update(groups=1, singleton_groups=int(n == 1),
                                 odd_groups=n % 2, c0_history=n, c1_history=keep)
        all_groups.append(dict(signature=list(sig), n=n, keep=keep))
        total += keep
    dense_groups = Counter((row['device'], row['protocol']) for row in assets.rows[:assets.dense_count])
    return dict(status='EXACT_QUOTA_BEFORE_SELECTION', total=total, dense=assets.dense_count,
                history=total - assets.dense_count, groups=len(groups),
                singleton_groups=sum(row['n'] == 1 for row in all_groups),
                odd_groups=sum(row['n'] % 2 for row in all_groups),
                largest_group=max((row['n'] for row in all_groups), default=0),
                max_pair_computations=sum(row['n'] * row['keep'] for row in all_groups),
                device_protocol=[
                    dict(device=k[0], protocol=k[1], dense=dense_groups[k],
                         **{name: v[name] for name in ('groups', 'singleton_groups', 'odd_groups',
                                                       'c0_history', 'c1_history')},
                         c1_total=v['c1_history'] + dense_groups[k])
                    for k in sorted(dense_groups) for v in [counts[k]]
                ], group_sizes=all_groups)


def seal(out, name, assets, indices, parents, input_receipt, package_sha, details):
    indices = np.asarray(indices)
    require(np.array_equal(indices, np.unique(indices)) and (indices >= 0).all() and
            (indices < len(assets.rows)).all(), 'CANDIDATE_SUBSET')
    bank = assets.bank(indices, retain_omitted_capture_cutoffs=name == 'M')
    if parents is not None:
        selected = set(indices)
        require(all(i in selected for i in parents.values()), 'REPRESENTATIVE_NOT_SELECTED')
        require(set(bank.groups) == set(assets.full_bank.groups), 'COMPRESSED_BANK_GROUP_LOSS')
        for i, rep in parents.items():
            require(signature(assets.rows[i], assets.full_bank) ==
                    signature(assets.rows[rep], bank), 'REPRESENTATIVE_ELIGIBILITY_MISMATCH')
    roster = out / (name + '_UIDS.jsonl.gz')
    n = write_rows(roster, (dict(uid=assets.rows[i]['uid'], row=int(i),
                                 source='TWO_HOUR' if i < assets.dense_count else 'HIST_REF')
                            for i in indices))
    mapping = None
    if parents is not None:
        path = out / (name + '_REPRESENTATIVES.jsonl.gz')
        count = write_rows(path, (dict(uid=assets.rows[i]['uid'], representative_uid=assets.rows[j]['uid'],
                                       row=int(i), representative_row=int(j)) for i, j in sorted(parents.items())))
        mapping = artifact(path, count)
    report = dict(status='SEALED', candidate=name, rows=n, reference_uid_sha256=uid_sha(uids(bank.rows)),
                  roster=artifact(roster, n), mapping=mapping, inputs=input_receipt,
                  package_manifest_sha256=package_sha, query_assets_read=0,
                  ends=[list(k) + [v] for k, v in sorted(bank.ends.items())],
                  frame_ends=[list(k) + [v] for k, v in sorted(bank.frame_ends.items())],
                  candidate_is_frozen_subset=True, **details)
    dump(out / (name + '_SEAL.json'), report)
    return report


def read_candidate(out, name, assets, package_sha):
    from common_round1 import load
    info = load(out / (name + '_SEAL.json'))
    require(info['status'] == 'SEALED' and info['candidate'] == name and
            info['package_manifest_sha256'] == package_sha, 'CANDIDATE_SEAL_IDENTITY')
    selected = read_rows(verify_artifact(out, info['roster']))
    ix = np.asarray([r['row'] for r in selected], dtype=np.int64)
    require(len(ix) == info['rows'] and np.array_equal(ix, np.unique(ix)) and
            (ix >= 0).all() and (ix < len(assets.rows)).all() and
            [r['uid'] for r in selected] == [assets.rows[i]['uid'] for i in ix] and
            all(r['source'] == ('TWO_HOUR' if i < assets.dense_count else 'HIST_REF')
                for i, r in zip(ix, selected)) and
            uid_sha([r['uid'] for r in selected]) == info['reference_uid_sha256'], 'CANDIDATE_UID_IDENTITY')
    if info['mapping']:
        verify_artifact(out, info['mapping'])
    return ix, info
