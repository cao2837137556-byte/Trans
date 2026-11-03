"""Explicit source fitting, calibration, and sealed target evaluation stages.

No remote execution, scheduling, polling, or import-time fitting is performed.
"""
import gzip
import json
from pathlib import Path
import time
import traceback

import numpy as np

import common as c
from reference_core import ReferenceBank, make_features, apply_correction
import tasks as tasklib
import learning
import evaluation


class IndexedRows:
    """Batch-only indexed view; avoids copying the full source E3 matrix."""
    def __init__(self, values, indices):
        self.values, self.indices = values, np.asarray(indices, dtype=np.int64)
        self.shape = (len(self.indices),)+values.shape[1:]

    def __getitem__(self, index):
        return self.values[self.indices[index]]


def _uids(rows):
    return [r['uid'] for r in rows]


def implementation_hashes():
    files = list(Path(__file__).resolve().parent.glob('*.py'))
    files += [c.ROOT/'repo/ood'/(name+'.py') for name in (
        'query_tail_core_v2', 'continuous_common_v3', 'continuous_model_v3',
        'legacy_qref_data_v1', 'indexed_features_v1', 'constrained_onboarding_core_v3',
        'constrained_onboarding_reference_v2', 'causal_reference_overlap_v1')]
    return {str(p.relative_to(c.ROOT)).replace('\\', '/'): c.sha(p) for p in sorted(files)}


def _verify_fit_code(fit_dir):
    c.require(c.read(Path(fit_dir)/'implementation_code.json') == implementation_hashes(),
              'IMPLEMENTATION_CODE_CHANGED_AFTER_FIT')
    saved = c.read(Path(fit_dir)/'runtime.json')['runtime']
    current = c.environment()
    for key in ('python', 'numpy', 'torch', 'numpy_blas_config', 'torch_threads', 'deterministic'):
        c.require(saved[key] == current[key], 'NUMERIC_RUNTIME_CHANGED_AFTER_FIT:'+key)


def _bank(refs, norm, target=False):
    return ReferenceBank(refs['rows'], refs['e3'], refs['q14'], norm,
                         feature_uids=refs['feature_uids'], q_uids=refs['q_uids'],
                         allow_target_prebank=target)


def _verify_trace(primary, split, *, mining=False):
    for field in ('eligible', 'reason', 'legal_reference_count', 'legal_component_count',
                  'matched_reference_uids', 'matched_components', 'bank_end_frame'):
        c.require(np.array_equal(primary[field], split[field]), 'REFERENCE_BLOCK_IDENTITY_DRIFT:'+field)
    for field in ('dz', 'dq', 'd', 'qref', 'bank_end'):
        c.require(np.allclose(primary[field], split[field], rtol=1e-12, atol=1e-12,
                              equal_nan=True), 'REFERENCE_BLOCK_GEOMETRY_DRIFT:'+field)
    if mining:
        # The mining distance is a fixed row-wise reduction. Require exact values
        # here so the subsequent alternate-score H comparison also covers geometry.
        c.require(np.array_equal(primary['d'], split['d']), 'MINING_DISTANCE_DRIFT')


def _trace_checked(bank, rows, z, q, *, mining=False, donor_keys=None, reference_uids=None):
    options = dict(feature_uids=_uids(rows), q_uids=_uids(rows),
                   donor_keys=donor_keys, reference_uids=reference_uids)
    trace = bank.trace(rows, z, q, **options)
    split = bank.trace(rows, z, q, query_batch=127, reference_block=31, **options)
    _verify_trace(trace, split, mining=mining)
    return trace


def _jsonl(path, rows):
    with gzip.open(path, 'wt', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False,
                               default=lambda x: x.artifact() if isinstance(x, BankCandidates)
                               else c._json_default(x))+'\n')


def source_isolation(rows, fit_indices, cal_indices, refs):
    """Validate actual index roles and all source dependency boundaries."""
    fit, cal = map(lambda x: np.asarray(x, dtype=np.int64), (fit_indices, cal_indices))
    c.require(len(set(fit.tolist())) == len(fit) and len(set(cal.tolist())) == len(cal)
              and not set(fit.tolist()).intersection(cal.tolist())
              and set(fit.tolist()) | set(cal.tolist()) == set(range(len(rows))),
              'FIT_CAL_INDEX_PARTITION')
    c.require(all(r['partition'] == 'LEARN' for r in rows), 'TARGET_IN_SOURCE')
    c.require(all(rows[int(i)]['fit_role'] == role for role, ix in (('FIT', fit), ('CAL', cal))
                  for i in ix), 'FIT_CAL_INDEX_ROLE')
    fr, cr = ([rows[int(i)] for i in ix] for ix in (fit, cal))
    for name, key in (('component', lambda r: r['component_id']),
                      ('session', lambda r: (r['source_sha256'], r['session_id']))):
        c.require(not {key(r) for r in fr}.intersection(key(r) for r in cr),
                  'FIT_CAL_'+name.upper()+'_OVERLAP')
    c.require(not set(_uids(rows)).intersection(_uids(refs['rows'])), 'SOURCE_REFERENCE_QUERY_UID_OVERLAP')
    c.require(all(r['partition'] == 'LEARN' and r['use'] == 'REFERENCE' and r['label'] == 0
                  for r in refs['rows']), 'SOURCE_REFERENCE_ROLE')
    c.require(not {r['component_id'] for r in cr}.intersection(r['component_id'] for r in refs['rows']),
              'CAL_REFERENCE_COMPONENT_LEAKAGE')
    g0, g1 = set(c.GROUPS[0]), set(c.GROUPS[1])
    captures = [{r['source_sha256'] for r in fr if r['device'] in g} for g in (g0, g1)]
    c.require({r['device'] for r in rows} == g0 | g1 and
              {r['device'] for r in fr} == g0 | g1, 'SOURCE_SIX_DEVICE_RECIPE')
    return c.record('learned-onboarding-source-isolation-v1', status='READY',
                    source_rows=len(rows), fit_rows=len(fit), cal_rows=len(cal),
                    fit_uid_sha256=c.uid_hash(_uids(fr), ordered=True),
                    cal_uid_sha256=c.uid_hash(_uids(cr), ordered=True),
                    new_group_capture_overlap=sorted(captures[0] & captures[1]),
                    isolation_scope='head and fitted preprocessing; not independent captures')


