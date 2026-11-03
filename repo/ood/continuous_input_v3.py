"""Current-inclusive bounded input; no labels, model, raw-file I/O or role logic."""
from collections import Counter, deque
from decimal import Decimal
import hashlib
import json
import math

VERSION = 'continuous-input-core-repair-design-v3-20260929'
NS = 10**9
FIELDS = ('frame.number', 'frame.time_epoch', 'eth.src', 'eth.dst', 'ip.src', 'ip.dst',
          'ipv6.src', 'ipv6.dst', 'ip.hdr_len', 'ip.dsfield', 'ip.len', 'ip.flags',
          'ip.ttl', 'ipv6.tclass', 'ipv6.plen', 'ipv6.hlim', 'tcp.flags',
          'tcp.window_size_value', 'tcp.seq_raw', 'tcp.ack_raw', 'tcp.urgent_pointer',
          'udp.length')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def integer(value):
    text = str(value)
    return int(text, 16) if text.lower().startswith('0x') else int(text)


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), ensure_ascii=True,
                                     allow_nan=False).encode()).hexdigest()


def nanos(value):
    n = Decimal(str(value)) * NS
    require(n.is_finite() and n == n.to_integral_value(), 'TIME_NOT_FINITE_NANOSECONDS')
    return int(n)


def ip_bytes(row):
    return integer(row['ip.len']) if row.get('ip.src') else integer(row['ipv6.plen']) + 40


def tokens(value, count=1):
    value = int(value) & ((1 << (16 * count)) - 1)
    return [(value >> (16 * i)) & 65535 for i in reversed(range(count))]


def headers(row, protocol, first_src, seq_anchor, ack_anchor):
    ipv4 = bool(row.get('ip.src'))
    src = row.get('ip.src') or row.get('ipv6.src')
    value = [integer(row['ip.hdr_len']) if ipv4 else 40,
             integer(row['ip.dsfield'] if ipv4 else row['ipv6.tclass']), ip_bytes(row),
             integer(row['ip.flags']) if ipv4 else 0,
             integer(row['ip.ttl'] if ipv4 else row['ipv6.hlim'])]
    result = [t for v in value for t in tokens(v)]
    if protocol == 6:
        seq, ack = integer(row['tcp.seq_raw']), integer(row['tcp.ack_raw'])
        if src == first_src:
            seq = (seq - seq_anchor) & 0xffffffff
            ack = 0 if ack_anchor == 0 else (ack - ack_anchor) & 0xffffffff
        else:
            seq, ack = (seq - ack_anchor) & 0xffffffff, (ack - seq_anchor) & 0xffffffff
        result += (tokens(integer(row['tcp.flags'])) + tokens(integer(row['tcp.window_size_value'])) +
                   tokens(seq, 2) + tokens(ack, 2) + tokens(integer(row['tcp.urgent_pointer'])))
    else:
        result += tokens(integer(row['udp.length']))
    require(len(result) == (12 if protocol == 6 else 6), 'HEADER_TOKEN_COUNT')
    return result


