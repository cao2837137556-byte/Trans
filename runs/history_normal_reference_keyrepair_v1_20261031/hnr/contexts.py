"""History-only conservative handling of undecodable transport namespaces.

Every decoder row is consumed. No ports are invented and no fragment is
silently skipped. Unknown ports taint all sessions sharing observed owner,
protocol and unordered IP pair until a genuine adjacent group idle >60s.
Frozen Contexts logic below is retained for all other decisions.
"""
from continuous_input_engineering_v1 import Contexts as EngineeringContexts
from continuous_input_v3 import NS, RecentState, integer, nanos, require


class Contexts(EngineeringContexts):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.namespace_groups = {}
        self.namespace_generations = {}

    def append(self, row):
        import legacy_reference_sample_prepare_v1 as prep
        import legacy_reference_context_scope_v1 as guard
        now, frame = nanos(row['frame.time_epoch']), integer(row['frame.number'])
        require(frame == self.frame + 1, 'NONCONTIGUOUS_CAPTURE_FRAME')
        back = self.previous_ns is not None and now < self.previous_ns
        self.events = []; self.query_allowed = False; self.query_reason = 'OUTSIDE_SCOPE'
        self.frame_required_owner = False
        self.previous_ns, self.frame = now, frame
        event = self.api.event_from_tshark(row)
        owners = {row.get('eth.src', '').lower(), row.get('eth.dst', '').lower()} & self.known
        if len(owners) != 1:
            self.reasons['PROTOCOL_OR_OWNER_OUTSIDE'] += 1
            if back: self.record('CAPTURE_REGRESSION_OUTSIDE_SCOPE')
            return None, None, event
        owner = next(iter(owners))
        if owner not in self.required:
            self.record('OUTSIDE_REQUIRED_OWNER', owner=owner)
            self.query_reason = 'OUTSIDE_REQUIRED_OWNER'
            if back: self.record('CAPTURE_REGRESSION_OUTSIDE_SCOPE')
            return None, None, event
        self.frame_required_owner = True
        key = prep.old.old_key(event)
        if key is None:
            self.reasons['PROTOCOL_OR_OWNER_OUTSIDE'] += 1
            if back: self.record('CAPTURE_REGRESSION_OUTSIDE_SCOPE')
            return None, None, event
        key_fields = (('ip.src','ip.dst') if event.ip_version == 4 else ('ipv6.src','ipv6.dst'))
        key_fields += ('tcp.srcport','tcp.dstport') if event.ip_proto == 6 else ('udp.srcport','udp.dstport')
        # The legacy parser defaults missing ports to zero. Never let that
        # manufacture a namespace and incorrectly declare another key unaffected.
        complete_namespace = all(row.get(k, '') != '' for k in key_fields)
        # Unknown IP identity remains a hard stop. Missing transport ports are
        # scoped only by the actually observed owner/protocol/IP pair.
        ip_fields = key_fields[:2]
        require(all(row.get(k, '') != '' for k in ip_fields), 'MISSING_NAMESPACE_IP_HEADERS')
        group_key = (owner, event.ip_version, event.ip_proto,
                     tuple(sorted(row[k] for k in ip_fields)))
        if group_key not in self.namespace_groups:
            require(len(self.namespace_groups) < self.max_states, 'NAMESPACE_GROUP_MEMORY_LIMIT')
        group = self.namespace_groups.setdefault(group_key, dict(last=None, tainted=False, generation=0))
        require(group['last'] is None or now >= group['last'], 'NAMESPACE_GROUP_TIMESTAMP_REGRESSION')
        if group['tainted'] and now-group['last'] > 60*NS:
            group['tainted'] = False
            self.record('MISSING_NAMESPACE_GROUP_IDLE_RESET', group=group_key)
        group['last'] = now
        if not complete_namespace:
            if not group['tainted']:
                group['generation'] += 1
            group['tainted'] = True
            self.record('MISSING_NAMESPACE_HEADERS_TAINT', group=group_key)
            self.query_reason = 'MISSING_NAMESPACE_HEADERS'
            return owner, None, event
        ok, reason = guard.context_decision(row, event, owner_mac=owner, known_device_macs=self.known,
            capture_id=self.capture, query_capture_id=self.capture, query_frame=frame,
            query_timestamp=event.timestamp, query_key=key)
        if not ok:
            self.reasons[reason] += 1
            if back: self.record('CAPTURE_REGRESSION_OUTSIDE_SCOPE')
            return None, None, event
        ns = guard.prefix_namespace(owner_mac=owner, capture_id=self.capture, event=event)
        if ns in self.poisoned:
            self.record('POISONED_PREFIX', ns)
            self.query_reason = 'POISONED_PREFIX'
            return owner, ns, event
        last = self.last_seen.get(ns)
        if last is not None and now < last:
            self.poisoned.add(ns)
            self.record('NEW_TIMESTAMP_REGRESSION', ns, previous_ns=last, now_ns=now)
            self.query_reason = 'NEW_TIMESTAMP_REGRESSION'
            return owner, ns, event
        if back: self.record('CAPTURE_REGRESSION_CROSS_KEY', ns)
        if ns not in self.last_seen:
            require(len(self.last_seen) < self.max_states, 'NAMESPACE_LEDGER_MEMORY_LIMIT')
        self.last_seen[ns] = now
        if not group['tainted'] and self.namespace_generations.get(ns, 0) < group['generation']:
            # A real group idle gap proves every compatible key has also been
            # idle. Permanent poisoning and last_seen are deliberately kept.
            self.states.pop(ns, None); self.retired.pop(ns, None)
            self.tainted.discard(ns)
            self.namespace_generations[ns] = group['generation']
            self.record('MISSING_NAMESPACE_STATE_RESET', ns)
        if group['tainted']:
            self.tainted.add(ns)
            self.record('MISSING_NAMESPACE_HISTORY', ns, group=group_key)
            self.query_reason = 'MISSING_NAMESPACE_HISTORY'
            return owner, ns, event
        if ns in self.tainted and last is not None and now-last > 60*NS:
            # Only an actual gap between adjacent eligible events proves reset.
            # Dropping one packet out of the last72 cannot erase decayed state.
            self.tainted.remove(ns)
            self.record('MISSING_HEADER_TAINT_RESET', ns)
            self.states.pop(ns, None); self.retired.pop(ns, None)
        if not prep.headers_complete(row, event):
            self.tainted.add(ns)
            self.record('MISSING_REQUIRED_HEADERS', ns)
            self.query_reason = 'MISSING_REQUIRED_HEADERS'
            return owner, ns, event
        truncated = prep.old.number(row.get('frame.cap_len')) < event.frame_len
        if truncated: self.record('PAYLOAD_TRUNCATED_HEADERS_COMPLETE', ns)
        if ns in self.tainted:
            self.query_reason = 'MISSING_HEADER_HISTORY'
            return owner, ns, event
        if ns not in self.states:
            if len(self.states) >= self.max_states:
                # Evict only semantically expired keys, never a still-active key.
                for k,s in list(self.states.items()):
                    if now-s.last_ns > 60*NS:
                        self.retired[k]=(s.last_ns,s.last_frame);del self.states[k]
                require(len(self.retired) <= self.max_states, 'STATE_TOMBSTONE_MEMORY_LIMIT')
            require(len(self.states) < self.max_states, 'STATE_MEMORY_LIMIT_NO_LRU')
            self.states[ns] = RecentState(owner, ns, event.ip_proto)
            if ns in self.retired:
                self.states[ns].last_ns,self.states[ns].last_frame=self.retired.pop(ns)
        self.states[ns].append(row)
        self.query_allowed = not truncated
        self.query_reason = 'PAYLOAD_TRUNCATED_QUERY' if truncated else 'VALID'
        return owner, ns, event