def source_coverage(rows, e3, q14, refs, norm, guard=None):
    """Exact causal qualification before either auxiliary head is trained."""
    bank = _bank(refs, norm)
    records, counts = [], {}
    for start in range(0, len(rows), 256):
        rr = rows[start:start+256]
        # Validate numerical inputs once; qualification itself is metadata-only.
        # Representative distances are computed in the later sealed geometry stage.
        bank._queries(rr, e3[start:start+256], q14[start:start+256], _uids(rr), _uids(rr))
        trace = bank.qualification(rr)
        for i, row in enumerate(rr):
            key = (row['device'], row['protocol'], row['label'], str(trace['reason'][i]))
            counts[key] = counts.get(key, 0)+1
            if trace['eligible'][i]:
                records.append(dict(uid=row['uid'], view=0, device=row['device'],
                                    label=row['label'], eligible=True, own_bank=True))
        if guard:
            guard(stage='source_coverage', completed=min(start+256, len(rows)), total=len(rows))
    result = tasklib.coverage_precheck(records) if records else dict(
        status='NOT_EVALUABLE', normal_devices=[], attack_own_bank_devices=[])
    return c.record('learned-onboarding-frame-coverage-v1', **result,
        fit_rows=len(rows), frame_causality_checked=True,
        source_reference_rows=len(refs['rows']),
        groups=[dict(device=k[0], protocol=k[1], label=k[2], reason=k[3], rows=n)
                for k, n in sorted(counts.items())])


class BankCandidates:
    """Small lazy task view; never retain one Python dict per query/bank pair."""
    __slots__ = ('store', 'view', 'slot', 'columns')

    def __init__(self, store, view, slot, columns):
        self.store, self.view, self.slot, self.columns = store, view, slot, tuple(columns)

    def __len__(self):
        return len(self.columns)

    def __getitem__(self, position):
        j = self.columns[position]
        distances = self.store.views[self.view][1]
        return dict(column=j, bank_key=self.store.keys[j],
            d2=float(max(distances[self.slot, j, 1, 0]/2, distances[self.slot, j, 1, 1])))

    def artifact(self):
        result = []
        store, i = self.store, self.slot
        pairs = store.views[self.view][0]
        for index in range(len(self)):
            item = self[index]
            j, key = item['column'], item['bank_key']
            refs = [store.refs['rows'][int(p)] for p in pairs[i, j]]
            item.update(bank_end=store.bank_ends[key],
                bank_end_frame=store.bank_frame_ends.get(key[:2]+(store.rows[i]['capture_id'],)),
                matched_reference_uids=_uids(refs), matched_components=[r['component_id'] for r in refs],
                legal_component_count=int(store.count[i, j]))
            result.append(item)
        return result


