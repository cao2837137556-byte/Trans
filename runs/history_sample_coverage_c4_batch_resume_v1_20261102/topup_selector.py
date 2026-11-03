"""C4 reference-only frequency sampling, retaining the complete previous bank.

This selector receives legal historical endpoint metadata from the frozen
frontend. It must never receive A/B query scores, predictions or error lists.
Up to 4096 NEW endpoints per device/protocol; no device-specific scoring rule.
Full preparation/encoding/evaluation integration is a separate stage.
"""
import hashlib
import heapq
import json

CAP = 4096
SALT = 'C4_HISTORY_SAMPLE_COVERAGE_V1_20261101'
FORBIDDEN = {'score', 'logits', 'support', 'prediction', 'is_fp', 'query_uid', 'nearest_query'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def physical(row):
    raw, ordinal = row.get('origin_raw_sha256'), row.get('origin_packet_ordinal')
    require(isinstance(raw, str) and len(raw)==64 and all(c in '0123456789abcdef' for c in raw), 'RAW_SHA')
    require(type(ordinal) is int and ordinal>0, 'ORIGIN_ORDINAL')
    return raw, ordinal, row['owner']


def rank(origin):
    value=json.dumps([SALT,*origin],separators=(',',':'),ensure_ascii=True)
    return int(hashlib.sha256(value.encode('ascii')).hexdigest(),16)


def select(candidates, old_rows, admitted, *, cap=CAP):
    """One pass over legal HIST_REF rows, independent of component frequencies.

    `admitted`: device -> raw_sha256, owner, reference_end_us, bank_end_frame.
    Caller verifies census UID/origin uniqueness in its on-disk primary keys;
    this function also rejects duplicate selected physical endpoints. No
    query/DEV records may be fed to it, even if they are labeled normal.
    Existing references remain outside this function and are always unioned.
    """
    require(cap==CAP,'FIXED_CAP')
    require(admitted and isinstance(admitted,dict),'ADMITTED_INPUTS_REQUIRED')
    old_physical=set()
    old_uids=set()
    for row in old_rows:
        require(row['use']=='REFERENCE' and type(row['label']) is int and row['label']==0,'OLD_REFERENCE_ROLE')
        require(row['uid'] not in old_uids,'DUPLICATE_OLD_UID');old_uids.add(row['uid'])
        if 'origin_raw_sha256' in row:old_physical.add(physical(row))
    heaps={};kept_origins={};kept_scores={};seen_counts={};excluded={}
    for row in candidates:
        require(not (FORBIDDEN & row.keys()),'TARGET_FEEDBACK_FIELD')
        require(row.get('history_role')=='HIST_REF' and row.get('use')=='REFERENCE'
                and type(row.get('label')) is int and row['label']==0,'REFERENCE_ONLY')
        require(row.get('device') in admitted,'UNADMITTED_DEVICE')
        spec=admitted[row['device']]
        origin=physical(row)
        require(origin[0]==spec['raw_sha256'] and origin[2]==spec['owner'],'ADMITTED_SOURCE_IDENTITY')
        require(row.get('protocol') in (6,17),'PROTOCOL')
        require(type(row.get('timestamp_us')) is int and row['timestamp_us']<=spec['reference_end_us'],'CAUSAL_TIME')
        require(type(row.get('frame')) is int and 0<row['frame']<=spec['bank_end_frame'],'CAUSAL_FRAME')
        require(row.get('reference_end_us')==spec['reference_end_us'] and row.get('bank_end_frame')==spec['bank_end_frame'],'BANK_CUTOFF_IDENTITY')
        require(isinstance(row.get('uid'),str) and len(row['uid'])==64,'UID')
        require(isinstance(row.get('component_id'),str) and len(row['component_id'])==64,'COMPONENT')
        group=row['device'],row['protocol'];seen_counts[group]=seen_counts.get(group,0)+1
        if row['uid'] in old_uids or origin in old_physical:
            excluded[group]=excluded.get(group,0)+1;continue
        h=heaps.setdefault(group,[])
        origins=kept_origins.setdefault(group,set())
        scores=kept_scores.setdefault(group,set())
        # Negated rank forms a max heap using heapq; deterministic physical-ID
        # ties avoid depending on row traversal order. SHA collision is stopped.
        score=rank(origin)
        require(origin not in origins,'DUPLICATE_CANDIDATE_ORIGIN')
        require(score not in scores,'HASH_RANK_COLLISION')
        if len(h)<cap:
            heapq.heappush(h,(-score,row['uid'],dict(row)))
            origins.add(origin);scores.add(score)
        elif score < -h[0][0]:
            removed=heapq.heapreplace(h,(-score,row['uid'],dict(row)))
            origins.remove(physical(removed[2]));scores.remove(-removed[0])
            origins.add(origin);scores.add(score)
    selected=sorted((entry[2] for h in heaps.values() for entry in h),key=lambda r:r['uid'])
    require(len({r['uid'] for r in selected})==len(selected),'SELECTED_UID_DUPLICATE')
    require(len({physical(r) for r in selected})==len(selected),'SELECTED_PHYSICAL_DUPLICATE')
    require(not old_uids.intersection(r['uid'] for r in selected),'OLD_UID_SELECTED_AGAIN')
    require(not old_physical.intersection(physical(r) for r in selected),'OLD_PHYSICAL_SELECTED_AGAIN')
    groups=[]
    for key in sorted(seen_counts):
        chosen=[r for r in selected if (r['device'],r['protocol'])==key]
        groups.append(dict(device=key[0],protocol=key[1],candidate_rows=seen_counts[key],
            old_reference_rows_excluded=excluded.get(key,0),new_rows=len(chosen),
            new_components=len({r['component_id'] for r in chosen})))
    return selected,dict(rule=SALT,per_device_protocol_cap=cap,groups=groups,
        selection_signal='Uniform deterministic physical-endpoint hash sampling, with no component balancing or target feedback',
        union_policy='Retain every prior reference and add only selected new physical endpoints')
