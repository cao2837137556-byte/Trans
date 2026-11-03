"""Summarize audited metadata and sealed prior evidence without model access."""
import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import legacy_reference_material_audit_v1 as audit

ROOT = audit.ROOT
OUT = ROOT / 'runs/legacy_reference_material_audit_v1_20260916'
PRIOR_ROOT = audit.PRIOR.parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canon(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def old_evidence(scope):
    seals = dict(line.split('  ', 1)[::-1] for line in (PRIOR_ROOT / 'SHA256SUMS').read_text(encoding='utf-8').splitlines())
    def sealed(relative):
        path = PRIOR_ROOT / relative
        assert audit.source_hash(path) == seals[relative], relative
        return path
    selected = {m['member_path']:m for m in read(sealed('execution/selected_members.json'))}
    candidates = defaultdict(lambda: defaultdict(list))
    with gzip.open(sealed('annotation_candidates.jsonl.gz'),'rt',encoding='utf-8') as fin:
        for line in fin:
            row=json.loads(line)
            candidates[row['member_path']][row['stream']].append(row)
    rows, flows = {}, {}
    for i,spec in enumerate(scope['members'],1):
        if spec['intended_next_action'] != 'REUSE_EXISTING_SEALED_AUDIT':
            continue
        src=selected[spec['member_path']]
        summary=read(sealed('execution/%02d_summary.json' % src['file_id']))
        stream_rows=[]
        for stream in summary['transport_streams']:
            targets=candidates[spec['member_path']][stream['stream_id']]
            key=[6 if stream['stream_id'].startswith('tcp:') else 17]+sorted([[stream['src'],stream['src_port']],[stream['dst'],stream['dst_port']]])
            stream_rows.append({'stream':stream['stream_id'],'canonical_key':key,'first_timestamp':stream['first_timestamp'],
                'last_timestamp':stream['last_timestamp'],'first_frame':stream['first_frame'],'last_frame':stream['last_frame'],
                'packets':stream['packets'],'candidate_targets':len(targets),'candidate_first_time':min((x['timestamp'] for x in targets),default=None),
                'candidate_last_time':max((x['timestamp'] for x in targets),default=None),'first_syn_without_ack':stream['first_syn_without_ack'],
                'protocol':key[0],'source':'REUSED_SEALED_METADATA'})
        independent=summary['independent_capture_check']
        count=summary['counts']
        rows[i]={'file_id':i,'member_path':spec['member_path'],'member_sha256':src['member_sha256'],'device_label':spec['device_label'],
            'provenance':spec['provenance'],'proposed_device_partition':spec['proposed_device_partition'],'role_assigned':None,
            'counts':{'packets':count['packets'],'legacy_valid':count['legacy_gate_headers_complete'],
                'expected_mac_present':sum(summary['roster_mac_packet_counts'].values()),'candidate_targets':sum(len(v) for v in candidates[spec['member_path']].values()),
                'header_missing':count['legacy_gate_headers_missing'],'truncated':count['truncated_packets'],
                'session_regressions':count['session_time_regressions']},
            'independent':{'min_timestamp':independent['first_timestamp'],'max_timestamp':independent['last_timestamp'],
                'counts':{'byte_repeat_packets':independent.get('exact_captured_bytes_repeat',0),'byte_repeat_within_1ms':independent.get('exact_repeat_within_1ms',0)}},
            'transport_streams':len(stream_rows),'candidate_streams':sum(x['candidate_targets']>0 for x in stream_rows),
            'candidate_canonical_sessions':len({canon(x['canonical_key']) for x in stream_rows if x['candidate_targets']}),
            'candidate_stream_cap32':sum(min(32,x['candidate_targets']) for x in stream_rows),'source':'REUSED_SEALED_METADATA',
            'old_file_id':src['file_id'],'ports':[dict(protocol=x['protocol'],src_port=x['src_port'],dst_port=x['dst_port'],direction='unknown_in_prior_summary',packets=x['packets']) for x in summary['directed_endpoint_counts']]}
        flows[i]=stream_rows
    return rows,flows


def main():
    scope=read(audit.DESIGN/'proposed_material_scope.json')
    status=read(OUT/'status.json')
    assert status['status']=='COMPLETE_RAW_AUDIT_REQUIRES_REVIEW'
    rows,flowmap=old_evidence(scope)
    attack_behavior=[]
    for path in sorted(OUT.glob('[0-9][0-9][0-9]_summary.json')):
        summary=read(path)
        i=summary['file_id']
        assert i not in rows
        rows[i]=summary
        # Preserve full files as evidence, but only candidate-bearing streams
        # are needed for prospective counts; avoid retaining millions of SYN
        # background/zero-HTTP-screen rows from all captures simultaneously.
        all_flows=read(OUT/summary['flows_file'])
        flowmap[i]=[f for f in all_flows if f['candidate_targets']>0]
        if summary['provenance']=='attack':
            attack_behavior.append({'file_id':i,'device':summary['device_label'],'member_path':summary['member_path'],
                'directory_mode':summary['member_path'].split('/')[-2],
                'all_transport_streams':len(all_flows),'streams_with_payload':sum(f['payload_packets']>0 for f in all_flows),
                'syn_packets':sum(f['syn'] for f in all_flows),'rst_packets':sum(f['rst'] for f in all_flows),
                'http_requests':sum(f['http_requests'] for f in all_flows),
                'screen_candidates':summary['counts'].get('candidate_targets',0),
                'candidate_streams':summary['candidate_streams']})
        del all_flows
    assert len(rows)==295
    devices=[]
    prospective=defaultdict(Counter)
    memberships=[]
    for device in sorted({x['device_label'] for x in rows.values()}):
        files=[x for x in rows.values() if x['device_label']==device]
        normal=[x for x in files if x['provenance']=='normal']
        attacks=[x for x in files if x['provenance']=='attack']
        eligible=sorted([x for x in normal if x['counts'].get('candidate_targets',0)>0],key=lambda x:(x['independent']['min_timestamp'],x['member_path']))
        refs=eligible[:3]
        refids={x['file_id'] for x in refs}
        cutoff=max((x['independent']['max_timestamp'] for x in refs),default=None)
        reference_flows=[dict(flow,file_id=x['file_id']) for x in refs for flow in flowmap[x['file_id']] if flow['candidate_targets']>0 and flow['last_timestamp']<=cutoff]
        refkeys={canon(f['canonical_key']) for f in reference_flows}
        later_normal=[x for x in normal if x['file_id'] not in refids and cutoff is not None and x['independent']['min_timestamp']>cutoff]
        later_attack=[x for x in attacks if cutoff is not None and x['independent']['min_timestamp']>cutoff]
        # Same tuple is a conservative dependency flag, not proof of a shared session.
        qnormal=[dict(f,file_id=x['file_id']) for x in later_normal for f in flowmap[x['file_id']] if f['candidate_targets']>0]
        qattack=[dict(f,file_id=x['file_id']) for x in later_attack for f in flowmap[x['file_id']] if f['candidate_targets']>0]
        ambiguous=[f for f in qnormal if canon(f['canonical_key']) in refkeys]
        conservative=[f for f in qnormal if canon(f['canonical_key']) not in refkeys]
        activity=lambda x:x['member_path'].split('/')[-2]
        reference_activities=sorted({activity(x) for x in refs})
        query_activities=sorted({activity(x) for x in later_normal if x['counts'].get('candidate_targets',0)})
        modes=defaultdict(Counter)
        for x in attacks:
            mode='Hydra' if '/Hydra/' in x['member_path'] else activity(x)
            modes[mode]['captures']+=1
            modes[mode]['packets']+=x['counts']['packets']
            modes[mode]['screen_candidate_targets']+=x['counts'].get('candidate_targets',0)
            modes[mode]['candidate_streams']+=x['candidate_streams']
            modes[mode]['captures_with_candidates']+=int(x['counts'].get('candidate_targets',0)>0)
        def days(group):
            return sorted({datetime.fromtimestamp(x['independent']['min_timestamp'],timezone.utc).date().isoformat() for x in group})
        def intervals_union_seconds(group):
            intervals=sorted((x['independent']['min_timestamp'],x['independent']['max_timestamp']) for x in group)
            end=None
            total=0.0
            for a,b in intervals:
                total+=max(0,b-max(a,end if end is not None else a))
                end=max(b,end if end is not None else b)
            return total
        row={'device':device,'proposed_partition':files[0]['proposed_device_partition'],
            'normal_captures':len(normal),'normal_packets':sum(x['counts']['packets'] for x in normal),
            'normal_provenance_candidate_targets':sum(x['counts'].get('candidate_targets',0) for x in normal),
            'normal_candidate_streams':sum(x['candidate_streams'] for x in normal),
            'normal_capture_seconds_sum':sum(x['independent']['max_timestamp']-x['independent']['min_timestamp'] for x in normal),
            'normal_capture_seconds_union':intervals_union_seconds(normal),
            'normal_utc_dates':days(normal),'attack_utc_dates':days(attacks),
            'normal_captures_with_candidates':sum(x['candidate_streams']>0 for x in normal),
            'normal_captures_missing_expected_mac':[x['file_id'] for x in normal if not x['counts'].get('expected_mac_present',0)],
            'attack_captures_missing_expected_mac':[x['file_id'] for x in attacks if not x['counts'].get('expected_mac_present',0)],
            'normal_activity_labels':sorted({activity(x) for x in normal}),
            'attack_captures':len(attacks),'attack_packets':sum(x['counts']['packets'] for x in attacks),
            'attack_screen_candidate_targets':sum(x['counts'].get('candidate_targets',0) for x in attacks),
            'attack_screen_candidate_streams':sum(x['candidate_streams'] for x in attacks),
            'attack_modes':dict(modes),'reference_capture_ids':sorted(refids),'reference_cutoff':cutoff,
            'reference_candidate_targets':sum(f['candidate_targets'] for f in reference_flows),
            'reference_streams':len(reference_flows),'reference_canonical_keys':len(refkeys),'reference_budget_actual_upper':min(64,len(refkeys)),
            'reference_activities':reference_activities,'later_normal_captures':len(later_normal),
            'reference_seconds_sum':sum(x['independent']['max_timestamp']-x['independent']['min_timestamp'] for x in refs),
            'later_normal_seconds_sum':sum(x['independent']['max_timestamp']-x['independent']['min_timestamp'] for x in later_normal),
            'later_normal_utc_dates':days(later_normal),
            'later_normal_captures_with_candidates':sum(x['candidate_streams']>0 for x in later_normal),
            'later_normal_unique_canonical_keys':len({canon(f['canonical_key']) for f in qnormal}),
            'later_normal_candidate_targets':sum(f['candidate_targets'] for f in qnormal),
            'later_normal_candidate_streams':len(qnormal),'later_normal_cap32_stream_upper':sum(min(32,f['candidate_targets']) for f in qnormal),
            'reference_query_same_tuple_streams':len(ambiguous),'reference_query_same_tuple_targets':sum(f['candidate_targets'] for f in ambiguous),
            'conservative_normal_query_targets':sum(f['candidate_targets'] for f in conservative),
            'conservative_normal_query_streams':len(conservative),
            'conservative_normal_unique_canonical_keys':len({canon(f['canonical_key']) for f in conservative}),
            'conservative_normal_cap32_stream_upper':sum(min(32,f['candidate_targets']) for f in conservative),
            'normal_query_activities':query_activities,'normal_query_novel_activities':sorted(set(query_activities)-set(reference_activities)),
            'later_attack_captures':len(later_attack),'later_attack_screen_targets':sum(f['candidate_targets'] for f in qattack),
            'later_attack_captures_with_candidates':sum(x['candidate_streams']>0 for x in later_attack),
            'reference_attack_same_tuple_streams':sum(canon(f['canonical_key']) in refkeys for f in qattack),
            'later_attack_candidate_streams':len(qattack),'later_attack_cap32_stream_upper':sum(min(32,f['candidate_targets']) for f in qattack),
            'identity_expected_mac_missing_packets':sum(x['counts']['packets']-x['counts'].get('expected_mac_present',0) for x in files),
            'prefix_regressions':sum(x['counts'].get('session_regressions',0) for x in files),
            'header_missing':sum(x['counts'].get('header_missing',0) for x in files),
            'truncated_packets':sum(x['counts'].get('truncated',0) for x in files),
            'qualified_independent_units':None,'training_ready':False}
        devices.append(row)
        aggregate=prospective[row['proposed_partition']]
        aggregate['devices']+=1
        for key in ['normal_captures','normal_provenance_candidate_targets','normal_candidate_streams','normal_capture_seconds_sum','attack_captures','attack_screen_candidate_targets','reference_streams','reference_budget_actual_upper','reference_candidate_targets','later_normal_captures','later_normal_candidate_targets','later_normal_candidate_streams','later_normal_unique_canonical_keys','later_normal_cap32_stream_upper','conservative_normal_query_targets','conservative_normal_query_streams','conservative_normal_unique_canonical_keys','conservative_normal_cap32_stream_upper','later_attack_captures','later_attack_captures_with_candidates','later_attack_screen_targets','later_attack_candidate_streams','later_attack_cap32_stream_upper']:
            aggregate[key]+=row[key]
        for x in files:
            kind='REFERENCE' if x['file_id'] in refids else ('LATER_NORMAL_QUERY' if x in later_normal else ('LATER_ATTACK_QUERY' if x in later_attack else 'NOT_TIME_ELIGIBLE'))
            memberships.append({'file_id':x['file_id'],'device':device,'member_path':x['member_path'],'prospective_use':kind,'not_a_frozen_role':True})
    groups=defaultdict(list)
    for r in rows.values():groups[r['member_sha256']].append(r['file_id'])
    duplicate_files=[v for v in groups.values() if len(v)>1]
    # Observed same raw bytes across new normal captures, without labeling all
    # identical payload/frames as leakage when they occur at different times.
    fingerprint_index=defaultdict(list)
    for path in sorted(OUT.glob('*_normal_fingerprints.json')):
        i=int(path.name.split('_')[0])
        for f in read(path):fingerprint_index[f['sha256']].append((i,f['first_timestamp'],f['first_frame']))
    cross=[]
    for fp,observations in fingerprint_index.items():
        if len(observations)>1:
            temporal=any(a[0]!=b[0] and abs(a[1]-b[1])<=.001 for k,a in enumerate(observations) for b in observations[k+1:])
            cross.append({'sha256':fp,'observations':observations,'within_1ms_cross_capture':temporal})
    totals=Counter()
    for r in rows.values():
        totals['packets']+=r['counts']['packets']
        totals['legacy_valid']+=r['counts'].get('legacy_valid',0)
        totals['candidate_targets']+=r['counts'].get('candidate_targets',0)
        totals['raw_exact_repeats']+=r['independent']['counts'].get('byte_repeat_packets',0)
    result={'status':'RAW_REVIEW_COMPLETE_MATERIAL_ADEQUACY_REQUIRES_SCIENTIFIC_DECISION','scope_files':295,'new_decoded':277,'old_reused':18,
        'totals':dict(totals),'devices':devices,'prospective_partition_totals':{k:dict(v) for k,v in prospective.items()},
        'duplicate_capture_groups':duplicate_files,'cross_new_normal_exact_byte_groups':len(cross),
        'cross_new_normal_same_time_groups':sum(x['within_1ms_cross_capture'] for x in cross),
        'limitations':['All target quantities precede final label review and dependency deduplication.',
            'Flood counts are deliberately directional screens, not wholesale assigned positives.',
            'Same tuple across captures is conservative dependency ambiguity, not proof of one ongoing session.',
            'Cross-capture raw-byte comparison covers new normals; old eighteen use sealed metadata, no raw reread.',
            'Fingerprint timing compares the first occurrence per exact frame per file; it is not an exhaustive comparison of all repeated timestamps.',
            'Stream count and cap32 are not independent sample counts.',
            'Reference budget is an upper bound from observed captures; last observed packet is not proof of true session termination.',
            'UTC date and interval duration describe capture coverage, not independent days or continuous monitoring.',
            'Prior exact-byte repeat fields unavailable in old summaries contribute zero to tally, not a claim of zero duplicates.',
            'No model scores, training, parameter selection or new downloads.']}
    audit.dump(OUT/'review_summary.json',result)
    audit.dump(OUT/'prospective_time_membership.json',memberships)
    audit.dump(OUT/'cross_normal_fingerprints.json',cross)
    audit.dump(OUT/'reused_and_new_file_metadata.json',list(sorted(rows.values(),key=lambda r:r['file_id'])))
    audit.dump(OUT/'new_attack_observed_behavior.json',attack_behavior)
    services=[]
    for device in sorted({x['device_label'] for x in rows.values()}):
        counts={'normal':Counter(),'attack':Counter()}
        files=[x for x in rows.values() if x['device_label']==device and x.get('source')!='REUSED_SEALED_METADATA']
        for x in files:
            for port in x['ports']:
                if port['direction']=='inbound':
                    counts[x['provenance']][(port['protocol'],port['dst_port'])]+=port['packets']
        services.append({'device':device,'new_normal_captures':sum(x['provenance']=='normal' for x in files),
            'new_attack_captures':sum(x['provenance']=='attack' for x in files),
            'normal_inbound_protocol_and_device_port':[{'protocol':k[0],'device_port':k[1],'packets':v} for k,v in counts['normal'].most_common()],
            'attack_inbound_protocol_and_device_port':[{'protocol':k[0],'device_port':k[1],'packets':v} for k,v in counts['attack'].most_common()],
            'shared_protocol_device_port':sorted(set(counts['normal'])&set(counts['attack'])),
            'interpretation':'Header-gate inbound observations, not assigned labels or model predictions; old18 are outside this direction comparison.'})
    audit.dump(OUT/'new_normal_attack_service_overlap.json',services)
    print(json.dumps({'totals':dict(totals),'prospective_partitions':result['prospective_partition_totals'],'duplicate_files':duplicate_files,'cross_time_groups':result['cross_new_normal_same_time_groups']},ensure_ascii=False))


if __name__=='__main__':
    main()