class GeometryStore:
    """Compact mmap geometry: store representative slots, never dense N×bank×50."""
    def __init__(self, folder, rows, e3, q14, refs):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.rows, self.e3, self.q14, self.refs = rows, e3, q14, refs
        self.keys = sorted({(r['partition'], r['device'], r['protocol']) for r in refs['rows']})
        self.key_index = {k: i for i, k in enumerate(self.keys)}
        self.ref_index = {r['uid']: i for i, r in enumerate(refs['rows'])}
        self.bank_ends = {k: next(r['reference_end'] for r in refs['rows']
            if (r['partition'], r['device'], r['protocol']) == k) for k in self.keys}
        self.bank_frame_ends = {(r['partition'], r['device'], r['capture_id']): r['bank_end_frame']
                                for r in refs['rows'] if 'bank_end_frame' in r}
        n, k = len(rows), len(self.keys)
        self.eligible = np.lib.format.open_memmap(self.folder/'eligible.npy', mode='w+',
                                                 dtype=np.bool_, shape=(n, k))
        self.count = np.lib.format.open_memmap(self.folder/'components.npy', mode='w+',
                                              dtype=np.int32, shape=(n, k))
        self.reasons = np.lib.format.open_memmap(self.folder/'reasons.npy', mode='w+',
                                                dtype=np.uint8, shape=(n, k))
        self.eligible[:] = False
        self.count[:] = 0
        self.reasons[:] = 0
        self.reason_codes = {'PROTOCOL_MISMATCH': 0}
        self.views = {}

    def close(self):
        for array in [self.eligible, self.count, self.reasons]+[a for values in self.views.values() for a in values]:
            array.flush()
            if getattr(array, '_mmap', None) is not None and not array._mmap.closed:
                array._mmap.close()

    def build(self, view, norms, guard=None):
        n, k = len(self.rows), len(self.keys)
        pairs = np.lib.format.open_memmap(self.folder/('pairs_'+str(view)+'.npy'),
                    mode='w+', dtype=np.int16, shape=(n, k, 2))
        distances = np.lib.format.open_memmap(self.folder/('distances_'+str(view)+'.npy'),
                    mode='w+', dtype=np.float64, shape=(n, k, 2, 2))
        pairs[:] = -1
        distances[:] = 0
        # Norm groups contain disjoint query indices; formal view has one group.
        for indices, norm in norms:
            bank = _bank(self.refs, norm)
            for start in range(0, len(indices), 256):
                ix = np.asarray(indices[start:start+256], dtype=np.int64)
                rr = [self.rows[int(i)] for i in ix]
                for j, key in enumerate(self.keys):
                    positions = [p for p, r in enumerate(rr) if r['protocol'] == key[2]]
                    if not positions:
                        continue
                    use = ix[positions]
                    sub = [self.rows[int(i)] for i in use]
                    tr = _trace_checked(bank, sub, self.e3[use], self.q14[use],
                                        donor_keys=[key]*len(use), mining=True)
                    if view == 0:
                        self.eligible[use, j] = tr['eligible']
                        self.count[use, j] = tr['legal_component_count']
                        for reason in tr['reason']:
                            if str(reason) not in self.reason_codes:
                                self.reason_codes[str(reason)] = len(self.reason_codes)
                        self.reasons[use, j] = [self.reason_codes[str(reason)] for reason in tr['reason']]
                    else:
                        c.require(np.array_equal(self.eligible[use, j], tr['eligible']),
                                  'VIEW_ELIGIBILITY_CHANGED')
                    for pos in np.flatnonzero(tr['eligible']):
                        index = int(use[pos])
                        pairs[index, j] = [self.ref_index[u] for u in tr['matched_reference_uids'][pos]]
                        distances[index, j, :, 0] = tr['dz'][pos]
                        distances[index, j, :, 1] = tr['dq'][pos]
                if guard:
                    guard(stage='geometry_'+str(view), completed=min(start+256, len(indices)), total=len(indices))
        pairs.flush(); distances.flush(); self.eligible.flush(); self.count.flush(); self.reasons.flush()
        c.write(self.folder/'qualification_index.json', c.record('learned-onboarding-geometry-index-v1',
            status='RECORDED', reason_codes=self.reason_codes, bank_keys=self.keys,
            ordered_query_uid_sha256=c.uid_hash(_uids(self.rows), ordered=True),
            references=self.refs['rows'], reference_uids=self.refs['feature_uids'],
            layout='source_metadata.jsonl.gz rows; arrays indexed [source_slot,bank_column]'))
        self.views[view] = (pairs, distances)

    def features(self, view, indices, bank_columns, centers, scales):
        """Reconstruct 50 slots from two reference slots and four distances."""
        ix, cols = np.asarray(indices, np.int64), np.asarray(bank_columns, np.int64)
        pairs, distances = self.views[view]
        rep = np.asarray(pairs[ix, cols])
        c.require(np.all(rep >= 0), 'MISSING_GEOMETRY_REPRESENTATIVE')
        q = np.asarray(self.q14[ix], np.float64)
        qr = np.asarray(self.refs['q14'][rep], np.float64)
        delta = q[:, None, :]-qr
        ds = np.asarray(distances[ix, cols])
        scores = np.asarray([self.task_scores[view][int(i)] for i in ix], np.float64)
        t, s = np.asarray(centers), np.asarray(scales)
        result = np.zeros((len(ix), 50), np.float32)
        result[:, :14] = q
        result[:, 14:28] = delta.mean(axis=1)
        result[:, 28:42] = np.abs(delta).mean(axis=1)
        result[:, 42:46] = np.column_stack((ds[:, 0, 0]/2, ds[:, 1, 0]/2,
                                           ds[:, 0, 1], ds[:, 1, 1]))
        positive = s > 0
        result[positive, 46] = np.clip((scores[positive]-t[positive])/s[positive], -8, 8)/8
        result[:, 47] = np.minimum(np.log2(self.count[ix, cols])/6, 1)
        result[:, 48] = [self.rows[int(i)]['protocol'] == 6 for i in ix]
        result[:, 49] = 1-result[:, 48]
        c.require(np.isfinite(result).all(), 'GEOMETRY_FEATURE_NONFINITE')
        return result

    def task_records(self, scores, statistics, folds, auxiliary_statistics, guard=None):
        self.task_scores = scores
        records = []
        for view in (0, 1):
            pairs, distances = self.views[view]
            for i, row in enumerate(self.rows):
                own_key = (row['partition'], row['device'], row['protocol'])
                own = self.key_index[own_key]
                columns = ([own] if row['label'] == 0 else
                           np.flatnonzero(self.eligible[i]).tolist())
                columns = [j for j in columns if self.eligible[i, j]]
                if not columns:
                    continue
                stat = statistics[folds[row['uid']]['fold']] if view == 0 else auxiliary_statistics[row['device']]
                record = {key: row[key] for key in ('uid', 'device', 'label', 'protocol', 'activity',
                    'capture_id', 'source_sha256', 'session_id', 'component_id')}
                record.update(view=view, fit_role='FIT', partition='LEARN',
                    fold=folds[row['uid']]['fold'], group=folds[row['uid']]['group'],
                    source_slot=i, own_bank=bool(self.eligible[i, own]), eligible=True,
                    score=float(scores[view][i]), t=stat['t'], s=stat['s'],
                    banks=BankCandidates(self, view, i, columns))
                records.append(record)
                if guard and i % 4096 == 0:
                    guard(stage='source_task_records', view=view, completed=i, total=len(self.rows))
        return sorted(records, key=lambda x: (x['view'], x['uid']))

    def batch(self, records, indices):
        chosen = [records[int(i)] for i in indices]
        width = max(len(t['banks']) for t in chosen)
        x = np.zeros((len(chosen), width, 50), np.float32)
        mask = np.zeros((len(chosen), width), bool)
        for view in (0, 1):
            for column in range(width):
                positions = [p for p, t in enumerate(chosen) if t['view'] == view and
                             column < len(t['banks']) and t['s'] > 0]
                if not positions:
                    continue
                group = [chosen[p] for p in positions]
                x[positions, column] = self.features(view,
                    [t['source_slot'] for t in group], [t['banks'][column]['column'] for t in group],
                    [t['t'] for t in group], [t['s'] for t in group])
                mask[positions, column] = True
        return dict(features=x, candidate_mask=mask,
            margins=np.asarray([(t['score']-t['t'])/t['s'] if t['s'] > 0 else 0 for t in chosen]),
            scales=np.asarray([t['s'] for t in chosen]), labels=np.asarray([t['label'] for t in chosen]))


