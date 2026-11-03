"""Enumerate all legal endpoints from the three pinned REFERENCE captures."""
from collections import Counter, defaultdict
import copy
import csv
import subprocess

from common import *


def walk_capture(decoded, spec, known_macs, event_api, cutoff):
    import continuous_input_v3 as inp
    from constrained_onboarding_reference_v2 import reference_descriptor
    context = inp.Contexts(spec['capture_id'], known_macs, event_api, required_owners=[spec['owner']])
    entries, rejected = [], []
    first = last = None
    for packet in decoded:
        frame = inp.integer(packet['frame.number'])
        need(frame == context.frame + 1, 'NONCONTIGUOUS_RAW_CAPTURE')
        now = float(packet['frame.time_epoch'])
        first = now if first is None else first; last = now
        owner, namespace, event = context.append(packet)
        if not context.query_allowed:
            rejected.append(dict(frame=frame, reason=context.query_reason))
            continue
        need(owner == spec['owner'] and event.ip_proto in (6, 17), 'EXPECTED_OWNER_PROTOCOL')
        flow, state, provenance = context.states[namespace].snapshot()
        key = namespace[-1]
        row = dict(uid=inp.digest([spec['sha256'], frame, owner]), source_sha256=spec['sha256'],
            capture_id=spec['capture_id'], frame=frame, timestamp=now, owner=owner, device=spec['device'],
            partition=spec['partition'], label=0, use='REFERENCE', history_role='HIST_REF',
            protocol=event.ip_proto, canonical_key=key, component_id=inp.digest([owner, key]),
            session_id=inp.digest(namespace), activity='LAN_WATCH', activity_verified=True,
            activity_evidence=spec['member_path'], normality_evidence=spec['normality_evidence'],
            reference_end=cutoff, bank_end_frame=spec['expected_packets'], origin='C3_ADMITTED_LEGACY_REFERENCE')
        body = dict(flow=flow, state=state, provenance=provenance, source_sha256=spec['sha256'])
        q14, info = reference_descriptor(body, row)
        entries.append(copy.deepcopy(dict(uid=row['uid'], row=row, body=body, q14=q14.tolist(), descriptor=info)))
    need(context.frame == spec['expected_packets'] and first == spec['first'] and last == spec['last'], 'CAPTURE_COMPLETENESS')
    return entries, dict(capture_id=spec['capture_id'], packets=context.frame, first=first, last=last,
                         accepted=len(entries), rejected=rejected, frontend_reasons=dict(context.reasons))


def decode(spec, output):
    import continuous_input_v3 as inp
    import legacy_reference_sample_prepare_v1 as prep
    fields = list(dict.fromkeys([f for f in prep.old.legacy_runtime()[2]
                                if f not in ('tcp.payload', 'rtsp.url', 'rtsp.cseq')] + list(inp.FIELDS)))
    command = ['C:/Program Files/Wireshark/tshark.exe', '-n', '-r', str(ROOT / spec['path']),
               '-T', 'fields', '-E', 'header=y', '-E', 'separator=/t', '-E', 'quote=d', '-E', 'occurrence=f']
    for field in fields: command += ['-e', field]
    log = output / (str(spec['file_id']) + '.tshark.stderr.log')
    with log.open('x', encoding='utf-8') as err:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True, encoding='utf-8')
        try:
            reader = csv.DictReader(proc.stdout, delimiter='\t', quotechar='"')
            need(reader.fieldnames == fields, 'DECODER_FIELDS')
            for row in reader:
                need(None not in row and all(v is not None for v in row.values()), 'DECODE_ROW_SCHEMA')
                yield row
            need(proc.wait(timeout=30) == 0, 'TSHARK_EXIT')
        finally:
            if proc.poll() is None: proc.kill(); proc.wait(timeout=10)
            proc.stdout.close()
    need(log.stat().st_size == 0, 'DECODER_WARNING_REQUIRES_REVIEW')


