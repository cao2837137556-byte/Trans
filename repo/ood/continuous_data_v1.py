"""Pinned metadata/cache input, never sample-selection or label-policy changes."""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import sqlite3
import numpy as np
import continuous_common_v1 as c
from legacy_qref_data_v1 import split, class_weights, validate_controls, metadata_valid


def save_rows(path, values):
    with gzip.open(path, 'wt', encoding='utf-8', newline='\n') as stream:
        for r in values:
            stream.write(json.dumps(r, separators=(',', ':'))+'\n')


def load_inputs(root, runtime, design, out):
    out = Path(out); out.mkdir(exist_ok=False)
    cache = Path(runtime['source_cache']); ext = Path(runtime['external_run'])
    receipt = c.read(cache/'cache.json')
    c.require(receipt['status'] == 'COMPLETE' and receipt['stage'] == 'LEARN_DEV' and not receipt['synthetic_only'], 'SOURCE_CACHE_NOT_COMPLETE')
    metadata, old = {}, {}
    source_catalog = c.read(Path(root)/'frozen/capture_catalog.json')
    raw_inventory = c.read(Path(root)/'frozen/source_input_inventory.json')
    raw_by = {x['capture_id']: x for x in raw_inventory['assets'] if x['kind'] == 'raw_capture'}
    for role, spec in design['data']['source_old_cache_pins'].items():
        rr = list(c.rows(c.pin(cache/spec['metadata'], spec['metadata_sha256'])))
        metadata_valid(rr, {'LEARN','DEV'} if role=='REFERENCE' else {role}, role=='REFERENCE')
        c.require(len(rr) == spec['rows'] and c.uid_sha(r['uid'] for r in rr) == spec['uid_sha256'], 'SOURCE_UID:'+role)
        feature = c.pin(cache/spec['features'], spec['features_sha256'])
        arr = np.load(feature, mmap_mode='r', allow_pickle=False)
        c.require(arr.shape == (len(rr), 768) and arr.dtype == np.float32, 'SOURCE_FEATURE_SCHEMA')
        for start in range(0, len(arr), 4096): c.require(np.isfinite(arr[start:start+4096]).all(), 'OLD_FEATURE_NONFINITE')
        original = design['data']['source_manifests'][role]
        source = Path(runtime['source_inputs'])/original['path'].replace('\\', '/')
        raw_rows = (r for r in c.rows(c.pin(source, original['sha256'])) if role != 'REFERENCE' or r['partition'] in {'LEARN', 'DEV'})
        count = 0
        for count, r in enumerate(raw_rows, 1):
            c.require(count <= len(rr) and all(rr[count-1].get(k) == v for k, v in r.items()), 'SOURCE_MANIFEST_JOIN')
        c.require(count == len(rr), 'SOURCE_MANIFEST_COUNT')
        name = {'LEARN':'LEARN', 'DEV':'CIC_DEV', 'REFERENCE':'SOURCE_REFS'}[role]
        metadata[name] = rr; old[name] = str(feature)
    source_refs = [r for r in metadata['SOURCE_REFS'] if r['partition'] == 'LEARN']
    roles = split(metadata['LEARN'], source_refs, design['data']['split_salt'])
    for role, ix in roles.items():
        identity = design['data']['fit_cal_identity'][role]
        c.require(len(ix) == identity['rows'] and c.uid_sha(metadata['LEARN'][int(i)]['uid'] for i in ix) == identity['uid_sha256'], 'SOURCE_SPLIT')
        for i in ix: metadata['LEARN'][int(i)]['fit_role'] = role
    # Resolve all reference denominators before spending any raw-decode/E3 work.
    source_groups=defaultdict(list)
    for r in source_refs: source_groups[(r['device'],r['protocol'])].append(r)
    for role,ix in roles.items():
        use=[int(i) for i in ix if len(source_groups.get((metadata['LEARN'][int(i)]['device'],metadata['LEARN'][int(i)]['protocol']),[]))>=2]
        identity=design['data']['fit_cal_identity'][role]
        c.require(len(use)==identity['eligible_rows'] and c.uid_sha(metadata['LEARN'][i]['uid'] for i in use)==identity['eligible_uid_sha256'],'EARLY_REFERENCE_ELIGIBILITY_'+role)
    pairs=0
    for i in roles['CAL']:
        r=metadata['LEARN'][int(i)]
        if r['label']!=1:continue
        banks=[rr for (_,protocol),rr in source_groups.items() if protocol==r['protocol'] and len(rr)>=2 and max(x['reference_end'] for x in rr)<r['timestamp']]
        c.require(banks,'EARLY_CAL_ATTACK_WITHOUT_BANK');pairs+=len(banks)
    c.require(pairs==design['data']['CAL']['attack_donor_pairs'],'EARLY_CAL_PAIR_COUNT')
    # Direct labels are frozen original metadata; no score-driven relabeling.
    ext_spec = c.read(Path(root)/'frozen/external_input_pins.json')
    for rel, spec in ext_spec.items():
        p = ext/rel; c.require(p.stat().st_size == spec['bytes'], 'EXTERNAL_BYTES')
        c.pin(p, spec['sha256'])
    metadata['UNSW_DEV'] = list(c.rows(ext/'runs/real_evaluation/manifests/queries.jsonl.gz'))
    metadata['UNSW_REFS'] = list(c.rows(ext/'runs/real_evaluation/manifests/references.jsonl.gz'))
    metadata_valid(metadata['UNSW_DEV'],{'EXTERNAL_ARCHIVAL_EVALUATION'})
    metadata_valid(metadata['UNSW_REFS'],{'EXTERNAL_ARCHIVAL_EVALUATION'},True)
    ext_uids = c.read(ext/'runs/real_evaluation/features/uids.json')
    combined = metadata['UNSW_DEV'] + metadata['UNSW_REFS']
    c.require(ext_uids == [r['uid'] for r in combined], 'EXTERNAL_FEATURE_UID_ORDER')
    arr = np.load(ext/'runs/real_evaluation/features/features.npy', mmap_mode='r', allow_pickle=False)
    c.require(arr.shape == (148408, 768) and arr.dtype == np.float32, 'EXTERNAL_FEATURE_SCHEMA')
    for start in range(0,len(arr),4096): c.require(np.isfinite(arr[start:start+4096]).all(), 'EXTERNAL_FEATURE_NONFINITE')
    old['UNSW_DEV'] = str(ext/'runs/real_evaluation/features/features.npy')
    expected = {'LEARN':766727, 'CIC_DEV':179886, 'SOURCE_REFS':179, 'UNSW_DEV':148316, 'UNSW_REFS':92}
    c.require({k: len(v) for k, v in metadata.items()} == expected, 'ALL_ROW_COUNTS')
    for role in ('CIC_DEV', 'UNSW_DEV'):
        rr = metadata[role]; census = design['data'][role]
        c.require(Counter(r['label'] for r in rr) == {0:census['normal'], 1:census['attack']}, 'POOL_LABEL_COUNTS')
    for label in (0, 1):
        rr = [r for r in metadata['CIC_DEV'] if r['label'] == label]
        c.require(np.allclose(class_weights(rr), [1/r['label_metric_weight_denominator'] for r in rr], atol=1e-15, rtol=0), 'CIC_METRIC_WEIGHT')
    # External weighted denominators are already bound by exact original manifest SHA.
    all_uids = [r['uid'] for rr in metadata.values() for r in rr]
    c.require(len(all_uids) == len(set(all_uids)) == design['data']['new_feature_rows'], 'GLOBAL_UID_OVERLAP')
    dependency_roles = defaultdict(set)
    for role, rr in metadata.items():
        for r in rr:
            key = (r['source_sha256'], r['session_id'])
            if role == 'LEARN': dependency_roles[key].add(r['fit_role'])
            elif role == 'SOURCE_REFS' and r['partition'] == 'LEARN': dependency_roles[key].add('FIT')
            else: dependency_roles[key].add(r['partition'])
    c.require(all(len(v) == 1 for v in dependency_roles.values()), 'CAUSAL_KEY_CROSS_ROLE')
    captures = {r['capture_id'] for rr in metadata.values() for r in rr}
    specs = []
    for spec in source_catalog:
        if spec['capture_id'] not in captures: continue
        a = raw_by[spec['capture_id']]
        c.require((spec['sha256'], spec['bytes']) == (a['sha256'], a['bytes']), 'SOURCE_RAW_IDENTITY')
        specs.append(dict(spec, path=str(Path(runtime['source_inputs'])/a['bundle_path'])))
    external_recipe = c.read(Path(root)/'frozen/external_recipe.json')
    for spec in external_recipe['sources']:
        specs.append(dict(spec, path=str(Path(runtime['external_raw'])/Path(spec['path']).name),
                          expected_packets=runtime['external_packet_counts'][spec['capture_id']], external=True))
    c.require({s['capture_id'] for s in specs} == captures, 'RAW_CATALOG_COVERAGE')
    verified_raw = {}
    for s in specs:
        p = Path(s['path']); c.require(p.stat().st_size == s['bytes'], 'RAW_BYTES')
        c.pin(p, s['sha256']); verified_raw[s['capture_id']] = dict(path=str(p), sha256=s['sha256'], bytes=s['bytes'])
    for role, rr in metadata.items(): save_rows(out/(role+'.jsonl.gz'), rr)
    for role, ix in roles.items(): c.save_arrays(out/(role+'.npz'), indices=ix)
    c.write(out/'raw_catalog.json', specs); c.write(out/'raw_verified.json', verified_raw)
    c.write(out/'old_features.json', old)
    # Original control plans preserved, no donor selection from new scores.
    recipe = c.read(Path(root)/'frozen/source_qref_recipe.json')
    validate_controls(metadata['CIC_DEV'], metadata['SOURCE_REFS'], recipe)
    cic_controls = recipe['evaluation']['controls']
    external_controls = []
    er = metadata['UNSW_REFS']
    for p in c.read(Path(root)/'frozen/external_controls.json')['controls']:
        qr = [r for r in metadata['UNSW_DEV'] if r['device'] == p['device_id'] and r['protocol'] == p['protocol']]
        item = dict(device=p['device_id'], protocol=p['protocol'], status='UNAVAILABLE',rows=len(qr))
        if p['status'] == 'PLANNED_MATCHED':
            own = sorted(r['uid'] for r in er if r['device'] == p['device_id'] and r['protocol'] == p['protocol'])[:p['count_each']]
            wrong = sorted(r['uid'] for r in er if r['device'] == p['donor_device_id'] and r['protocol'] == p['protocol'])[:p['count_each']]
            item.update(status='MATCHED', donor=p['donor_device_id'], count=p['count_each'], rows=len(qr),
                query_uid_sha256=c.uid_sha(r['uid'] for r in qr), correct_reference_uids=own, wrong_reference_uids=wrong)
        external_controls.append(item)
    c.write(out/'controls.json', dict(CIC_DEV=cic_controls, UNSW_DEV=external_controls))
    validate_controls(metadata['UNSW_DEV'],metadata['UNSW_REFS'],{'evaluation':{'controls':external_controls}})
    c.write(out/'receipt.json', dict(status='COMPLETE', rows=len(all_uids), role_counts=expected,
        metadata_uid_sha256={k:c.uid_sha(r['uid'] for r in rr) for k, rr in metadata.items()},
        design_digest=c.digest(design), raw_captures=len(specs), external_training=False))
    c.seal(out); c.verify(out)
    return metadata, specs


def old_tail_audit(metadata, feature_paths, out):
    """Required old LEARN/DEV audit piggybacks on P; saved features only."""
    answer = {}
    for role in ('LEARN', 'CIC_DEV'):
        array = np.load(feature_paths[role], mmap_mode='r', allow_pickle=False)
        groups = defaultdict(list)
        for i, r in enumerate(metadata[role]): groups[(r['device'], r['session_id'])].append(i)
        counts = Counter(); device = defaultdict(Counter)
        for key, ix in groups.items():
            ix.sort(key=lambda i:(metadata[role][i]['timestamp'], metadata[role][i]['frame'], metadata[role][i]['uid']))
            last = array[ix[-1]]; n = 1
            for i in reversed(ix[:-1]):
                if not np.array_equal(array[i], last): break
                n += 1
            counts['sessions'] += 1; device[key[0]]['sessions'] += 1
            if n > 1:
                counts['repeated_suffix_rows'] += n; device[key[0]]['repeated_suffix_rows'] += n
        answer[role] = dict(counts=counts, per_device=device, raw_omission_proven=False)
    c.write(out, answer)