def _guard_callback(guard, phase_hours=None):
    started = time.monotonic()
    def tick(**progress):
        if phase_hours is not None:
            c.require(time.monotonic()-started <= phase_hours*3600, 'RESOURCE_STAGE_TIME_LIMIT')
        if guard is not None:
            guard.check(**progress)
    return tick


def fit_source(source, output, *, synthetic=False, auxiliary_epochs=40, module_steps=4000, guard=None):
    """Explicit fitting stage; target loader is deliberately absent from this API."""
    learning._setup()
    out = c.fresh(output)
    rows = source['rows']; refs = source['references']
    c.require(source.get('feature_uids') == _uids(rows) == source.get('q_uids') and
              len(set(_uids(rows))) == len(rows), 'SOURCE_ORDERED_UID_JOIN')
    isolation = source_isolation(rows, source['fit_indices'], source['cal_indices'], refs)
    c.write(out/'input_binding.json', source['binding'])
    c.write(out/'implementation_code.json', implementation_hashes())
    c.write(out/'runtime.json', c.record('learned-onboarding-numeric-runtime-v1', status='RECORDED',
                                       runtime=c.environment()))
    c.write(out/'source_isolation.json', isolation)
    fit_ix = np.asarray(source['fit_indices'], np.int64)
    rr = [rows[int(i)] for i in fit_ix]
    _jsonl(out/'source_metadata.jsonl.gz', rr)
    z, q = IndexedRows(source['e3'], fit_ix), IndexedRows(source['q14'], fit_ix)
    callback = _guard_callback(guard)
    coverage = source_coverage(rr, z, q, refs, source['normalizer'], callback)
    c.write(out/'source_task_receipt.json', coverage)
    if coverage['status'] != 'READY':
        return _noop(out, coverage['status'], coverage, synthetic)
    folds = tasklib.dependency_folds(rr)
    c.write(out/'dependency_folds.json', folds)
    # Compute complementary FIT statistics before auxiliary training; invalid folds stop scientifically.
    formal_scores = np.asarray(source['score_main'](fit_ix), np.float64)
    try:
        statistics = tasklib.fit_statistics(rr, formal_scores, folds)
    except ValueError as error:
        if str(error) == 'SOURCE_TASK_NOT_EVALUABLE':
            return _noop(out, 'SOURCE_TASK_NOT_EVALUABLE', coverage, synthetic)
        raise
    aux_scores = np.empty(len(rr), np.float64)
    aux_split_scores = np.empty(len(rr), np.float64)
    aux_norms, aux_statistics, aux_receipts = [], {}, {}
    for group_index, devices in enumerate(c.GROUPS):
        train_ix = np.asarray([i for i, r in enumerate(rr) if r['device'] in devices], np.int64)
        held_ix = np.asarray([i for i, r in enumerate(rr) if r['device'] not in devices], np.int64)
        receipt = learning.fit_auxiliary_head(rr, z, q, train_ix, out/('AUX_G'+str(group_index)),
            synthetic=synthetic, epochs=auxiliary_epochs, guard=_guard_callback(guard, 4))
        model, mean, scale, checkpoint = learning.load_auxiliary_head(receipt['checkpoint'], allow_synthetic=synthetic)
        fitted = learning.score_auxiliary_head(receipt['checkpoint'], IndexedRows(z, train_ix),
                    IndexedRows(q, train_ix), allow_synthetic=synthetic)
        # Auxiliary t/s uses its own complete training group only, never its held group.
        stat = tasklib._statistics([rr[int(i)] for i in train_ix], fitted)
        train_uids, held_uids = _uids([rr[int(i)] for i in train_ix]), _uids([rr[int(i)] for i in held_ix])
        c.require(not set(train_uids).intersection(held_uids) and
                  checkpoint['fit_uids'] == train_uids, 'AUX_TRAIN_HELD_UID_IDENTITY')
        c.write(out/('AUX_G'+str(group_index))/'isolation.json', c.record('learned-onboarding-aux-isolation-v1',
            status='VERIFIED', train_devices=devices, held_devices=c.GROUPS[1-group_index],
            fit_uid_sha256=c.uid_hash(train_uids, ordered=True),
            normalizer_uid_sha256=checkpoint['normalizer_uid_hash'],
            held_uid_sha256=c.uid_hash(held_uids, ordered=True), uid_overlap=0))
        aux_scores[held_ix] = learning.score_auxiliary_head(receipt['checkpoint'], IndexedRows(z, held_ix),
                    IndexedRows(q, held_ix), allow_synthetic=synthetic)
        aux_split_scores[held_ix] = learning.score_auxiliary_head(receipt['checkpoint'], IndexedRows(z, held_ix),
                    IndexedRows(q, held_ix), allow_synthetic=synthetic, batch_size=127)
        replay = learning.verify_auxiliary_replay(receipt['checkpoint'], IndexedRows(z, held_ix),
            IndexedRows(q, held_ix), stat['t'], [rr[int(i)]['label'] for i in held_ix],
            allow_synthetic=synthetic)
        c.write(out/('AUX_G'+str(group_index))/'replay.json', c.record('learned-onboarding-aux-replay-v1',
            status='PASS', threshold_scope='FIT_PSEUDO_ONLY', **replay))
        for i in held_ix:
            aux_statistics[rr[int(i)]['device']] = stat
        aux_norms.append((held_ix, (mean, scale)))
        aux_receipts['AUX_G'+str(group_index)] = receipt
        c.write(out/('AUX_G'+str(group_index))/'endpoint.json', c.record('learned-onboarding-endpoint-v1',
            status='COMPLETE', **receipt))
        c.seal(out/('AUX_G'+str(group_index)))
    geometry = GeometryStore(out/'source_geometry', rr, z, q, refs)
    geometry.build(0, [(np.arange(len(rr)), source['normalizer'])], callback)
    geometry.build(1, aux_norms, callback)
    records = geometry.task_records({0: formal_scores, 1: aux_scores}, statistics, folds, aux_statistics, callback)
    for task in records:
        if task['view'] == 1:
            task['score'] = float(aux_split_scores[task['source_slot']])
    alternate_hard, _ = tasklib.mine_hard_tasks(records)
    for task in records:
        if task['view'] == 1:
            task['score'] = float(aux_scores[task['source_slot']])
    hard, hard_receipt = tasklib.mine_hard_tasks(records)
    c.require(hard == alternate_hard, 'QUERY_BATCH_H_SET_DRIFT')
    del alternate_hard, aux_split_scores
    callback(stage='source_mining_complete', tasks=len(records))
    c.write(out/'numeric_source_replay.json', c.record('learned-onboarding-source-replay-v1',
        status='PASS', reference_representatives_equal=True, hard_sets_equal=True,
        query_batches=[256, 127], reference_blocks=[64, 31], target_queries_read=0))
    for task in records:
        task['hard'] = (task['view'], task['uid']) in hard
    signal = tasklib.residual_signal(records)
    c.write(out/'source_signal.json', c.record('learned-onboarding-residual-signal-v1', **signal))
    c.write(out/'fit_statistics.json', c.record('learned-onboarding-fit-statistics-v1', status='SEALED',
            formal=statistics, auxiliary_by_device=aux_statistics))
    np.savez_compressed(out/'fit_scores.npz', formal=formal_scores, auxiliary=aux_scores)
    _jsonl(out/'source_tasks.jsonl.gz', records)
    _jsonl(out/'hard_tasks.jsonl.gz', (t for t in records if t['hard']))
    c.write(out/'hard_task_receipt.json', c.record('learned-onboarding-mining-v1', status='SEALED', groups=hard_receipt))
    ordered, p0, ph = tasklib.build_task_distribution(records, hard)
    np.savez_compressed(out/'sampling.npz', ordinary=p0, hard=ph,
                        uniforms=tasklib.uniform_stream(module_steps, 256))
    c.write(out/'sampling_receipt.json', c.record('learned-onboarding-sampling-v1', status='SEALED',
        task_order_digest=c.digest([(t['view'], t['uid']) for t in ordered]),
        hard_count=len(hard), sampling_sha256=c.sha(out/'sampling.npz'), synthetic_only=synthetic))
    if signal['status'] != 'READY':
        geometry.close()
        return _noop(out, signal['status'], coverage, synthetic, auxiliary=aux_receipts, signal=signal)
    receipts = learning.train_modules(ordered, lambda ix: geometry.batch(ordered, ix), out, hard,
                synthetic=synthetic, steps=module_steps, guard=_guard_callback(guard, 2))
    # FIT-only probes cover each view/fold/device/class, including all its banks.
    probes = {}
    for i, task in enumerate(ordered):
        key = (task['view'], task['fold'], task['device'], task['label'])
        if len(probes.setdefault(key, [])) < 32:
            probes[key].append(i)
    for arm in c.ARMS:
        replay = []
        for key, indices in sorted(probes.items()):
            group = [ordered[i] for i in indices]
            batch = geometry.batch(ordered, indices)
            mask = batch['candidate_mask']
            if not mask.any():
                continue
            base = np.repeat([t['score'] for t in group], mask.shape[1])[mask.ravel()]
            scales = np.repeat([t['s'] for t in group], mask.shape[1])[mask.ravel()]
            labels = np.repeat([t['label'] for t in group], mask.shape[1])[mask.ravel()]
            item = learning.verify_module_replay(receipts[arm]['checkpoint'], batch['features'][mask],
                base, scales, group[0]['t'], labels, allow_synthetic=synthetic)
            replay.append(dict(group=key, **item))
        c.write(out/arm/'replay.json', c.record('learned-onboarding-module-replay-v1',
            status='PASS', threshold_scope='FIT_PSEUDO_ONLY',
            coverage='up to 32 eligible queries per view/fold/device/class, all legal banks', groups=replay))
        c.write(out/arm/'endpoint.json', c.record('learned-onboarding-endpoint-v1', status='COMPLETE', **receipts[arm]))
        c.seal(out/arm)
    geometry.close()
    result = c.record('learned-onboarding-fit-v1', status='COMPLETE', synthetic_only=synthetic,
        source_coverage=coverage, source_signal=signal, auxiliary=aux_receipts, modules=receipts,
        final_statistics=statistics['full'], target_queries_read=0, scientific_results=None)
    c.write(out/'FIT_COMPLETE.json', result)
    if guard:
        guard.check(force=True, stage='fit_artifacts_complete')
    c.seal(out)
    return result


