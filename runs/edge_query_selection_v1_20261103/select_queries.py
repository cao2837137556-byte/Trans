"""Seal header-only query selection against an existing complete eligibility mask.

No encoder, numerical snapshots, heads, distance or external quality metrics.
All original packets are decoded; the previously sealed mask determines legal
endpoints. Future feature replay must still append the complete original prefix.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import heapq
import io
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINEERING = ROOT / 'runs/edge_external_test1_engineering_v1_20261103'
sys.path.insert(0, str(ENGINEERING / 'adapter'))
import edge_adapter as edge
from selection_core import (NORMAL_SALT, ATTACK_SALT, HTTP_STRATA, normal_plan,
                            attack_plan, normal_weights, attack_weights, hash_rank,
                            http_stratum)

FIELDS = ('uid', 'frame', 'timestamp_ns', 'protocol', 'capture_id', 'component_id',
          'tcp_flags', 'stratum', 'direction')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return edge.sha(path)


def read(path):
    return edge.read(path)


def write(path, value):
    edge.write(path, value)


def sidecar(path):
    path = Path(path)
    path.with_name(path.name + '.sha256').write_text(sha(path)+'  '+path.name+'\n', encoding='utf-8')


@contextmanager
def gzip_text(path):
    """Stable compressed bytes; path names and wall clocks cannot enter output."""
    with Path(path).open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=1) as zipped:
            with io.TextIOWrapper(zipped, encoding='utf-8', newline='\n') as text:
                yield text


def keep_smallest(heap, row, count, salt):
    if count == 0:
        return
    rank = int(hash_rank(salt, row['uid']), 16)
    uid = int(row['uid'], 16)
    # Smaller hashes win; the current worst retained endpoint is the heap root.
    item = (-rank, -uid, row)
    if len(heap) < count:
        heapq.heappush(heap, item)
    elif (rank, uid) < (-heap[0][0], -heap[0][1]):
        heapq.heapreplace(heap, item)


def spool_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            for name in ('frame', 'timestamp_ns', 'protocol', 'tcp_flags'):
                row[name] = int(row[name])
            yield row


def enumerate_metadata(out, *, tshark, seconds=2400):
    started = time.monotonic()
    deadline = started + seconds
    value = edge.card()
    population_path = ENGINEERING / 'adapter/population_v1/POPULATION.json'
    population = read(population_path)
    require(sha(edge.CARD) == population['card_sha256'], 'POPULATION_CARD_PIN')
    api = edge.prep.old.legacy_runtime()[0]
    reports = {}
    normal_components = Counter()
    pins = {str(population_path.relative_to(ROOT)): sha(population_path),
            str(edge.CARD.relative_to(ROOT)): sha(edge.CARD)}
    for role in ('NORMAL', 'HTTP', 'UDP'):
        spec = value['raw_inputs'][role]
        raw = Path(spec['path'])
        initial = (raw.stat().st_size, raw.stat().st_mtime_ns)
        require(initial[0] == spec['bytes'] and sha(raw) == spec['sha256'], 'RAW_PIN:' + role)
        pop = population['roles'][role]
        mask_path = population_path.parent / pop['mask_file']
        require(sha(mask_path) == pop['mask_sha256'], 'MASK_PIN:' + role)
        mask = mask_path.read_bytes()
        require(len(mask) == 2 * spec['records'], 'MASK_LENGTH:' + role)
        pins[str(mask_path.relative_to(ROOT))] = pop['mask_sha256']
        counts = Counter()
        strata = Counter()
        uid_all, uid_primary = hashlib.sha256(), hashlib.sha256()
        spool = out / (role + '_metadata.tsv.gz')
        role_started = time.monotonic()
        with gzip_text(spool) as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter='\t', lineterminator='\n')
            writer.writeheader()
            for packet in edge.decode_rows(raw, out/(role+'_decoder.stderr.log'), tshark=tshark,
                                           deadline=deadline):
                frame = int(packet['frame.number'])
                counts['decoded_records'] += 1
                require(frame == counts['decoded_records'], 'NONCONTIGUOUS_PHYSICAL_FRAME')
                truth, reason = mask[2*(frame-1):2*frame]
                if truth and reason == population['mask_schema']['second_byte']['VALID']:
                    uid = edge.frozen.digest([spec['sha256'], frame, edge.OWNER])
                    uid_all.update((uid+'\n').encode())
                    counts['full_eligible'] += 1
                    if truth != 1:
                        uid_primary.update((uid+'\n').encode())
                        event = api.event_from_tshark(packet)
                        key = edge.prep.old.old_key(event)
                        require(key is not None, 'SEALED_ELIGIBLE_KEY_MISSING')
                        component = edge.frozen.digest([edge.OWNER, key])
                        segment = edge.segment_for(role, frame, value)
                        flags = edge.frozen.integer(packet['tcp.flags']) if event.ip_proto == 6 else 0
                        stratum = 'NORMAL' if role == 'NORMAL' else http_stratum(flags) if role == 'HTTP' else 'UDP'
                        row = dict(uid=uid, frame=frame,
                            timestamp_ns=edge.frozen.nanos(packet['frame.time_epoch']),
                            protocol=event.ip_proto, capture_id=segment['capture_id'],
                            component_id=component, tcp_flags=flags, stratum=stratum,
                            direction='OUT' if packet.get('eth.src','').lower() == edge.OWNER else 'IN')
                        writer.writerow(row)
                        counts['query_candidates'] += 1
                        strata[stratum] += 1
                        if role == 'NORMAL':
                            normal_components[component] += 1
                if frame % 65536 == 0:
                    write(out/'PROGRESS.json', dict(stage='METADATA_ONLY_SCAN', role=role,
                        physical_frame=frame, total_frames=spec['records'],
                        elapsed_seconds=time.monotonic()-started, model_forwards=0,
                        numerical_snapshots=0, external_quality_evaluations=0))
        require(counts['decoded_records'] == spec['records'], 'RAW_RECORD_COUNT:' + role)
        require(uid_all.hexdigest() == pop['full_uid_sha256'], 'FULL_UID_REPLAY:' + role)
        require(uid_primary.hexdigest() == pop['primary_uid_sha256'], 'PRIMARY_UID_REPLAY:' + role)
        require(initial == (raw.stat().st_size, raw.stat().st_mtime_ns) and sha(raw) == spec['sha256'],
                'RAW_UNCHANGED:' + role)
        sidecar(spool)
        reports[role] = dict(counts=dict(counts), strata=dict(strata),
            raw_sha256=spec['sha256'], raw_bytes=spec['bytes'], raw_unchanged=True,
            mask_sha256=pop['mask_sha256'], full_uid_sha256=uid_all.hexdigest(),
            primary_uid_sha256=uid_primary.hexdigest(), metadata_file=spool.name,
            metadata_sha256=sha(spool), seconds=time.monotonic()-role_started)
    write(out/'NORMAL_COMPONENT_COUNTS.json', dict(sorted(normal_components.items())))
    result = dict(schema='EDGE_METADATA_QUERY_CENSUS_V1', status='METADATA_ONLY_CENSUS_PASS',
        roles=reports, normal_component_count=len(normal_components), input_pins=pins,
        elapsed_seconds=time.monotonic()-started, model_forwards=0, numerical_snapshots=0,
        external_quality_evaluations=0, decode_order='ALL_ORIGINAL_PHYSICAL_ROWS',
        eligibility='Use immutable original complete eligibility mask; verify both ordered UID digests against it')
    write(out/'METADATA_CENSUS.json', result)
    return result


def select(out, census, budget=20000):
    counts = read(out/'NORMAL_COMPONENT_COUNTS.json')
    normal = normal_plan(counts, budget)
    plans = dict(NORMAL=normal,
        HTTP=attack_plan(census['roles']['HTTP']['strata'], budget),
        UDP=attack_plan(census['roles']['UDP']['strata'], budget, order=('UDP',)))
    reports = {}
    selection_files = []
    for role in ('NORMAL', 'HTTP', 'UDP'):
        plan = plans[role]
        heaps = defaultdict(list)
        salt = NORMAL_SALT if role == 'NORMAL' else ATTACK_SALT
        for row in spool_rows(out/census['roles'][role]['metadata_file']):
            group = row['component_id'] if role == 'NORMAL' else row['stratum']
            n = plan['quotas'].get(group, 0)
            if n:
                keep_smallest(heaps[group], row, n, salt)
        selected = []
        for group, quota in plan['quotas'].items():
            require(len(heaps[group]) == quota, 'SELECTED_GROUP_COUNT:' + role + ':' + group)
            for _, _, row in heaps[group]:
                population = counts[group] if role == 'NORMAL' else census['roles'][role]['strata'][group]
                weights = (normal_weights(population, quota, normal['component_count'],
                    normal['selected_component_count'], normal['branch']) if role == 'NORMAL'
                    else attack_weights(population, quota))
                selected.append(dict(row, source_role=role, use='QUERY', owner=edge.OWNER,
                    source_sha256=census['roles'][role]['raw_sha256'],
                    group_population=population, group_selected=quota,
                    weights=weights, selection_rank=hash_rank(salt, row['uid'])))
        selected.sort(key=lambda row: row['uid'])
        require(len(selected) == plan['effective_budget'] and
                len({r['uid'] for r in selected}) == len(selected), 'QUERY_UID_UNIQUENESS:' + role)
        query_file = out/(role+'_SELECTED_QUERIES.jsonl.gz')
        with gzip_text(query_file) as stream:
            for row in selected:
                stream.write(json.dumps(row, sort_keys=True, separators=(',',':'))+'\n')
        sidecar(query_file)
        uid_file = out/(role+'_SELECTED_UIDS.txt')
        uid_file.write_text(''.join(row['uid']+'\n' for row in selected), encoding='utf-8', newline='\n')
        sidecar(uid_file)
        frame_file = out/(role+'_SELECTED_FRAMES.json')
        write(frame_file, dict(role=role, original_physical_frames=sorted(r['frame'] for r in selected),
            selected_rows=len(selected), ordering='Frames for decode scheduling only; final identity ordered by UID'))
        summary = dict(selected_rows=len(selected), population_count=plan['population_count'],
            strata=dict(Counter(r['stratum'] for r in selected)),
            protocols=dict(Counter(str(r['protocol']) for r in selected)),
            selected_file=query_file.name, selected_sha256=sha(query_file),
            uid_file=uid_file.name, ordered_uid_sha256=sha(uid_file),
            frame_file=frame_file.name, frame_sha256=sha(frame_file),
            sample_exact_rate=True, full_packet_exact_rate=False)
        if role == 'NORMAL':
            summary.update(branch=normal['branch'], population_components=normal['component_count'],
                selected_components=normal['selected_component_count'],
                component_equal_metric='Estimated over sampled components' if normal['branch']=='HASH_COMPONENT_FALLBACK'
                    else 'All eligible components represented')
        reports[role] = summary
        selection_files.extend([query_file, uid_file, frame_file])
    refs = ENGINEERING/'adapter/population_v1/REFERENCE_ROWS.jsonl.gz'
    refs_before = sha(refs)
    references = []
    with gzip.open(refs, 'rt', encoding='utf-8') as stream:
        references = [json.loads(line) for line in stream]
    require(len(references) == 4124 and len({r['uid'] for r in references}) == 4124, 'REFERENCE_COUNT')
    reference_uid_file = out/'REFERENCE_UIDS.txt'
    reference_uid_file.write_text(''.join(sorted(r['uid']+'\n' for r in references)), encoding='utf-8', newline='\n')
    sidecar(reference_uid_file)
    selected_uids = set()
    for role in reports:
        selected_uids.update((out/reports[role]['uid_file']).read_text(encoding='utf-8').splitlines())
    require(not selected_uids & {r['uid'] for r in references}, 'POSTBANK_QUERY_REFERENCE_OVERLAP')
    plans['reference'] = dict(rows=4124, source_path=refs.relative_to(ROOT).as_posix(),
        source_sha256=refs_before, ordered_uid_file=reference_uid_file.name,
        ordered_uid_sha256=sha(reference_uid_file), reference_rule_changed=False)
    write(out/'SELECTION_PLANS.json', plans)
    outputs = {p.name:dict(bytes=p.stat().st_size,sha256=sha(p))
        for p in selection_files+[reference_uid_file,out/'SELECTION_PLANS.json',out/'METADATA_CENSUS.json',
                                 out/'NORMAL_COMPONENT_COUNTS.json']}
    result = dict(schema='EDGE_QUERY_SELECTION_SEAL_V1', status='SEALED_METADATA_ONLY_BASE_QUOTA',
        scientific_execution_ready=False, base_role_budget=budget, current_uniform_factor=1,
        formal_final_quota_pending_linux_throughput=True, roles=reports, references=plans['reference'],
        selected_query_rows=sum(r['selected_rows'] for r in reports.values()),
        total_logical_encoding_rows=sum(r['selected_rows'] for r in reports.values())+len(references),
        output_pins=outputs,
        selection_code_pins={p.name:sha(p) for p in (HERE/'selection_core.py',Path(__file__))},
        source_contract=dict(path='runs/mainline_docs/collab/20261103_edge_query_selection_convergence_claude.md',
            sha256=sha(ROOT/'runs/mainline_docs/collab/20261103_edge_query_selection_convergence_claude.md')),
        immutable_asset_freeze_sha256=sha(ROOT/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json'),
        full_view_normal_metric='NOT_EVALUABLE_FROM_THIS_POSTWINDOW_SAMPLE',
        population_estimate='Known full N denominator; inverse row inclusion probabilities, including component selection',
        precision_guarantee=False, causal_context='ALL_ORIGINAL_ROWS_REPLAYED_BEFORE_SELECTED_SNAPSHOTS',
        unselected_rows='NOT_SAMPLED, never interpreted as correct negatives',
        input_tensor_dedup=False, model_forwards=0, numerical_snapshots=0,
        external_quality_evaluations=0, cloud_jobs_submitted=0)
    write(out/'QUERY_SELECTION_SEAL.json',result)
    write(out/'PROGRESS.json',dict(stage='SEALED_METADATA_ONLY_BASE_QUOTA',selected_rows=result['selected_query_rows'],
        logical_encoding_rows=result['total_logical_encoding_rows'],model_forwards=0))
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--tshark',default=str(edge.TSHARK))
    parser.add_argument('--wall-seconds',type=int,default=2400)
    args=parser.parse_args()
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=False)
    census=enumerate_metadata(out,tshark=Path(args.tshark),seconds=args.wall_seconds)
    result=select(out,census)
    print(json.dumps({k:result[k] for k in ('status','selected_query_rows','total_logical_encoding_rows')},indent=2))


if __name__=='__main__':
    main()
