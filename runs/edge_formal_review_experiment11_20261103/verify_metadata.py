"""Independent exact-rational checks on existing sealed metadata only."""
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'runs/edge_formal_execution_v1_20261103'
SEAL=ROOT/'runs/edge_query_selection_v1_20261103/seal20k'


def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as s:
        for b in iter(lambda:s.read(4*1024**2),b''): h.update(b)
    return h.hexdigest()
def ratio(v): return Fraction(v['numerator'],v['denominator'])
def rows(p):
    with gzip.open(p,'rt',encoding='utf-8') as s: return [json.loads(x) for x in s]


def main():
    seal=read(SEAL/'QUERY_SELECTION_SEAL.json')
    population=read(SOURCE/'POPULATION_TEMPORAL_CENSUS.json')
    normal_counts=Counter()
    for group in population['groups']:
        if group['source_role']=='NORMAL':
            normal_counts.update(group['component_counts'])
    refs=rows(ROOT/seal['references']['source_path'])
    assert sha(ROOT/seal['references']['source_path'])==seal['references']['source_sha256']
    uids={r['uid'] for r in refs}; assert len(uids)==len(refs)==4124
    facts={}
    for role,spec in seal['roles'].items():
        path=SEAL/spec['selected_file']; assert sha(path)==spec['selected_sha256']
        rr=rows(path); assert len(rr)==spec['selected_rows']==20000
        assert len({r['uid'] for r in rr})==len(rr)
        assert not uids & {r['uid'] for r in rr}
        uids.update(r['uid'] for r in rr)
        counts=Counter(r['component_id'] if role=='NORMAL' else r['stratum'] for r in rr)
        expanded=Fraction(); component=Fraction()
        for r in rr:
            key=r['component_id'] if role=='NORMAL' else r['stratum']
            n=normal_counts[key] if role=='NORMAL' else population['roles'][role]['strata'][key]
            expected=Fraction(n,counts[key]); w=r['weights']
            assert ratio(w['population_expansion_weight'])==expected
            assert ratio(w['row_inclusion_probability'])==1/expected
            expanded+=expected
            if role=='NORMAL':
                c=Fraction(1,len(normal_counts)*counts[key])
                assert ratio(w['component_metric_weight'])==c
                component+=c
        assert expanded==spec['population_count']==population['roles'][role]['population_count']
        if role=='NORMAL':
            assert set(counts)==set(normal_counts) and len(counts)==17025 and component==1
        facts[role]=dict(rows=len(rr),population=int(expanded),
                         normal_components=len(counts) if role=='NORMAL' else None,
                         exact_rational_weights_verified=True)
    manifest=read(SOURCE/'DELIVERY_DELTA_MANIFEST.json')
    archive=ROOT/manifest['archive']['path']
    assert archive.stat().st_size==manifest['archive']['bytes'] and sha(archive)==manifest['archive']['sha256']
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        assert len(members)==len(manifest['files']) and {m.name for m in members}==set(manifest['files'])
        for m in members:
            b=tar.extractfile(m).read(); spec=manifest['files'][m.name]
            assert len(b)==spec['bytes'] and hashlib.sha256(b).hexdigest()==spec['sha256']
            assert sha(ROOT/m.name)==spec['sha256']
    result=dict(status='PASS_METADATA_AND_EXISTING_DELTA',roles=facts,reference_rows=4124,
                all_disjoint_logical_uids=len(uids),delta_members=len(members),
                delta_sha256=sha(archive),models_loaded=0,external_predictions_read=0,
                raw_packets_read=0,cloud_jobs_submitted=0)
    target=HERE/'METADATA_AND_DELTA_VERIFICATION.json'
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