def _noop(out, reason, coverage, synthetic, auxiliary=None, signal=None):
    modules = {}
    for arm in c.ARMS:
        folder = out/arm
        folder.mkdir(exist_ok=True)
        modules[arm] = c.record('learned-onboarding-endpoint-v1', status='NOT_TRAINED',
            noop=True, reason=reason, synthetic_only=synthetic, optimizer_updates=0)
        c.write(folder/'endpoint.json', modules[arm]); c.seal(folder)
    result = c.record('learned-onboarding-fit-v1', status='NOOP', reason=reason,
        synthetic_only=synthetic, source_coverage=coverage, source_signal=signal,
        auxiliary=auxiliary or {}, modules=modules, target_queries_read=0, scientific_results=None)
    c.write(out/'FIT_COMPLETE.json', result); c.seal(out)
    return result


def _load_modules(fit_dir, synthetic):
    receipt = c.read(Path(fit_dir)/'FIT_COMPLETE.json')
    c.require(synthetic or not receipt['synthetic_only'], 'SYNTHETIC_MODEL_IN_PRODUCTION')
    models = {}
    if receipt['status'] == 'COMPLETE':
        for arm in c.ARMS:
            c.verify_seal(Path(fit_dir)/arm)
            models[arm] = (learning.load_module(Path(fit_dir)/arm/'final.pt', allow_synthetic=synthetic)[0],
                           learning.load_module(Path(fit_dir)/arm/'final.pt', allow_synthetic=synthetic)[0])
    else:
        c.require(receipt['status'] == 'NOOP', 'FIT_NOT_COMPLETE')
    return receipt, models


