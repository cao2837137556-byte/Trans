"""Pin tiny frame-only engineering slice before any encoder is invoked."""
from collections import defaultdict
import json
from pathlib import Path
import time

import edge_adapter as edge


def plan(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();deadline=started+300
    value=edge.card();api=edge.prep.old.legacy_runtime()[0]
    result={'status':'FIXED_HEADER_ONLY_ENGINEERING_SLICE','model_evaluations':0,
            'features_generated':0,'distance_pairs':0,'frame_id_semantics':'original physical frame',
            'rules':{'reference':'First 8 canonical component digests globally plus first2 UDP component digests in complete legal first7200 universe; first up to2 legal frames each, deduplicated',
                     'normal_query':'First16 legal post7200 physical frames plus earliest legal post7200 UDP if absent',
                     'attack_query':'HTTP first<=4 legal direct per fixed SYN_no_ACK, PSH_ACK, ACK_only header stratum; UDP first16 legal direct; no score selection'}}
    for role in ('NORMAL','HTTP','UDP'):
        candidates=defaultdict(list);queries=[];protocols={};first_udp_query=None;http_strata=defaultdict(list)
        ctx=edge.eligibility_context(edge.segments(role,value)[0]['capture_id'],api,
                                     max_states=value['raw_inputs'][role]['records']+1)
        limit=125000 if role=='NORMAL' else 8192 if role=='HTTP' else 4096
        source=edge.decode_rows(value['raw_inputs'][role]['path'],output/(role+'_decoder.stderr.log'),stop_after=limit,deadline=deadline)
        try:
            for packet in source:
                frame=edge.frozen.integer(packet['frame.number']);now=edge.frozen.nanos(packet['frame.time_epoch'])
                owner,ns,event=ctx.append(packet)
                truth,label=edge.label_role(role,packet,now,value)
                if not truth or not ctx.query_allowed or ns is None:continue
                if truth==1:
                    component=edge.frozen.digest([edge.OWNER,ns[-1]])
                    protocols[component]=event.ip_proto
                    if len(candidates[component])<2:candidates[component].append(frame)
                else:
                    if role=='HTTP':
                        flags=edge.frozen.integer(packet['tcp.flags'])
                        name='SYN_no_ACK' if flags&2 and not flags&16 else 'PSH_ACK' if flags==0x18 else 'ACK_only' if flags==0x10 else None
                        if name and len(http_strata[name])<4:http_strata[name].append(frame)
                    elif len(queries)<16:queries.append(frame)
                    if role=='NORMAL' and event.ip_proto==17 and first_udp_query is None:
                        first_udp_query=frame
        finally:
            source.close()
        if role=='HTTP':
            edge.frozen.require(set(http_strata)=={'SYN_no_ACK','PSH_ACK','ACK_only'} and all(len(x)==4 for x in http_strata.values()),'SLICE_HTTP_STRATA_COVERAGE')
            queries=sorted(f for group in http_strata.values() for f in group)
        else:edge.frozen.require(len(queries)==16,'SLICE_QUERY_COUNT')
        result[role]=dict(query_frames=queries,eligible_component_count=len(ctx.last_seen),
                          decoder_prefix_frames=limit,query_frame_count=len(queries))
        if role=='HTTP':result[role]['flags_strata_frames']=dict(http_strata)
        if role=='NORMAL':
            chosen_components=sorted(set(sorted(candidates)[:8])|set(sorted(k for k in candidates if protocols[k]==17)[:2]))
            refs=[f for key in chosen_components for f in candidates[key]]
            edge.frozen.require(first_udp_query is not None,'SLICE_NORMAL_UDP_QUERY')
            if first_udp_query not in queries:queries.append(first_udp_query)
            result[role]['query_frames']=queries
            result[role]['query_frame_count']=len(queries)
            result[role]['reference_frames']=refs
            result[role]['reference_components']=chosen_components
            result[role]['reference_protocols']={key:protocols[key] for key in chosen_components}
            edge.frozen.require(len(candidates)>=2 and len(refs)<=20,'SLICE_TWO_COMPONENT_BANK')
    result['elapsed_seconds']=time.monotonic()-started
    edge.write(output/'SLICE_FRAME_PLAN.json',result)
    return result


if __name__=='__main__':
    import sys
    value=plan(sys.argv[1]);print(json.dumps(value))
