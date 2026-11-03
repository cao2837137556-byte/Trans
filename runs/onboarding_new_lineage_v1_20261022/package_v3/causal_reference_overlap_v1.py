"""Validate duplicate historical observation identities, never rename/drop queries."""
import math

IDENTITY=('uid','source_sha256','frame','owner','component_id','session_id','capture_id',
          'device','partition','protocol','timestamp')

def require_prebank_history(query,reference):
    def require(value,reason):
        if not value:raise ValueError(reason)
    require(all(k in query and k in reference and query[k]==reference[k] for k in IDENTITY),
            'HISTORY_REPLAY_IDENTITY_MISMATCH')
    require(query['partition'] in ('DEV','EXTERNAL_ARCHIVAL_EVALUATION') and
            query['use']!='REFERENCE' and reference['use']=='REFERENCE' and
            query['label']==reference['label']==0,'HISTORY_REPLAY_ROLE_OR_SOURCE')
    end=reference.get('reference_end');frame_end=reference.get('bank_end_frame')
    require(type(end) in (float,int) and math.isfinite(end) and
            math.isfinite(query['timestamp']) and query['timestamp']<=end and
            type(frame_end) is int and 0<query['frame']<=frame_end,
            'HISTORY_REPLAY_NOT_BEFORE_COMPLETE_BANK')
    return dict(uid=query['uid'],timestamp=query['timestamp'],frame=query['frame'],
                reference_end=end,bank_end_frame=frame_end,required_support=0.0,
                required_behavior='EXACT_HEAD_FALLBACK')