def main():
    card, manifest = verify_contract()
    need(sha(manifest['tshark']['path']) == manifest['tshark']['sha256'], 'DECODER_BINARY_PIN')
    need(read(HERE / 'IMPLEMENTATION_CHECK.json')['execution_card_sha256'] == sha(HERE / 'EXECUTION_CARD.json'), 'ENGINEERING_CARD_PIN')
    write(HERE / 'PREPARE_ATTEMPT.json', dict(candidate=CANDIDATE, automatic_retry=False), exclusive=True)
    out = HERE / 'prepared'; out.mkdir(exist_ok=False)
    progress('PREPARING', '正在按冻结前端遍历三个已准入正常文件')
    import legacy_reference_sample_prepare_v1 as prep
    event_api = prep.old.legacy_runtime()[0]
    old = [r for r in rows(ROOT / manifest['old_a_rows']) if r['device'] == HEIM]
    need(len(old) == 11, 'ORIGINAL_11_REQUIRED')
    cutoffs = {r['reference_end'] for r in old}; need(len(cutoffs) == 1, 'OLD_HISTORY_CUTOFF')
    entries, captures = [], []
    for spec in sorted(manifest['captures'], key=lambda s: s['first']):
        need(spec['provenance'] == 'normal' and spec['use'] == 'REFERENCE' and spec['mode'] == 'LAN_WATCH', 'SOURCE_ROLE')
        ee, receipt = walk_capture(decode(spec, out), spec, manifest['known_macs'], event_api, next(iter(cutoffs)))
        entries += ee; captures.append(receipt)
    groups = defaultdict(list)
    for e in entries: groups[(e['row']['device'], e['row']['protocol'])].append(e['row'])
    selected, selection = [], []
    for (device, proto), candidates in sorted(groups.items()):
        prior = [r for r in old if r['device'] == device and r['protocol'] == proto]
        extra, branch = complete_small_group(candidates, prior)
        selected += extra
        selection.append(dict(device=device, protocol=proto, legal_candidates=len(candidates), old=len(prior), new=len(extra), branch=branch, cap=CAP))
    counts = Counter(r['protocol'] for r in selected)
    need(0 < len(selected) <= 278 and counts[6] <= 212 and counts[17] <= 66, 'NEW_FRAME_BUDGET')
    # The existing descriptors are a real integration check of the frozen frontend.
    asset = read(C1 / 'config/ASSETS.json')['a_history']
    all_old = list(rows(ROOT / asset['rows']['path']))
    with np.load(ROOT / asset['arrays']['path'], allow_pickle=False) as z:
        need(z['uid'].tolist() == [r['uid'] for r in all_old], 'OLD_A_UID_ARRAY')
        oldq = {r['uid']: q for r, q in zip(all_old, z['q14']) if r['device'] == HEIM}
    by_uid = {e['uid']: e for e in entries}
    need(all(np.array_equal(np.asarray(by_uid[u]['q14'], dtype=np.float32), q) for u, q in oldq.items()), 'OLD_11_Q14_EXACT_REPLAY')
    entries = [by_uid[r['uid']] for r in sorted(selected, key=lambda r: r['uid'])]
    write_rows(out / 'REFERENCES.jsonl.gz', [e['row'] for e in entries])
    write_rows(out / 'SNAPSHOTS.jsonl.gz', entries)
    write(out / 'PREPARE_RESULT.json', dict(status='PREPARED', candidate=CANDIDATE, captures=captures,
        groups=selection, new_rows=len(entries), old_q14_replay_rows=11, all_old_references_preserved=True,
        normality_basis=manifest['normality_basis'], B_census=manifest['B_census'],
        selection_uses_query_scores=False, selection_uses_query_labels=False,
        input_readout='RECENT_CURRENT_INCLUSIVE', capture_boundary_preserved=True,
        overlap_audit_reused=manifest['overlap_evidence'],
        files={p.name: sha(p) for p in out.iterdir() if p.is_file()}))
    verify_contract()
    progress('PREPARED', '合法参考帧已验收，等待冻结超算环境编码', new_rows=len(entries), new_TCP=counts[6], new_UDP=counts[17], old_q14_exact=11)


if __name__ == '__main__': main()
