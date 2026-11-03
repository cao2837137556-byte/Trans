"""Prospective sample guard only. Does not alter old E3, scores, labels or denominators."""
import math

SHARED_DHCP_KEY=(17,('0.0.0.0',68),('255.255.255.255',67))


class ContextOrderError(RuntimeError):
    """Invalidate the query; never silently drop an earlier row to hide regression."""


def canonical_key(event):
    return (event.ip_proto,)+tuple(sorted(((event.src,event.src_port),(event.dst,event.dst_port))))


def context_decision(row,event,*,owner_mac,known_device_macs,capture_id,query_capture_id,
                     query_frame,query_timestamp,query_key):
    """Apply before BOTH target selection and every legacy prefix append.

    Device MAC is identity metadata, never a model input. No future event or
    label is needed for this decision. The caller still applies all old header,
    protocol and timestamp-regression rules. This guard is not a new frontend.
    """
    owner=owner_mac.lower()
    known={x.lower() for x in known_device_macs}
    if owner not in known:return False,'UNKNOWN_OWNER'
    if capture_id!=query_capture_id:return False,'OTHER_CAPTURE'
    matched={str(row.get(k,'')).lower() for k in ('eth.src','eth.dst')} & known
    if matched!={owner}:
        return False,'OTHER_OR_MULTIPLE_DEVICE_OWNERS'
    event_key=canonical_key(event)
    if event_key==SHARED_DHCP_KEY:
        return False,'SHARED_DHCP_CONTEXT'
    if event_key!=query_key:
        return False,'OTHER_CANONICAL_SESSION'
    try:
        frame=int(row['frame.number'])
    except (KeyError,TypeError,ValueError):return False,'INVALID_FRAME'
    if not (math.isfinite(event.timestamp) and math.isfinite(query_timestamp)):
        return False,'INVALID_TIME'
    if frame<1 or frame>query_frame:
        return False,'FUTURE_OR_INVALID_POSITION'
    if event.timestamp>query_timestamp:
        raise ContextOrderError('Earlier capture row has later time; preserve old regression invalidation')
    return True,'OWNER_LOCAL_CAUSAL_CONTEXT'


def prefix_namespace(*,owner_mac,capture_id,event):
    """The old canonical key remains intact inside a device/capture namespace."""
    return (owner_mac.lower(),capture_id,canonical_key(event))


def reference_decision(*,reference_owner,query_owner,certified_normal,
                       reference_end,first_query_time,reference_partition,query_partition):
    if reference_owner!=query_owner:return False,'REFERENCE_OWNER_MISMATCH'
    if not certified_normal:return False,'NO_INDEPENDENT_NORMAL_PROVENANCE'
    if reference_partition!=query_partition:return False,'CROSS_PARTITION_REFERENCE'
    if not (math.isfinite(reference_end) and math.isfinite(first_query_time)):
        return False,'INVALID_TIME'
    if reference_end>=first_query_time:return False,'REFERENCE_NOT_STRICTLY_EARLIER'
    return True,'ELIGIBLE_EARLIER_NORMAL_REFERENCE'
