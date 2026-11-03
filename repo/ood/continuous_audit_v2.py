"""Packet identity audit and four-capture preflight; never runs E3 or optimizer."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import continuous_common_v2 as c
from continuous_input_v2 import Contexts
import legacy_reference_sample_prepare_v1 as prep
from legacy_unsw_archival_runtime_v1 import decode

ANOMALIES = ('NEW_TIMESTAMP_REGRESSION', 'POISONED_PREFIX', 'INCOMPLETE_TARGET')


def targets_by_capture(metadata):
    result = defaultdict(dict)
    for role, rows in metadata.items():
        for slot, row in enumerate(rows):
            c.require(row['frame'] not in result[row['capture_id']], 'DUPLICATE_CAPTURE_TARGET')
            result[row['capture_id']][row['frame']] = (role, slot, row)
    return result


def check_target(spec, target, owner, ns, event, contexts):
    contexts.require_target()
    frame = contexts.frame
    c.require(ns is not None and owner == target['owner'] and prep.digest(ns) == target['session_id'], 'TARGET_SCOPE')
    c.require(target['source_sha256'] == spec['sha256'] and target['capture_id'] == spec['capture_id'] and
        target['uid'] == prep.digest([spec['sha256'], frame, owner]) and target['timestamp'] == event.timestamp and
        target['protocol'] == event.ip_proto, 'TARGET_IDENTITY')
    c.require(target['timestamp'] <= target['reference_end'] if target['use'] == 'REFERENCE' else
              target['timestamp'] > target['reference_end'], 'REFERENCE_QUERY_TIME')


class CaptureAudit:
    def __init__(self, spec, known, api, targets, directory, expected=None):
        self.spec, self.targets, self.expected = spec, targets, expected
        self.contexts = Contexts(spec['capture_id'], known, api[0])
        # Literal legacy implementation, not a reimplementation of float rules.
        self.legacy = prep.ScopedPrefixes(spec['capture_id'], known, api[1])
        self.stream = gzip.open(Path(directory)/(spec['capture_id']+'.anomalies.jsonl.gz'), 'wt', encoding='utf-8')
        self.anomaly_hash, self.target_hash = hashlib.sha256(), hashlib.sha256()
        self.seen, self.count = 0, 0

    def write(self, value):
        text = json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n'
        self.stream.write(text); self.stream.flush()
        self.anomaly_hash.update(text.encode())

    def append(self, row):
        before = self.legacy.reasons.copy()
        try:
            owner, ns, event = self.contexts.append(row)
        except Exception as exc:
            self.write(dict(frame=row.get('frame.number'), timestamp=row.get('frame.time_epoch'),
                            context_failure=str(exc), empty_fields=sorted(k for k,v in row.items() if v=='')))
            raise
        lo, ln, valid = self.legacy.append(row, event)
        changes = self.legacy.reasons-before
        kinds = [k for k in ANOMALIES if changes[k]]
        current = {x['kind'] for x in self.contexts.events}
        target = self.targets.get(self.contexts.frame)
        if kinds or self.contexts.events:
            self.write(dict(frame=self.contexts.frame, namespace=ns, legacy_namespace=ln,
                            timestamp=row['frame.time_epoch'], legacy_anomalies=kinds,
                            captured_bytes=row.get('frame.cap_len'), frame_bytes=row.get('frame.len'),
                            empty_fields=sorted(k for k,v in row.items() if v==''),
                            current_events=self.contexts.events, legacy_query_valid=valid,
                            fixed_uid=None if target is None else target[2]['uid']))
        c.require((lo, ln) == (owner, ns), 'LEGACY_NAMESPACE_IDENTITY')
        for k in ('NEW_TIMESTAMP_REGRESSION','POISONED_PREFIX'):
            c.require((k in kinds) == (k in current), 'LEGACY_NS_ANOMALY_IDENTITY:'+k+':frame='+str(self.contexts.frame))
        incomplete = bool(current & {'MISSING_REQUIRED_HEADERS','PAYLOAD_TRUNCATED_HEADERS_COMPLETE'})
        c.require(('INCOMPLETE_TARGET' in kinds) == incomplete, 'LEGACY_INCOMPLETE_IDENTITY')
        self.count += 1
        if target is not None:
            if not self.contexts.query_allowed:
                self.write(dict(frame=self.count, fixed_uid=target[2]['uid'],
                                target_failure=self.contexts.query_reason, namespace=ns))
            check_target(self.spec, target[2], owner, ns, event, self.contexts)
            c.require(valid, 'LEGACY_FIXED_QUERY_INVALID')
            identity = [target[2]['uid'], self.count, ns, row['frame.time_epoch'], self.contexts.query_reason]
            self.target_hash.update((json.dumps(identity,separators=(',',':'))+'\n').encode())
            self.seen += 1
        return owner, ns, event

    def finish(self):
        c.require(self.count == self.spec['expected_packets'] and self.seen == len(self.targets), 'CAPTURE_COVERAGE')
        observed = {k:self.legacy.reasons[k] for k in ANOMALIES}
        if self.expected is not None:
            c.require(observed == self.expected['anomalies'], 'STATIC_RECEIPT_ANOMALIES:'+self.spec['capture_id'])
            c.require(self.count == self.expected['packets'], 'STATIC_RECEIPT_PACKETS')
        return dict(capture=self.spec['capture_id'], packets=self.count, targets=self.seen,
                    legacy_anomalies=observed, current_reasons=dict(self.contexts.reasons),
                    anomaly_identity_sha256=self.anomaly_hash.hexdigest(),
                    target_identity_sha256=self.target_hash.hexdigest())

    def close(self): self.stream.close()


def reconcile(early, main):
    c.require(early == main, 'EARLY_MAIN_FRAME_NAMESPACE_OR_TARGET_MISMATCH')


def early_target_uids(metadata, design):
    spec=design['evaluation']['early_attack_diagnostic']; result=[]
    for device in spec['devices']:
        rows=sorted([r for r in metadata[spec['pool']] if r['device']==device and r['label']==1],
                    key=lambda r:tuple(r[k] for k in spec['order']))[:spec['rows_each']]
        c.require(len(rows)==spec['rows_each'], 'EARLY_DIAGNOSTIC_SUPPORT')
        result.extend(r['uid'] for r in rows)
    return result


def preflight(root, out, metadata, specs, runtime, design, progress):
    out=Path(out); out.mkdir(exist_ok=False)
    by=targets_by_capture(metadata); selected={s['capture_id']:s for s in specs}
    receipts=c.read(Path(root)/'frozen/anomaly_receipts.json')
    priority=design['execution_delivery_requirements']['anomaly_preflight']['captures']
    c.require(set(priority) <= set(selected), 'FOUR_CAPTURE_MISSING')
    c.require(set(selected) <= set(receipts), 'STATIC_RECEIPT_COVERAGE')
    for name,spec in selected.items():
        c.require(receipts[name]['sha256']==spec['sha256'] and receipts[name]['packets']==spec['expected_packets'], 'STATIC_CAPTURE_IDENTITY')
    c.write(out/'static_receipts.json',dict(selected={n:receipts[n] for n in sorted(selected)},
        captures=len(selected), priority=priority, E3_forwards=0))
    api=prep.old.legacy_runtime(); summaries={}
    for name in priority:
        spec=selected[name]; known=runtime['external_known_macs' if spec.get('external') else 'source_known_macs']
        audit=CaptureAudit(spec,known,api,by[name],out,receipts[name])
        before=(Path(spec['path']).stat().st_size,Path(spec['path']).stat().st_mtime_ns)
        progress.stage='P_ANOMALY_PREFLIGHT_'+name; progress.tick(0,spec['expected_packets'])
        try:
            with decode(spec['path'],spec,api,progress,out/(name+'.stderr.log'),runtime['tshark']) as rows:
                for i,row in enumerate(rows,1):
                    audit.append(row)
                    if i%8192==0:progress.tick(i,spec['expected_packets'])
            summaries[name]=audit.finish()
            c.require(before==(Path(spec['path']).stat().st_size,Path(spec['path']).stat().st_mtime_ns),'RAW_CHANGED_DURING_PREFLIGHT')
            c.write(out/(name+'.json'),summaries[name])
        finally: audit.close()
    c.write(out/'receipt.json',dict(status='COMPLETE',summaries=summaries,extra_decodes=4,E3_forwards=0))
    c.seal(out);c.verify(out)
    return summaries
