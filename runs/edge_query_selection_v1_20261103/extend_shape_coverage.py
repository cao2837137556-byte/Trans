"""Derive full+target shape union from sealed census; never reads PCAP/model."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    path.with_name(path.name+'.sha256').write_text(sha(path)+'  '+path.name+'\n', encoding='utf-8')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def union_representatives(census):
    by_shape = {}
    # Prefer actual selected-target representatives when both sources cover a
    # shape. Full-only missing shapes use the frozen census's original frame.
    for domain in ('target', 'full'):
        for rep in census[domain+'_requirements']['representatives']:
            key = tuple(rep['shape'])
            if key not in by_shape:
                by_shape[key] = dict(rep, requirement_domains=[])
            by_shape[key]['requirement_domains'].append(domain)
    return [by_shape[key] for key in sorted(by_shape)]


def derive(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = HERE/'shapes_v2/SHAPE_CENSUS.json'
    parent = HERE/'shapes_v2/SLICE_CARD.json'
    census, card = read(source), read(parent)
    summary = read(HERE/'shapes_v2/SUMMARY.json')
    require(sha(source) == summary['census_sha256'] and sha(parent) == summary['slice_sha256'],
            'SEALED_CENSUS_OR_PARENT_CARD_CHANGED')
    seal = read(HERE/'seal20k/QUERY_SELECTION_SEAL.json')
    require(census['selection_seal_sha256'] == sha(HERE/'seal20k/QUERY_SELECTION_SEAL.json'), 'SELECTION_SEAL_PIN')
    selected, ref_frames = {}, set()
    for role in ('NORMAL','HTTP','UDP'):
        item = seal['roles'][role]
        path = HERE/'seal20k'/item['selected_file']
        require(sha(path) == item['selected_sha256'], 'SELECTED_ROWS_PIN')
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            selected[role] = {int(r['frame']) for r in map(json.loads,stream)}
    refs = ROOT/seal['references']['source_path']
    require(sha(refs) == seal['references']['source_sha256'], 'REFERENCE_PIN')
    with gzip.open(refs, 'rt', encoding='utf-8') as stream:
        ref_frames = {int(r['frame']) for r in map(json.loads,stream)}
    selected['NORMAL'] |= ref_frames
    population_path = ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/population_v1/POPULATION.json'
    population = read(population_path)
    require(census['population_sha256'] == sha(population_path), 'POPULATION_PIN')
    masks = {}
    for role in ('NORMAL','HTTP','UDP'):
        info = population['roles'][role]
        path = population_path.parent/info['mask_file']
        require(sha(path) == info['mask_sha256'], 'MASK_PIN')
        masks[role] = path.read_bytes()
    reps = union_representatives(census)
    slices = {r['role']:copy.deepcopy(r) for r in card['slices']}
    new_points = []
    for rep in reps:
        role, frame = rep['role'], rep['frame']
        truth, reason = masks[role][2*(frame-1):2*frame]
        require(truth and reason == population['mask_schema']['second_byte']['VALID'], 'FULL_REP_NOT_LEGAL')
        is_target = frame in selected[role]
        is_ref = role == 'NORMAL' and frame in ref_frames
        raw_sha = population['inputs'][role]['sha256']
        uid = hashlib.sha256(json.dumps([raw_sha,frame,'dc:a6:32:fb:69:b5'],separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        rep.update(uid=uid, is_selected_target=is_target, is_reference=is_ref,
            legal_population_mask_code=truth,
            engineering_scope='SELECTED_TARGET_SHAPE_FIXTURE' if is_target else 'ENGINEERING_ONLY_FULL_POPULATION_SHAPE_COVERAGE',
            scientific_query_population_changed=False)
        if frame not in slices[role]['frames']:
            slices[role]['frames'].append(frame)
            new_points.append(copy.deepcopy(rep))
        if is_ref and frame not in slices[role]['reference_frames']:
            slices[role]['reference_frames'].append(frame)
    for row in slices.values():
        row['frames'] = sorted(set(row['frames']))
        row['reference_frames'] = sorted(set(row['reference_frames']))
    rows = sum(len(r['frames']) for r in slices.values())
    require(rows+len(reps) <= 100, 'UNION_SLICE_PLUS_PROBES_EXCEEDS_100')
    source_shapes = {tuple(r['shape']) for domain in ('target','full')
                     for r in census[domain+'_requirements']['representatives']}
    require(source_shapes == {tuple(r['shape']) for r in reps}, 'UNION_SHAPE_COVERAGE')
    coverage = dict(schema='EDGE_FULL_AND_TARGET_SHAPE_COVERAGE_DERIVATION_V1', status='PASS_METADATA_ONLY',
        source_census_path=source.relative_to(ROOT).as_posix(), source_census_sha256=sha(source),
        parent_slice_path=parent.relative_to(ROOT).as_posix(), parent_slice_sha256=sha(parent),
        selection_seal_sha256=sha(HERE/'seal20k/QUERY_SELECTION_SEAL.json'),
        required=dict(scope='FULL_AND_SELECTED_TARGET_TOP10_AND_EXTREMES_UNION', representatives=reps),
        added_engineering_points=new_points, base_rows=rows, singleton_probes=len(reps),
        total_logical_with_probes=rows+len(reps), raw_pcap_scans=0, model_forwards=0,
        numerical_snapshots=0, external_quality_evaluations=0,
        original_v2_preserved=True, original_scientific_population_preserved=True,
        source_script_sha256=sha(Path(__file__)))
    write(output/'SHAPE_COVERAGE.json', coverage)
    updated = copy.deepcopy(card)
    updated.update(slices=[slices[r] for r in ('NORMAL','HTTP','UDP')],
        plan_path=(output/'SHAPE_COVERAGE.json').relative_to(ROOT).as_posix(),
        plan_sha256=sha(output/'SHAPE_COVERAGE.json'),
        parent_slice_path=parent.relative_to(ROOT).as_posix(), parent_slice_sha256=sha(parent))
    updated['shape_expansion'].update(source='Frozen full population and selected-target shape census union; no new PCAP pass',
        required=coverage['required'], added_full_population_shape_points=new_points)
    write(output/'SLICE_CARD.json', updated)
    verification = dict(status='PASS_METADATA_ONLY', source_shapes=len(source_shapes), representative_count=len(reps),
        expanded_slice_unique_rows=rows, additional_singleton_logical_probes=len(reps),
        total_logical_rows_with_probes=rows+len(reps), full_population_count=sum(census['full_shape_counts'].values()),
        target_encoding_count=sum(census['target_shape_counts'].values()),
        all_union_shapes_covered=True, representatives_legal_under_original_mask=True,
        nonsampled_engineering_points=sum(not r['is_selected_target'] for r in new_points),
        original_scientific_query_population_unchanged=True, original_reference_bank_unchanged=True,
        coverage_sha256=sha(output/'SHAPE_COVERAGE.json'), slice_sha256=sha(output/'SLICE_CARD.json'),
        raw_pcap_scans=0, model_forwards=0, numerical_snapshots=0)
    write(output/'VERIFICATION.json',verification)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(derive(Path(args.output).resolve()),indent=2))
