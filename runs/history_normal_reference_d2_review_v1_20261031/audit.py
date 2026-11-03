"""Read existing metadata and frozen results; never score a candidate or decode PCAP.

This audit writes only its own receipt. It does not import experiment runners.
"""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUTS = {}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def pin(relative):
    path = ROOT / relative
    INPUTS[path.relative_to(ROOT).as_posix()] = dict(bytes=path.stat().st_size, sha256=digest(path))
    return path


def read(relative):
    return json.loads(pin(relative).read_text(encoding='utf-8'))


def rows(relative):
    with gzip.open(pin(relative), 'rt', encoding='utf-8') as f:
        for line in f:
            yield json.loads(line)


def main():
    review = 'runs/mainline_docs/collab/20261031_history_normal_reference_d2_trace_review_antigravity.md'
    assert digest(pin(review)) == '471f061102bcc0b9b5f1f19269bd907c95f86cf08cd89af54598edfb4aefc3ab'
    legacy = 'runs/legacy_reference_material_audit_v1_20260916/'
    research = read('runs/targeted_normal_data_research_v1_20261030/A_LOCAL_REFERENCE_RESEARCH.json')
    registered = {r['file_id']: r for r in research['files']}
    heim = []
    fingerprint_set = set()
    for number in (189, 190, 191):
        summary = read(legacy + f'{number}_summary.json')
        flows = read(legacy + f'{number}_flows.json')
        fingerprints = read(legacy + f'{number}_normal_fingerprints.json')
        fingerprint_set.update(r['sha256'] for r in fingerprints)
        path = pin(legacy + f'raw_selected/{number}.pcap')
        assert digest(path) == summary['member_sha256'] == registered[number]['member_sha256']
        assert registered[number]['is_old_REFERENCE_capture']
        tcp = [r for r in flows if r['protocol'] == 6]
        assert len(tcp) == 1
        flow = tcp[0]
        heim.append(dict(file_id=number, bytes=path.stat().st_size, sha256=digest(path),
                         registered_reference=True, canonical_key=flow['canonical_key'],
                         tcp_candidates=flow['candidate_targets'], tcp_valid_targets=flow['valid_targets'],
                         tcp_payload_packets=flow['payload_packets'],
                         tcp_nonpayload_packets=flow['packets'] - flow['payload_packets'],
                         tcp_prefix_changed=flow['candidate_retained_prefix_changed'],
                         tcp_inbound=flow['inbound'], tcp_outbound=flow['outbound'],
                         udp_candidates=sum(r['candidate_targets'] for r in flows if r['protocol'] == 17),
                         capture_first=summary['independent']['first_timestamp'],
                         capture_last=summary['independent']['last_timestamp'],
                         tcp_first=flow['first_timestamp'], tcp_last=flow['last_timestamp']))
    allowed_captures = {f'interaction-attack-{n}' for n in (189, 190, 191)}
    allowed_hashes = {r['sha256'] for r in heim}
    forbidden_captures = {f'interaction-attack-{n}' for n in (183, 184, 185, 186, 187, 188, 192, 193)}
    forbidden_hashes = {registered[n]['member_sha256'] for n in (183, 184, 185, 186, 187, 188, 192, 193)}
    ab_path = pin('runs/history_normal_reference_d2_trace_v1_20261031/retrieved/ab/CIC_DEV/DECISIONS.npz')
    with np.load(ab_path, allow_pickle=False) as z:
        saved_a_uids = set(z['uid'].tolist())
    overlap = {}
    for name in ('LEARN', 'CIC_DEV'):
        count = 0
        matches = Counter()
        excluded = Counter()
        excluded_saved = Counter()
        excluded_labels = Counter()
        fingerprint_examples = []
        for r in rows(f'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/{name}.jsonl.gz'):
            count += 1
            for key, yes in (
                ('candidate_capture_id', r.get('capture_id') in allowed_captures),
                ('candidate_source_sha256', r.get('source_sha256') in allowed_hashes),
                ('candidate_packet_sha256', r.get('packet_sha256') in fingerprint_set),
            ):
                matches[key] += int(yes)
                if key == 'candidate_packet_sha256' and yes and len(fingerprint_examples) < 5:
                    fingerprint_examples.append({k: r.get(k) for k in ('uid', 'capture_id', 'source_sha256', 'packet_sha256')})
            if r.get('capture_id') in forbidden_captures or r.get('source_sha256') in forbidden_hashes:
                excluded[r['capture_id']] += 1
                excluded_labels[str(r['label'])] += 1
                if name == 'CIC_DEV' and r['uid'] in saved_a_uids:
                    excluded_saved[r['capture_id']] += 1
        overlap[name] = dict(rows=count, matches=dict(matches), fingerprint_examples=fingerprint_examples,
                             forbidden_capture_rows=dict(excluded), forbidden_labels=dict(excluded_labels),
                             forbidden_rows_in_saved_full_A_decisions=dict(excluded_saved))
    old = [r for r in rows('runs/diagnostics_d1_d2_v1_20261022/assets/reference_scores/CIC_DEV_OLD_BANK.jsonl.gz')
           if r['device'] == 'HeimVision Camera']
    old_brief = [{k: r.get(k) for k in ('uid', 'capture_id', 'source_sha256', 'frame', 'protocol', 'use')} for r in old]
    ordered = sorted(heim, key=lambda r: r['capture_first'])
    gaps = [dict(from_file=a['file_id'], to_file=b['file_id'],
                 capture_gap_seconds=round(b['capture_first'] - a['capture_last'], 6),
                 tcp_gap_seconds=round(b['tcp_first'] - a['tcp_last'], 6))
            for a, b in zip(ordered, ordered[1:])]
    trace_base = 'runs/history_normal_reference_d2_trace_v1_20261031/'
    power_base = trace_base + 'retrieved/history/WEMO_POWER/'
    selection = read(power_base + 'selection/SELECTION.json')
    rr = list(rows(power_base + 'encoded/references.jsonl.gz'))
    tcp_rows = [r for r in rr if r['protocol'] == 6]
    component_sizes = Counter(r['component_id'] for r in tcp_rows)
    by_port = {}
    for port in (49153, 49152, 8443, 8899):
        subset = [r for r in tcp_rows if port in {int(e[1]) for e in r['canonical_key'][1:]}]
        sizes = Counter(r['component_id'] for r in subset)
        by_port[str(port)] = dict(rows=len(subset), components=len(sizes),
                                 selected_rows_per_component_histogram=dict(sorted(Counter(sizes.values()).items())))
    power = dict(selection_tcp_group=next(g for g in selection['groups'] if g['role'] == 'HIST_REF' and g['protocol'] == 6),
                 actual_tcp_selected_rows=len(tcp_rows), actual_tcp_selected_components=len(component_sizes),
                 selected_rows_per_component_histogram=dict(sorted(Counter(component_sizes.values()).items())),
                 selected_reference_endpoint_ports=by_port)
    trace_counts = Counter()
    matched_ports = Counter()
    trace_query_keys = set()
    for r in rows(trace_base + 'output/NEIGHBORS.jsonl.gz'):
        if r['cohort'] != 'P4_WEMO_POWER_RESIDUAL':
            continue
        trace_counts['rows'] += 1
        trace_query_keys.update(r['query'])
        trace_counts['query_has_canonical_key'] += int('canonical_key' in r['query'])
        pair = r['neighbors']
        if len(pair) == 2:
            common = ({int(e[1]) for e in pair[0]['reference']['canonical_key'][1:]} &
                      {int(e[1]) for e in pair[1]['reference']['canonical_key'][1:]})
            matched_ports.update(common)
            trace_counts['paired_reference_common_8443_or_8899'] += int(bool(common & {8443, 8899}))
            trace_counts['paired_reference_common_both_8443_and_8899'] += int({8443, 8899} <= common)
    power['trace_reference_port_statistic'] = dict(**dict(trace_counts), common_reference_port_counts=dict(matched_ports),
                                                 query_metadata_fields=sorted(trace_query_keys),
                                                 meaning='Matched reference endpoints, not query endpoint ports.')
    dev_rows = list(rows(trace_base + 'retrieved/dev/QUERIES.jsonl.gz'))
    dev_path = pin(trace_base + 'retrieved/dev/DEV_DECISIONS.npz')
    with np.load(dev_path, allow_pickle=False) as z:
        dev_arrays = {k: dict(shape=list(z[k].shape), dtype=str(z[k].dtype)) for k in z.files}
        assert [r['uid'] for r in dev_rows] == z['uid'].tolist()
    dev = dict(rows=len(dev_rows), arrays=dev_arrays,
               rows_with_q14=sum('q14' in r for r in dev_rows),
               rows_with_flags=sum(any(k in r for k in ('flags', 'tcp_flags', 'tcp.flags')) for r in dev_rows),
               missing_local_query_arrays=[trace_base + f'retrieved/history/{key}/encoded/queries.npz'
                                           for key in ('TP_LINK', 'SAMSUNG', 'WEMO_POWER')
                                           if not (ROOT / trace_base / f'retrieved/history/{key}/encoded/queries.npz').exists()])
    snapshot = read('runs/reference_attack_competition_progress_20261029/runtime/FINAL_PROGRESS_SNAPSHOT.json')
    declared = {}

    def collect(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ('G0/CAL/SCORES.npz', 'G0/S/SCORES.npz', 'G1/CAL/SCORES.npz', 'G1/S/SCORES.npz') and isinstance(v, str):
                    declared[k] = v
                collect(v)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(snapshot)
    assert len(declared) == 4
    source = {k: dict(expected_sha256=v,
                      local_expected_path='runs/reference_attack_competition_v1_20261029/outputs/source_180228/' + k,
                      exists_at_local_expected_path=(ROOT / 'runs/reference_attack_competition_v1_20261029/outputs/source_180228' / k).exists())
              for k, v in sorted(declared.items())}
    result = dict(status='READ_ONLY_REVIEW_COMPLETE', inputs=INPUTS,
                  scope=dict(pcap_decode=False, new_model_features=False, candidate_scoring=False,
                             new_distance_pairs=0, remote_actions=False, experiment_execution=False),
                  heim=dict(files=heim, capture_gaps=gaps, overlap=overlap, old_reference_rows=old_brief,
                            candidate_tcp_total=sum(r['tcp_candidates'] for r in heim),
                            candidate_udp_total=sum(r['udp_candidates'] for r in heim),
                            exact_flag_histogram_available_in_flow_metadata=False,
                            current_encoder_admission_or_causal_gain_verified=False),
                  power=power, hist_dev_local_inputs=dev, source_180228_saved_scores=source)
    result['audit_code_sha256'] = digest(Path(__file__))
    destination = HERE / 'REVIEW_EVIDENCE.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], heim_overlap=overlap, heim_capture_gaps=gaps,
                          power=power, hist_dev_missing_q14=dev['rows_with_q14'] == 0,
                          source_scores_local={k: v['exists_at_local_expected_path'] for k, v in source.items()},
                          receipt_sha256=digest(destination)), ensure_ascii=False))


if __name__ == '__main__':
    main()
