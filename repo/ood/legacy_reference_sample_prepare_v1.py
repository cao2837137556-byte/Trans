"""Prepare identity/label manifests, never load an encoder, score or optimizer.

All writes belong to a new run. The literal legacy prefix and the prospective
owner guard are shared by manifest preparation and the future feature adapter.
"""
from __future__ import annotations

import argparse
from array import array
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import dpkt
import legacy_cic2022_two_camera_semantic_probe_v1 as old
import legacy_reference_context_scope_v1 as guard

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'runs/legacy_reference_material_audit_v1_20260916'
COMPLETE = ROOT / 'runs/legacy_normal_supplement_completion_v2_20260917'
TSHARK = Path('C:/Program Files/Wireshark/tshark.exe')
CAP = 32
REFERENCE_CAP = 64
SELECTION_SALT = 'legacy-reference-sample-v1-20260917'
ATTACKER_MAC = 'f0:18:98:0c:aa:af'
ATTACKER_IP = '192.168.137.5'


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def dump(p, value):
    p = Path(p)
    temp = p.with_name(p.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(p)


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def even_indices(n, cap=CAP):
    """Equal-rank coverage including both endpoints; no score-informed choice."""
    if n <= cap:
        return list(range(n))
    if cap == 1:
        return [n - 1]
    return [i * (n - 1) // (cap - 1) for i in range(cap)]


def headers_complete(row, event):
    fields = ('ip.src','ip.dst','ip.hdr_len','ip.dsfield','ip.len','ip.flags','ip.ttl') if event.ip_version == 4 else ('ipv6.src','ipv6.dst','ipv6.tclass','ipv6.plen','ipv6.hlim')
    fields += ('tcp.srcport','tcp.dstport','tcp.flags','tcp.window_size_value','tcp.seq_raw','tcp.ack_raw','tcp.urgent_pointer','tcp.hdr_len') if event.ip_proto == 6 else ('udp.srcport','udp.dstport','udp.length')
    return all(row.get(k, '') != '' for k in fields)


class ScopedPrefixes:
    """Guard EVERY append, with no future labels, query selection or file stats."""
    def __init__(self, capture, known, prefix_api, retain_full_rows=False):
        self.capture, self.known, self.api = capture, frozenset(known), prefix_api
        self.states, self.poisoned = {}, set()
        self.reasons = Counter()
        self.retain_full_rows = retain_full_rows

    def append(self, row, event):
        key = old.old_key(event)
        if key is None:
            self.reasons['OUTSIDE_LEGACY_PROTOCOL'] += 1
            return None, None, False
        matches = {row.get('eth.src', '').lower(), row.get('eth.dst', '').lower()} & self.known
        if len(matches) != 1:
            self.reasons['OWNER_AMBIGUOUS_OR_OUTSIDE'] += 1
            return None, None, False
        owner = next(iter(matches))
        accepted, reason = guard.context_decision(row, event, owner_mac=owner, known_device_macs=self.known,
            capture_id=self.capture, query_capture_id=self.capture, query_frame=int(row['frame.number']),
            query_timestamp=event.timestamp, query_key=key)
        if not accepted:
            self.reasons[reason] += 1
            return None, None, False
        namespace = guard.prefix_namespace(owner_mac=owner, capture_id=self.capture, event=event)
        if namespace in self.poisoned:
            self.reasons['POISONED_PREFIX'] += 1
            return owner, namespace, False
        prefix = self.states.setdefault(namespace, self.api.BoundedNetfoundPrefix())
        try:
            retained_row = row if self.retain_full_rows else {k:row.get(k,'') for k in ('frame.number','frame.time_epoch','ip.src','ipv6.src')}
            prefix.append(retained_row, event.timestamp)
        except self.api.SessionTimestampRegression:
            self.poisoned.add(namespace)
            self.states.pop(namespace, None)
            self.reasons['NEW_TIMESTAMP_REGRESSION'] += 1
            return owner, namespace, False
        valid = headers_complete(row, event) and old.number(row.get('frame.cap_len')) >= event.frame_len
        if not valid:
            self.reasons['INCOMPLETE_TARGET'] += 1
        return owner, namespace, valid

    def snapshot(self, namespace, translator):
        import copy
        if not self.retain_full_rows:
            raise RuntimeError('Metadata-only prefix cannot generate features')
        if namespace in self.poisoned:
            raise RuntimeError('Poisoned feature prefix')
        # A later append must never mutate a previously queued feature example.
        return copy.deepcopy(self.states[namespace].flow(translator))


def label(spec, row, event, owner):
    if spec['provenance'] == 'normal':
        return 0, 'certified_normal_source'
    if owner != spec['owner'] or row.get('eth.dst', '').lower() != owner:
        return None, 'not_inbound_victim'
    if spec['mode'] == 'Hydra':
        marker = old.rtsp_markers(row)
        if event.ip_proto == 6 and event.dst_port == 554 and marker['method'] == 'DESCRIBE' and marker['authorization_line_count'] > 0:
            return 1, 'hydra_current_authorized_describe'
        return None, 'hydra_response_background_or_unlabeled_request'
    if row.get('eth.src', '').lower() != ATTACKER_MAC or event.src != ATTACKER_IP or event.dst_port != 80:
        return None, 'not_verified_flood_source_destination_service'
    if spec['mode'] == 'UDP' and event.ip_proto == 17 and old.number(row.get('udp.length')) > 8:
        return 1, 'loic_inbound_udp_payload'
    if spec['mode'] == 'TCP' and event.ip_proto == 6:
        if old.number(row.get('tcp.len')) > 0:
            return 1, 'loic_inbound_tcp_payload'
        if event.tcp_syn and not event.tcp_ack:
            return 1, 'loic_inbound_tcp_syn'
    if spec['mode'] == 'HTTP' and event.ip_proto == 6 and row.get('http.request.method'):
        return 1, 'loic_current_http_request'
    return None, 'unassigned_attack_capture_packet'


def source_catalog():
    from legacy_normal_supplement_audit_v1 import roster
    devices = roster()
    byname = {d['device']: d for d in devices}
    review = load(AUDIT / 'review_summary.json')
    for d in review['devices']:
        byname[d['device']].update(reference_ids=d['reference_capture_ids'], reference_end=d['reference_cutoff'])
    members = {m['member_path']: m for m in load(AUDIT / 'selected_new_members.json')}
    prior = load(ROOT / 'runs/legacy_cic2022_two_camera_semantic_probe_v1_20260915/execution/selected_members.json')
    members.update({m['member_path']: m for m in prior})
    time_roles = {d['file_id']: d['prospective_use'] for d in load(AUDIT / 'prospective_time_membership.json')}
    catalog = []
    for s in load(AUDIT / 'reused_and_new_file_metadata.json'):
        m, d = members[s['member_path']], byname[s['device_label']]
        normal = s['provenance'] == 'normal'
        mode = 'Hydra' if '/Hydra/' in s['member_path'] else Path(s['member_path']).parent.name
        spec = dict(capture_id='interaction-attack-%03d' % s['file_id'], file_id=s['file_id'],
            member_path=s['member_path'], path=m['local_path'], sha256=s['member_sha256'], bytes=m['member_bytes'],
            provenance=s['provenance'], device=d['device'], owner=d['mac'], partition=d['proposed_partition'],
            mode=mode, use=time_roles[s['file_id']], expected_packets=s['counts']['packets'],
            old_candidate_count=s['counts'].get('candidate_targets', 0),
            first=s['independent']['min_timestamp'], last=s['independent']['max_timestamp'])
        spec['skip_reason'] = 'NO_CURRENT_HTTP_REQUEST_TARGETS_PRIOR_AUDIT' if not normal and mode == 'HTTP' and not spec['old_candidate_count'] else None
        catalog.append(spec)
    for i in range(7):
        base = ROOT / 'runs/legacy_normal_supplement_acquisition_v1_20260917' if i < 5 else COMPLETE
        m, s = load(base / ('%02d_receipt.json' % i)), load(base / ('%02d_summary.json' % i))
        catalog.append(dict(capture_id='active-%02d' % i, file_id=296+i, member_path=m['file'],path=m['local_path'],
            sha256=m['sha256'],bytes=m['bytes'],provenance='normal',device=None,owner=None,partition=None,
            mode='ACTIVE_UNANNOTATED',use='LATER_NORMAL_QUERY',expected_packets=s['counts']['packets'],
            old_candidate_count=sum(d['counts'].get('legacy_valid_candidates',0) for d in s['devices']),
            first=s['integrity']['minimum_timestamp'],last=s['integrity']['maximum_timestamp'],skip_reason=None))
    return devices, catalog


def pin_sources():
    baseline = load(ROOT / 'runs/legacy_normal_supplement_research_v1_20260917/verification_and_sources.json')
    for p in baseline['unrelated_files_unchanged']:
        if old.sha(ROOT / p['path']) != p['sha256']:
            raise RuntimeError('Unrelated baseline changed: ' + p['path'])
    pins = []
    for name in ('legacy_normal_supplement_completion_result_v3_20260917',
                 'legacy_reference_sample_scope_and_control_v1_20260917',
                 'legacy_reference_conditioned_joint_design_v1_20260916'):
        p = ROOT / 'runs/mainline_docs' / (name + '.md')
        expected = p.with_suffix('.sha256').read_text().split()[0]
        if old.sha(p) != expected:
            raise RuntimeError('Source document drift: ' + str(p))
        pins.append(dict(path=str(p.relative_to(ROOT)),sha256=expected))
    for p in [Path(__file__), Path(guard.__file__), Path(old.__file__),old.LEGACY_EVENT,old.LEGACY_PREFIX,old.LEGACY_TRANSLATOR]:
        pins.append(dict(path=str(p.relative_to(ROOT)),sha256=old.sha(p)))
    for base, names in [(AUDIT, ['reused_and_new_file_metadata.json','review_summary.json','selected_new_members.json','prospective_time_membership.json']),
                        (COMPLETE,['reference_scope_feasibility.json','prospective_sample_scope_contract.json'])]:
        sealed = dict((name,h) for h,name in (line.split('  ',1) for line in (base/'SHA256SUMS').read_text().splitlines()))
        for name in names:
            h = old.sha(base/name)
            if h != sealed[name]: raise RuntimeError('Source seal drift: '+name)
            pins.append(dict(path=str((base/name).relative_to(ROOT)),sha256=h))
    return dict(sources=pins, unrelated_files=baseline['unrelated_files_unchanged'])


def decoded_rows(spec, log):
    _, _, all_fields = old.legacy_runtime()
    exclude = {'tcp.payload','rtsp.url','rtsp.cseq','rtsp.method','rtsp.status'}
    fields = [k for k in all_fields if k not in exclude]
    fields += ['http.request.method']
    if spec['mode'] == 'Hydra': fields += ['tcp.payload','rtsp.method']
    command = [str(TSHARK), '-n','-r',spec['path'],'-T','fields','-E','header=y','-E','separator=/t','-E','quote=d','-E','occurrence=f']
    for k in fields: command += ['-e', k]
    with Path(log).open('w',encoding='utf-8') as err:
        p = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',errors='strict')
        try:
            reader=csv.DictReader(p.stdout,delimiter='\t',quotechar='"')
            if list(reader.fieldnames or []) != fields: raise RuntimeError('Decoder schema drift')
            for row in reader:
                if None in row: raise RuntimeError('Decoder malformed row')
                yield row
            if p.wait(timeout=30): raise RuntimeError('Decoder failed')
        finally:
            if p.poll() is None: p.kill();p.wait(timeout=30)
            p.stdout.close()
    if Path(log).stat().st_size: raise RuntimeError('Decoder diagnostic requires review')


def scan_capture(spec, devices, out):
    """One new manifest pass; old audit files are read-only, never rerun."""
    out=Path(out); cid=spec['capture_id']; path=Path(spec['path'])
    status_path=out/(cid+'_progress.json')
    started=time.time()
    dump(status_path,dict(status='HASH',capture=cid,packets=0,total=spec['expected_packets']))
    if path.stat().st_size!=spec['bytes'] or old.sha(path)!=spec['sha256']:
        raise RuntimeError('Raw identity drift: '+cid)
    if spec['skip_reason']:
        result=dict(capture_id=cid,status='EXCLUDED_BY_FROZEN_LABEL_RULE',reason=spec['skip_reason'],selected=0,raw_identity_verified=True)
        dump(out/(cid+'_receipt.json'),result);dump(status_path,result);return result
    api,prefix_api,_=old.legacy_runtime()
    bymac={d['mac']:d for d in devices}
    contexts=ScopedPrefixes(cid,bymac,prefix_api)
    sessions={}; counts=Counter(); evidence=Counter(); owners=Counter()
    for row in decoded_rows(spec,out/(cid+'_tshark.stderr.log')):
        counts['packets']+=1
        frame=int(row['frame.number'])
        if frame!=counts['packets']:raise RuntimeError('Frame order drift')
        event=api.event_from_tshark(row)
        owner,key,valid=contexts.append(row,event)
        if key is not None:
            session=sessions.setdefault(key,dict(frames=array('I'),times=array('d'),first=event.timestamp,last=event.timestamp,
                first_frame=frame,last_frame=frame,protocol=event.ip_proto,seen_packets=0,owner=owner,
                direction_counts=Counter(),device_ports=set(),transport_streams=set()))
            session['last']=event.timestamp;session['last_frame']=frame;session['seen_packets']+=1
            stream='tcp:'+row['tcp.stream'] if row.get('tcp.stream') else 'udp:'+row['udp.stream'] if row.get('udp.stream') else None
            if stream:session['transport_streams'].add(stream)
        if valid:
            if spec['owner'] is not None and owner!=spec['owner']:
                counts['other_device_unassigned']+=1
            else:
                y,why=label(spec,row,event,owner)
                evidence[why]+=1
                if y is not None:
                    session['frames'].append(frame);session['times'].append(event.timestamp)
                    inbound=row['eth.dst'].lower()==owner
                    session['direction_counts']['inbound' if inbound else 'outbound']+=1
                    session['device_ports'].add(event.dst_port if inbound else event.src_port)
                    counts['labeled_eligible']+=1;owners[owner]+=1
        if counts['packets']%100000==0:
            dump(status_path,dict(status='INDEXING',capture=cid,packets=counts['packets'],total=spec['expected_packets'],elapsed_seconds=time.time()-started))
    if counts['packets']!=spec['expected_packets']:raise RuntimeError('Raw audit packet denominator drift')
    if spec['provenance']=='attack' and counts['labeled_eligible']!=spec['old_candidate_count']:
        raise RuntimeError('Attack source/label refinement changed audited candidate count: '+cid)
    # Select by candidate rank, never features/scores. The full contexts remain
    # raw-source-addressable; selection cannot determine prefix membership.
    targets=[]; session_rows=[]
    for key,s in sessions.items():
        n=len(s['frames'])
        if not n:continue
        d=bymac[s['owner']]; session_id=digest(key); component_id=digest([s['owner'],key[-1]])
        idx=even_indices(n,1 if spec['use']=='REFERENCE' else CAP)
        group=dict(capture_id=cid,device=d['device'],owner=s['owner'],partition=d['proposed_partition'],
            session_id=session_id,component_id=component_id,canonical_key=key[-1],first=s['first'],last=s['last'],
            first_frame=s['first_frame'],last_frame=s['last_frame'],eligible=n,selected=len(idx),
            observed_transport_streams=len(s['transport_streams']),protocol=s['protocol'],
            device_ports=sorted(s['device_ports']),direction_counts=dict(s['direction_counts']))
        session_rows.append(group)
        for i in idx:
            frame=int(s['frames'][i]);timestamp=float(s['times'][i])
            if spec['use']!='REFERENCE':
                ok,why=guard.reference_decision(reference_owner=s['owner'],query_owner=s['owner'],certified_normal=True,
                    reference_end=d['reference_end'],first_query_time=timestamp,reference_partition=d['proposed_partition'],query_partition=d['proposed_partition'])
                if not ok:raise RuntimeError(why+': '+cid)
            targets.append(dict(uid=digest([spec['sha256'],frame,s['owner']]),capture_id=cid,source_sha256=spec['sha256'],
                frame=frame,timestamp=timestamp,device=d['device'],owner=s['owner'],partition=d['proposed_partition'],
                use=spec['use'],label=int(spec['provenance']=='attack'),activity=spec['mode'],
                session_id=session_id,component_id=component_id,protocol=s['protocol'],canonical_key=key[-1],
                candidate_rank=i,candidate_count=n,sample_count=len(idx),reference_end=d['reference_end']))
    targets.sort(key=lambda x:x['frame'])
    # Hash exact captured bytes only for selected targets, with independent frame
    # and timestamp validation. Byte equality at different times is not leakage.
    frame_map={t['frame']:t for t in targets}
    with path.open('rb') as fin:
        magic=fin.read(4);fin.seek(0)
        reader=dpkt.pcapng.Reader(fin) if magic==b'\x0a\x0d\x0d\x0a' else dpkt.pcap.Reader(fin)
        for n,(ts,packet) in enumerate(reader,1):
            if n in frame_map:
                t=frame_map[n]
                if abs(float(ts)-t['timestamp'])>0.000002:raise RuntimeError('Independent timestamp mismatch')
                t['packet_sha256']=hashlib.sha256(packet).hexdigest()
    if any('packet_sha256' not in t for t in targets):raise RuntimeError('Independent selected coverage mismatch')
    with gzip.open(out/(cid+'_targets.jsonl.gz'),'wt',encoding='utf-8') as f:
        for t in targets:f.write(json.dumps(t,separators=(',',':'))+'\n')
    dump(out/(cid+'_sessions.json'),session_rows)
    result=dict(capture_id=cid,status='COMPLETE',counts=dict(counts),selected=len(targets),sessions=len(session_rows),
        per_owner_candidates=dict(owners),context_reasons=dict(contexts.reasons),label_evidence=dict(evidence),
        elapsed_seconds=time.time()-started,raw_identity_verified=True)
    dump(out/(cid+'_receipt.json'),result);dump(status_path,result)
    return result


def progress(out,status):
    dump(out/'status.json',status)
    (out/'PROGRESS.md').write_text('# 样本与配方准备\n\n状态：%s\n\n完成 %s / %s 个捕获条目。\n\n训练、模型评分、HPC：未启动。\n\n%s\n' %
        (status['status'],status.get('completed',0),status.get('total',0),status.get('error','')),encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(ROOT):raise RuntimeError('Output outside workspace')
    out.mkdir(parents=True,exist_ok=False);(out/'captures').mkdir()
    status=dict(status='PREPARING',completed=0,total=302,started_epoch=time.time(),training=False,scoring=False,hpc=False,retries=0)
    progress(out,status)
    try:
        pins=pin_sources();dump(out/'input_pins.json',pins)
        devices,catalog=source_catalog();dump(out/'devices.json',devices);dump(out/'capture_catalog.json',catalog)
        dump(out/'authorization.json',dict(user_quote='可以，动手下一步。',scope='Implement and execute bounded UID/label/reference preparation and freeze a complete prospective recipe; no features, scoring, training, downloads or HPC.',
             selection=dict(per_canonical_capture_cap=CAP,reference_cap=REFERENCE_CAP,method='equal candidate rank endpoints; all eligible canonical sessions retained before explicit duplicate checks',salt=SELECTION_SALT),
             workers=2,fail_policy='STOP_NO_AUTOMATIC_RETRY',prior_result_files_read_only=True))
        (out/'git_status_before.txt').write_text(subprocess.run(['git','status','--short'],cwd=ROOT,capture_output=True,text=True,check=True).stdout,encoding='utf-8')
        results=[];iterator=iter(catalog)
        with ProcessPoolExecutor(max_workers=2) as pool:
            pending={}
            for _ in range(2):
                spec=next(iterator,None)
                if spec:pending[pool.submit(scan_capture,spec,devices,str(out/'captures'))]=spec
            while pending:
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    spec=pending.pop(future);results.append(future.result())
                    status.update(status='INDEXING',completed=len(results),last_completed=spec['capture_id'],elapsed_seconds=time.time()-status['started_epoch'])
                    progress(out,status)
                    next_spec=next(iterator,None)
                    if next_spec:pending[pool.submit(scan_capture,next_spec,devices,str(out/'captures'))]=next_spec
        dump(out/'capture_receipts.json',results)
        status.update(status='MANIFEST_SCAN_COMPLETE_REQUIRES_FINALIZATION',completed=len(results),elapsed_seconds=time.time()-status['started_epoch'])
    except BaseException as exc:
        status.update(status='STOPPED_NO_RETRY',error=type(exc).__name__+': '+str(exc));raise
    finally:progress(out,status)


if __name__=='__main__':main()
