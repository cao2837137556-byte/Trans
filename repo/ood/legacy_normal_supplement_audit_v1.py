"""Raw-only multi-device coverage audit; literal old eligibility, no features/model."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import struct
import subprocess
import time
from collections import Counter
from pathlib import Path

import dpkt
import legacy_cic2022_two_camera_semantic_probe_v1 as old
from legacy_normal_supplement_acquire_v1 import ROOT, RUN, RESEARCH, dump

PRIOR = ROOT/'runs/legacy_reference_material_audit_v1_20260916'
TSHARK = Path('C:/Program Files/Wireshark/tshark.exe')


def utc(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


def roster():
    inventory = ROOT/'runs/legacy_cic2022_support_inventory_v1_20260915/support_inventory.json'
    mapping = ROOT/'runs/legacy_cic2022_interactions_acquisition_v1_20260915/metadata_assessment.json'
    devices = json.loads((PRIOR/'review_summary.json').read_text(encoding='utf-8'))['devices']
    rows = {r['source_row']:r for r in json.loads(inventory.read_text(encoding='utf-8'))['device_roster']['devices']}
    names = {r['attack_device_label']:r for r in json.loads(mapping.read_text(encoding='utf-8'))['attack_normal_name_correspondence']}
    result = []
    for d in devices:
        r = names[d['device']]
        if len(r['roster_candidate_rows']) != 1:
            raise RuntimeError('Ambiguous target roster')
        result.append(dict(device=d['device'], proposed_partition=d['proposed_partition'],
            mac=rows[r['roster_candidate_rows'][0]]['mac'].lower(), earliest_attack_date=min(d['attack_utc_dates'])))
    assert len(result)==11 and len({x['mac'] for x in result})==11
    return result


def strict_records(path):
    """Check record/block boundaries, then yield (timestamp, bytes, original length)."""
    with path.open('rb') as f:
        magic=f.read(4)
        if magic==b'\x0a\x0d\x0d\x0a':
            # Validate every block boundary; dpkt handles packet timestamp resolution.
            f.seek(0)
            endian=None
            while True:
                head=f.read(12)
                if not head: break
                if len(head)!=12: raise RuntimeError('Truncated PCAPNG block header')
                if head[:4]==magic:
                    endian={b'\x4d\x3c\x2b\x1a':'<',b'\x1a\x2b\x3c\x4d':'>'}.get(head[8:12])
                if endian is None: raise RuntimeError('Bad PCAPNG byte order')
                n=struct.unpack(endian+'I',head[4:8])[0]
                if n<12 or n%4 or n>64*1024*1024: raise RuntimeError('Invalid PCAPNG block size')
                tail=f.read(n-12)
                if len(tail)!=n-12 or struct.unpack(endian+'I',(head+tail)[-4:])[0]!=n:
                    raise RuntimeError('Truncated/mismatched PCAPNG block')
            f.seek(0)
            reader=dpkt.pcapng.Reader(f)
            if reader.datalink()!=1: raise RuntimeError('Non-Ethernet capture requires scope review')
            for ts, packet in reader:
                yield float(ts),packet,None
        else:
            formats={b'\xd4\xc3\xb2\xa1':('<',1e6),b'\xa1\xb2\xc3\xd4':('>',1e6),
                     b'\x4d\x3c\xb2\xa1':('<',1e9),b'\xa1\xb2\x3c\x4d':('>',1e9)}
            if magic not in formats: raise RuntimeError('Bad PCAP magic')
            endian,scale=formats[magic]
            rest=f.read(20)
            if len(rest)!=20: raise RuntimeError('Truncated global header')
            major,minor,zone,sig,snap,link=struct.unpack(endian+'HHiIII',rest)
            if (major,minor)!=(2,4) or (link & 0xffff)!=1: raise RuntimeError('Unsupported version/linktype')
            while True:
                h=f.read(16)
                if not h: break
                if len(h)!=16: raise RuntimeError('Truncated record header')
                sec,frac,caplen,wirelen=struct.unpack(endian+'IIII',h)
                if frac>=scale or caplen>snap or caplen>wirelen or caplen>64*1024*1024:
                    raise RuntimeError('Invalid PCAP record lengths/timestamp')
                packet=f.read(caplen)
                if len(packet)!=caplen: raise RuntimeError('Truncated record body')
                yield sec+frac/scale,packet,wirelen


def integrity(path, targets, index, status):
    bits={bytes.fromhex(x['mac'].replace(':','')):1<<i for i,x in enumerate(targets)}
    c=Counter(); minimum=math.inf; maximum=-math.inf; previous=None
    seen=set()
    fp=RUN/('%02d_fingerprints.bin'%index)
    with fp.open('xb') as out:
        for ts,packet,wire in strict_records(path):
            c['packets']+=1; c['captured_bytes']+=len(packet)
            minimum=min(minimum,ts); maximum=max(maximum,ts)
            if previous is not None and ts<previous: c['time_regressions']+=1
            previous=ts
            if wire is not None and len(packet)<wire: c['snaplen_truncated_packets']+=1
            mask=bits.get(packet[:6],0)|bits.get(packet[6:12],0)
            if mask:
                digest=hashlib.sha256(packet).digest()
                if digest in seen: c['target_exact_byte_repeats']+=1
                seen.add(digest)
                # Hash, microsecond timestamp, device bit mask. No packet payload export.
                out.write(struct.pack('<32sqH',digest,round(ts*1e6),mask))
                c['target_records']+=1
            if c['packets']%100000==0:
                status.update(stage='INTEGRITY',packets=c['packets'])
                dump(RUN/'audit_status.json',status)
    if not c['packets']: raise RuntimeError('Empty capture')
    return dict(counts=dict(c),minimum_timestamp=minimum,maximum_timestamp=maximum,
                first_utc=utc(minimum),last_utc=utc(maximum),target_unique_packet_bytes=len(seen),
                fingerprints=fp.name,fingerprint_record_format='<32sqH',fingerprint_record_bytes=42)


def required_headers(event):
    r=['ip.src','ip.dst','ip.hdr_len','ip.dsfield','ip.len','ip.flags','ip.ttl'] if event.ip_version==4 else ['ipv6.src','ipv6.dst','ipv6.tclass','ipv6.plen','ipv6.hlim']
    r+=['tcp.srcport','tcp.dstport','tcp.flags','tcp.window_size_value','tcp.seq_raw','tcp.ack_raw','tcp.urgent_pointer','tcp.hdr_len'] if event.ip_proto==6 else ['udp.srcport','udp.dstport','udp.length']
    return r


def audit(index):
    marker=RUN/('%02d_audit_attempt.json'%index)
    if marker.exists(): raise RuntimeError('Audit already attempted; no automatic rerun')
    receipt=json.loads((RUN/('%02d_receipt.json'%index)).read_text(encoding='utf-8'))
    path=Path(receipt['local_path'])
    targets=roster()
    pins=json.loads((PRIOR/'execution_manifest.json').read_text(encoding='utf-8'))
    for row in pins['legacy_source_pins']:
        if old.sha(Path(row['path']))!=row['sha256']: raise RuntimeError('Legacy source changed')
    dump(marker,dict(start_epoch=time.time(),script_sha256=old.sha(Path(__file__)),
        targets=targets,legacy_source_pins=pins['legacy_source_pins'],raw_sha256_expected=receipt['sha256']))
    status=dict(status='RUNNING',file=receipt['file'],stage='HASH',packets=0,retries=0)
    dump(RUN/'audit_status.json',status)
    try:
        if path.stat().st_size!=receipt['bytes'] or old.sha(path)!=receipt['sha256']:
            raise RuntimeError('Downloaded identity mismatch')
        record=integrity(path,targets,index,status)
        # Stop on date contradiction before downloading any later file.
        date=receipt['file'].split('/')[-1][:10].replace('_','-')
        if record['first_utc'][:10]!=date or record['last_utc'][:10]>=min(x['earliest_attack_date'] for x in targets):
            dump(RUN/('%02d_integrity.json'%index),record)
            raise RuntimeError('Actual capture chronology contradicts proposed filename/attack order')
        runtime,prefix_api,fields=old.legacy_runtime()
        fields=tuple(dict.fromkeys([x for x in fields if x not in {'tcp.payload','rtsp.url','rtsp.cseq'}]+['http.request.method','http.response.code']))
        bymac={x['mac']:i for i,x in enumerate(targets)}
        counts=Counter(); protocols=Counter(); prefixes={}; flows={}
        devices=[dict(meta=x,counts=Counter(),minutes=set(),dates=set(),inbound=Counter(),outbound=Counter(),protocols=Counter(),http_methods=Counter(),first=None,last=None) for x in targets]
        command=[str(TSHARK),'-n','-r',str(path),'-T','fields','-E','header=y','-E','separator=/t','-E','quote=d','-E','occurrence=f']
        for field in fields: command+=['-e',field]
        with (RUN/('%02d_tshark.stderr.log'%index)).open('w',encoding='utf-8') as err:
            proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',errors='strict')
            try:
                reader=csv.DictReader(proc.stdout,delimiter='\t',quotechar='"')
                if tuple(reader.fieldnames or ())!=fields: raise RuntimeError('TShark schema mismatch')
                for row in reader:
                    if None in row: raise RuntimeError('TShark row mismatch')
                    counts['packets']+=1
                    if int(row['frame.number'])!=counts['packets']: raise RuntimeError('Frame order mismatch')
                    e=runtime.event_from_tshark(row)
                    ts=e.timestamp
                    if not math.isfinite(ts): raise RuntimeError('Invalid timestamp')
                    caplen=old.number(row['frame.cap_len'])
                    counts['captured_bytes']+=caplen
                    counts['truncated']+=int(caplen<e.frame_len)
                    leaf=row['frame.protocols'].split(':')[-1]
                    protocols[leaf]+=1
                    sm,dm=row['eth.src'].lower(),row['eth.dst'].lower()
                    matches=sorted({bymac[m] for m in (sm,dm) if m in bymac})
                    roles={targets[i]['proposed_partition'] for i in matches}
                    counts['cross_role_direct_packets']+=int(len(roles)>1)
                    key=old.old_key(e)
                    valid=False; retained=False
                    if key is not None:
                        counts['legacy_gate']+=1
                        p=prefixes.setdefault(key,{'prefix':prefix_api.BoundedNetfoundPrefix(),'poisoned':False})
                        if not p['poisoned']:
                            try:
                                p['prefix'].append({k:row[k] for k in ('frame.number','frame.time_epoch','ip.src','ipv6.src')},ts)
                                retained=p['prefix'].bursts[e.src==p['prefix'].first_src][-1][-1]['frame.number']==row['frame.number']
                            except prefix_api.SessionTimestampRegression:
                                p['poisoned']=True; counts['session_regressions']+=1
                        complete=all(row.get(k,'')!='' for k in required_headers(e))
                        valid=not p['poisoned'] and complete and caplen>=e.frame_len
                        counts['legacy_valid']+=int(valid)
                        counts['header_missing']+=int(not complete)
                    stream=('tcp:'+row['tcp.stream']) if row.get('tcp.stream') else ('udp:'+row['udp.stream']) if row.get('udp.stream') else None
                    if matches and key is not None and stream:
                        f=flows.setdefault(stream,dict(stream=stream,canonical_key=list(key),first_timestamp=ts,last_timestamp=ts,
                            first_syn_without_ack=bool(e.tcp_syn and not e.tcp_ack) if e.ip_proto==6 else None,
                            packets=0,valid=0,syn=0,fin=0,rst=0,device_indices=set(),proposed_roles=set(),http_requests=0,payload_packets=0))
                        f['last_timestamp']=ts; f['packets']+=1; f['valid']+=int(valid)
                        f['syn']+=int(e.tcp_syn); f['fin']+=int(e.tcp_fin); f['rst']+=int(e.tcp_rst)
                        f['device_indices'].update(matches); f['proposed_roles'].update(roles)
                        f['http_requests']+=int(bool(row.get('http.request.method')))
                        f['payload_packets']+=int(old.number(row.get('tcp.len'))>0 or old.number(row.get('udp.length'))>8)
                    for i in matches:
                        d=devices[i]; d['counts']['packets']+=1; d['protocols'][leaf]+=1
                        if d['first'] is None:d['first']=ts
                        d['last']=ts
                        d['counts']['legacy_gate']+=int(key is not None)
                        d['counts']['legacy_valid_candidates']+=int(valid)
                        d['counts']['retained_prefix_changed_candidates']+=int(valid and retained)
                        d['counts']['cross_role_direct_packets']+=int(len(roles)>1)
                        if valid:
                            d['minutes'].add(int(ts//60));d['dates'].add(utc(ts)[:10])
                        if key is not None:
                            if dm==targets[i]['mac']: d['inbound'][(e.ip_proto,e.dst_port)]+=1
                            if sm==targets[i]['mac']: d['outbound'][(e.ip_proto,e.src_port)]+=1
                        if row.get('http.request.method'):d['http_methods'][row['http.request.method']]+=1
                    if counts['packets']%50000==0:
                        status.update(stage='PROTOCOL_AND_CAUSAL_PREFIX',packets=counts['packets'])
                        dump(RUN/'audit_status.json',status)
                if proc.wait(timeout=30):raise RuntimeError('TShark failed')
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
        for k in ('packets','captured_bytes'):
            if counts[k]!=record['counts'][k]:raise RuntimeError('Independent '+k+' mismatch')
        if (RUN/('%02d_tshark.stderr.log'%index)).stat().st_size:
            raise RuntimeError('TShark diagnostics require review; stop before next file')
        serial=[]
        for i,d in enumerate(devices):
            related=[f for f in flows.values() if i in f['device_indices']]
            serial.append(dict(**d['meta'],counts=dict(d['counts']),observed_transport_streams=len(related),
                candidate_streams=sum(f['valid']>0 for f in related),tcp_streams_with_initial_syn=sum(f['first_syn_without_ack'] is True for f in related),
                valid_utc_dates=sorted(d['dates']),active_candidate_minutes=len(d['minutes']),minute_bins=sorted(d['minutes']),
                first_timestamp=d['first'],last_timestamp=d['last'],protocol_leaf_counts=dict(d['protocols']),
                inbound_services=[dict(protocol=k[0],device_port=k[1],packets=n) for k,n in d['inbound'].most_common()],
                outbound_device_ports=[dict(protocol=k[0],device_port=k[1],packets=n) for k,n in d['outbound'].most_common()],
                http_methods=dict(d['http_methods']),activity_labels_available=False))
        flowrows=[]
        for f in flows.values():
            f['device_indices']=sorted(f['device_indices']);f['proposed_roles']=sorted(f['proposed_roles']);flowrows.append(f)
        dump(RUN/('%02d_flows.json'%index),flowrows)
        result=dict(status='RAW_CHECK_COMPLETE',file=receipt['file'],sha256=receipt['sha256'],bytes=receipt['bytes'],
            integrity=record,counts=dict(counts),protocol_leaf_counts=dict(protocols),devices=serial,
            role_assigned=False,labels_assigned=False,model_features_generated=False,independent_sessions_claimed=False,
            activity_annotation='Active provenance only; individual user activities unknown',
            legacy_prefix_policy='Literal old causal grouping; no IPv6 fallback or model feature generation',
            completed_epoch=time.time())
        dump(RUN/('%02d_summary.json'%index),result)
        status.update(status='RAW_CHECK_COMPLETE',stage='COMPLETE',packets=counts['packets'])
        dump(RUN/'audit_status.json',status)
        print(json.dumps(dict(status=status,devices=[dict(device=d['device'],candidates=d['counts'].get('legacy_valid_candidates',0),streams=d['candidate_streams']) for d in serial]),ensure_ascii=False))
    except BaseException as exc:
        status.update(status='STOPPED_NO_RETRY',reason=type(exc).__name__+': '+str(exc))
        dump(RUN/'audit_status.json',status)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--index',type=int,required=True)
    args=parser.parse_args()
    if args.index not in range(7):raise RuntimeError('Outside named scope')
    audit(args.index)
