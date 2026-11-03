"""Merge sealed old audits with two new audits, preserving exact device attribution."""
import json
import shutil
import sqlite3
import struct
from collections import Counter,defaultdict

import legacy_reference_material_review_v1 as legacy
import legacy_normal_supplement_audit_v1 as audit
from legacy_normal_supplement_resume_v2 import ROOT,RUN,PRIOR,dump
from legacy_reference_context_scope_v1 import SHARED_DHCP_KEY


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def canon(v):return json.dumps(v,separators=(',',':'),sort_keys=True)


def attribution_bounds(flows,owner_index,exact_total,keep):
    """Every flow-wide count is a capacity, never copied to all its owners."""
    relevant=[f for f in flows if owner_index in f['device_indices'] and f['valid']>0]
    single=[f for f in relevant if len(f['device_indices'])==1]
    mixed=[f for f in relevant if len(f['device_indices'])>1]
    residual=exact_total-sum(f['valid'] for f in single)
    capacity=sum(f['valid'] for f in mixed)
    if not 0<=residual<=capacity:raise RuntimeError('Device/flow conservation failed')
    fixed=sum(f['valid'] for f in single if keep(f))
    kept=sum(f['valid'] for f in mixed if keep(f))
    dropped=sum(f['valid'] for f in mixed if not keep(f))
    lower=fixed+max(0,residual-dropped)
    upper=fixed+min(residual,kept)
    assert 0<=lower<=upper<=exact_total
    return dict(lower=lower,upper=upper,exact=lower==upper,
                device_candidates_in_mixed_streams=residual,mixed_stream_records=len(mixed))


