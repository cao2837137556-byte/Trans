"""Describe saved D2 traces only; no distances, hypothetical scoring or tuning."""
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
OUT=HERE/'output'


def flags(q):return sum((1<<i) for i in range(9) if q[i+1]==1)
def quantile(values):return np.quantile(values,[0,.25,.5,.75,1]).tolist() if values else []


def describe(rr):
    pairs=[r['neighbors'] for r in rr if len(r['neighbors'])==2]
    near_ports=Counter();same_peer_port_change=0;same_ips=0
    spans=[];dz_block=dq_block=both_block=0;limit_z=limit_q=0
    for pair in pairs:
        a,b=(x['reference']['canonical_key'] for x in pair)
        ea,eb=set(map(tuple,a[1:])),set(map(tuple,b[1:]))
        common=ea&eb
        pa,pb={x[1] for x in ea},{x[1] for x in eb}
        near_ports.update(pa&pb)
        if {x[0] for x in ea}=={x[0] for x in eb}:same_ips+=1
        if len(common)==1:
            aa=next(iter(ea-common));bb=next(iter(eb-common))
            if aa[0]==bb[0] and aa[1]!=bb[1]:same_peer_port_change+=1
        spans.append(abs(pair[0]['reference']['timestamp']-pair[1]['reference']['timestamp']))
        z=max(x['dz_over_rho'] for x in pair);q=max(x['dq_over_rho'] for x in pair)
        if z>=1:dz_block+=1
        if q>=1:dq_block+=1
        if z>=1 and q>=1:both_block+=1
        if z>=q:limit_z+=1
        else:limit_q+=1
    return dict(rows=len(rr),eligible=sum(r['trace']['eligible'] for r in rr),
        support_quantiles=quantile([r['trace']['support'] for r in rr]),
        query_flags=dict(Counter(str(flags(r['query_q14'])) for r in rr)),
        query_context_direction_bit=dict(Counter(str(r['query_q14'][13]) for r in rr)),
        matched_pair_sources=dict(Counter('+'.join(sorted(x['source'] for x in p)) for p in pairs)),
        matched_pair_flags=dict(Counter('+'.join(map(str,sorted(flags(x['q14']) for x in p))) for p in pairs)),
        matched_pair_both_syn_no_ack=sum(all(flags(x['q14'])&2 and not flags(x['q14'])&16 for x in p) for p in pairs),
        same_two_endpoint_IPs=same_ips,one_endpoint_same_other_IP_same_only_port_changes=same_peer_port_change,
        common_port_numbers=dict(near_ports),reference_pair_time_gap_seconds_quantiles=quantile(spans),
        joint_pair_z_radius_blocks=dz_block,joint_pair_q_radius_blocks=dq_block,both_radius_blocks=both_block,
        joint_pair_limiter_z=limit_z,joint_pair_limiter_q=limit_q,
        z_radius_blocked_reference_sources=dict(Counter(x['source'] for p in pairs for x in p if x['dz_over_rho']>=1)),
        q_radius_blocked_reference_sources=dict(Counter(x['source'] for p in pairs for x in p if x['dq_over_rho']>=1)),
        source_unique_refs=dict(Counter(k for k,u in {(x['source'],x['reference']['uid']) for p in pairs for x in p})),
        withdrawn_by_head={s:sum(r['base'][j] and not r['corrected'][j] for r in rr)
                           for j,s in enumerate(('27','127','227','ensemble'))},
        normal_query_ensemble_fp=sum(r['query']['label']==0 and r['corrected'][3] for r in rr))


def main():
    status=json.loads((OUT/'STATUS.json').read_text())
    assert status['status']=='COMPLETE_ALL_REPLAY_CHECKS_PASSED'
    groups=defaultdict(list)
    with gzip.open(OUT/'NEIGHBORS.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line);q=r['query']
            device=q.get('display_name',q['device'])
            groups[r['cohort']+'|'+device].append(r)
            if r['cohort']=='P1_WITHDRAWN' and q.get('annotation_id'):
                groups['ATTACK_WITHDRAWN|'+q['annotation_id']].append(r)
            if r['cohort']=='P3_HEIM_NORMAL':
                name='HEIM_TCP_RESIDUAL' if q['protocol']==6 and r['corrected'][3] else 'HEIM_TCP_PASSED' if q['protocol']==6 else 'HEIM_UDP_RESIDUAL'
                groups[name].append(r)
    result={k:describe(v) for k,v in groups.items()}
    (OUT/'TRACE_SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    examples={}
    for name in ('ATTACK_WITHDRAWN|annotations/00166cab6b88.csv:4','HEIM_TCP_RESIDUAL','P4_WEMO_POWER_RESIDUAL|WEMO Power Switch'):
        candidates=groups.get(name,[])
        if not candidates:continue
        r=min(candidates,key=lambda x:x['query']['uid'])
        examples[name]=dict(uid=r['query']['uid'],query_flags=flags(r['query_q14']),
            support=r['trace']['support'],second_joint=r['trace']['second_joint'],
            neighbors=[dict(uid=n['reference']['uid'],canonical_key=n['reference']['canonical_key'],
                            source=n['source'],timestamp=n['reference']['timestamp'],flags=flags(n['q14']),
                            dz_over_rho=n['dz_over_rho'],dq_over_rho=n['dq_over_rho']) for n in r['neighbors']])
    (OUT/'TRACE_EXAMPLES.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name,r in result.items():
        print(json.dumps(dict(group=name,**{k:r[k] for k in ('rows','support_quantiles','matched_pair_both_syn_no_ack',
                'same_two_endpoint_IPs','one_endpoint_same_other_IP_same_only_port_changes','joint_pair_z_radius_blocks',
                'joint_pair_q_radius_blocks','joint_pair_limiter_z','joint_pair_limiter_q')}),ensure_ascii=False))


if __name__=='__main__':main()
