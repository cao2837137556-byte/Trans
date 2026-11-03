"""Edge-IIoTset isolated causal adapter, with no model/score imports.

The full population pass calls the frozen Contexts eligibility implementation
with a deliberately non-numerical state sink. Selected snapshot replay calls
the complete unchanged numerical implementation. Original physical frames,
integer clocks and raw SHA identities are never rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'repo/ood'))
import continuous_input_v3 as frozen
from continuous_input_engineering_v1 import Contexts as NumericalContexts
import legacy_reference_sample_prepare_v1 as prep
from legacy_unsw_archival_runtime_v1 import fields as decoder_fields

CARD = ROOT / 'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json'
TARGET_IP = '192.168.0.128'
OWNER = 'dc:a6:32:fb:69:b5'
DEVICE = 'Edge-IIoTset Raspberry Pi edge server'
PARTITION = 'EXTERNAL_ARCHIVAL_EVALUATION'
TSHARK = Path('C:/Program Files/Wireshark/tshark.exe')
VERSION = 'EDGE_CAUSAL_RAW_ADAPTER_V1_20261103'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, body):
    path = Path(path)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    path.with_name(path.name+'.sha256').write_text(sha(path)+'  '+path.name+'\n', encoding='utf-8')


def card():
    value = read(CARD)
    frozen.require(value['method']['p'] == 3 and value['reference']['observation_seconds'] == 7200,
                   'FROZEN_EXTERNAL_CARD_CONTRACT')
    return value


def segments(role, value=None):
    value = card() if value is None else value
    if role == 'NORMAL':
        return [dict(x, capture_id='EDGE_NORMAL_SEGMENT_%d' % i) for i, x in enumerate(value['capture_boundaries']['normal_segments'], 1)]
    raw = value['raw_inputs'][role]
    return [dict(first_frame=1, last_frame=raw['records'], capture_id='EDGE_'+role)]


def segment_for(role, frame, value=None):
    for item in segments(role, value):
        if item['first_frame'] <= frame <= item['last_frame']:
            return item
    raise ValueError('FRAME_OUTSIDE_PINNED_SEGMENTS')


class _NoNumericalState:
    """Population eligibility sink. It can never be used to emit a feature."""
    def append(self, row):
        pass

    def snapshot(self):
        raise RuntimeError('ELIGIBILITY_PASS_CANNOT_EMIT_NUMERICAL_SNAPSHOTS')


class EligibilityOnlyStore:
    """All numeric-state operations are ineligible for population-only use.

    Contexts' owner, last_seen, poisoned and tainted ledgers stay authoritative.
    Their update/eligibility logic is executed by the original append method.
    Numeric RECENT values do not participate in any eligibility branch.
    """
    state = _NoNumericalState()

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return self.state

    def pop(self, key, default=None):
        return default


def eligibility_context(capture, api, first_frame=1, max_states=4_000_000):
    ctx = frozen.Contexts(capture, {OWNER}, api, max_states=max_states, required_owners={OWNER})
    ctx.states = EligibilityOnlyStore()
    # The raw source is not rewritten. This counter is a stream-continuity
    # guard; numerical state and all namespace ledgers start empty.
    ctx.frame = first_frame-1
    return ctx


def numerical_context(capture, api, working, first_frame=1, max_states=4_000_000):
    ctx = NumericalContexts(capture, {OWNER}, api, max_states=max_states,
                            required_owners={OWNER}, storage_path=Path(working), resident_contexts=256)
    ctx.frame = first_frame-1
    return ctx


def decode_rows(path, log, *, tshark=TSHARK, stop_after=None, deadline=None):
    """Unfiltered raw prefix/all rows, same field/occurrence decoder contract."""
    runtime = prep.old.legacy_runtime()
    names = decoder_fields(runtime)
    command = [str(tshark), '-n', '-r', str(path), '-T', 'fields', '-E', 'header=y',
               '-E', 'separator=/t', '-E', 'quote=d', '-E', 'occurrence=f']
    if stop_after is not None:
        command += ['-c', str(stop_after)]
    for field in names:
        command += ['-e', field]
    log = Path(log)
    with log.open('x', encoding='utf-8') as err:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err,
                                   text=True, encoding='utf-8', errors='strict')
        try:
            rows = csv.DictReader(process.stdout, delimiter='\t', quotechar='"')
            frozen.require(rows.fieldnames == names, 'DECODER_FIELD_ORDER')
            for row in rows:
                frozen.require(None not in row and None not in row.values(), 'DECODER_FIELD_COLUMNS')
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError('ENGINEERING_POPULATION_WALL_LIMIT')
                yield row
            frozen.require(process.wait(timeout=30) == 0, 'DECODER_FAILED')
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
            process.stdout.close()
    frozen.require(log.stat().st_size == 0, 'DECODER_STDERR_NOT_EMPTY')


def label_role(role, row, now_ns, value=None):
    """Researcher-reconstructed pinned direction, independent of scores."""
    value = card() if value is None else value
    proto = int(row['ip.proto']) if row.get('ip.proto') else None
    if role == 'NORMAL':
        if proto in (6, 17) and TARGET_IP in (row.get('ip.src'), row.get('ip.dst')):
            return (1 if now_ns <= value['reference']['cutoff_ns'] else 2), 0
    elif role == 'HTTP':
        lo, hi = value['labels']['HTTP']['captured_interval_ns']
        if (row.get('ip.src') == '192.168.0.170' and row.get('ip.dst') == TARGET_IP
                and row.get('eth.dst', '').lower() == OWNER and proto == 6
                and row.get('tcp.dstport') == '80' and lo <= now_ns <= hi):
            return 3, 1
    elif role == 'UDP':
        lo, hi = value['labels']['UDP']['captured_interval_ns']
        if (row.get('ip.dst') == TARGET_IP and row.get('eth.dst', '').lower() == OWNER
                and proto == 17 and row.get('udp.dstport') == '0' and lo <= now_ns <= hi):
            return 4, 1
    return 0, None


def metadata(role, packet, ctx, namespace, event, label, value=None):
    value = card() if value is None else value
    frame = frozen.integer(packet['frame.number'])
    now = frozen.nanos(packet['frame.time_epoch'])
    spec = value['raw_inputs'][role]
    segment = segment_for(role, frame, value)
    key = namespace[-1]
    return dict(uid=frozen.digest([spec['sha256'], frame, OWNER]), frame=frame,
        original_frame=frame, logical_frame=frame-segment['first_frame']+1,
        timestamp=float(Decimal(now)/Decimal(frozen.NS)), timestamp_ns=now,
        owner=OWNER, device=DEVICE, partition=PARTITION, protocol=event.ip_proto,
        capture_id=ctx.capture, source_sha256=spec['sha256'], origin_raw_sha256=spec['sha256'],
        origin_packet_ordinal=frame, session_id=frozen.digest(namespace),
        component_id=frozen.digest([OWNER, key]), canonical_key=key,
        use='QUERY', label=label, activity='UNKNOWN', activity_verified=False,
        source_role=role, scenario=role,
        label_basis='OFFICIAL_NORMAL_FILE' if role == 'NORMAL' else 'RECONSTRUCTED_ATTACK_ASSOCIATED_DIRECT_DIRECTION')


def reference_row(row, value=None):
    value = card() if value is None else value
    frozen.require(row['source_role'] == 'NORMAL' and row['label'] == 0 and
                   row['timestamp_ns'] <= value['reference']['cutoff_ns'] and
                   row['frame'] <= value['reference']['original_prefix_frames'][1], 'REFERENCE_SCOPE')
    return dict(row, use='REFERENCE',
        reference_end=float(Decimal(value['reference']['cutoff_ns'])/Decimal(frozen.NS)),
        bank_end_frame=value['reference']['original_prefix_frames'][1],
        normality_evidence='Author normal Temperature_and_Humidity file; pinned earliest unfiltered 7200s')


def prebank_query_for_reference(entry):
    """Reuse an original commissioning feature in the FULL query population.

    This never changes its physical identity or creates a second logical E3
    observation. Its full-view score is exactly RAW: the bank is not yet
    available. The paired reference is kept for later causal query use.
    """
    from causal_reference_overlap_v1 import require_prebank_history
    from constrained_onboarding_reference_v2 import query_descriptor
    row=dict(entry['row'],use='QUERY')
    require_prebank_history(row,entry['row'])
    q14,info=query_descriptor(entry['body'],row)
    return dict(uid=row['uid'],row=row,body=entry['body'],q14=q14.tolist(),info=info,
                required_support=0.0,required_behavior='EXACT_RAW_PREBANK_FALLBACK',
                feature_reuse='SAME_PHYSICAL_OBSERVATION_NO_REENCODING')


def selected_snapshots(role, frames, working_directory, *, tshark=TSHARK,
                       reference_frames=(), value=None, deadline=None):
    """Replay every original row to selected endpoints using full frozen core.

    No file/time sorting, direction filtering, or bank-role context reset.
    The caller chooses frames before model execution. Outside-label frames are
    never promoted into a normal/attack query or a reference.
    """
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
    value = card() if value is None else value
    wanted, refs = set(map(int, frames)), set(map(int, reference_frames))
    frozen.require(wanted and refs <= wanted, 'SELECTED_FRAME_SET')
    raw=Path(value['raw_inputs'][role]['path']);raw_spec=value['raw_inputs'][role]
    raw_before=(raw.stat().st_size,raw.stat().st_mtime_ns)
    frozen.require(raw_before[0]==raw_spec['bytes'] and sha(raw)==raw_spec['sha256'], 'RAW_SNAPSHOT_REPLAY_INPUT_PIN')
    work = Path(working_directory)
    work.mkdir(parents=True, exist_ok=False)
    api = prep.old.legacy_runtime()[0]
    ctx = None; found = set(); current_segment = None
    try:
        for packet in decode_rows(value['raw_inputs'][role]['path'], work/'decoder.stderr.log',
                                  tshark=tshark, stop_after=max(wanted), deadline=deadline):
            frame = frozen.integer(packet['frame.number'])
            segment = segment_for(role, frame, value)
            if current_segment != segment['capture_id']:
                if ctx is not None:
                    ctx.close()
                ctx = numerical_context(segment['capture_id'], api, work/(segment['capture_id']+'.sqlite'),
                                        segment['first_frame'], value['raw_inputs'][role]['records']+1)
                current_segment = segment['capture_id']
            owner, namespace, event = ctx.append(packet)
            if frame not in wanted:
                continue
            frozen.require(ctx.query_allowed and namespace is not None and owner == OWNER,
                           'REQUESTED_FRAME_INVALID:'+str(frame)+':'+ctx.query_reason)
            truth, label = label_role(role, packet, frozen.nanos(packet['frame.time_epoch']), value)
            frozen.require(truth != 0, 'REQUESTED_FRAME_OUTSIDE_TRUTH_SCOPE')
            row = metadata(role, packet, ctx, namespace, event, label, value)
            if frame in refs:
                row = reference_row(row, value)
            flow, state, provenance = ctx.states[namespace].snapshot()
            body = dict(flow=flow, state=state, provenance=provenance, source_sha256=row['source_sha256'])
            descriptor = reference_descriptor if row['use'] == 'REFERENCE' else query_descriptor
            q14, info = descriptor(body, row)
            found.add(frame)
            yield dict(uid=row['uid'], row=row, body=body, q14=q14.tolist(), info=info)
        frozen.require(found == wanted, 'REQUESTED_FRAME_COVERAGE')
    finally:
        if ctx is not None:
            ctx.close()
        frozen.require(raw_before==(raw.stat().st_size,raw.stat().st_mtime_ns) and
                       sha(raw)==raw_spec['sha256'],'RAW_SNAPSHOT_REPLAY_INPUT_UNCHANGED')


def population(output, *, roles=('NORMAL', 'HTTP', 'UDP'), tshark=TSHARK, wall_seconds=2400):
    """Seal raw-frame eligibility, UID digests, and prospective anchor planning.

    Frame mask is two bytes per record: truth stratum then reason-code. No
    token/snapshot/score population is retained. Full metadata is reproducible
    from the pinned raw sources, code, segment map, and this mask.
    """
    from constrained_onboarding_reference_v2 import plan_banks, VERSION as REFERENCE_VERSION
    from onboarding_dense_reference_v1 import plan_dense_positions
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic(); deadline = started+wall_seconds
    value = card(); api = prep.old.legacy_runtime()[0]
    decoder_version = subprocess.run([str(tshark), '--version'], capture_output=True, text=True, check=True, timeout=30).stdout
    identity = dict(executable=str(tshark), sha256=sha(tshark), version=decoder_version,
                    fields=decoder_fields(prep.old.legacy_runtime()), unfiltered=True, occurrence='f')
    write(output/'DECODER_IDENTITY.json', identity)
    reasons = {'OUTSIDE_TRUTH': 0, 'VALID': 1}
    report = {}; candidates = []; component_last = {}; preflight = {'NORMAL': [], 'HTTP': [], 'UDP': []}
    normal_components = {}; all_inputs = {}; all_seen=0
    for role in roles:
        spec = value['raw_inputs'][role]; path = Path(spec['path'])
        before = (path.stat().st_size, path.stat().st_mtime_ns)
        frozen.require(before[0] == spec['bytes'] and sha(path) == spec['sha256'], 'RAW_INPUT_PIN')
        counts=Counter(); populations=Counter(); segment_reports=[]; current=None; ctx=None
        uid_full=hashlib.sha256(); uid_primary=hashlib.sha256()
        mask = output/(role+'_FRAME_POPULATION.u8x2.bin')
        role_start=time.monotonic()
        with mask.open('xb') as stream:
            for packet in decode_rows(path, output/(role+'_decoder.stderr.log'), tshark=tshark, deadline=deadline):
                frame = frozen.integer(packet['frame.number']); now=frozen.nanos(packet['frame.time_epoch'])
                segment = segment_for(role, frame, value)
                if current != segment['capture_id']:
                    if ctx is not None:
                        segment_reports.append(dict(capture_id=current, events=dict(ctx.reasons),
                            namespaces=len(ctx.last_seen), poisoned=len(ctx.poisoned), tainted=len(ctx.tainted)))
                    ctx=eligibility_context(segment['capture_id'], api, segment['first_frame'], spec['records']+1)
                    current=segment['capture_id']
                owner, namespace, event=ctx.append(packet)
                truth,label=label_role(role, packet, now, value)
                counts['raw_records']+=1; populations[str(truth)]+=1
                valid=ctx.query_allowed and namespace is not None and owner == OWNER
                reason='OUTSIDE_TRUTH' if truth == 0 else 'VALID' if valid else ctx.query_reason
                if reason not in reasons:
                    frozen.require(len(reasons)<256, 'REASON_BYTE_CODE_LIMIT')
                    reasons[reason]=len(reasons)
                stream.write(bytes((truth,reasons[reason])))
                if truth:
                    counts['truth_candidates']+=1
                    counts['eligible' if valid else 'unscored']+=1
                    counts[('eligible|' if valid else 'unscored|')+str(truth)+'|'+reason]+=1
                if truth and valid:
                    row=metadata(role,packet,ctx,namespace,event,label,value)
                    uid_full.update((row['uid']+'\n').encode())
                    if truth != 1:
                        uid_primary.update((row['uid']+'\n').encode())
                    if role == 'NORMAL' and truth == 1:
                        rr=reference_row(row,value); candidates.append(rr)
                        old=component_last.get(rr['component_id'])
                        if old is None or (rr['timestamp'],rr['capture_id'],rr['frame'],rr['uid']) > (old['timestamp'],old['capture_id'],old['frame'],old['uid']):
                            component_last[rr['component_id']]=rr
                        bucket=normal_components.setdefault(rr['component_id'],[])
                        if len(bucket)<2:
                            bucket.append(frame)
                    if role == 'NORMAL' and truth == 2 and len(preflight[role])<16:
                        preflight[role].append(frame)
                    elif role != 'NORMAL' and len(preflight[role])<16:
                        preflight[role].append(frame)
                if frame % 32768 == 0:
                    all_seen += 32768
                    if shutil.disk_usage(output).free < 2*1024**3:
                        raise OSError('ENGINEERING_MINIMUM_2GIB_FREE')
                    write(output/'PROGRESS.json',dict(stage='ELIGIBILITY_NO_NUMERIC_STATE',role=role,
                        completed=frame,total=spec['records'],elapsed_seconds=time.monotonic()-started,
                        model_rows=0,distance_pairs=0,full_evaluation=False))
            frozen.require(counts['raw_records']==spec['records'], 'RAW_RECORD_COUNT_MISMATCH')
        segment_reports.append(dict(capture_id=current, events=dict(ctx.reasons),
            namespaces=len(ctx.last_seen), poisoned=len(ctx.poisoned), tainted=len(ctx.tainted)))
        frozen.require(before == (path.stat().st_size,path.stat().st_mtime_ns) and sha(path)==spec['sha256'], 'RAW_INPUT_UNCHANGED')
        report[role]=dict(counts=dict(counts),truth_strata=dict(populations),segments=segment_reports,
            full_uid_sha256=uid_full.hexdigest(),primary_uid_sha256=uid_primary.hexdigest(),
            mask_file=mask.name,mask_sha256=sha(mask),mask_bytes=mask.stat().st_size,
            elapsed_seconds=time.monotonic()-role_start,features_generated=0)
        all_inputs[role]=dict(path=str(path),sha256=spec['sha256'],bytes=before[0],unchanged=True)
        del ctx
    if 'NORMAL' in roles:
        ordered=sorted(component_last.values(),key=lambda r:(r['device'],r['protocol'],r['component_id']))
        t0=float(Decimal(value['reference']['t0_ns'])/Decimal(frozen.NS))
        census=dict(generator_version=REFERENCE_VERSION,status='COMPLETE',enumeration='ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT',
            window_closed=True,duration_seconds=7200,t0=t0,cutoff=t0+7200,candidate_rows=len(ordered),
            candidates_sha256=frozen.digest(ordered),decoder_identity=identity,source_sha256=value['raw_inputs']['NORMAL']['sha256'],
            normality_evidence='Pinned author normal Temperature_and_Humidity complete earliest 7200s',
            device_registry=[dict(device=DEVICE,owner=OWNER,partition=PARTITION)],
            capture_id=segments('NORMAL',value)[0]['capture_id'],cutoff_frame=value['reference']['original_prefix_frames'][1])
        sparse=plan_banks(ordered,census,t0=t0,policy='B2')
        anchors={r['uid'] for r in sparse['rows']}
        windows=[dict(partition=PARTITION,device=DEVICE,source_sha256=value['raw_inputs']['NORMAL']['sha256'],
                      capture_id=segments('NORMAL',value)[0]['capture_id'],start=t0,end=t0+7200,
                      reference_end=t0+7200,frame_end=value['reference']['original_prefix_frames'][1])]
        # Planner "encoded" input is a scheduling priority only in this new
        # domain. No E3 cache exists or is claimed. Encode anchors first and
        # complete every selected position before activating the bank.
        dense=plan_dense_positions(candidates,windows,encoded_uids=anchors,mandatory_uids=anchors)
        dense['prospective_planning']=dict(scheduled_anchor_priority=sorted(anchors),
            actual_encoded_available=0,all_selected_positions_require_encoding=True,
            planner_encoded_input_is_not_an_availability_receipt=True,
            activation_rule='All selected rows successfully encoded and identity-joined; no partial bank')
        chosen=[candidates[i] for i in dense['selected_indices']]
        with gzip.open(output/'REFERENCE_ROWS.jsonl.gz','wt',encoding='utf-8',newline='\n') as stream:
            for row in chosen:
                stream.write(json.dumps(row,separators=(',',':'),ensure_ascii=True)+'\n')
        write(output/'SPARSE_B2_ANCHOR_PLAN.json',sparse)
        write(output/'DENSE_REFERENCE_PLAN.json',dense)
        write(output/'COMMISSIONING_CENSUS.json',census)
        # Engineering-only bank subset: first components by frozen component ID,
        # first two legal positions each; no score or label selection.
        ref_frames=[f for key in sorted(normal_components)[:8] for f in normal_components[key]]
        preflight['REFERENCE_NORMAL']=ref_frames
        preflight['reference_rule']='First 8 canonical component digests lexicographically; first <=2 legal positions per component, commissioning only; engineering subset, never formal bank.'
    write(output/'PREFLIGHT_FRAMES.json',preflight)
    result=dict(status='COMPLETE_POPULATION_NO_MODEL_EVALUATION',version=VERSION,roles=report,inputs=all_inputs,
        physical_logical_mapping={r:segments(r,value) for r in roles},
        frame_semantics='row.frame/provenance frames are original physical ordinals; logical_frame=physical-first+1 is audit-only',
        mask_schema=dict(bytes_per_raw_record=2,first_byte={'0':'OUTSIDE_TRUTH','1':'NORMAL_FIRST_7200','2':'NORMAL_POST_7200','3':'HTTP_DIRECT','4':'UDP_DIRECT'},second_byte=reasons),
        eligibility_implementation='Frozen continuous_input_v3.Contexts.append with explicitly non-numerical state sink; no flow/state snapshots can be emitted.',
        reference_legal_positions=len(candidates),reference_distinct_components=len(component_last),
        selected_reference_rows=len(chosen) if 'NORMAL' in roles else None,
        full_view_reference_overlap_policy='Every eligible commissioning row, including selected reference UIDs, remains a QUERY in full view with exact RAW fallback; reuse its physical feature once. No reference UID is removed from full population.',
        query_reference_overlap_adapter='prebank_query_for_reference; frozen require_prebank_history contract',
        model_evaluations=0,features_generated=0,distance_pairs=0,elapsed_seconds=time.monotonic()-started,
        card_sha256=sha(CARD),decoder_identity_sha256=sha(output/'DECODER_IDENTITY.json'))
    write(output/'POPULATION.json',result)
    write(output/'PROGRESS.json',dict(stage='COMPLETE_POPULATION_NO_MODEL_EVALUATION',elapsed_seconds=time.monotonic()-started))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['population'])
    parser.add_argument('--output',required=True)
    parser.add_argument('--wall-seconds',type=int,default=2400)
    args=parser.parse_args()
    value=population(args.output,wall_seconds=args.wall_seconds)
    print(json.dumps(dict(status=value['status'],elapsed_seconds=value['elapsed_seconds'],selected_reference_rows=value['selected_reference_rows'])))
