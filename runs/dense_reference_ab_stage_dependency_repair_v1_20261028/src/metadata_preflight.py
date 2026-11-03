"""Read-only identity/q14/overlap gate; never compute E3/support/score/CAL."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import importlib
import json
from pathlib import Path
import sys

import numpy as np

REPAIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPAIR/'bootstrap'))
from repair_runtime import install, require, sha

OLD_PROJECT='/public/home/jiangxinwei.zr/work/paper04/'
OLD_SCIENCE=OLD_PROJECT+'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/'
LOCAL_PROJECT='D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/'
LOCAL_SCIENCE=LOCAL_PROJECT+'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027/evidence179602/science/'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def forbidden(*args,**kwargs):
    raise RuntimeError('METADATA_ONLY_FORBIDS_SUPPORT_DISTANCE_E3_SCORE_CAL')


def install_metadata_guards(core,budget):
    core.ReferenceBank.__init__=forbidden
    core.ReferenceBank.own=forbidden
    core.ReferenceBank.matrix=forbidden
    core.ReferenceBank._evaluate_group=forbidden
    core._second_distinct=forbidden
    core._unit=forbidden
    budget.prepare_budget_calibration=forbidden
    budget.select_budget_lambda=forbidden


class Pins:
    def __init__(self,project,science):
        self.project,self.science=Path(project).resolve(),Path(science).resolve()
        self.checked={}

    def resolve(self,value):
        # Exact registered prefixes only. No glob, basename or workspace search.
        for prefix in (OLD_SCIENCE,LOCAL_SCIENCE):
            if value.startswith(prefix):
                return self.science/value[len(prefix):]
        for prefix in (OLD_PROJECT,LOCAL_PROJECT):
            if value.startswith(prefix):
                return self.project/value[len(prefix):]
        require(not Path(value).is_absolute() and ':' not in value and '..' not in Path(value).parts,
                'UNREGISTERED_PIN_PATH:'+value)
        return self.project/value

    def pin(self,spec):
        path=self.resolve(spec['path']).resolve()
        require(path.is_relative_to(self.project) or path.is_relative_to(self.science),
                'PIN_OUTSIDE_EXPLICIT_ROOTS')
        require(path.is_file(),'MISSING_PIN:'+str(path))
        expected=spec['sha256']
        require(len(expected)==64,'PIN_SHA_SCHEMA')
        if path not in self.checked:
            require(sha(path)==expected,'PIN_SHA256:'+str(path))
            self.checked[path]=expected
        require(self.checked[path]==expected,'CONTRADICTORY_PIN')
        if 'bytes' in spec: require(path.stat().st_size==spec['bytes'],'PIN_BYTES')
        return path

    def source_seal_pin(self,original,digest):
        primary=self.resolve(original)
        # Accepted local retrieval has no readonly_view; these exact canonical
        # aliases preserve the original seal bytes and are SHA checked.
        candidates=[primary]
        if original.startswith(OLD_SCIENCE+'readonly_view/'):
            candidates.append(self.project/original[len(OLD_SCIENCE+'readonly_view/'):])
        path=next((p for p in candidates if p.is_file()),None)
        require(path is not None,'MISSING_SOURCE_SEAL_PIN:'+original)
        require(path.resolve().is_relative_to(self.project) or path.resolve().is_relative_to(self.science),
                'SOURCE_SEAL_ALIAS_OUTSIDE_ROOTS')
        require(sha(path)==digest,'SOURCE_SEAL_SHA256:'+original)
        self.checked[path.resolve()]=digest
        return path


def all_pins(value):
    if isinstance(value,dict):
        if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):
            yield value
        for child in value.values(): yield from all_pins(child)
    elif isinstance(value,list):
        for child in value: yield from all_pins(child)


def rows(path):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def check_dataset(pins,spec,core,reference):
    metadata=rows(pins.pin(spec['rows']))
    core._rows(metadata,reference=reference)
    uids=[r['uid'] for r in metadata]
    digest=core._uid_hash(uids)
    require(spec['feature_uid_sha256']==digest==spec['q_uid_sha256'],'ORDERED_UID_SHA')
    for field in ('feature_uids','q_uids'):
        if field in spec: require(read(pins.pin(spec[field]))==uids,'ORDERED_UID_JOIN:'+field)
    path=pins.pin(spec['q14'])
    if path.suffix=='.npz':
        # Never access the E3 or score members of these NPZ files.
        with np.load(path,allow_pickle=False) as archive:
            require(archive[spec['q14'].get('uid_key',spec.get('uid_key','uid'))].tolist()==uids,
                    'REFERENCE_NPZ_UID_JOIN')
            q14=archive[spec['q14'].get('key','q14')]
    else:
        q14=np.load(path,mmap_mode='r',allow_pickle=False)
    require(q14.shape==(len(metadata),14) and q14.dtype.kind in 'fiu','Q14_SHAPE_DTYPE')
    require(np.isfinite(q14).all() and np.all((q14>=0)&(q14<=1)),'Q14_FINITE_RANGE')
    return metadata,dict(rows=len(metadata),ordered_uid_sha256=digest,q14_shape=list(q14.shape),
                         q14_dtype=str(q14.dtype),q14_finite_range_pass=True)


def roster(metadata):
    groups=defaultdict(list)
    for r in metadata: groups[(r['partition'],r['device'],r['protocol'])].append(r)
    return [dict(partition=k[0],device=k[1],protocol=k[2],rows=len(values),
        distinct_components=len({r['component_id'] for r in values}))
        for k,values in sorted(groups.items())]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',required=True)
    parser.add_argument('--science-root',required=True)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    output=Path(args.output).resolve()
    require(not output.exists(),'FRESH_METADATA_REPORT_REQUIRED')
    require(not output.is_relative_to(REPAIR),'METADATA_OUTPUT_OUTSIDE_SEALED_OVERLAY')
    closure=read(REPAIR/'DEPENDENCY_CLOSURE.json')
    manifest_path=Path(args.manifest).resolve()
    accepted_hashes={closure['config_files'][name]['sha256'] for name in
                     ('MATRIX_CANDIDATE_HPC.json','MATRIX_CANDIDATE_LOCAL.json')}
    require(sha(manifest_path) in accepted_hashes,'FROZEN_MATRIX_MANIFEST_REQUIRED')
    require(sha(REPAIR/'config/SOURCE_INPUT_SEAL.json')==
            closure['config_files']['SOURCE_INPUT_SEAL.json']['sha256'],'SOURCE_SEAL_BYTES')
    require(sha(REPAIR/'config/ACCEPTED_RESULT_MANIFEST.json')==
            closure['accepted_result_manifest_sha256'],'ACCEPTED_RESULT_MANIFEST_SHA')
    dependencies=install(REPAIR)
    loaded={name:importlib.import_module(name) for name in dependencies}
    for name,module in loaded.items():
        require(Path(module.__file__).resolve()==REPAIR/'vendor/ood'/(name+'.py'),
                'STRICT_FROZEN_MODULE_PATH:'+name)
    core,budget=loaded['constrained_onboarding_core_v3'],loaded['onboarding_budget_v1']
    install_metadata_guards(core,budget)
    overlap_check=loaded['causal_reference_overlap_v1'].require_prebank_history
    pins=Pins(args.project_root,args.science_root)
    manifest=read(manifest_path)
    require([p['pool_id'] for p in manifest['pools']]==['CIC_DEV','UNSW_DEV'],'EXACT_AB_POOLS')
    # Byte hashing E3 and score containers is input identity, never np.load.
    for spec in all_pins(manifest): pins.pin(spec)
    seal=read(REPAIR/'config/SOURCE_INPUT_SEAL.json')
    require(len(seal)==19,'EXACT_NINETEEN_SOURCE_SEAL_MEMBERS')
    seal_report=[dict(original_path=path,verified_path=str(pins.source_seal_pin(path,digest)),sha256=digest)
                 for path,digest in seal.items()]
    bank_reports=[]
    expected={('CIC_DEV','b2_bank'):(67,64),('CIC_DEV','dense_bank'):(8574,3334),
              ('UNSW_DEV','b2_bank'):(148,19),('UNSW_DEV','dense_bank'):(13247,1319)}
    total_queries=0
    for pool in manifest['pools']:
        queries,query_report=check_dataset(pins,pool['query'],core,False)
        require(len(queries)==pool['query_rows'],'QUERY_ROW_COUNT')
        total_queries+=len(queries)
        for name in ('b2_bank','dense_bank'):
            refs,ref_report=check_dataset(pins,pool[name],core,True)
            by_uid={r['uid']:r for r in refs}
            overlaps=[q for q in queries if q['uid'] in by_uid]
            for query in overlaps:
                requirement=overlap_check(query,by_uid[query['uid']])
                require(requirement['required_support']==0. and
                    requirement['required_behavior']=='EXACT_HEAD_FALLBACK','HISTORY_FALLBACK_INVARIANT')
            require((len(refs),len(overlaps))==expected[(pool['pool_id'],name)],'FROZEN_OVERLAP_COUNTS')
            bank_reports.append(dict(pool_id=pool['pool_id'],bank=name,query=query_report,
                reference=ref_report,overlapping_uids=len(overlaps),all_history_identities_pass=True,
                reference_roster=roster(refs)))
    require(total_queries==328202,'EXACT_AB_QUERY_COUNT')
    source_reports=[]
    source_b2_original=OLD_SCIENCE+'readonly_view/runs/diagnostics_d1_d2_v1_20261022/assets/reference_scores/SOURCE_REFS.jsonl.gz'
    source_dense_original=OLD_SCIENCE+'encode/banks/SOURCE_REFS/references.jsonl.gz'
    require(source_b2_original in seal and source_dense_original in seal,'SOURCE_REFERENCE_SEAL_MEMBERS_REQUIRED')
    source_b2_path=pins.source_seal_pin(source_b2_original,seal[source_b2_original])
    source_dense_path=pins.source_seal_pin(source_dense_original,seal[source_dense_original])
    for name,path,expected_rows in (
        ('SOURCE_B2',source_b2_path,104),
        ('SOURCE_DENSE',source_dense_path,4728)):
        source=rows(path)
        core._rows(source,reference=True)
        require(len(source)==expected_rows,'SOURCE_REFERENCE_ROW_COUNT')
        source_reports.append(dict(name=name,rows=len(source),roster=roster(source)))
    result=dict(schema='paper04-ab-dependency-metadata-preflight-v1',status='PASS_METADATA_ONLY',
        created_utc=datetime.now(timezone.utc).isoformat(),matrix_manifest_sha256=sha(manifest_path),
        source_seal_sha256=sha(REPAIR/'config/SOURCE_INPUT_SEAL.json'),
        source_seal_files_verified=len(seal_report),source_seal_aliases=seal_report,
        modules={name:dict(path=str(Path(module.__file__).resolve()),
                          sha256=dependencies[name]['sha256']) for name,module in loaded.items()},
        query_rows=total_queries,banks=bank_reports,source_banks=source_reports,
        distinct_pinned_files=len(pins.checked),input_files=[dict(path=str(path),sha256=digest)
            for path,digest in sorted(pins.checked.items(),key=lambda pair:str(pair[0]))],
        target_score_arrays_opened=0,e3_arrays_opened=0,e3_arithmetic_calls=0,
        reference_bank_constructions=0,distances_computed=0,support_calls=0,
        score_evaluations=0,model_forwards=0,training_updates=0,new_encoding_rows=0,
        new_CAL_runs=0,scheduler_submissions=0,scientific_retries=0,
        metadata_guards_active=True,scientific_result=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=result['status'],query_rows=total_queries,
        source_seal_files_verified=len(seal_report),banks=[dict(pool=b['pool_id'],bank=b['bank'],
        refs=b['reference']['rows'],overlap=b['overlapping_uids']) for b in bank_reports],
        output=str(output))))


if __name__=='__main__': main()
