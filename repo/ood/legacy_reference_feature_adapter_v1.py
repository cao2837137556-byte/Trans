"""Prospective E3 input adapter. No asset loading or real execution on import."""
from __future__ import annotations
import legacy_reference_sample_prepare_v1 as prep

E3_KEYS={'flow_duration','burst_tokens','directions','bytes','iats','counts','protocol'}


def selected_flows(rows,targets,spec,known_macs,event_api,prefix_api,translator):
    """Yield exact UID and immutable causal flow; caller owns authorized forward.

    Training/evaluation roles do not enter input features. All capture rows,
    including unselected ones, pass through the identical owner scope guard.
    """
    by_frame={r['frame']:r for r in targets}
    if not targets or len(by_frame)!=len(targets):raise RuntimeError('Empty/duplicate capture target')
    if any(t['source_sha256']!=spec['sha256'] or t['capture_id']!=spec['capture_id'] for t in targets):
        raise RuntimeError('Target/source identity mismatch')
    contexts=prep.ScopedPrefixes(spec['capture_id'],known_macs,prefix_api,retain_full_rows=True)
    completed=set()
    for n,row in enumerate(rows,1):
        if int(row['frame.number'])!=n:raise RuntimeError('Noncontiguous capture order')
        event=event_api.event_from_tshark(row)
        owner,key,valid=contexts.append(row,event)
        target=by_frame.get(n)
        if target is None:continue
        if not valid or owner!=target['owner'] or prep.digest(key)!=target['session_id']:
            raise RuntimeError('Manifest target scope or causal prefix drift')
        if event.timestamp!=target['timestamp'] or prep.digest([spec['sha256'],n,owner])!=target['uid']:
            raise RuntimeError('Manifest UID/time drift')
        y,_=prep.label(spec,row,event,owner)
        if y!=target['label']:raise RuntimeError('Current-packet label drift')
        flow=contexts.snapshot(key,translator)
        if set(flow)!=E3_KEYS:raise RuntimeError('Unexpected model input metadata')
        completed.add(n)
        yield target['uid'],flow
    if completed!=set(by_frame):raise RuntimeError('Incomplete feature UID coverage')