def _predict(bank, rows, z, q, scores, stat, model, query_only=False, donor_keys=None, reference_uids=None,
             return_trace=False, decision_cut=None, lambda_value=0.):
    strength = np.zeros(len(rows), np.float64)
    eligible = np.zeros(len(rows), bool)
    reasons, representatives, traces = [], [], []
    for start in range(0, len(rows), 256):
        sl = slice(start, start+256); rr = rows[sl]
        tr = _trace_checked(bank, rr, z[sl], q[sl],
            donor_keys=None if donor_keys is None else donor_keys[sl],
            reference_uids=None if reference_uids is None else reference_uids[sl])
        use = np.flatnonzero(tr['eligible'])
        if model is not None and stat['s'] > 0 and len(use):
            x = make_features(rr, q[sl], scores[sl], stat['t'], stat['s'], tr, query_only=query_only)
            first, second = model if isinstance(model, tuple) else (model, model)
            a = learning.score_module(first, x[use], query_only=query_only)
            reloaded = learning.score_module(second, x[use], query_only=query_only)
            split = learning.score_module(first, x[use], query_only=query_only, batch_size=127)
            if decision_cut is None:
                c.require(np.array_equal(a, reloaded) and np.allclose(a, split, rtol=1e-6, atol=1e-6),
                          'MODULE_SCORE_REPLAY_DRIFT')
            else:
                for candidate in c.LAMBDAS:
                    learning._replay_compare(a, reloaded, split, np.asarray(scores[sl])[use],
                        np.full(len(use), stat['s']), decision_cut, [rr[int(i)]['label'] for i in use], candidate)
            strength[start+use] = a
        eligible[sl] = tr['eligible']
        reasons.extend(tr['reason'].tolist())
        representatives.extend(tr['matched_reference_uids'].tolist())
        if return_trace:
            for i in range(len(rr)):
                traces.append(dict(matched_components=tr['matched_components'][i].tolist(),
                    legal_component_count=int(tr['legal_component_count'][i]),
                    legal_reference_count=int(tr['legal_reference_count'][i]),
                    bank_key=tr['bank_key'][i],
                    bank_end=float(tr['bank_end'][i]) if np.isfinite(tr['bank_end'][i]) else None,
                    bank_end_frame=tr['bank_end_frame'][i], prebank_audit=tr['prebank_audit'][i]))
    result = (strength, eligible, reasons, representatives)
    return result+(traces,) if return_trace else result


def calibrate_source(source, fit_dir, output, *, synthetic=False, guard=None):
    """Source CAL only, after every fitted weight and source recipe is sealed."""
    learning._setup()
    c.verify_seal(fit_dir)
    _verify_fit_code(fit_dir)
    c.require(c.read(Path(fit_dir)/'input_binding.json') == source['binding'], 'FIT_SOURCE_BINDING_CHANGED')
    fit, models = _load_modules(fit_dir, synthetic)
    out = c.fresh(output)
    c.write(out/'input_binding.json', source['binding'])
    if not synthetic:
        from source_inputs import verify_source_cut
        c.write(out/'source_cut_replay.json', verify_source_cut(source))
    rr_all = source['rows']; ix_all = np.asarray(source['cal_indices'], np.int64)
    ix = np.asarray([i for i in ix_all if rr_all[int(i)]['label'] == 1], np.int64)
    rows = [rr_all[int(i)] for i in ix]
    z, q = IndexedRows(source['e3'], ix), IndexedRows(source['q14'], ix)
    scores = np.asarray(source['score_main'](ix), np.float64)
    bank = _bank(source['references'], source['normalizer'])
    stats = c.read(Path(fit_dir)/'fit_statistics.json')['formal']['full'] if models else dict(t=0., s=0.)
    arms = {}
    for arm in c.ARMS:
        aa, ee = np.zeros((len(rows), len(bank.keys))), np.zeros((len(rows), len(bank.keys)), bool)
        for j, key in enumerate(bank.keys):
            # Only matching protocols enter the bank API; other rows retain exact fallback.
            positions = np.asarray([i for i, r in enumerate(rows) if r['protocol'] == key[2]], np.int64)
            sub = [rows[int(i)] for i in positions]
            a, e, _, _ = _predict(bank, sub, IndexedRows(z, positions), IndexedRows(q, positions),
                scores[positions], stats, models.get(arm), arm == 'L_QUERY_ONLY', [key]*len(sub),
                decision_cut=source['cut'])
            aa[positions, j], ee[positions, j] = a, e
            if guard:
                guard.check(stage='calibration_'+arm, bank=j)
        arms[arm] = evaluation.calibrate_lambda(rows, scores, source['cut'], aa, ee, stats['s'],
            bank.keys, source_components=[r['component_id'] for r in source['references']['rows']])
    # Fixed geometry comparison remains the original scalar v3 algorithm.
    refs = source['references']
    v3 = evaluation.ScalarV3(refs['rows'], refs['e3'], refs['q14'], source['normalizer'],
            feature_uids=refs['feature_uids'], q_uids=refs['q_uids'], allowed_partitions=('LEARN',))
    fi = np.asarray(source['fit_indices'], np.int64)
    normal = np.asarray([i for i in fi if rr_all[int(i)]['label'] == 0], np.int64)
    nr = [rr_all[int(i)] for i in normal]
    geometry = v3.fit_geometry(nr, source['e3'][normal], source['q14'][normal],
                              feature_uids=_uids(nr), q_uids=_uids(nr))
    scale = v3.fit_scales([rr_all[int(i)] for i in fi], source['score_main'](fi))
    protection = v3.choose_lambda(rows, scores, source['cut'], scale['scale'],
                                 source['e3'][ix], source['q14'][ix], geometry,
                                 feature_uids=_uids(rows), q_uids=_uids(rows))
    result = c.record('learned-onboarding-calibration-stage-v1', status='SEALED',
        synthetic_only=synthetic, fit_seal_sha256=c.sha(Path(fit_dir)/'SEAL.json'),
        input_binding_digest=c.digest(source['binding']), cut=source['cut'],
        statistics=stats, arms=arms, v3=dict(geometry=geometry, scales=scale, protection=protection),
        target_queries_read=0)
    c.write(out/'calibration.json', result)
    c.write(out/'runtime.json', c.record('learned-onboarding-numeric-runtime-v1', status='RECORDED',
                                       runtime=c.environment()))
    if guard:
        guard.check(force=True, stage='calibration_artifacts_complete')
    c.seal(out)
    return result


