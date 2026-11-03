"""Independent readback of the new sample manifests and finite resource recipe."""
from collections import Counter,defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

import legacy_reference_sample_prepare_v1 as prep

ROOT=prep.ROOT
RUN=ROOT/'runs/legacy_reference_sample_preparation_v1_20260917'


def main():
    out=RUN/'finalized';verification=RUN/'independent_verification.json'
    if verification.exists():raise RuntimeError('Refuse overwrite verification')
    for line in (out/'SHA256SUMS').read_text().splitlines():
        h,name=line.split('  ',1)
        if prep.old.sha(out/name)!=h:raise RuntimeError('Finalized seal mismatch')
    index=prep.load(out/'manifest_index.json');recipe=prep.load(out/'recipe.json');summary=prep.load(out/'denominators.json')
    catalog={s['capture_id']:s for s in prep.load(RUN/'capture_catalog.json')}
    devices={d['device']:d for d in prep.load(RUN/'devices.json')}
    all_uids=set();event_keys=set();partition_counts={};by_device=defaultdict(Counter);ref_components=defaultdict(set)
    total_rows=0;checks=Counter();reference_by_uid={};reference_activities=defaultdict(set)
    for role,meta in index.items():
        if prep.old.sha(ROOT/meta['path'])!=meta['sha256']:raise RuntimeError('Manifest SHA mismatch')
        uids=[];mass=[[],[]]
        with gzip.open(ROOT/meta['path'],'rt',encoding='utf8') as f:
            for line in f:
                row=json.loads(line);s=catalog[row['capture_id']];d=devices[row['device']]
                if row['source_sha256']!=s['sha256'] or row['owner']!=d['mac'] or row['partition']!=d['proposed_partition']:
                    raise RuntimeError('Source/device join mismatch')
                if role!='REFERENCE' and row['partition']!=role:raise RuntimeError('Partition mismatch')
                if not 1<=row['frame']<=s['expected_packets']:raise RuntimeError('Frame outside capture')
                if row['uid']!=prep.digest([s['sha256'],row['frame'],d['mac']]):raise RuntimeError('UID formula mismatch')
                if row['session_id']!=prep.digest([d['mac'],s['capture_id'],row['canonical_key']]):raise RuntimeError('Context identity mismatch')
                if row['component_id']!=prep.digest([d['mac'],row['canonical_key']]):raise RuntimeError('Dependency identity mismatch')
                if row['uid'] in all_uids:raise RuntimeError('Duplicate UID across materialized sets')
                all_uids.add(row['uid']);uids.append(row['uid'])
                event=(row['packet_sha256'],round(row['timestamp']*1e6))
                if event in event_keys:raise RuntimeError('Duplicate packet/time in finalized set')
                event_keys.add(event)
                if row['label']!=int(s['provenance']=='attack'):raise RuntimeError('Source label mismatch')
                if s['skip_reason']:raise RuntimeError('Excluded HTTP capture in manifest')
                if row['candidate_rank'] not in prep.even_indices(row['candidate_count'],1 if role=='REFERENCE' else prep.CAP):
                    raise RuntimeError('Systematic rank selection mismatch')
                if role=='REFERENCE':
                    if row['use']!='REFERENCE' or row['label']!=0 or row['timestamp']>d['reference_end']:raise RuntimeError('Reference scope mismatch')
                    if row['component_id'] in ref_components[row['device']]:raise RuntimeError('Reference component duplicated')
                    ref_components[row['device']].add(row['component_id'])
                    reference_by_uid[row['uid']]=row
                    reference_activities[row['device']].add(row['activity'])
                else:
                    if row['timestamp']<=d['reference_end'] or row['use']=='REFERENCE':raise RuntimeError('Temporal leakage')
                    activity='attack' if row['label'] else 'unannotated_active' if row['activity']=='ACTIVE_UNANNOTATED' else 'reference_covered' if row['activity'] in reference_activities[row['device']] else 'reference_not_covered'
                    dependency='same_canonical_component' if row['component_id'] in ref_components[row['device']] else 'different_canonical_component'
                    if activity!=row['normal_activity_stratum'] or dependency!=row['reference_dependency_stratum']:raise RuntimeError('Reference coverage stratum mismatch')
                    mass[row['label']].append(1/row['label_metric_weight_denominator'])
                    by_device[row['device']][row['label']]+=1
                checks['exact_UID_scope_label_time_verified']+=1
        if len(uids)!=meta['rows'] or hashlib.sha256(''.join(x+'\n' for x in sorted(uids)).encode()).hexdigest()!=meta['sorted_uid_lines_sha256']:
            raise RuntimeError('Manifest denominator or UID seal mismatch')
        if role!='REFERENCE' and any(not math.isclose(math.fsum(x),1,abs_tol=1e-12) for x in mass):raise RuntimeError('Weight sums not1')
        total_rows+=len(uids);partition_counts[role]=len(uids)
    if set(ref_components)!=set(devices) or any(not 1<=len(x)<=64 for x in ref_components.values()):raise RuntimeError('Reference availability/budget mismatch')
    for control in prep.load(out/'reference_interventions.json'):
        if control['status']!='DEFINED':continue
        correct=[reference_by_uid[u] for u in control['correct_reference_uids']]
        wrong=[reference_by_uid[u] for u in control['wrong_reference_uids']]
        if len(correct)!=len(wrong) or len(correct)!=control['equal_count']:raise RuntimeError('Unequal intervention reference budget')
        if Counter(r['protocol'] for r in correct)!=Counter(r['protocol'] for r in wrong):raise RuntimeError('Unmatched intervention protocol multiset')
        if any(r['device']!=control['device'] for r in correct) or any(r['device']!=control['donor'] for r in wrong):raise RuntimeError('Control owner drift')
        if any(r['partition']!=control['partition'] for r in correct+wrong):raise RuntimeError('Cross-partition control references')
        checks['equal_budget_protocol_controls_verified']+=1
    for d in summary['devices']:
        if by_device[d['device']][0]!=d['normal'] or by_device[d['device']][1]!=d['attack']:raise RuntimeError('Summary denominator drift')
    if recipe['runtime']['exact_new_feature_rows']!=total_rows or recipe['optimization']['updates_per_model']!=40*math.ceil(index['LEARN']['rows']/256):
        raise RuntimeError('Resource/optimizer denominator drift')
    active_candidates=Counter();active_regressions=0
    for cid,s in catalog.items():
        receipt=prep.load(RUN/'captures'/(cid+'_receipt.json'))
        if not receipt['raw_identity_verified']:raise RuntimeError('Raw receipt absent')
        if not s['skip_reason'] and receipt['counts']['packets']!=s['expected_packets']:raise RuntimeError('Raw count conservation failed')
        if cid.startswith('active-'):
            active_candidates.update(receipt['per_owner_candidates']);active_regressions+=receipt['context_reasons'].get('NEW_TIMESTAMP_REGRESSION',0)
    # Independently compare the earlier metadata estimate with actual guarded
    # candidate membership. Any difference must be disclosed, never patched.
    expected=1788610
    actual=sum(active_candidates.values())
    status=dict(status='PASS',manifest_rows=total_rows,partition_counts=partition_counts,checks=dict(checks),
        guarded_active_candidates=actual,prior_dhcp_only_estimate=expected,estimate_matches_actual=(actual==expected),
        guarded_active_candidates_by_owner=dict(active_candidates),active_prefix_regressions=active_regressions,
        contexts_not_features=True,no_models_or_new_scores=True,completed_epoch=time.time())
    prep.dump(verification,status)
    print(json.dumps(status,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