class RecentState:
    """One owner/capture/key; all state updated before an immutable snapshot."""
    def __init__(self, owner, namespace, protocol):
        self.owner, self.namespace, self.protocol = owner, namespace, protocol
        self.last_ns = None
        self.last_frame = 0
        self.reset_reason = 'FIRST_KEY'
        self.episode_first_frame = None
        self._reset()

    def _reset(self):
        self.bursts = [deque(maxlen=12), deque(maxlen=12)]
        self.direction_last = [None, None]
        self.values = [[[0.0] * 6 for _ in (1, 10)] for _ in (0, 1)]
        self.previous_iat = 0.0
        self.has_previous = False

    def append(self, row):
        now, frame = nanos(row['frame.time_epoch']), integer(row['frame.number'])
        require(frame > self.last_frame and (self.last_ns is None or now >= self.last_ns), 'STATE_ORDER')
        dt = 0 if self.last_ns is None else now - self.last_ns
        reset = self.last_ns is None or dt > 60 * NS
        if reset:
            self.reset_reason = 'FIRST_KEY' if self.last_ns is None else 'IDLE_GT_60S'
            self._reset()
            self.episode_first_frame = frame
        else:
            self.previous_iat = dt / NS
            self.has_previous = True
            for direction in (0, 1):
                for k, h in enumerate((1, 10)):
                    decay = 2.0 ** (-dt / NS / h)
                    self.values[direction][k] = [v * decay for v in self.values[direction][k]]
        outgoing = row.get('eth.src', '').lower() == self.owner
        incoming = row.get('eth.dst', '').lower() == self.owner
        require(outgoing != incoming, 'AMBIGUOUS_OWNER_DIRECTION')
        d = 0 if outgoing else 1
        flags = integer(row['tcp.flags']) if self.protocol == 6 else 0
        increment = [1, ip_bytes(row), int(bool(flags & 2) and not bool(flags & 16)),
                     int(bool(flags & 16)), int(bool(flags & 4)), int(bool(flags & 1))]
        for k in range(2):
            self.values[d][k] = [a + b for a, b in zip(self.values[d][k], increment)]
        if self.direction_last[d] is None or now - self.direction_last[d] > 10_000_000:
            self.bursts[d].append({'id': frame, 'rows': deque(maxlen=6), 'last_frame': frame})
        self.bursts[d][-1]['rows'].append({k: row.get(k, '') for k in FIELDS})
        self.bursts[d][-1]['last_frame'] = frame
        self.direction_last[d] = now
        self.last_ns, self.last_frame = now, frame

    def snapshot(self):
        require(self.last_ns is not None, 'EMPTY_STATE')
        bursts = sorted([b for group in self.bursts for b in group],
                        key=lambda b: b['last_frame'])[-12:]
        chosen = []
        for b in bursts:
            rows = [dict(r) for r in b['rows'] if self.last_ns - nanos(r['frame.time_epoch']) <= 60 * NS]
            if rows:
                chosen.append((b['id'], rows))
        chosen.sort(key=lambda b: (nanos(b[1][0]['frame.time_epoch']), integer(b[1][0]['frame.number'])))
        ordered = sorted([r for _, rows in chosen for r in rows], key=lambda r: integer(r['frame.number']))
        require(ordered and len(ordered) <= 72 and integer(ordered[-1]['frame.number']) == self.last_frame,
                'CURRENT_PACKET_NOT_RETAINED')
        first_src = ordered[0].get('ip.src') or ordered[0].get('ipv6.src')
        seq = integer(ordered[0]['tcp.seq_raw']) if self.protocol == 6 else 0
        ack = integer(ordered[0]['tcp.ack_raw']) if self.protocol == 6 else 0
        if self.protocol == 6 and ack == 0 and len(ordered) > 1:
            ack = integer(ordered[1]['tcp.seq_raw'])
        flow = dict(flow_duration=(self.last_ns - nanos(ordered[0]['frame.time_epoch'])) // 1000,
                    burst_tokens=[], directions=[], bytes=[], iats=[], counts=[], protocol=self.protocol)
        evidence = []
        previous_time = nanos(chosen[0][1][0]['frame.time_epoch'])
        for j, (burst_id, rows) in enumerate(chosen):
            now = nanos(rows[0]['frame.time_epoch'])
            packet_tokens = [headers(r, self.protocol, first_src, seq, ack) for r in rows]
            flow['burst_tokens'].append([t for p in packet_tokens for t in p + [0] * 6])
            flow['directions'].append((rows[0].get('ip.src') or rows[0].get('ipv6.src')) == first_src)
            flow['bytes'].append(sum(ip_bytes(r) for r in rows))
            flow['counts'].append(len(rows))
            flow['iats'].append(0 if j == 0 else now - previous_time)
            previous_time = now
            evidence.append(dict(burst_id=burst_id, frames=[integer(r['frame.number']) for r in rows],
                                 times_ns=[nanos(r['frame.time_epoch']) for r in rows],
                                 headers=packet_tokens))
        state = []
        for direction in (0, 1):
            for k, h in enumerate((1, 10)):
                n, b, *flags = self.values[direction][k]
                state += [math.log1p(n * math.log(2) / h), math.log1p(b * math.log(2) / h)]
                state += [v / max(n, 1e-12) for v in flags]
        state += [math.log1p(self.previous_iat), float(self.has_previous)]
        require(len(state) == 26 and all(math.isfinite(v) for v in state), 'STATE26_NONFINITE')
        provenance = dict(version=VERSION, namespace_sha256=digest(self.namespace), query_frame=self.last_frame,
                          query_time_ns=self.last_ns, reset_reason=self.reset_reason,
                          episode_first_frame=self.episode_first_frame, bursts=evidence)
        return flow, state, provenance


class Contexts:
    """Apply legacy protocol/owner/causal eligibility before state updates."""
    def __init__(self, capture, known, event_api, max_states=1_000_000, *, required_owners=None):
        self.capture, self.known, self.api = capture, set(x.lower() for x in known), event_api
        # Direct low-level callers default to all known owners. Production always
        # passes the frozen query/reference union via CaptureAudit.
        self.required = frozenset(self.known if required_owners is None else
                                  (x.lower() for x in required_owners))
        require(self.required <= self.known, 'REQUIRED_OWNER_NOT_REGISTERED')
        self.frame_required_owner = False
        self.states, self.reasons, self.max_states = {}, Counter(), max_states
        self.retired = {}
        self.previous_ns, self.frame = None, 0
        # This ledger survives physical GC and idle resets. Frame identities are
        # emitted by CaptureAudit; it never grows with packet count here.
        self.last_seen, self.poisoned, self.tainted = {}, set(), set()
        self.events = []; self.query_allowed = False; self.query_reason = 'NO_FRAME'

    def record(self, kind, ns=None, **detail):
        self.reasons[kind] += 1
        self.events.append(dict(kind=kind, frame=self.frame, namespace=ns, **detail))

    def require_target(self):
        require(self.query_allowed, 'FIXED_TARGET_INVALID:'+self.query_reason+':frame='+str(self.frame))

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
        require(all(row.get(k, '') != '' for k in key_fields), 'MISSING_NAMESPACE_HEADERS')
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


def verify_tokenized(flow, provenance, example):
    """Independent frame/header-to-token check after the pinned tokenizer."""
    require(len(provenance['bursts']) == len(example['input_ids']) == len(flow['counts']), 'TOKEN_BURST_COVERAGE')
    current = []
    header_length = 12 if flow['protocol'] == 6 else 6
    for j, b in enumerate(provenance['bursts']):
        expected = [65537] + [v + 1 for p in b['headers'] for v in p]
        require(example['input_ids'][j] == expected, 'FRAME_TO_TOKEN_VALUES')
        require(example['attention_mask'][j] == [1] * len(expected), 'CURRENT_TOKEN_MASK')
        require(example['dataset_burst_sizes'][j] == len(expected) - 1, 'BURST_SIZE_IDENTITY')
        require(len(b['frames']) == flow['counts'][j] <= 6, 'FRAME_COUNT')
        for i, (frame, time) in enumerate(zip(b['frames'], b['times_ns'])):
            require(frame <= provenance['query_frame'] and time <= provenance['query_time_ns'], 'FUTURE_PROVENANCE')
            if frame == provenance['query_frame']:
                current.append([j, 1 + i * header_length, header_length])
    require(len(current) == 1, 'CURRENT_PACKET_TOKEN_COVERAGE')
    return current[0]
