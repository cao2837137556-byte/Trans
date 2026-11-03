"""Header-only exact shape census; complete causal stream, no numerical features.

Frozen Contexts.append remains authoritative for eligibility/poisoning. Its
RecentState factory is replaced only in this fresh census process by ShapeState,
which retains the timestamp/frame burst information needed for tokenizer shape.
Neither model imports nor numerical snapshot construction occurs here.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINEERING = ROOT/'runs/edge_external_test1_engineering_v1_20261103'
sys.path.insert(0, str(ENGINEERING/'adapter'))
import edge_adapter as edge
from spill_mapping_v1 import SpillMap

NS = 10**9
ROLE_ORDER = ('NORMAL', 'HTTP', 'UDP')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


class ShapeState:
    """Only direction burst/frame/time state, with exact frozen retention."""
    __slots__ = ('owner', 'protocol', 'last_ns', 'last_frame', 'bursts', 'direction_last')

    def __init__(self, owner, namespace, protocol):
        self.owner, self.protocol = owner, protocol
        self.last_ns, self.last_frame = None, 0
        self._reset()

    def _reset(self):
        self.bursts = [deque(maxlen=12), deque(maxlen=12)]
        self.direction_last = [None, None]

    def append(self, row):
        now = edge.frozen.nanos(row['frame.time_epoch'])
        frame = edge.frozen.integer(row['frame.number'])
        require(frame > self.last_frame and (self.last_ns is None or now >= self.last_ns), 'SHAPE_STATE_ORDER')
        if self.last_ns is None or now-self.last_ns > 60*NS:
            self._reset()
        outgoing = row.get('eth.src', '').lower() == self.owner
        incoming = row.get('eth.dst', '').lower() == self.owner
        require(outgoing != incoming, 'SHAPE_OWNER_DIRECTION')
        direction = 0 if outgoing else 1
        if self.direction_last[direction] is None or now-self.direction_last[direction] > 10_000_000:
            self.bursts[direction].append(dict(rows=deque(maxlen=6), last_frame=frame))
        self.bursts[direction][-1]['rows'].append((now, frame))
        self.bursts[direction][-1]['last_frame'] = frame
        self.direction_last[direction] = now
        self.last_ns, self.last_frame = now, frame

    def shape(self):
        require(self.last_ns is not None, 'SHAPE_EMPTY_STATE')
        bursts = sorted([b for group in self.bursts for b in group],
                        key=lambda b: b['last_frame'])[-12:]
        lengths = [sum(self.last_ns-t <= 60*NS for t, _ in b['rows']) for b in bursts]
        lengths = [n for n in lengths if n]
        require(lengths and max(lengths) <= 6 and len(lengths) <= 12, 'SHAPE_BOUNDS')
        return self.protocol, max(lengths)*(12 if self.protocol == 6 else 6)+1, len(lengths)

    def snapshot(self):
        raise RuntimeError('SHAPE_ONLY_STATE_CANNOT_EMIT_NUMERICAL_FEATURES')


def encode_shape(state):
    body = (state.owner, state.protocol, state.last_ns, state.last_frame,
            state.direction_last,
            [[(b['last_frame'], list(b['rows'])) for b in group] for group in state.bursts])
    return pickle.dumps(body, protocol=5)


def decode_shape(blob):
    owner, proto, last_ns, last_frame, last_dir, groups = pickle.loads(blob)
    state = ShapeState(owner, None, proto)
    state.last_ns, state.last_frame, state.direction_last = last_ns, last_frame, last_dir
    state.bursts = [deque((dict(last_frame=frame, rows=deque(rows, maxlen=6))
                          for frame, rows in group), maxlen=12) for group in groups]
    return state


class ShapeSpillMap(SpillMap):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclusively owned scratch state is never reopened/resumed and never
        # counts as a sealed scientific output. Avoid random-page I/O churn;
        # process failure discards this DB and reruns from immutable raw bytes.
        self.db.commit()
        self.db.execute('PRAGMA cache_size=-131072')
        self.db.execute('PRAGMA journal_mode=MEMORY')
        self.db.execute('PRAGMA synchronous=OFF')
        self.sqlite_policy = dict(cache_KiB=131072, journal_mode='memory',
                                  synchronous=0, durability='DISPOSABLE_PROCESS_LOCAL_SCRATCH_ONLY')

    # SHA256 namespace identity is already used by the frozen pipeline. A short
    # fixed key avoids duplicating millions of long spoofed endpoint tuples in
    # both SQLite's objects and its unique-key index.
    @staticmethod
    def _key(key):
        return bytes.fromhex(edge.frozen.digest(key))

    def __iter__(self):
        raise RuntimeError('SHAPE_STORE_NEVER_PRUNES_OR_ITERATES_NAMESPACES')


def read_selected(selection):
    seal_path = selection/'QUERY_SELECTION_SEAL.json'
    seal = edge.read(seal_path)
    require(seal['status'] == 'SEALED_METADATA_ONLY_BASE_QUOTA', 'SELECTION_NOT_SEALED')
    frames = {}
    for role in ROLE_ORDER:
        item = seal['roles'][role]
        path = selection/item['selected_file']
        require(edge.sha(path) == item['selected_sha256'], 'SELECTION_FILE_PIN:'+role)
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            frames[role] = {int(row['frame']) for row in map(json.loads, stream)}
        require(len(frames[role]) == item['selected_rows'], 'SELECTION_COUNT:'+role)
    refs_path = ENGINEERING/'adapter/population_v1/REFERENCE_ROWS.jsonl.gz'
    require(edge.sha(refs_path) == seal['references']['source_sha256'], 'REFERENCE_PIN')
    with gzip.open(refs_path, 'rt', encoding='utf-8') as stream:
        references = {int(row['frame']) for row in map(json.loads, stream)}
    require(len(references) == seal['references']['rows'], 'REFERENCE_COUNT')
    frames['NORMAL'] |= references
    return frames, references, seal


def shape_key(shape):
    return ','.join(map(str, shape))


def add_count(counts, reps, shape, role, frame):
    key = shape_key(shape)
    counts[key] += 1
    candidate = dict(role=role, frame=frame, shape=list(shape))
    if key not in reps:
        reps[key] = candidate


def choose_required(counts, reps):
    require(counts and set(counts) == set(reps), 'SHAPE_REPRESENTATIVE_COVERAGE')
    top = sorted(counts, key=lambda k: (-counts[k], tuple(map(int, k.split(',')))))[:10]
    maximum_width = max(int(k.split(',')[1]) for k in counts)
    maximum_bursts = max(int(k.split(',')[2]) for k in counts)
    widest = min((k for k in counts if int(k.split(',')[1]) == maximum_width),
                 key=lambda k: (-int(k.split(',')[2]), k))
    most_bursts = min((k for k in counts if int(k.split(',')[2]) == maximum_bursts),
                     key=lambda k: (-int(k.split(',')[1]), k))
    keys = list(dict.fromkeys(top+[widest, most_bursts]))
    return dict(top10_shapes=top, maximum_width=maximum_width, maximum_bursts=maximum_bursts,
                widest_shape=widest, most_bursts_shape=most_bursts,
                representatives=[dict(reps[k], count=counts[k]) for k in keys])


def expand_slice(original, counts, reps, output):
    card = edge.read(original)
    require(card['mode'] == 'FIXED_HEADER_ONLY_ENGINEERING_SLICE', 'SLICE_MODE')
    required = choose_required(counts, reps)
    slices = {x['role']: dict(role=x['role'], frames=set(x['frames']),
                              reference_frames=list(x['reference_frames'])) for x in card['slices']}
    additions = []
    for rep in required['representatives']:
        role, frame = rep['role'], rep['frame']
        if frame not in slices[role]['frames']:
            slices[role]['frames'].add(frame)
            additions.append(rep)
        if rep.get('is_reference') and frame not in slices[role]['reference_frames']:
            slices[role]['reference_frames'].append(frame)
    for row in slices.values():
        row['frames'] = sorted(row['frames'])
    require(sum(len(x['frames']) for x in slices.values()) <= 100, 'EXPANDED_SLICE_EXCEEDS_100')
    result = dict(card, slices=[slices[r] for r in ROLE_ORDER],
        parent_slice_path=str(original), parent_slice_sha256=edge.sha(original),
        shape_expansion=dict(source='Complete header-only target shape census before model loading',
                             required=required, additions=additions,
                             no_score_or_label_dependent_shape_selection=True),
        plan_path=str(output/'SHAPE_CENSUS.json'), plan_sha256=edge.sha(output/'SHAPE_CENSUS.json'))
    edge.write(output/'SLICE_CARD.json', result)
    return result


def census(output, selection, wall_seconds=2400, disk_limit_bytes=1024**3):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    selection = Path(selection)
    started = time.monotonic()
    deadline = started+wall_seconds
    selected, reference_frames, seal = read_selected(selection)
    population_path = ENGINEERING/'adapter/population_v1/POPULATION.json'
    population = edge.read(population_path)
    value = edge.card()
    api = edge.prep.old.legacy_runtime()[0]
    original_factory = edge.frozen.RecentState
    edge.frozen.RecentState = ShapeState
    full_counts, target_counts, eligible_query_reps, target_reps = Counter(), Counter(), {}, {}
    roles = {}
    current_ctx = None
    try:
        for role in ROLE_ORDER:
            spec = value['raw_inputs'][role]
            raw = Path(spec['path'])
            require(raw.stat().st_size == spec['bytes'] and edge.sha(raw) == spec['sha256'], 'RAW_PIN:'+role)
            pop = population['roles'][role]
            mask_path = population_path.parent/pop['mask_file']
            require(edge.sha(mask_path) == pop['mask_sha256'], 'MASK_PIN:'+role)
            mask = mask_path.read_bytes()
            counts, role_full, role_target = Counter(), Counter(), Counter()
            uid_full, uid_primary = hashlib.sha256(), hashlib.sha256()
            current = None
            segment_reports = []
            found = set()
            owned_databases = []
            for row in edge.decode_rows(raw, output/(role+'_decoder.stderr.log'), deadline=deadline):
                frame = edge.frozen.integer(row['frame.number'])
                counts['raw_records'] += 1
                segment = edge.segment_for(role, frame, value)
                if current != segment['capture_id']:
                    if current_ctx is not None:
                        segment_reports.append(dict(capture_id=current,
                            namespaces=len(current_ctx.last_seen), poisoned=len(current_ctx.poisoned),
                            store=dict(current_ctx.states.stats)))
                        current_ctx.states.close()
                        # This process created the database exclusively. It is
                        # disposable working state, never a sealed artifact.
                        for db in owned_databases:
                            require(db.parent == output.resolve(), 'WORKING_DB_SCOPE')
                            db.unlink(missing_ok=True)
                        owned_databases.clear()
                    current = segment['capture_id']
                    current_ctx = edge.frozen.Contexts(current, {edge.OWNER}, api,
                        max_states=4_000_000, required_owners={edge.OWNER})
                    current_ctx.frame = segment['first_frame']-1
                    db_path = (output/(current+'.shape.sqlite')).resolve()
                    current_ctx.states = ShapeSpillMap(db_path, 8192, encode=encode_shape, decode=decode_shape)
                    owned_databases.append(db_path)
                owner, namespace, event = current_ctx.append(row)
                truth, reason = mask[2*(frame-1):2*frame]
                observed_truth, _ = edge.label_role(role, row, edge.frozen.nanos(row['frame.time_epoch']), value)
                require(truth == observed_truth, 'TRUTH_MASK_REPLAY:'+role+':'+str(frame))
                if truth:
                    valid = reason == population['mask_schema']['second_byte']['VALID']
                    require(valid == current_ctx.query_allowed, 'ELIGIBILITY_MASK_REPLAY:'+role+':'+str(frame))
                    if valid:
                        uid = edge.frozen.digest([spec['sha256'], frame, edge.OWNER])
                        uid_full.update((uid+'\n').encode())
                        if truth != 1:
                            uid_primary.update((uid+'\n').encode())
                        shape = current_ctx.states[namespace].shape()
                        add_count(full_counts, eligible_query_reps, shape, role, frame)
                        role_full[shape_key(shape)] += 1
                        counts['eligible'] += 1
                        if frame in selected[role]:
                            target_counts[shape_key(shape)] += 1
                            role_target[shape_key(shape)] += 1
                            found.add(frame)
                            counts['selected_targets'] += 1
                            is_ref = role == 'NORMAL' and frame in reference_frames
                            rep = dict(role=role, frame=frame, shape=list(shape), is_reference=is_ref)
                            # Prefer postbank query representatives, but a
                            # reference-only shape may use an actually admitted
                            # official reference as an extra tiny-bank fixture.
                            key = shape_key(shape)
                            if key not in target_reps or (target_reps[key]['is_reference'] and not is_ref):
                                target_reps[key] = rep
                if frame % 32768 == 0:
                    require(time.monotonic() < deadline, 'SHAPE_CENSUS_WALL_LIMIT')
                    db_bytes = sum(p.stat().st_size for p in owned_databases)
                    require(db_bytes <= disk_limit_bytes, 'SHAPE_CENSUS_DISK_LIMIT')
                    edge.write(output/'PROGRESS.json', dict(stage='HEADER_ONLY_EXACT_SHAPE_CENSUS', role=role,
                        frame=frame, records=spec['records'], elapsed_seconds=time.monotonic()-started,
                        database_bytes=db_bytes, numerical_snapshots=0, model_forwards=0))
            require(counts['raw_records'] == spec['records'] and counts['eligible'] == pop['counts']['eligible'],
                    'SHAPE_POPULATION_COUNT:'+role)
            require(uid_full.hexdigest() == pop['full_uid_sha256'] and
                    uid_primary.hexdigest() == pop['primary_uid_sha256'], 'SHAPE_UID_COVERAGE:'+role)
            require(found == selected[role], 'SHAPE_SELECTED_TARGET_COVERAGE:'+role)
            segment_reports.append(dict(capture_id=current, namespaces=len(current_ctx.last_seen),
                poisoned=len(current_ctx.poisoned), store=dict(current_ctx.states.stats)))
            current_ctx.states.close()
            current_ctx = None
            for db in owned_databases:
                require(db.parent == output.resolve(), 'WORKING_DB_SCOPE')
                db.unlink(missing_ok=True)
            require(edge.sha(raw) == spec['sha256'], 'RAW_UNCHANGED:'+role)
            roles[role] = dict(counts=dict(counts), full_shape_counts=dict(role_full),
                              target_shape_counts=dict(role_target), segments=segment_reports,
                              full_uid_sha256=uid_full.hexdigest(), primary_uid_sha256=uid_primary.hexdigest())
        # Every shape comes from a real selected query or admitted reference.
        # Reference-only shapes keep their reference role; no prebank query or
        # new official bank position is invented to make a fixture pass.
        missing = sorted(set(target_counts)-set(target_reps))
        require(not missing, 'TARGET_SHAPE_ONLY_PREBANK_REFERENCE:'+','.join(missing))
        result = dict(schema='EDGE_EXACT_HEADER_ONLY_SHAPE_CENSUS_V1', status='COMPLETE_NO_MODEL',
            roles=roles, full_shape_counts=dict(full_counts), target_shape_counts=dict(target_counts),
            full_requirements=choose_required(full_counts, eligible_query_reps),
            target_requirements=choose_required(target_counts, target_reps),
            selection_seal_sha256=edge.sha(selection/'QUERY_SELECTION_SEAL.json'),
            population_sha256=edge.sha(population_path),
            shape_semantics='(IP protocol, max retained rows in a burst * header_token_count + CLS1, retained burst count)',
            shape_state_source_sha256=edge.sha(Path(__file__)),
            frozen_state_source_sha256=edge.sha(ROOT/'repo/ood/continuous_input_v3.py'),
            scratch_sqlite_policy=dict(cache_KiB=131072, journal_mode='memory', synchronous=0,
                                       never_reused_after_process_exit=True),
            numerical_snapshots=0, model_forwards=0, external_quality_evaluations=0,
            ttl_state_pruning=False, full_unfiltered_context=True,
            elapsed_seconds=time.monotonic()-started)
        edge.write(output/'SHAPE_CENSUS.json', result)
        expanded = expand_slice(ENGINEERING/'preflight/SLICE_CARD.json', target_counts, target_reps, output)
        edge.write(output/'SUMMARY.json', dict(status='SHAPE_CENSUS_AND_SLICE_COMPLETE_NO_MODEL',
            census_sha256=edge.sha(output/'SHAPE_CENSUS.json'), slice_sha256=edge.sha(output/'SLICE_CARD.json'),
            slice_rows=sum(len(x['frames']) for x in expanded['slices']),
            numerical_snapshots=0, model_forwards=0, external_quality_evaluations=0))
        return result
    except BaseException as exc:
        edge.write(output/'FAILURE.json', dict(status='FAILED_NOT_PASSED', error_type=type(exc).__name__,
            message=str(exc), elapsed_seconds=time.monotonic()-started, model_forwards=0))
        raise
    finally:
        edge.frozen.RecentState = original_factory
        if current_ctx is not None:
            current_ctx.states.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection-directory', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--wall-seconds', type=int, default=2400)
    parser.add_argument('--disk-limit-bytes', type=int, default=1024**3)
    args = parser.parse_args()
    result = census(args.output, args.selection_directory, args.wall_seconds, args.disk_limit_bytes)
    print(json.dumps(dict(status=result['status'], elapsed_seconds=result['elapsed_seconds'])))