def evaluate_targets(source, fit_dir, calibration_dir, target_loader, output,
                     *, synthetic=False, guard=None):
    """The target loader is invoked only after fit and calibration seal validation."""
    learning._setup()
    c.verify_seal(fit_dir); c.verify_seal(calibration_dir)
    _verify_fit_code(fit_dir)
    c.require(c.read(Path(fit_dir)/'input_binding.json') == source['binding'], 'FIT_SOURCE_BINDING_CHANGED')
    fit, models = _load_modules(fit_dir, synthetic)
    cal = c.read(Path(calibration_dir)/'calibration.json')
    c.require(synthetic or not cal['synthetic_only'], 'SYNTHETIC_CALIBRATION_IN_PRODUCTION')
    c.require(cal['fit_seal_sha256'] == c.sha(Path(fit_dir)/'SEAL.json') and
              cal['input_binding_digest'] == c.digest(source['binding']) and
              cal['cut'] == source['cut'], 'CALIBRATION_BINDING_CHANGED')
    out = c.fresh(output)
    c.write(out/'input_binding.json', source['binding'])
    c.write(out/'runtime.json', c.record('learned-onboarding-numeric-runtime-v1', status='RECORDED',
                                       runtime=c.environment()))
    targets = target_loader()
    c.require(set(targets) == {'CIC_DEV', 'UNSW_DEV'}, 'TARGET_POOL_MATRIX')
    matrix, controls, plans = {}, {}, {}
    stats = cal['statistics']
    for pool, data in targets.items():
        rows, z, q, scores = (data[k] for k in ('rows', 'e3', 'q14', 'scores'))
        c.require(list(data['feature_uids']) == _uids(rows) == list(data['q_uids']), 'TARGET_UID_BINDING')
        c.require(set(data['banks']) == {'OLD_BANK', 'B0', 'B1', 'B2'}, 'TARGET_BANK_MATRIX')
        if not synthetic:
            replay = source['score_queries'](z, q)
            expected = np.asarray(scores, np.float64)
            actual = np.asarray(replay, np.float64)
            c.require(actual.shape == expected.shape and actual.tobytes() == expected.tobytes(),
                      'TARGET_BASE_SCORE_NOT_BITWISE:'+pool)
            c.write(out/(pool+'_base_replay.json'), c.record('learned-onboarding-target-base-replay-v1',
                status='PASS', ordered_uid_sha256=c.uid_hash(_uids(rows), ordered=True),
                rows=len(rows), source_binding_digest=c.digest(source['binding']),
                numeric_bytes_sha256=__import__('hashlib').sha256(actual.tobytes()).hexdigest()))
        # Seal all WRONG choices from metadata before producing target correction scores.
        pool_plans = {}
        bank = _bank(data['banks']['B2'], source['normalizer'], target=True)
        own = bank.qualification(rows)
        pool_plans = bank.plan_wrong(rows, own)
        plans[pool] = pool_plans
    c.write(out/'control_plan.json', c.record('learned-onboarding-controls-v1', status='SEALED', plans=plans))
    for pool, data in targets.items():
        rows, z, q, scores = (data[k] for k in ('rows', 'e3', 'q14', 'scores'))
        for policy, refs in data['banks'].items():
            bank = _bank(refs, source['normalizer'], target=policy != 'OLD_BANK')
            _, own, reasons, representatives, trace = _predict(bank, rows, z, q, scores, stats, None,
                                                               return_trace=True)
            base_pair = evaluation.evaluate_pair(rows, scores, scores, source['cut'], own, 0., 0.,
                reasons=reasons, pool=pool, bank=policy, arm='BASE')
            matrix[(pool, policy, 'BASE')] = _save_pair(out, pool, policy, 'BASE', base_pair, representatives, trace)
            v3 = evaluation.ScalarV3(refs['rows'], refs['e3'], refs['q14'], source['normalizer'],
                feature_uids=refs['feature_uids'], q_uids=refs['q_uids'], allow_prebank_history=policy != 'OLD_BANK')
            tr = v3.own(rows, z, q, cal['v3']['geometry'], feature_uids=_uids(rows), q_uids=_uids(rows))
            vs, vl = cal['v3']['scales']['scale'], cal['v3']['protection']['selected_lambda']
            changed = v3.correction(scores, tr, vs, vl)
            vp = evaluation.evaluate_pair(rows, scores, changed, source['cut'], tr['eligible'], vs, vl,
                reasons=tr['reason'], strengths=tr['support'], pool=pool, bank=policy, arm='V3')
            matrix[(pool, policy, 'V3')] = _save_pair(out, pool, policy, 'V3', vp, tr['matched_reference_uids'])
            for arm in c.ARMS:
                a, e, reason, reps, trace = _predict(bank, rows, z, q, scores, stats, models.get(arm),
                    arm == 'L_QUERY_ONLY', return_trace=True, decision_cut=source['cut'])
                lam = cal['arms'][arm]['selected_lambda']
                corrected = apply_correction(scores, a, e, stats['s'], lam)
                pair = evaluation.evaluate_pair(rows, scores, corrected, source['cut'], e, stats['s'], lam,
                    reasons=reason, strengths=a, pool=pool, bank=policy, arm=arm)
                matrix[(pool, policy, arm)] = _save_pair(out, pool, policy, arm, pair, reps, trace)
                if policy == 'B2':
                    controls[(pool, arm)] = _controls(out, pool, arm, bank, data, stats, models.get(arm),
                                                     lam, source['cut'], plans[pool])
                if guard:
                    guard.check(stage='evaluation', pool=pool, policy=policy, arm=arm)
    wrong = _wrong_summary(controls)
    decision = evaluation.scientific_decision(matrix, source_coverage=fit['source_coverage'],
                                              source_signal=fit.get('source_signal'), wrong_control=wrong)
    c.write(out/'paired_summary.json', c.record('learned-onboarding-matrix-v1', status='COMPLETE',
        cells=[dict(pool=k[0], bank=k[1], arm=k[2], summary=v) for k, v in matrix.items()], controls=wrong))
    c.write(out/'decision.json', decision)
    c.write(out/'EVALUATION_COMPLETE.json', c.record('learned-onboarding-evaluation-v1', status='COMPLETE',
        cells=len(matrix), synthetic_only=synthetic, scientific_decision='decision.json'))
    if guard:
        guard.check(force=True, stage='evaluation_artifacts_complete')
    c.seal(out)
    return decision


