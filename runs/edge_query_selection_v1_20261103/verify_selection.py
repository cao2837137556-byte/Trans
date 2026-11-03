"""Independent selected-endpoint integrity audit, with no model dependencies."""
from collections import Counter
from fractions import Fraction
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rank(salt, uid):
    return hashlib.sha256((salt+'|'+uid).encode()).hexdigest(),uid


def ratio(value):
    return Fraction(value['numerator'],value['denominator'])


def verify(folder):
    folder=Path(folder)
    root=Path(__file__).resolve().parents[2]
    seal=read(folder/'QUERY_SELECTION_SEAL.json')
    require(all(sha(folder.parent/name)==digest for name,digest in seal['selection_code_pins'].items()),
            'SELECTION_CODE_IDENTITY')
    for name,pin in seal['output_pins'].items():
        require((folder/name).stat().st_size==pin['bytes'] and sha(folder/name)==pin['sha256'],
                'OUTPUT_PIN:'+name)
    census=read(folder/'METADATA_CENSUS.json')
    plans=read(folder/'SELECTION_PLANS.json')
    counts=read(folder/'NORMAL_COMPONENT_COUNTS.json')
    normal=plans['NORMAL']
    require(sum(counts.values())==1220126,'NORMAL_POPULATION')
    require(normal['component_count']==len(counts),'COMPONENT_COUNT')
    if normal['branch']=='HASH_COMPONENT_FALLBACK':
        expected=set(sorted(counts,key=lambda g:rank(normal['salt'],g))[:normal['effective_budget']])
        require(set(normal['quotas'])==expected,'COMPONENT_HASH_BOUNDARY')
    audits={}
    all_uid=set()
    fields=('uid','frame','timestamp_ns','protocol','capture_id','component_id','tcp_flags','stratum','direction')
    for role in ('NORMAL','HTTP','UDP'):
        summary=seal['roles'][role]
        with gzip.open(folder/summary['selected_file'],'rt',encoding='utf-8') as f:
            rows=[json.loads(line) for line in f]
        uids=[r['uid'] for r in rows]
        require(uids==sorted(set(uids)),'SELECTED_ORDER_OR_DUPLICATES:'+role)
        require(not all_uid.intersection(uids),'CROSS_ROLE_UID_DUPLICATE')
        all_uid.update(uids)
        require(uids==(folder/summary['uid_file']).read_text(encoding='utf-8').splitlines(),'UID_LIST_JOIN:'+role)
        group=lambda r:r['component_id'] if role=='NORMAL' else r['stratum']
        actual=Counter(group(r) for r in rows)
        require(dict(actual)=={g:n for g,n in plans[role]['quotas'].items() if n},'QUOTA_COUNTS:'+role)
        thresholds={}
        chosen={r['uid']:r for r in rows}
        salt=plans[role]['salt']
        for r in rows:
            g=group(r)
            thresholds[g]=max(thresholds.get(g,('','')),rank(salt,r['uid']))
            n=counts[g] if role=='NORMAL' else census['roles'][role]['strata'][g]
            m=actual[g]
            inclusion=(Fraction(m,n) if role!='NORMAL' or normal['branch']=='B_RESIDUAL_CAPACITY'
                else Fraction(normal['selected_component_count'],normal['component_count']*n))
            require(ratio(r['weights']['row_inclusion_probability'])==inclusion and
                    ratio(r['weights']['population_expansion_weight'])==1/inclusion,
                    'INCLUSION_WEIGHT:'+r['uid'])
            require(r['use']=='QUERY' and r['source_role']==role and
                    r['source_sha256']==census['roles'][role]['raw_sha256'],'ROLE_IDENTITY')
        seen=set()
        candidate_count=0
        group_counts=Counter()
        time_blocks=Counter()
        capture_anchors={}
        population=read(root/'runs/edge_external_test1_engineering_v1_20261103/adapter/population_v1/POPULATION.json')
        card=read(root/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json')
        if role=='NORMAL':
            capture_anchors={x['capture_id']:x['min_ns'] for x in population['physical_logical_mapping'][role]}
        else:
            capture_anchors={'EDGE_'+role:card['labels'][role]['captured_interval_ns'][0]}
        metadata=folder/census['roles'][role]['metadata_file']
        require(sha(metadata)==census['roles'][role]['metadata_sha256'],'SPOOL_PIN:'+role)
        with gzip.open(metadata,'rt',encoding='utf-8',newline='') as f:
            for item in csv.DictReader(f,delimiter='\t'):
                candidate_count+=1
                g=group(item)
                group_counts[g]+=1
                time_blocks[item['capture_id'],(int(item['timestamp_ns'])-capture_anchors[item['capture_id']])//60_000_000_000]+=1
                if g not in thresholds:
                    continue
                if rank(salt,item['uid'])<=thresholds[g]:
                    require(item['uid'] in chosen,'OMITTED_SMALLER_HASH:'+role)
                if item['uid'] in chosen:
                    require(item['uid'] not in seen,'DUPLICATE_SPOOL_UID')
                    expected=chosen[item['uid']]
                    require(all(str(expected[k])==item[k] for k in fields),'SELECTED_METADATA_JOIN')
                    seen.add(item['uid'])
        require(len(seen)==len(rows),'SELECTED_NOT_IN_POPULATION')
        require(candidate_count==summary['population_count'],'CANDIDATE_COUNT:'+role)
        expected_groups=counts if role=='NORMAL' else census['roles'][role]['strata']
        require(dict(group_counts)==expected_groups,'FULL_GROUP_POPULATION:'+role)
        audits[role]=dict(candidate_count=candidate_count,selected_rows=len(rows),
                         full_population_hash_boundary_checked=True,
                         metadata_and_uid_joins=True,inclusion_weights=True,
                         complete_group_population_recount=True,
                         population_60s_blocks=[dict(capture_id=capture,block_index=block,population=n)
                             for (capture,block),n in sorted(time_blocks.items())])
    refs=set((folder/plans['reference']['ordered_uid_file']).read_text(encoding='utf-8').splitlines())
    require(len(refs)==4124 and not refs&all_uid,'REFERENCE_QUERY_OVERLAP')
    oldseal=read(root/'runs/edge_external_test1_engineering_v1_20261103/adapter/population_sealed_v1/POPULATION_SEAL.json')
    dense=root/'runs/edge_external_test1_engineering_v1_20261103/adapter/population_v1/DENSE_REFERENCE_PLAN.json'
    require(sha(dense)==oldseal['references']['original_dense_plan_sha256'],'ORIGINAL_REFERENCE_PLAN_PIN')
    require(refs==set(read(dense)['selected_uids']),'ORIGINAL_REFERENCE_UIDS')
    original_refs=root/seal['references']['source_path']
    sealed_refs=root/'runs/edge_external_test1_engineering_v1_20261103/adapter/population_sealed_v1/REFERENCE_ROWS.jsonl.gz'
    require(sha(sealed_refs)==oldseal['references']['reference_rows_sha256'],'ORIGINAL_SEALED_REFERENCE_BYTES')
    with gzip.open(original_refs,'rt',encoding='utf-8') as a,gzip.open(sealed_refs,'rt',encoding='utf-8') as b:
        original_rows=[dict(json.loads(line),scenario='NORMAL') for line in a]
        sealed_rows=[json.loads(line) for line in b]
    require(original_rows==sealed_rows,'ORIGINAL_REFERENCE_METADATA')
    require(seal['selected_query_rows']==len(all_uid)==60000,'BASE_SELECTED_QUERY_TOTAL')
    require(seal['total_logical_encoding_rows']==len(all_uid)+len(refs)==64124,'ENCODING_ROWS')
    return dict(status='PASS_REAL_METADATA_SELECTION_AUDIT',roles=audits,
                selected_queries=len(all_uid),reference_rows=len(refs),
                model_forwards=0,external_quality_evaluations=0,
                selector_reexecuted=False,selection_seal_sha256=sha(folder/'QUERY_SELECTION_SEAL.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args()
    result=verify(args.folder)
    path=Path(args.folder)/'VERIFICATION.json'
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    path.with_name(path.name+'.sha256').write_text(sha(path)+'  '+path.name+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','selected_queries','reference_rows','selection_seal_sha256')},indent=2))
