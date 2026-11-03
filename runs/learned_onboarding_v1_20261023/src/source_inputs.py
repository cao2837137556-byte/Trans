"""Read-only source adapter for the frozen QUERY_TAIL seed-27 head.

Only LEARN and SOURCE_REFS are opened from the verified cache. The completed
head archive is searched by an exact member allowlist; target pools stay sealed.
"""

import bisect
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tarfile

import numpy as np

from common import ROOT, check_spec, digest, pin, read, require, sha, uid_hash


DEFAULT_CACHE = ROOT / 'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022'
DEFAULT_ARCHIVE = ROOT / 'runs/query_tail_ecs_v1_20261022/pullback/results'
DEFAULT_BINDING = ROOT / 'runs/query_tail_ecs_v1_20261022/cache_binding.json'
DEFAULT_OUTPUT = ROOT / 'runs/learned_onboarding_v1_20261023/results/source_assets'
BACKUP_INDEX_SHA256 = '2fd46ea9e8db0b88eb1d375f20f366f0f80ec33189c2dcfa35493033734581b8'
QUERY_COMPLETE_SHA256 = 'fd9b46e510c0937d8c151aa80dd3940a636e8a68e618ec3ef9267a846705fd83'
QUERY_DESIGN_SHA256 = 'c6027a90f1f997b1bb1e8dd44409237531d7dc97cc13813e9bec364dc40b21af'
COUNTS = dict(LEARN=766727, FIT=617908, CAL=148819, SOURCE_REFS=179,
              LEARN_REFS=104)
ARCHIVE_WANTED = (
    'query_code/design_contract.json',
    'query_code/SHA256SUMS',
    'run/prepared/LEARN_q.npy', 'run/prepared/receipt.json',
    'run/prepared/SHA256SUMS', 'run/thresholds.json',
    'run/cache_binding.json', 'run/endpoint_audits/QUERY_TAIL_27/lineage.json',
    'run/endpoints/QUERY_TAIL_27/endpoint.json',
    'run/endpoints/QUERY_TAIL_27/head.npz',
    'run/endpoints/QUERY_TAIL_27/SHA256SUMS',
    'run/LINEAGE_P_COMPLETE.json', 'run/LINEAGE_T_COMPLETE.json',
    'run/LINEAGE_K_COMPLETE.json', 'run/QUERY_LINEAGE_COMPLETE.json',
    'run/endpoint_audits/QUERY_TAIL_27/SHA256SUMS',
)


class ConcatenatedChunks(io.RawIOBase):
    """Seekable tar reader without copying or unpacking the complete stream."""

    def __init__(self, folder, index, verify=True):
        self.folder = Path(folder)
        self.chunks = index['chunks']
        require(index.get('format') == 'tar-stream-concatenate-parts-in-order' and
                index.get('complete') is True, 'ARCHIVE_INDEX_FORMAT')
        self.offsets = [0]
        self.files = []
        for item in self.chunks:
            path = self.folder / item['name']
            require(path.name == item['name'] and path.is_file() and
                    path.stat().st_size == item['bytes'], 'ARCHIVE_CHUNK_SIZE')
            if verify:
                pin(path, item['sha256'])
            self.files.append(path.open('rb'))
            self.offsets.append(self.offsets[-1] + item['bytes'])
        require(self.offsets[-1] == index['bytes'], 'ARCHIVE_TOTAL_BYTES')
        self.position = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=os.SEEK_SET):
        position = (offset if whence == os.SEEK_SET else
                    self.position + offset if whence == os.SEEK_CUR else
                    self.offsets[-1] + offset)
        require(0 <= position <= self.offsets[-1], 'ARCHIVE_SEEK')
        self.position = position
        return position

    def read(self, size=-1):
        if size < 0:
            size = self.offsets[-1] - self.position
        size = min(size, self.offsets[-1] - self.position)
        parts = []
        while size:
            j = bisect.bisect_right(self.offsets, self.position) - 1
            length = min(size, self.offsets[j + 1] - self.position)
            f = self.files[j]
            f.seek(self.position - self.offsets[j])
            part = f.read(length)
            require(len(part) == length, 'ARCHIVE_SHORT_READ')
            parts.append(part)
            self.position += length
            size -= length
        return b''.join(parts)

    def close(self):
        for f in self.files:
            f.close()
        super().close()