def main():
    if (RUN/'combined_review.json').exists():raise RuntimeError('Review output already exists')
    sources=[PRIOR]*5
    for i in (5,6):
        if (RUN/('%02d_summary.json'%i)).exists():sources.append(RUN)
        else:break
    summaries=[read(src/('%02d_summary.json'%i)) for i,src in enumerate(sources)]
    flowdays=[read(src/('%02d_flows.json'%i)) for i,src in enumerate(sources)]
    flows=[dict(f,file_index=i) for i,fs in enumerate(flowdays) for f in fs]
    oldreview=read(audit.PRIOR/'review_summary.json')
    oldmetadata=read(audit.PRIOR/'reused_and_new_file_metadata.json')
    scope=read(ROOT/'runs/legacy_reference_conditioned_joint_design_v1_20260916/proposed_material_scope.json')
    _,reused=legacy.old_evidence(scope)
    rolekeys=defaultdict(set)
    for f in flows:rolekeys[canon(f['canonical_key'])].update(f['proposed_roles'])
    conflicts={k for k,roles in rolekeys.items() if len(roles)>1}
    dhcp=canon(SHARED_DHCP_KEY)
    rows=[];partitions=defaultdict(Counter)
    for i,old in enumerate(oldreview['devices']):
        name=old['device'];ref=set()
        for fid in old['reference_capture_ids']:
            ff=reused[fid] if fid in reused else read(audit.PRIOR/('%03d_flows.json'%fid))
            ref.update(canon(f['canonical_key']) for f in ff if f['candidate_targets']>0)
        daily=[s['devices'][i] for s in summaries]
        if any(d['device']!=name for d in daily):raise RuntimeError('Roster order mismatch')
        counts=Counter();dates=set();minutes=set();inbound=Counter();outbound=Counter()
        for d in daily:
            counts.update(d['counts']);dates.update(d['valid_utc_dates']);minutes.update(d['minute_bins'])
            for p in d['inbound_services']:inbound[(p['protocol'],p['device_port'])]+=p['packets']
            for p in d['outbound_device_ports']:outbound[(p['protocol'],p['device_port'])]+=p['packets']
        total=counts['legacy_valid_candidates']
        allbounds=attribution_bounds(flows,i,total,lambda f:True)
        dhcpbounds=attribution_bounds(flows,i,total,lambda f:canon(f['canonical_key'])!=dhcp)
        refbounds=attribution_bounds(flows,i,total,lambda f:canon(f['canonical_key']) not in ref)
        both=attribution_bounds(flows,i,total,lambda f:canon(f['canonical_key']) not in ref and canon(f['canonical_key'])!=dhcp)
        assert allbounds['lower']==allbounds['upper']==total
        attacks=Counter()
        for m in oldmetadata:
            if m['device_label']==name and m['provenance']=='attack':
                for p in m['ports']:
                    if p['direction']=='inbound':attacks[(p['protocol'],p['dst_port'])]+=p['packets']
        owned=[f for f in flows if i in f['device_indices'] and f['valid']>0]
        one=[f for f in owned if len(f['device_indices'])==1]
        mixed=[f for f in owned if len(f['device_indices'])>1]
        stream_low=len(one)+int(allbounds['device_candidates_in_mixed_streams']>0)
        stream_high=len(one)+min(len(mixed),allbounds['device_candidates_in_mixed_streams'])
        row=dict(device=name,proposed_partition=old['proposed_partition'],mac=daily[0]['mac'],counts=dict(counts),
            valid_dates=sorted(dates),valid_date_count=len(dates),active_minutes=len(minutes),
            candidate_streams_lower=stream_low,candidate_streams_upper=stream_high,
            after_prospective_dhcp_filter=dhcpbounds,after_conservative_reference_tuple_filter=refbounds,
            after_both_filters=both,all_capture_times_after_old_reference=all(s['integrity']['minimum_timestamp']>old['reference_cutoff'] for s in summaries),
            all_capture_dates_before_attack=all(s['integrity']['last_utc'][:10]<min(old['attack_utc_dates']) for s in summaries),
            normal_inbound_services=[dict(protocol=k[0],device_port=k[1],packets=v) for k,v in inbound.most_common()],
            normal_outbound_device_ports=[dict(protocol=k[0],device_port=k[1],packets=v) for k,v in outbound.most_common()],
            comparable_attack_inbound_services=[dict(protocol=k[0],device_port=k[1],packets=v) for k,v in attacks.most_common()],
            shared_inbound_services=sorted(set(inbound)&set(attacks)),activity_annotations_available=False,
            qualified_independent_units=None,daily=[dict(file=s['file'],candidates=d['counts'].get('legacy_valid_candidates',0),
                streams_upper=d['candidate_streams'],active_minutes=d['active_candidate_minutes']) for s,d in zip(summaries,daily)])
        rows.append(row)
        agg=partitions[row['proposed_partition']];agg['devices']+=1;agg['candidates']+=total
        agg['after_dhcp_lower']+=dhcpbounds['lower'];agg['after_dhcp_upper']+=dhcpbounds['upper']
    # Extend a COPY of the sealed fingerprint index, never mutate its original.
    db=RUN/'combined_fingerprint_index.sqlite'
    if db.exists():raise RuntimeError('Combined fingerprint index already exists')
    original=PRIOR/'normal_fingerprint_index.sqlite'
    oldseals={n:h for h,n in (line.split('  ',1) for line in (PRIOR/'SHA256SUMS').read_text().splitlines())}
    if audit.old.sha(original)!=oldseals[original.name]:raise RuntimeError('Old fingerprint seal changed')
    shutil.copyfile(original,db);conn=sqlite3.connect(str(db))
    for i in range(5,len(sources)):
        with (RUN/('%02d_fingerprints.bin'%i)).open('rb') as fin:
            while True:
                chunk=fin.read(42*30000)
                if not chunk:break
                if len(chunk)%42:raise RuntimeError('Fingerprint record truncation')
                conn.executemany('INSERT INTO fingerprints VALUES (?,?,?,1) ON CONFLICT(hash) DO UPDATE SET files=files|excluded.files,devices=devices|excluded.devices,n=n+1',
                    ((digest,1<<i,mask) for digest,ts,mask in struct.iter_unpack('<32sqH',chunk)))
            conn.commit()
    fp=dict(unique_hashes=conn.execute('SELECT count(*) FROM fingerprints').fetchone()[0],
        cross_file_byte_groups=conn.execute('SELECT count(*) FROM fingerprints WHERE files & (files-1) !=0').fetchone()[0],
        shared_prior_normal_byte_groups=conn.execute('SELECT count(*) FROM fingerprints JOIN prior_normal USING(hash)').fetchone()[0])
    masks=conn.execute('SELECT devices,count(*) FROM fingerprints GROUP BY devices').fetchall();conn.close()
    fp['cross_role_byte_groups']=sum(n for mask,n in masks if len({d['proposed_partition'] for i,d in enumerate(rows) if mask & (1<<i)})>1)
    intervals=[(s['integrity']['minimum_timestamp'],s['integrity']['maximum_timestamp']) for s in summaries]
    fp['new_file_intervals_disjoint']=all(a[1]<b[0] or b[1]<a[0] for i,a in enumerate(intervals) for b in intervals[i+1:])
    totals=Counter()
    for s in summaries:totals.update(s['counts'])
    conflictrows=[dict(canonical_key=json.loads(k),roles=sorted(rolekeys[k]),stream_records=[f for f in flows if canon(f['canonical_key'])==k]) for k in sorted(conflicts)]
    dump(RUN/'cross_role_contexts.json',conflictrows)
    result=dict(status='SEVEN_FILE_RAW_REVIEW_COMPLETE' if len(sources)==7 else 'PARTIAL_STOPPED_REVIEW',
        files=len(sources),old_raw_audits_reused=5,new_raw_audits=len(sources)-5,
        complete_file_bytes=sum(s['bytes'] for s in summaries),capture_hours=sum(b-a for a,b in intervals)/3600,
        exact_device_candidates=sum(d['counts']['legacy_valid_candidates'] for d in rows),totals=dict(totals),devices=rows,
        proposed_partition_totals={k:dict(v) for k,v in partitions.items()},fingerprint_checks=fp,
        cross_role_canonical_key_count=len(conflicts),context_policy_applied_to_real_features=False,
        normal_activity_annotations=False,training_started=False,
        source_receipts=[dict(index=i,source_run=str(src.relative_to(ROOT)),file=s['file'],bytes=s['bytes'],sha256=s['sha256']) for i,(src,s) in enumerate(zip(sources,summaries))],
        limitations=['No independent-unit or sufficient-data certification from packet counts.',
            'Bounds conservatively assign mixed-device flow capacities; never copy the full flow count to each owner.',
            'Counts after DHCP/reference filters are prospective metadata calculations, not materialized model rows.',
            'Same-service comparison uses known directional attack metadata; older reused18 direction differs.',
            'Reference-conditioned comparisons can test limited development utility; absent service/vantage controls prevent a claim of eliminating those shortcuts.'])
    dump(RUN/'combined_review.json',result)
    print(json.dumps({k:result[k] for k in ['status','files','complete_file_bytes','capture_hours','exact_device_candidates','cross_role_canonical_key_count']},ensure_ascii=False))


if __name__=='__main__':main()
