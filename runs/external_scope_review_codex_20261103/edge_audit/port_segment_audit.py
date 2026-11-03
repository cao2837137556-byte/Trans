"""Bounded raw header/clock review. No features, models, distances or network."""
from collections import Counter
from pathlib import Path
import hashlib
import importlib.util
import json
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'runs/edge_iiotset_raw_qualification_v1_20261102'
spec = importlib.util.spec_from_file_location('edge_raw_reader', OLD / 'scan_raw.py')
raw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw)
TARGET = '192.168.0.128'
NS = 1_000_000_000


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def summary(counter):
    return dict(counter)


def block():
    return {'counts': Counter(), 'protocols': Counter(), 'local_ports_tcp': Counter(),
            'local_ports_udp': Counter(), 'strata': Counter()}


def observe(st, row):
    st['counts']['IP_target_records'] += 1
    outbound = row['src'] == TARGET
    st['counts']['outbound' if outbound else 'inbound'] += 1
    proto = row['protocol']; st['protocols'][str(proto)] += 1
    st['strata'][('outbound|' if outbound else 'inbound|') + raw.strata(row)] += 1
    local = row['sport'] if outbound else row['dport']
    if proto in (6, 17) and local is not None:
        st['local_ports_tcp' if proto == 6 else 'local_ports_udp'][str(local)] += 1
        if proto == 6 and local == 80:
            st['counts']['target_local_TCP_80'] += 1
        if proto == 17 and local == 0:
            st['counts']['target_local_UDP_0'] += 1
        if proto == 6 and 80 in (row['sport'], row['dport']):
            st['counts']['either_endpoint_TCP_80'] += 1
        if proto == 17 and 0 in (row['sport'], row['dport']):
            st['counts']['either_endpoint_UDP_0'] += 1


def serial(st):
    return {k: summary(v) for k, v in st.items()}


def main():
    start = time.monotonic()
    normal = read_json(OLD / 'NORMAL_AUDIT.json')
    result = read_json(OLD / 'RESULT.json')
    path = Path(normal['input'])
    before = path.stat(); before_sha = raw.sha(path)
    assert before_sha == normal['input_sha256']
    groups = {name: block() for name in ('ALL', 'GLOBAL_FIRST_7200', 'AFTER_GLOBAL_7200')}
    segments = []
    for original in normal['segments']:
        s = dict(original)
        s.update(target_first_ns=None, target_last_ns=None, target_record_count=0,
                 before_first_attack=s['max_ns'] < result['earliest_attack_ns'],
                 groups={name: block() for name in ('ALL', 'FIRST_7200', 'AFTER_7200')})
        segments.append(s)
    idx = 0; seen = 0
    for frame, (ns, payload, caplen, wirelen, link, iface, snaplen) in enumerate(raw.RawRecords(path), 1):
        seen += 1
        while frame > segments[idx]['last_frame']:
            idx += 1
        s = segments[idx]
        row = raw.packet_header(payload, link)
        if row and not row.get('non_ip') and row.get('unsupported_linktype') is None and TARGET in (row['src'], row['dst']):
            s['target_record_count'] += 1
            s['target_first_ns'] = ns if s['target_first_ns'] is None else min(s['target_first_ns'], ns)
            s['target_last_ns'] = ns if s['target_last_ns'] is None else max(s['target_last_ns'], ns)
            observe(groups['ALL'], row)
            observe(groups['GLOBAL_FIRST_7200' if ns <= normal['first_record_ns'] + 7200*NS else 'AFTER_GLOBAL_7200'], row)
            observe(s['groups']['ALL'], row)
            observe(s['groups']['FIRST_7200' if ns <= s['min_ns'] + 7200*NS else 'AFTER_7200'], row)
        if frame % 100_000 == 0:
            (OUT/'PROGRESS.json').write_text(json.dumps({'phase':'NORMAL_RAW_PORT_SEGMENT_AUDIT','frames':frame,'total_frames':normal['counts']['records'],'elapsed_seconds':time.monotonic()-start}),encoding='utf-8')
            if time.monotonic()-start > 300:
                raise TimeoutError('bounded normal raw audit exceeded 300 seconds')
    assert seen == normal['counts']['records']
    assert groups['ALL']['counts']['IP_target_records'] == result['normal_edge_target']['counts']['records']
    for s in segments:
        s['target_span_seconds'] = (s['target_last_ns'] - s['target_first_ns']) / NS
        s['target_covers_7200_and_has_later_normal'] = s['target_span_seconds'] > 7200
        s['first_7200_cutoff_ns'] = s['min_ns'] + 7200*NS
        s['target_t0_equals_capture_segment_t0'] = s['target_first_ns'] == s['min_ns']
        s['groups'] = {k: serial(v) for k,v in s['groups'].items()}
    after_sha = raw.sha(path); after = path.stat()
    assert before_sha == after_sha and before.st_mtime_ns == after.st_mtime_ns and before.st_size == after.st_size
    out = {'status':'PASS_RAW_METADATA_ONLY','normal_input_sha256':before_sha,'normal_input_unchanged':True,
           'records_processed':seen,'definition_local_port':'target sport when outbound; target dport when inbound',
           'group_cutoff_rule':'timestamp <= segment t0+7200s is observation; > is later normal',
           'global_groups':{k:serial(v) for k,v in groups.items()},'segments':segments,
           'elapsed_seconds':time.monotonic()-start,'model_evaluations':0,'encodings':0,'distance_pairs':0,
           'scope':'Same original timestamps/frame identities; no sorting/splicing or new raw downloads; no attack truth inferred from filename'}
    (OUT/'RAW_PORT_SEGMENT_RESULT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':out['status'],'elapsed_seconds':out['elapsed_seconds'],'segments':len(segments),
                      'TCP80_local':groups['ALL']['counts']['target_local_TCP_80'],'UDP0_local':groups['ALL']['counts']['target_local_UDP_0']}))


if __name__ == '__main__':
    main()
