"""Aggregate new raw audit metadata and sealed prior evidence; no raw re-decode."""
import json
import sqlite3
import struct
import time
from collections import Counter, defaultdict
from pathlib import Path

import legacy_normal_supplement_audit_v1 as audit
import legacy_reference_material_review_v1 as prior_review
from legacy_normal_supplement_acquire_v1 import ROOT, RUN, dump


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def key(v):return json.dumps(v,separators=(',',':'),sort_keys=True)


def main():
    summaries=[read(p) for p in sorted(RUN.glob('[0-9][0-9]_summary.json'))]
    if not summaries:raise RuntimeError('No completed raw summaries')
    prior=read(audit.PRIOR/'review_summary.json')
    metadata=read(audit.PRIOR/'reused_and_new_file_metadata.json')
    scope=read(ROOT/'runs/legacy_reference_conditioned_joint_design_v1_20260916/proposed_material_scope.json')
    _,reused=prior_review.old_evidence(scope)
    targetmeta=audit.roster()
    refs={}
    for device in prior['devices']:
        k=set()
        for fid in device['reference_capture_ids']:
            flows=reused[fid] if fid in reused else read(audit.PRIOR/('%03d_flows.json'%fid))
            k.update(key(f['canonical_key']) for f in flows if f['candidate_targets']>0)
        assert len(k)==device['reference_canonical_keys']
        refs[device['device']]=k
    flowdays=[read(RUN/('%02d_flows.json'%i)) for i in range(len(summaries))]
    allkeyroles=defaultdict(set)
    for flows in flowdays:
        for f in flows:allkeyroles[key(f['canonical_key'])].update(f['proposed_roles'])
    devices=[];partitions=defaultdict(Counter)
    for i,meta in enumerate(targetmeta):
        name=meta['device']; old=next(x for x in prior['devices'] if x['device']==name)
        daily=[s['devices'][i] for s in summaries]
        assert all(d['device']==name and d['mac']==meta['mac'] for d in daily)
        counts=Counter();normalservices=Counter();protocols=Counter();dates=set();minutes=set()
        for d in daily:
            counts.update(d['counts']);protocols.update(d['protocol_leaf_counts'])
            dates.update(d['valid_utc_dates']);minutes.update(d['minute_bins'])
            for p in d['inbound_services']:normalservices[(p['protocol'],p['device_port'])]+=p['packets']
        observed=[f for flows in flowdays for f in flows if i in f['device_indices'] and f['valid']>0]
        ambiguous=[f for f in observed if key(f['canonical_key']) in refs[name]]
        conservative=[f for f in observed if key(f['canonical_key']) not in refs[name]]
        attackservices=Counter()
        for m in metadata:
            if m['device_label']==name and m['provenance']=='attack':
                for p in m['ports']:
                    if p['direction']=='inbound':attackservices[(p['protocol'],p['dst_port'])]+=p['packets']
        row=dict(**meta,counts=dict(counts),valid_dates=sorted(dates),valid_date_count=len(dates),
            active_candidate_minutes=len(minutes),candidate_streams=sum(x['candidate_streams'] for x in daily),
            tcp_streams_with_initial_syn=sum(x['tcp_streams_with_initial_syn'] for x in daily),
            distinct_canonical_keys=len({key(f['canonical_key']) for f in observed}),
            candidate_streams_reusing_old_reference_tuple=len(ambiguous),
            candidate_targets_in_reference_tuple_streams=sum(f['valid'] for f in ambiguous),
            conservative_tuple_excluded_candidate_targets=sum(f['valid'] for f in conservative),
            conservative_tuple_excluded_streams=len(conservative),
            conservative_cap32_per_stream_upper=sum(min(32,f['valid']) for f in conservative),
            candidate_streams_with_cross_role_canonical_key=sum(len(allkeyroles[key(f['canonical_key'])])>1 for f in observed),
            all_new_capture_times_after_old_reference=all(s['integrity']['minimum_timestamp']>old['reference_cutoff'] for s in summaries),
            all_new_capture_times_before_device_attack=all(s['integrity']['last_utc'][:10]<meta['earliest_attack_date'] for s in summaries),
            inbound_normal_services=[dict(protocol=k[0],device_port=k[1],packets=v) for k,v in normalservices.most_common()],
            prior_new_attack_inbound_services=[dict(protocol=k[0],device_port=k[1],packets=v) for k,v in attackservices.most_common()],
            shared_protocol_device_port=sorted(set(normalservices)&set(attackservices)),
            protocol_leaf_counts=dict(protocols),activities_verified=False,qualified_independent_units=None,
            daily=[dict(file=s['file'],candidates=d['counts'].get('legacy_valid_candidates',0),streams=d['candidate_streams'],
                        minutes=d['active_candidate_minutes']) for s,d in zip(summaries,daily)])
        devices.append(row)
        agg=partitions[meta['proposed_partition']]
        agg['devices']+=1;agg['candidate_targets']+=counts['legacy_valid_candidates']
        for field in ['candidate_streams','conservative_tuple_excluded_candidate_targets','conservative_tuple_excluded_streams']:
            agg[field]+=row[field]
    # Bounded on-disk hash index: packet content hashes only, no raw payload.
    dbpath=RUN/'normal_fingerprint_index.sqlite'
    if dbpath.exists():raise RuntimeError('Do not overwrite previous review index')
    conn=sqlite3.connect(str(dbpath))
    conn.execute('CREATE TABLE fingerprints (hash BLOB PRIMARY KEY, files INTEGER, devices INTEGER, n INTEGER) WITHOUT ROWID')
    conn.execute('CREATE TABLE prior_normal (hash BLOB PRIMARY KEY) WITHOUT ROWID')
    for i in range(len(summaries)):
        with (RUN/('%02d_fingerprints.bin'%i)).open('rb') as fin:
            while True:
                chunk=fin.read(42*30000)
                if not chunk:break
                assert len(chunk)%42==0
                conn.executemany('INSERT INTO fingerprints VALUES (?,?,?,1) ON CONFLICT(hash) DO UPDATE SET files=files|excluded.files,devices=devices|excluded.devices,n=n+1',
                    ((digest,1<<i,mask) for digest,ts,mask in struct.iter_unpack('<32sqH',chunk)))
            conn.commit()
    prior_files=0
    for p in sorted(audit.PRIOR.glob('*_normal_fingerprints.json')):
        records=read(p);prior_files+=1
        conn.executemany('INSERT OR IGNORE INTO prior_normal VALUES (?)',((bytes.fromhex(r['sha256']),) for r in records))
    conn.commit()
    n_unique=conn.execute('SELECT count(*) FROM fingerprints').fetchone()[0]
    repeated=conn.execute('SELECT count(*),COALESCE(sum(n),0) FROM fingerprints WHERE (files & (files-1)) != 0').fetchone()
    masks=conn.execute('SELECT devices,count(*) FROM fingerprints GROUP BY devices').fetchall()
    cross_role_hashes=sum(n for mask,n in masks if len({m['proposed_partition'] for i,m in enumerate(targetmeta) if mask&(1<<i)})>1)
    shared_prior=conn.execute('SELECT count(*) FROM fingerprints JOIN prior_normal USING(hash)').fetchone()[0]
    conn.close()
    intervals=[(s['integrity']['minimum_timestamp'],s['integrity']['maximum_timestamp']) for s in summaries]
    disjoint=all(a[1]<b[0] or b[1]<a[0] for i,a in enumerate(intervals) for b in intervals[i+1:])
    prior_normal=[m for m in metadata if m['provenance']=='normal']
    disjoint_prior=all(a[1]<m['independent']['min_timestamp'] or m['independent']['max_timestamp']<a[0] for a in intervals for m in prior_normal)
    totals=Counter()
    for s in summaries:totals.update(s['counts'])
    result=dict(status='COMPLETE' if len(summaries)==7 else 'PARTIAL_STOPPED',reviewed_files=len(summaries),
        source_raw_bytes=sum(s['bytes'] for s in summaries),capture_hours_sum=sum(b-a for a,b in intervals)/3600,
        totals=dict(totals),devices=devices,proposed_partition_totals={k:dict(v) for k,v in partitions.items()},
        normal_fingerprints=dict(unique_packet_byte_hashes=n_unique,cross_day_byte_hash_groups=repeated[0],
            records_in_cross_day_byte_hash_groups=repeated[1],cross_proposed_role_byte_hash_groups=cross_role_hashes,
            prior_new_normal_fingerprint_files_compared=prior_files,shared_prior_normal_byte_hashes=shared_prior,
            all_new_file_time_intervals_disjoint=disjoint,all_new_vs_prior_normal_intervals_disjoint=disjoint_prior,
            exact_same_time_cross_capture_records=0 if disjoint and disjoint_prior else None,
            old18_fingerprint_coverage='Not redecoded; no exhaustive old18 byte-hash comparison'),
        legacy_reference_recipe_changed=False,roles_frozen=False,labels_assigned=False,training_started=False,
        limitations=['Candidate counts are not final labels, independent examples or model predictions.',
            'Same five-tuple across dates is dependency ambiguity, not proof of same connection or leakage.',
            'Cross-role canonical keys flag potential context sharing; no role assignments are materialized.',
            'Stream/cap32 counts are descriptive sensitivity summaries, not frozen sampling rules.',
            'Active has no per-packet activity annotation; more dates do not establish diverse activities.',
            'Shared service comparison uses directional prior NEW attack audit; reused18 lack comparable direction metadata.',
            'Byte identity on disjoint dates can be periodic repeat traffic, not duplicated observations.',
            'Seven dates belong to one network environment; no independent deployment replication is claimed.'],
        completed_epoch=time.time())
    dump(RUN/'review_summary.json',result)
    print(json.dumps(dict(status=result['status'],bytes=result['source_raw_bytes'],hours=result['capture_hours_sum'],
        devices=[{k:d[k] for k in ['device','valid_date_count','candidate_streams','conservative_tuple_excluded_candidate_targets','shared_protocol_device_port']}|{'candidates':d['counts'].get('legacy_valid_candidates',0)} for d in devices]),ensure_ascii=False))


if __name__=='__main__':main()
