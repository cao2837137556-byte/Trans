"""Exact archival labels, identity selection, and immutable causal snapshots."""
import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import legacy_unsw_archival_common_v1 as c
import legacy_reference_sample_prepare_v1 as prep


def quotas(counts, budget):
    c.require(counts and all(type(n) is int and n > 0 for n in counts.values()), 'POPULATION_COUNTS')
    total, components = sum(counts.values()), len(counts)
    k = min(budget, total)
    c.require(components <= k, 'COMPONENTS_EXCEED_BUDGET')
    if total == components:
        return dict(counts)
    remaining, denominator = k - components, total - components
    answer = {g: 1 + remaining * (n - 1) // denominator for g, n in counts.items()}
    order = sorted(counts, key=lambda g: (-(remaining * (counts[g]-1) % denominator), g))
    for g in order[:k - sum(answer.values())]:
        answer[g] += 1
    c.require(sum(answer.values()) == k and all(1 <= answer[g] <= counts[g] for g in counts), 'QUOTA_DRIFT')
    return answer


def attack_label(row, event, owner, intervals):
    matches = [a for a in intervals if a['owner'] == owner and
               a['start'] <= event.timestamp <= a['end'] and event.ip_proto == 6 and
               row.get('eth.dst', '').lower() == owner and event.src == a['attacker_ip'] and
               event.dst == a['victim_ip'] and event.dst_port == a['target_tcp_port'] and
               event.tcp_syn and not event.tcp_ack]
    c.require(len(matches) <= 1, 'AMBIGUOUS_ATTACK_LABEL')
    return matches[0] if matches else None


def target_metadata(spec, row, event, owner, namespace, device, label, interval=None):
    return dict(uid=prep.digest([spec['sha256'], int(row['frame.number']), owner]),
        source_sha256=spec['sha256'], capture_id=spec['capture_id'], owner=owner,
        device=device['device_id'], display_name=device['display_name'], partition=c.ROLE,
        frame=int(row['frame.number']), timestamp=event.timestamp, protocol=event.ip_proto,
        session_id=prep.digest(namespace), component_id=prep.digest([owner, namespace[2]]),
        reference_end=device['cutoff'], label=label, activity='UNKNOWN',
        use='QUERY', annotation_id=interval['annotation_id'] if interval else None,
        attack_rate=interval['rate_metadata'] if interval else None,
        direction='outbound' if row.get('eth.src', '').lower() == owner else 'inbound',
        stream_id=row.get('tcp.stream') if event.ip_proto == 6 else row.get('udp.stream'),
        label_evidence=None if interval is None else dict(attacker_ip=event.src, victim_ip=event.dst,
            target_tcp_port=event.dst_port, syn=event.tcp_syn, ack=event.tcp_ack,
            destination_mac=row.get('eth.dst', '').lower(), annotation_id=interval['annotation_id']))


def select_references(endpoints, policy):
    by_protocol = {}
    for proto in policy['supported_protocols']:
        by_protocol[proto] = sorted([r for r in endpoints if r['protocol'] == proto],
            key=lambda r: (hashlib.sha256((policy['ordering_salt']+'|'+r['component_id']).encode()).hexdigest(),
                           r['component_id']))
    answer = []
    index = 0
    while len(answer) < policy['max_total_components']:
        before = len(answer)
        for proto in policy['supported_protocols']:
            if index < len(by_protocol[proto]) and len(answer) < policy['max_total_components']:
                answer.append(dict(by_protocol[proto][index], use='REFERENCE'))
        if len(answer) == before:
            break
        index += 1
    return answer


def enumerate_source(decoded, spec, roster, labels, known, runtime, db, progress):
    """All causal context passes original guard; only target-device legal rows enter population."""
    api, prefix, _ = runtime
    context = prep.ScopedPrefixes(spec['capture_id'], known, prefix)
    devices = {d['mac']: d for d in roster}
    endpoints = {}; counts = Counter(); intervals = Counter(); normal_proto = Counter()
    previous = -math.inf
    for n, row in enumerate(decoded, 1):
        c.require(int(row['frame.number']) == n, 'NONCONTIGUOUS_FRAME')
        ts = float(row['frame.time_epoch'])
        c.require(math.isfinite(ts) and ts >= previous, 'CAPTURE_TIME_REGRESSION')
        previous = ts
        counts['packets'] += 1
        event = api.event_from_tshark(row)
        owner, ns, valid = context.append(row, event)
        if owner in devices and valid:
            d = devices[owner]
            if spec['kind'] == 'normal':
                c.require(ts >= d['t0'], 'BEFORE_CAPTURE_T0')
                r = target_metadata(spec, row, event, owner, ns, d, 0)
                if ts <= d['cutoff']:
                    c.require(n <= d['cutoff_frame'], 'REFERENCE_FRAME_AFTER_CUTOFF')
                    key = r['component_id']
                    if key not in endpoints or (ts, spec['capture_id'], n, r['uid']) > (
                            endpoints[key]['timestamp'], endpoints[key]['capture_id'], endpoints[key]['frame'], endpoints[key]['uid']):
                        endpoints[key] = r
                    counts['reference_positions'] += 1
                else:
                    rank = hashlib.sha256((spec['selection_salt']+'|'+r['uid']).encode()).hexdigest()
                    db.execute('INSERT INTO population VALUES(?,?,?,?,?,?,?)',
                               (r['uid'], owner, r['component_id'], 0, rank, None, json.dumps(r)))
                    counts['normal'] += 1
                    normal_proto[owner, event.ip_proto] += 1
            else:
                a = attack_label(row, event, owner, labels['intervals'])
                if a:
                    r = target_metadata(spec, row, event, owner, ns, d, 1, a)
                    c.require(ts > d['cutoff'], 'ATTACK_BEFORE_REGISTRATION')
                    db.execute('INSERT INTO population VALUES(?,?,?,?,?,?,?)',
                               (r['uid'], owner, r['component_id'], 1, '', a['annotation_id'], json.dumps(r)))
                    counts['attack'] += 1
                    intervals[a['annotation_id']] += 1
                else:
                    counts['mixed_legal_unlabeled'] += 1
        else:
            counts['not_selected_owner_or_not_legal'] += 1
        if n % 8192 == 0:
            db.commit()
            progress.tick(n, spec['packet_count'])
    db.commit()
    c.require(counts['packets'] == spec['packet_count'], 'PACKET_COUNT')
    c.require(not context.poisoned, 'POISONED_CONTEXT')
    progress.tick(counts['packets'], spec['packet_count'], force=True)
    return list(endpoints.values()), dict(counts=counts, interval_counts=intervals,
        normal_protocol_counts=[dict(owner=o, protocol=p, count=n) for (o,p),n in sorted(normal_proto.items())],
        context_rejections=dict(context.reasons))


def materialize(root, out, recipe, roster, labels, specs, known, decoder, progress):
    out = Path(out); out.mkdir(exist_ok=False)
    db = sqlite3.connect(str(out/'population.sqlite'))
    db.execute('CREATE TABLE population(uid TEXT PRIMARY KEY,owner TEXT,component TEXT,label INTEGER,rank TEXT,interval TEXT,metadata TEXT)')
    endpoints = []; audits = []
    try:
        runtime = prep.old.legacy_runtime()
        for spec in specs:
            progress.stage = 'ENUMERATE_' + spec['capture_id']
            with decoder(spec) as decoded:
                refs, audit = enumerate_source(decoded, spec, roster, labels, known, runtime, db, progress)
            endpoints.extend(refs); audits.append(dict(capture_id=spec['capture_id'], **audit))
        db.execute('CREATE INDEX groups_idx ON population(owner,label,component,rank,uid)')
        refs = []; query = []; groups = []
        for d in roster:
            owner = d['mac']; rr = [r for r in endpoints if r['owner'] == owner]
            c.require(Counter(str(r['protocol']) for r in rr) == d['eligible_reference_components_by_protocol'], 'REFERENCE_POPULATION')
            chosen = select_references(rr, recipe['reference_policy'])
            c.require(Counter(str(r['protocol']) for r in chosen) == d['planned_selected_references_by_protocol'], 'REFERENCE_QUOTA')
            refs.extend(chosen)
            counts = dict(db.execute('SELECT component,count(*) FROM population WHERE owner=? AND label=0 GROUP BY component', (owner,)))
            c.require(sum(counts.values()) == d['full_normal_eligible_positions'], 'NORMAL_POPULATION')
            pp = {str(x['protocol']):x['count'] for x in audits[0]['normal_protocol_counts'] if x['owner']==owner}
            c.require(pp == d['normal_later_protocol_counts'], 'NORMAL_PROTOCOL_POPULATION')
            take = quotas(counts, recipe['normal_queries']['device_budget'])
            c.require(sum(take.values()) == d['planned_normal_query_count'], 'NORMAL_SELECTED_COUNT')
            for comp, n in sorted(counts.items()):
                m = take[comp]
                selected = [json.loads(x[0]) for x in db.execute(
                    'SELECT metadata FROM population WHERE owner=? AND label=0 AND component=? ORDER BY rank,uid LIMIT ?', (owner,comp,m))]
                for r in selected:
                    r.update(label_metric_weight_denominator=len(roster)*len(counts)*m,
                             population_group_count=n, selected_group_count=m)
                query.extend(selected)
                groups.append(dict(owner=owner,component_id=comp,population=n,selected=m))
            aa = [json.loads(x[0]) for x in db.execute('SELECT metadata FROM population WHERE owner=? AND label=1 ORDER BY uid', (owner,))]
            c.require(len(aa) == d['planned_attack_query_count'], 'ATTACK_DEVICE_COUNT')
            ag = Counter((r['annotation_id'], r['component_id']) for r in aa)
            ac = Counter(a for a, comp in ag)
            c.require(len(ac) == 3, 'ATTACK_THREE_INTERVALS')
            for r in aa:
                r['label_metric_weight_denominator'] = len(roster)*3*ac[r['annotation_id']]*ag[r['annotation_id'],r['component_id']]
            query.extend(aa)
        actual = Counter(r['annotation_id'] for r in query if r['label']==1)
        c.require(actual == {a['annotation_id']:a['expected_legal_positive_count'] for a in labels['intervals']}, 'ATTACK_INTERVAL_COUNTS')
        query.sort(key=lambda r:r['uid']); refs.sort(key=lambda r:r['uid'])
        c.require(len(query) == recipe['counts']['queries'] and len(refs) == recipe['counts']['references'], 'MANIFEST_COUNTS')
        c.require(len({r['uid'] for r in query+refs}) == len(query)+len(refs), 'UID_OVERLAP')
        for y in (0,1):
            c.require(math.isclose(math.fsum(1/r['label_metric_weight_denominator'] for r in query if r['label']==y),1.,abs_tol=1e-12), 'WEIGHT_MASS')
        ref_groups = {(r['device'],r['protocol']):0 for r in refs}
        ref_components = {r['component_id'] for r in refs}
        for r in refs: ref_groups[r['device'],r['protocol']] += 1
        for r in query:
            r['reference_available'] = ref_groups.get((r['device'],r['protocol']),0)>=2
            r['reference_shared_component'] = r['component_id'] in ref_components
            r['hour_block'] = int((r['timestamp']-r['reference_end'])//3600)
        c.save_rows(out/'queries.jsonl.gz',query); c.save_rows(out/'references.jsonl.gz',refs)
        c.write(out/'component_counts.json',groups); c.write(out/'enumeration.json',audits)
        c.write(out/'manifest.json',dict(status='IDENTITIES_SEALED_BEFORE_ANY_FORWARD',queries=len(query),references=len(refs),
             recipe_sha256=c.RECIPE_SHA,model_forwards=0,independent_ID='NOT_RUN'))
    finally:
        db.close()
    c.seal(out); c.verify(out)
    return query, refs


def selected_snapshots(decoded, spec, targets, known, runtime, translator):
    """New archival label adapter; the original prefix/translator remain byte-identical."""
    api, prefix, _ = runtime
    by_frame = {r['frame']:r for r in targets}
    c.require(len(by_frame)==len(targets), 'DUPLICATE_TARGET_FRAME')
    context = prep.ScopedPrefixes(spec['capture_id'],known,prefix,retain_full_rows=True)
    seen = set(); count=0
    for count,row in enumerate(decoded,1):
        c.require(int(row['frame.number'])==count,'SNAPSHOT_FRAME_ORDER')
        event=api.event_from_tshark(row)
        owner,ns,valid=context.append(row,event)
        t=by_frame.get(count)
        if t is None: continue
        c.require(valid and owner==t['owner'] and prep.digest(ns)==t['session_id'],'TARGET_CONTEXT_DRIFT')
        c.require(t['source_sha256']==spec['sha256'] and t['capture_id']==spec['capture_id'] and
                  prep.digest([spec['sha256'],count,owner])==t['uid'] and event.timestamp==t['timestamp'] and
                  event.ip_proto==t['protocol'],'TARGET_IDENTITY_DRIFT')
        if t['use']=='REFERENCE':
            c.require(event.timestamp<=t['reference_end'],'FUTURE_REFERENCE')
        else: c.require(event.timestamp>t['reference_end'],'QUERY_BEFORE_CUTOFF')
        if spec['kind']=='normal': c.require(t['label']==0,'NORMAL_LABEL_DRIFT')
        else:
            a=attack_label(row,event,owner,spec['intervals'])
            c.require(a is not None and t['label']==1 and a['annotation_id']==t['annotation_id'],'ATTACK_LABEL_DRIFT')
        flow=context.snapshot(ns,translator)
        c.require(set(flow)=={'flow_duration','burst_tokens','directions','bytes','iats','counts','protocol'},'E3_METADATA_LEAK')
        seen.add(t['uid'])
        yield t['uid'],flow
    c.require(count==spec['packet_count'] and seen=={r['uid'] for r in targets},'SNAPSHOT_COVERAGE')