def archive_members(folder, *, verify=True):
    folder = Path(folder)
    index_path = folder / 'BACKUP_INDEX.json'
    if folder.resolve() == DEFAULT_ARCHIVE.resolve():
        pin(index_path, BACKUP_INDEX_SHA256)
    index = read(index_path)
    with ConcatenatedChunks(folder, index, verify=verify) as stream:
        with tarfile.open(fileobj=stream, mode='r:') as archive:
            return {m.name: dict(size=m.size, offset_data=m.offset_data,
                                 file=m.isfile()) for m in archive.getmembers()}


def extract_source_members(folder, destination, *, verify=True):
    """Extract only named source/head metadata; never target query members."""
    folder, destination = Path(folder), Path(destination)
    index_path = folder / 'BACKUP_INDEX.json'
    if folder.resolve() == DEFAULT_ARCHIVE.resolve():
        pin(index_path, BACKUP_INDEX_SHA256)
    index = read(index_path)
    destination.mkdir(parents=True, exist_ok=True)
    extracted = {}
    with ConcatenatedChunks(folder, index, verify=verify) as stream:
        with tarfile.open(fileobj=stream, mode='r:') as archive:
            members = {m.name: m for m in archive.getmembers()}
            for name in ARCHIVE_WANTED:
                member = members.get(name)
                if member is None:
                    continue
                require(member.isfile(), 'ARCHIVE_MEMBER_TYPE:' + name)
                target = destination / name
                require(destination.resolve() in target.resolve().parents,
                        'ARCHIVE_PATH_ESCAPE')
                source = archive.extractfile(member)
                require(source is not None, 'ARCHIVE_MEMBER_READ:' + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                member_hash = hashlib.sha256()
                if target.exists():
                    require(target.stat().st_size == member.size,
                            'EXTRACTED_SIZE_DRIFT:' + name)
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        member_hash.update(block)
                else:
                    with target.open('xb') as output:
                        while True:
                            block = source.read(1024 * 1024)
                            if not block:
                                break
                            member_hash.update(block)
                            output.write(block)
                copied_sha = sha(target)
                require(copied_sha == member_hash.hexdigest(),
                        'EXTRACTED_MEMBER_DRIFT:' + name)
                extracted[name] = dict(path=str(target.resolve()),
                                       size=member.size, sha256=copied_sha)
    return extracted


def _manifest(folder, expected):
    pin(folder / 'SHA256SUMS', expected)
    result = {}
    for line in (folder / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        file_sha, name = line.split('  ', 1)
        target = (folder / name).resolve()
        require(name not in result and folder.resolve() in target.parents and
                len(file_sha) == 64, 'MANIFEST_SCHEMA')
        result[name] = file_sha
    return result


def _rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _source_metadata(cache, binding):
    marker = binding['marker']
    inputs = cache / 'inputs'
    manifests = _manifest(inputs, marker['original_input_manifest_sha256'])
    rows = _rows(pin(inputs / 'LEARN.jsonl.gz', manifests['LEARN.jsonl.gz']))
    refs_all = _rows(pin(inputs / 'SOURCE_REFS.jsonl.gz',
                         manifests['SOURCE_REFS.jsonl.gz']))
    require(len(rows) == COUNTS['LEARN'] and len(refs_all) == COUNTS['SOURCE_REFS'],
            'SOURCE_ROW_COUNT')
    receipt = read(pin(inputs / 'receipt.json', manifests['receipt.json']))
    require(uid_hash(r['uid'] for r in rows) == receipt
            ['metadata_uid_sha256']['LEARN'], 'SOURCE_UID_HASH')
    require(uid_hash(r['uid'] for r in refs_all) == receipt
            ['metadata_uid_sha256']['SOURCE_REFS'], 'REFERENCE_UID_HASH')
    reference_rows = [dict(r, parent_slot=i) for i, r in enumerate(refs_all)
                      if r['partition'] == 'LEARN']
    require(len(reference_rows) == COUNTS['LEARN_REFS'] and
            all(r['use'] == 'REFERENCE' and r['label'] == 0 for r in reference_rows),
            'SOURCE_REFERENCE_SCOPE')
    source_uids = {r['uid'] for r in rows}
    require(len(source_uids) == len(rows) and
            not any(r['uid'] in source_uids for r in reference_rows),
            'SOURCE_REFERENCE_QUERY_UID_OVERLAP')
    component_roles, dependency_roles = {}, {}
    for row in rows:
        role = row.get('fit_role')
        require(row.get('partition') == 'LEARN' and role in ('FIT', 'CAL') and
                row.get('use') != 'REFERENCE' and row.get('label') in (0, 1) and
                type(row.get('frame')) is int and row['frame'] > 0 and
                type(row.get('timestamp')) in (int, float) and
                math.isfinite(row['timestamp']) and
                all(isinstance(row.get(k), str) and row[k] for k in
                    ('device', 'source_sha256', 'capture_id', 'session_id',
                     'component_id')), 'SOURCE_ROW_SCHEMA')
        component = row['component_id']
        dependency = (row['source_sha256'], row['session_id'])
        require(component_roles.setdefault(component, role) == role and
                dependency_roles.setdefault(dependency, role) == role,
                'SOURCE_FIT_CAL_DEPENDENCY_OVERLAP')
    indices = {}
    for role in ('FIT', 'CAL'):
        with np.load(pin(inputs / (role + '.npz'),
                         manifests[role + '.npz']), allow_pickle=False) as saved:
            ix = saved['indices'].copy()
        require(ix.dtype == np.int64 and ix.ndim == 1 and
                len(ix) == COUNTS[role] and len(set(ix)) == len(ix) and
                np.all((ix >= 0) & (ix < len(rows))) and
                all(rows[int(i)]['fit_role'] == role for i in ix),
                'SOURCE_SPLIT_INDEX:' + role)
        indices[role] = ix
    require(len(set(indices['FIT']) | set(indices['CAL'])) == len(rows) and
            not set(indices['FIT']) & set(indices['CAL']), 'SOURCE_SPLIT_COVERAGE')
    return rows, reference_rows, indices, manifests


def prepare_source(config=None, output_dir=None, validate_only=True):
    """Bind source assets and expose unchanged seed-27 score replay on demand.

    validate_only controls whether score_main can be called; preparation itself
    performs no model forward and never opens target query files.
    """
    check_spec()
    config = {} if config is None else dict(config)
    cache = Path(config.get('cache', DEFAULT_CACHE)).resolve()
    archive = Path(config.get('archive', DEFAULT_ARCHIVE)).resolve()
    binding_path = Path(config.get('binding', DEFAULT_BINDING)).resolve()
    destination = Path(output_dir or config.get('output_dir', DEFAULT_OUTPUT)).resolve()
    require(not any(destination == protected or protected in destination.parents or
                    destination in protected.parents for protected in
                    (cache, archive, binding_path)), 'SOURCE_OUTPUT_INPUT_OVERLAP')
    binding = read(binding_path)
    require(binding['query_design_sha256'] == QUERY_DESIGN_SHA256 and
            binding['marker']['lineage'] == 'NEW_RECONSTRUCTION_LINEAGE',
            'SOURCE_CACHE_BINDING')
    rows, refs, indices, input_pins = _source_metadata(cache, binding)
    feature_pins = _manifest(cache / 'features',
                             binding['marker']['feature_manifest_sha256'])
    learn_path = pin(cache / 'features/LEARN.npy', feature_pins['LEARN.npy'])
    ref_path = pin(cache / 'features/SOURCE_REFS.npy',
                   feature_pins['SOURCE_REFS.npy'])
    values = np.load(learn_path, mmap_mode='r', allow_pickle=False)
    ref_values = np.load(ref_path, mmap_mode='r', allow_pickle=False)
    require(values.shape == (len(rows), 794) and
            ref_values.shape == (COUNTS['SOURCE_REFS'], 794) and
            values.dtype == ref_values.dtype == np.float32,
            'SOURCE_FEATURE_SCHEMA')
    norm_pins = _manifest(cache / 'normalizers',
                          binding['marker']['normalizer_manifest_sha256'])
    norm_path = pin(cache / 'normalizers/RECENT.npz', norm_pins['RECENT.npz'])
    with np.load(norm_path, allow_pickle=False) as saved:
        norm = saved['mean'].copy(), saved['scale'].copy()
    require(all(v.shape == (768,) and np.isfinite(v).all() for v in norm)
            and np.all(norm[1] > 0), 'SOURCE_NORMALIZER_SCHEMA')
    extracted = extract_source_members(archive, destination, verify=True)
    required = ('run/prepared/LEARN_q.npy', 'run/prepared/receipt.json',
                'run/prepared/SHA256SUMS', 'run/thresholds.json',
                'run/endpoints/QUERY_TAIL_27/endpoint.json',
                'run/endpoints/QUERY_TAIL_27/head.npz',
                'run/cache_binding.json',
                'query_code/design_contract.json',
                'run/QUERY_LINEAGE_COMPLETE.json')
    require(all(name in extracted for name in required),
            'SOURCE_ARCHIVE_MEMBER_MISSING:' + repr([x for x in required
                                                     if x not in extracted]))
    prepared = destination / 'run/prepared'
    run_binding = read(destination / 'run/cache_binding.json')
    require(run_binding == binding, 'SOURCE_RUN_CACHE_BINDING')
    pin(destination / 'query_code/design_contract.json',
        QUERY_DESIGN_SHA256)
    code_pins = _manifest(destination / 'query_code',
                          extracted['query_code/SHA256SUMS']['sha256'])
    runtime_code = {}
    for rel in ('repo/ood/query_tail_core_v2.py',
                'repo/ood/continuous_common_v3.py',
                'repo/ood/legacy_qref_data_v1.py',
                'repo/ood/continuous_model_v3.py'):
        pin(ROOT / rel, code_pins[rel])
        runtime_code[rel] = code_pins[rel]
    design = read(destination / 'query_code/design_contract.json')
    complete_path = pin(destination / 'run/QUERY_LINEAGE_COMPLETE.json',
                        QUERY_COMPLETE_SHA256)
    complete = read(complete_path)
    require(complete.get('status') == 'COMPLETE' and
            complete.get('lineage') == 'NEW_RECONSTRUCTION_LINEAGE' and
            complete.get('parent_parity') == 'PARENT_PARITY_UNAVAILABLE',
            'SOURCE_RUN_COMPLETE')
    for stage in ('P', 'T', 'K'):
        stage_path = pin(destination / ('run/LINEAGE_' + stage + '_COMPLETE.json'),
                         complete[stage + '_sha256'])
        require(read(stage_path).get('status') == 'COMPLETE',
                'SOURCE_STAGE_COMPLETE:' + stage)
    p_complete = read(destination / 'run/LINEAGE_P_COMPLETE.json')
    require(p_complete['prepared_seal_sha256'] ==
            extracted['run/prepared/SHA256SUMS']['sha256'],
            'SOURCE_PREPARED_PARENT_SEAL')
    prepared_receipt = read(prepared / 'receipt.json')
    require(prepared_receipt.get('status') == 'COMPLETE' and
            prepared_receipt.get('binding_digest') == digest(binding) and
            p_complete.get('cache_binding_digest') == digest(binding),
            'SOURCE_PREPARED_RECEIPT')
    prepared_pins = _manifest(prepared, extracted['run/prepared/SHA256SUMS']['sha256'])
    require(prepared_pins['LEARN.jsonl.gz'] == input_pins['LEARN.jsonl.gz'],
            'SOURCE_PREPARED_UID_BINDING')
    q_path = pin(prepared / 'LEARN_q.npy', prepared_pins['LEARN_q.npy'])
    q = np.load(q_path, mmap_mode='r', allow_pickle=False)
    require(q.shape == (len(rows), 14) and q.dtype == np.float32,
            'SOURCE_Q_SCHEMA')
    for start in range(0, len(q), 4096):
        block = q[start:start + 4096]
        require(np.isfinite(block).all() and np.all((block >= 0) & (block <= 1)),
                'SOURCE_Q_RANGE')
    spool_pins = _manifest(cache / 'spool',
                           binding['marker']['spool_manifest_sha256'])
    spool = pin(cache / 'spool/snapshots.sqlite',
                spool_pins['snapshots.sqlite'])
    require(sha(spool) == binding['marker']['spool_sha256'],
            'SOURCE_SPOOL_BINDING')
    repo = ROOT / 'repo/ood'
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    import constrained_onboarding_reference_v2 as reference
    ref_q = reference.extract_old_bank_q14(
        spool, refs, binding['marker']['spool_sha256'])
    ref_ix = np.asarray([r['parent_slot'] for r in refs], dtype=np.int64)
    endpoint = destination / 'run/endpoints/QUERY_TAIL_27'
    receipt = read(endpoint / 'endpoint.json')
    endpoint_pins = _manifest(endpoint, extracted[
        'run/endpoints/QUERY_TAIL_27/SHA256SUMS']['sha256'])
    pin(endpoint / 'endpoint.json', endpoint_pins['endpoint.json'])
    require(receipt.get('status') == 'COMPLETE' and
            receipt.get('arm') == 'QUERY_TAIL' and receipt.get('seed') == 27 and
            receipt.get('dimension') == 782 and receipt.get('rows') == COUNTS['FIT'] and
            receipt.get('uid_sha256') == uid_hash(
                (rows[int(i)]['uid'] for i in indices['FIT'])) and
            receipt.get('normalizer_digest') ==
            digest([v.tolist() for v in norm]) and
            receipt.get('design_digest') == digest(design) and
            receipt.get('synthetic_only') is False and
            receipt.get('DEV_used') is False and
            receipt.get('reference_used') is False,
            'SOURCE_HEAD_IDENTITY')
    pin(endpoint / 'head.npz', receipt['head_sha256'])
    require(endpoint_pins['head.npz'] == receipt['head_sha256'],
            'SOURCE_HEAD_SEAL')
    training = read(destination / 'run/LINEAGE_T_COMPLETE.json')
    require(receipt in training.get('endpoints', []),
            'SOURCE_HEAD_T_ENDPOINT_JOIN')
    lineage_path = destination / 'run/endpoint_audits/QUERY_TAIL_27/lineage.json'
    lineage_pins = _manifest(lineage_path.parent, extracted[
        'run/endpoint_audits/QUERY_TAIL_27/SHA256SUMS']['sha256'])
    pin(lineage_path, lineage_pins['lineage.json'])
    lineage = read(lineage_path)
    require(lineage['head_sha256'] == receipt['head_sha256'] and
            lineage['fit_uid_sha256'] == receipt['uid_sha256'] and
            lineage['cache_binding_sha256'] == sha(destination / 'run/cache_binding.json'),
            'SOURCE_ENDPOINT_LINEAGE')
    thresholds = read(destination / 'run/thresholds.json')
    require(thresholds.get('source') == 'ORIGINAL_SOURCE_CAL_NORMAL_ONLY' and
            thresholds.get('comparator') == 'strict >' and
            thresholds.get('budget') == .01 and
            thresholds.get('normal_rows') == 33147,
            'SOURCE_THRESHOLD_CONTRACT')
    cal_normal_uids = [rows[int(i)]['uid'] for i in indices['CAL']
                       if rows[int(i)]['label'] == 0]
    require(thresholds['normal_uid_sha256'] == uid_hash(cal_normal_uids) and
            np.isfinite(thresholds['cuts']['QUERY_TAIL_27']),
            'SOURCE_THRESHOLD_IDENTITY')

    model_cache = []

    def _model():
        require(not validate_only, 'SOURCE_SCORE_DISABLED_VALIDATION_ONLY')
        import torch
        import query_tail_core_v2 as head_core
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        if not model_cache:
            model = head_core.classifier(27, 782)
            with np.load(endpoint / 'head.npz', allow_pickle=False) as saved:
                require(set(saved.files) == set(model.state_dict()),
                        'SOURCE_HEAD_STATE_KEYS')
                model.load_state_dict({name: torch.from_numpy(saved[name].copy())
                                       for name in saved.files})
            model_cache.append(model.eval().requires_grad_(False))
        return model_cache[0]

    def score_main(row_indices):
        import query_tail_core_v2 as head_core
        ix = np.asarray(row_indices, dtype=np.int64)
        require(ix.ndim == 1 and np.all((ix >= 0) & (ix < len(rows))),
                'SOURCE_SCORE_INDICES')
        return head_core.scores(_model(), values, q, ix, norm, 782)

    def score_queries(e3, q14):
        """Replay explicit query arrays; no target source is opened here."""
        import query_tail_core_v2 as head_core
        query_e3 = np.asarray(e3)
        query_q = np.asarray(q14)
        require(query_e3.ndim == 2 and query_e3.shape[1] == 768 and
                query_q.shape == (len(query_e3), 14) and
                query_e3.dtype.kind in 'fiu' and query_q.dtype.kind in 'fiu',
                'QUERY_SCORE_SHAPE')
        return head_core.scores(_model(), query_e3, query_q,
                                np.arange(len(query_e3), dtype=np.int64), norm, 782)

    ref_uids = [r['uid'] for r in refs]
    ordered_uids = [r['uid'] for r in rows]
    result = dict(rows=rows, e3=values[:, :768], q14=q,
                  feature_uids=ordered_uids, q_uids=ordered_uids,
                  fit_indices=indices['FIT'], cal_indices=indices['CAL'],
                  references=dict(rows=refs, e3=ref_values[ref_ix, :768],
                                  q14=ref_q, feature_uids=ref_uids,
                                  q_uids=ref_uids),
                  normalizer=norm, cut=float(thresholds['cuts']['QUERY_TAIL_27']),
                  head=dict(endpoint=str(endpoint), receipt=receipt),
                  score_main=score_main, score_queries=score_queries,
                  binding=dict(cache=str(cache), archive=str(archive),
                               input_manifest_sha256=binding['marker']['original_input_manifest_sha256'],
                               feature_manifest_sha256=binding['marker']['feature_manifest_sha256'],
                               spool_sha256=binding['marker']['spool_sha256'],
                               learn_feature_sha256=feature_pins['LEARN.npy'],
                               q14_sha256=prepared_pins['LEARN_q.npy'],
                               head_sha256=receipt['head_sha256'],
                               thresholds_sha256=sha(destination / 'run/thresholds.json'),
                               cut=float(thresholds['cuts']['QUERY_TAIL_27']),
                               normalizer_sha256=norm_pins['RECENT.npz'],
                               runtime_code_sha256=runtime_code,
                               reference_extractor_sha256=sha(
                                   ROOT / 'repo/ood/constrained_onboarding_reference_v2.py'),
                               extracted=extracted,
                               source_uid_sha256=uid_hash(ordered_uids),
                               reference_uid_sha256=uid_hash(ref_uids)))
    return result


def verify_source_cut(source):
    """Replay only CAL normal rows with the frozen weighted 1% rule."""
    import query_tail_core_v2 as head_core
    import legacy_qref_data_v1 as hierarchy

    rows = source['rows']
    normal_ix = np.asarray([int(i) for i in source['cal_indices']
                            if rows[int(i)]['label'] == 0], dtype=np.int64)
    require(len(normal_ix) == 33147, 'SOURCE_CAL_NORMAL_COUNT')
    normal_rows = [rows[int(i)] for i in normal_ix]
    scores = source['score_main'](normal_ix)
    replayed = head_core.threshold(scores, normal_rows, budget=.01)
    stored = source['cut']
    require(replayed == stored, 'SOURCE_CAL_CUT_NOT_REPRODUCED')
    weights = hierarchy.class_weights(normal_rows)
    strict_fp_mass = float(np.sum(weights[scores > stored], dtype=np.float64))
    require(strict_fp_mass <= .01, 'SOURCE_CAL_BUDGET')
    return dict(status='EXACT_CUT_REPRODUCED', rows=len(normal_ix),
                normal_uid_sha256=uid_hash(r['uid'] for r in normal_rows),
                score_bytes_sha256=hashlib.sha256(scores.tobytes(order='C')).hexdigest(),
                score_dtype=str(scores.dtype), stored_cut=stored,
                replayed_cut=replayed, strict_weighted_fpr=strict_fp_mass,
                budget=.01, comparator='strict >',
                algorithm='continuous_model_v3.threshold + legacy_qref_data_v1.class_weights')