def _save_pair(out, pool, policy, arm, pair, reps, trace=None):
    folder = Path(out)/'predictions'/pool/policy/arm
    folder.mkdir(parents=True)
    for row, representative in zip(pair['per_query'], reps):
        row['matched_reference_uids'] = list(representative)
    if trace is not None:
        c.require(len(trace) == len(pair['per_query']), 'PREDICTION_TRACE_ROWS')
        for row, item in zip(pair['per_query'], trace):
            row.update(item)
    _jsonl(folder/'predictions.jsonl.gz', pair['per_query'])
    c.write(folder/'summary.json', pair['summary'])
    return pair['summary']


def _controls(out, pool, arm, bank, data, stat, model, lam, cut, plan):
    rows, z, q, scores = (data[k] for k in ('rows', 'e3', 'q14', 'scores'))
    # EMPTY is represented by exact source-copy scores and no network call.
    empty = evaluation.evaluate_pair(rows, scores, scores, cut, np.zeros(len(rows), bool), stat['s'], 0.,
        reasons=['EMPTY_BANK']*len(rows), pool=pool, bank='EMPTY', arm=arm)
    _save_pair(out, pool, 'EMPTY', arm, empty, [[None, None]]*len(rows))
    a, e, reason, reps, trace = _predict(bank, rows, z, q, scores, stat, model, arm == 'L_QUERY_ONLY',
        plan['donor_keys'], plan['reference_uids'], return_trace=True, decision_cut=cut)
    corrected = apply_correction(scores, a, e, stat['s'], lam)
    pair = evaluation.evaluate_pair(rows, scores, corrected, cut, e, stat['s'], lam,
        reasons=reason, strengths=a, pool=pool, bank='WRONG', arm=arm)
    _save_pair(out, pool, 'WRONG', arm, pair, reps, trace)
    aa, own, _, _ = _predict(bank, rows, z, q, scores, stat, model, arm == 'L_QUERY_ONLY')
    own_scores = apply_correction(scores, aa, own, stat['s'], lam)
    normal = np.asarray([r['label'] == 0 for r in rows])
    matched = e & own
    eligible_fp = normal & matched & (scores > cut)
    weights = np.asarray([1./r['label_metric_weight_denominator'] for r in rows])
    own_fixed = eligible_fp & ~(own_scores > cut)
    wrong_fixed = eligible_fp & ~(corrected > cut)
    denominator = float(weights[normal & matched].sum())
    return dict(matched_rows=int(matched.sum()), matched_normal_base_fp=int(eligible_fp.sum()),
        matched_normal_weight=denominator,
        own_fixed_weight=float(weights[own_fixed].sum()), wrong_fixed_weight=float(weights[wrong_fixed].sum()),
        own_subset_weighted_fpr=float(weights[normal & matched & (own_scores > cut)].sum()/denominator)
            if denominator else None,
        wrong_subset_weighted_fpr=float(weights[normal & matched & (corrected > cut)].sum()/denominator)
            if denominator else None,
        own_fixed=int((eligible_fp & ~(own_scores > cut)).sum()),
        wrong_fixed=int((eligible_fp & ~(corrected > cut)).sum()),
        wrong_new_fn=pair['summary']['new_fn_count'])


def _wrong_summary(controls):
    items = [dict(pool=pool, arm=arm, **value) for (pool, arm), value in controls.items()]
    hard = [x for x in items if x['arm'] == 'L_HARD' and x['matched_normal_base_fp'] > 0]
    informative = bool(hard)
    return dict(status='EVALUATED' if informative else 'NOT_EVALUABLE', cells=items,
        equally_effective=informative and all(x['wrong_new_fn'] == 0 and x['wrong_fixed'] >= x['own_fixed'] and
            x['wrong_fixed_weight'] >= x['own_fixed_weight'] for x in hard))


def write_exception(output, stage, error):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    last = c.read(out/'status.json') if (out/'status.json').is_file() else None
    bindings = c.read(out/'input_binding.json') if (out/'input_binding.json').is_file() else None
    completed_cells = [str(p.parent.relative_to(out)) for p in out.rglob('summary.json')]
    c.write(out/'EXCEPTION_STOP.json', c.record('learned-onboarding-exception-v1',
        status='EXCEPTION_STOP', stage=stage, error_type=type(error).__name__,
        error=str(error), traceback=traceback.format_exc(), automatic_retry=False,
        existing_artifacts_retained=True, last_progress=last, input_binding=bindings,
        completed_cells=completed_cells))
