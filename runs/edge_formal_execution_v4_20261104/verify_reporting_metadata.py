"""Verify reporting joins/denominators using metadata only, never predictions."""
from collections import Counter,defaultdict
from fractions import Fraction
import gzip
import json
from pathlib import Path

from build_population_census import read,sha
from reporting import BLOCK_NS,ROLES,_population,fraction,group_key,need

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SEAL=ROOT/'runs/edge_query_selection_v1_20261103/seal20k'


def verify():
    population_path=HERE/'POPULATION_TEMPORAL_CENSUS.json'
    population=read(population_path)
    groups=_population(population)
    seal=read(SEAL/'QUERY_SELECTION_SEAL.json')
    all_uids=set()
    component_weights=defaultdict(Fraction)
    selected_blocks=Counter()
    facts={}
    pins={str(population_path.relative_to(ROOT)):sha(population_path),
          str((SEAL/'QUERY_SELECTION_SEAL.json').relative_to(ROOT)):sha(SEAL/'QUERY_SELECTION_SEAL.json')}
    for role in ROLES:
        spec=seal['roles'][role]
        path=SEAL/spec['selected_file']
        need(sha(path)==spec['selected_sha256'],'SELECTED_QUERY_SHA:'+role)
        pins[str(path.relative_to(ROOT))]=spec['selected_sha256']
        uids=[]
        expansion=Fraction()
        for line in gzip.open(path,'rt',encoding='utf-8'):
            row=json.loads(line)
            need(row['source_role']==role and row['use']=='QUERY','SELECTED_ROLE_USE')
            uid=row['uid']
            need(uid not in all_uids,'DUPLICATE_SELECTED_UID')
            all_uids.add(uid)
            uids.append(uid)
            group=groups[group_key(row)]
            block=(row['timestamp_ns']-group['anchor_ns'])//BLOCK_NS
            need(group['block_population_counts'].get(str(block),0)>0,'SELECTED_POPULATION_BLOCK')
            selected_blocks[group_key(row)+(block,)]+=1
            weight=fraction(row['weights']['population_expansion_weight'])
            inclusion=fraction(row['weights']['row_inclusion_probability'])
            need(weight*inclusion==1,'INVERSE_INCLUSION')
            expansion+=weight
            if role=='NORMAL':
                need(row['component_id'] in group['component_counts'],'NORMAL_COMPONENT_POPULATION')
                component_weights[row['component_id']]+=fraction(row['weights']['component_metric_weight'])
        need(uids==(SEAL/spec['uid_file']).read_text(encoding='utf-8').splitlines(),'EXACT_SELECTED_UID_ORDER')
        need(len(uids)==spec['selected_rows'],'SELECTED_ROLE_COUNT')
        need(population['roles'][role]['population_count']==spec['population_count'],'SEAL_POPULATION_COUNT')
        if role!='NORMAL' or spec['branch']=='B_RESIDUAL_CAPACITY':
            need(expansion==spec['population_count'],'EXACT_EXPANDED_POPULATION_COUNT')
        facts[role]=dict(selected_rows=len(uids),known_population_count=spec['population_count'],
                         expanded_selected_count=dict(numerator=expansion.numerator,denominator=expansion.denominator))
    normal=seal['roles']['NORMAL']
    need(len(component_weights)==normal['selected_components'],'NORMAL_COMPONENT_COVERAGE')
    need(sum(component_weights.values(),Fraction())==1,'NORMAL_COMPONENT_MASS')
    need(all(w==Fraction(1,normal['selected_components']) for w in component_weights.values()),
         'EQUAL_NORMAL_COMPONENT_MASS')
    ref_path=SEAL/seal['references']['ordered_uid_file']
    need(sha(ref_path)==seal['references']['ordered_uid_sha256'],'REFERENCE_UID_PIN')
    refs=set(ref_path.read_text(encoding='utf-8').splitlines())
    need(not(all_uids & refs),'REFERENCE_QUERY_OVERLAP')
    pins[str(ref_path.relative_to(ROOT))]=sha(ref_path)
    group_facts=[]
    for key,g in groups.items():
        blocks=list(map(int,g['block_population_counts']))
        selected_count=sum(selected_blocks[key+(b,)] for b in blocks)
        group_facts.append(dict(source_role=key[0],capture_id=key[1],scenario=key[2],
            population_blocks=len(blocks),zero_eligible_blocks=sum(v==0 for v in g['block_population_counts'].values()),
            selected_rows=selected_count,zero_selected_blocks=sum(selected_blocks[key+(b,)]==0 for b in blocks)))
    result=dict(status='PASS_REAL_SELECTED_METADATA_JOIN_AND_DENOMINATORS',roles=facts,
        normal_selected_components=len(component_weights),reference_query_overlap=0,
        groups=group_facts,input_pins=pins,model_calls=0,external_quality_evaluations=0,
        raw_packets_read=False,cloud_jobs_submitted=0)
    (HERE/'STATISTICS_METADATA_VERIFICATION.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],roles=facts,groups=group_facts)))
    return result


if __name__=='__main__':
    verify()
