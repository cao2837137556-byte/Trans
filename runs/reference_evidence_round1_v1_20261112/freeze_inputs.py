"""Resolve the run's input pins from the accepted producers without reading query arrays."""
from pathlib import Path
import argparse
import collections
import hashlib

from common_round1 import HERE, HEADS, POOL, ROOT, dump, load, require, sha, write_text

PROJECT = HERE.parents[1]
RUNS = 'runs/'
P4 = RUNS + 'p4_complete_bank_v1_20261111/'
ACCEPTED = RUNS + 'p4_tabm_acceptance_v1_20261111/'
HISTORY = RUNS + 'same_bank_context_v6_20261106/'
DENSE = RUNS + 'context_geometry_attribution_v2_20261106/'
EVAL = RUNS + 'device_context_evaluation_v1_20261105/'
SOURCE = RUNS + 'device_context_training_v2_20261105/'
TRAIN = RUNS + 'device_context_head_training_v2_20261105/'
BINDINGS = RUNS + 'dense_reference_matrix_v1_20261027/preparation/frozen_final/bindings.json'
WRITING = RUNS + 'mainline_docs/paper_writing_v1/'
METHOD = WRITING + 'paper_main_configuration_p4_codex_20261112.json'
SPEC = WRITING + 'reference_round1_execution_spec_codex_20261112.md'
AUDIT = WRITING + 'reference_round1_decision_and_asset_audit_codex_20261112.md'
VENDOR = {
    **{n + '.py': TRAIN + n + '.py' for n in (
        'constrained_onboarding_core_v3', 'causal_reference_overlap_v1', 'indexed_features_v1',
        'legacy_qref_common_v1', 'legacy_qref_data_v1')},
    **{n + '.py': HISTORY + n + '.py' for n in (
        'history_context', 'physical', 'source_packets', 'stream_core', 'packet_reader',
        'fast_geometry', 'geometry_frozen')},
    'analysis_core.py': P4 + 'analysis_core.py',
    'p4_worker.py': P4 + 'worker.py',
}
QUOTAS = [
    ('00:16:6c:ab:6b:88', 6, 358, 359), ('00:16:6c:ab:6b:88', 17, 1334, 1335),
    ('50:c7:bf:00:56:39', 6, 73, 74), ('50:c7:bf:00:56:39', 17, 7, 7),
    ('70:ee:50:18:34:43', 6, 804, 805), ('70:ee:50:18:34:43', 17, 586, 586),
    ('ec:1a:59:79:f4:89', 6, 44, 44), ('ec:1a:59:79:f4:89', 17, 26, 26),
    ('ec:1a:59:83:28:11', 6, 4096, 0), ('ec:1a:59:83:28:11', 17, 2683, 0),
]


def relative(path):
    return Path(path).relative_to(ROOT).as_posix() if str(path).startswith('/') else path


def unique(values):
    return list(dict.fromkeys(values))


def write_once(path, value):
    if path.exists():
        require(load(path) == value, 'FROZEN_LOCAL_FILE_DIFFERS:' + str(path))
    else:
        dump(path, value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent-commit', required=True)
    args = parser.parse_args()
    evidence = {}

    def read(name):
        p = PROJECT / name
        evidence[name] = sha(p)
        return load(p)

    paper = read(METHOD)
    require(evidence[METHOD] == '06d43dfb05b77dd6a87fdf6acd4af1af0913c292bc1e84e728b5b93f31464b5c',
            'PAPER_P4_FILE_IDENTITY')
    for name in [SPEC, AUDIT]:
        evidence[name] = sha(PROJECT / name)
    accepted = read(ACCEPTED + 'FORMAL_ACCEPTANCE.json')
    require(accepted['status'] == 'PASS', 'ORIGINAL_P4_ACCEPTANCE')
    for name in ('controls/COMPLETE.json', 'controls/METRICS.json', 'controls/PAIRED_CHANGES.json',
                 'FORMAL_ACCEPTANCE.json', 'HISTORY_LINEAGE_COUNTS_CORRECTED.json'):
        path = ACCEPTED + name
        read(path)
        require(evidence[path] == paper['adopted_result_inputs'][path], 'ADOPTED_P4_INPUT:' + name)
    old_result = read(ACCEPTED + 'controls/COMPLETE.json')
    controls = {}
    for name in ['METRICS.json', 'PAIRED_CHANGES.json', 'VERIFICATION.json', 'QUERY_ASSETS.json', 'REFERENCE_BANKS.json']:
        original = P4 + 'received/results/controls/' + name
        controls[name] = read(original)
        require(evidence[original] == old_result['outputs_sha256'][name], 'P4_RESULT_ARTIFACT:' + name)
    require(controls['VERIFICATION.json']['status'] == 'PASS' and
            controls['VERIFICATION.json']['gates'][POOL]['status'] == 'PASS', 'ORIGINAL_CONTROL_GATE')
    old_ab = read(EVAL + 'AB_RESULT.json')
    old_assets = read(EVAL + 'OLD_ASSETS.json')
    old_radii = read(EVAL + 'METHOD_FREEZE.json')['calibration']
    original_heads = read(EVAL + 'FINAL_TRAINING_ACCEPTANCE.json')
    c_normalizer = read(EVAL + 'NORMALIZER.json')
    source_features = read(EVAL + 'SOURCE_FEATURE_ACCEPTANCE.json')
    admission = read(SOURCE + 'ADMISSION_RESULT.json')
    require(evidence[SOURCE + 'ADMISSION_RESULT.json'] == source_features['receipt_sha256']['ADMISSION_RESULT.json'],
            'SOURCE_ADMISSION_PROVENANCE')
    provenance = next(x for x in read(BINDINGS)['pools'] if x['pool_id'] == POOL)
    query_provenance = provenance['query']
    dense_pref = read(DENSE + 'PREFLIGHT_RESULT.json')
    dense_result = read(DENSE + 'DIAGNOSE_RESULT.json')
    full_pref = read(HISTORY + 'PREFLIGHT_RESULT.json')
    full_result = read(HISTORY + 'DIAGNOSE_RESULT.json')
    hist = read(HISTORY + 'HISTORY_INPUTS.json')
    inventory = read(HISTORY + 'HISTORY_INVENTORY.json')
    recorded = controls['REFERENCE_BANKS.json'][POOL]
    qp = controls['QUERY_ASSETS.json'][POOL]
    dense_spec = old_assets['pools'][POOL]['dense_bank']
    require(all(a['status'] == 'PASS' for a in (dense_pref, dense_result, full_pref, full_result)), 'PARENT_GATES')
    require(recorded['commission_rows'] == dense_spec['expected_rows'] == 13247 and
            recorded['commission_uid_sha256'] == dense_spec['expected_ordered_uid_sha256'] and
            recorded['full_bank'] == paper['references'][POOL] and
            recorded['commission_support_artifact'] == dense_result['pools'][POOL]['large_artifacts'],
            'REFERENCE_BASELINE_BINDING')
    require(full_pref['pools'][POOL]['reference_uid_sha256'] ==
            full_result['pools'][POOL]['reference_uid_sha256'] == paper['references'][POOL]['uid_sha256'],
            'FULL_BANK_ORDER_IDENTITY')
    require(paper['correction']['scales'] == old_radii['scales']['scales'] and
            paper['correction']['p'] == 4 and paper['correction']['lambda_value'] == .25 and
            paper['correction']['kernel'] == 'g(s)=1-(1-s)^4', 'P4_BASE_SCALE')
    require(all(paper['heads'][h]['head_sha256'] == original_heads['heads']['FUSION790_' + h]['head_sha256'] and
                paper['heads'][h]['cut'] == original_heads['heads']['FUSION790_' + h]['cut'] for h in HEADS[:3]) and
            paper['ensemble']['cut'] == original_heads['ensembles']['FUSION790']['cut'], 'FROZEN_MLP_IDENTITY')
    protocol = dense_pref['calibration']['protocols']
    require(protocol == full_result['calibration'] and all(
        protocol[k]['eligible_uid_sha256'] == old_radii['geometry']['protocols'][k]['eligible_uid_sha256']
        for k in protocol), 'FROZEN_SOURCE_CONTEXT_RADII')
    require(qp['population'] is None and qp['views'] == ['full', 'post_window_primary'], 'FROZEN_UNSW_SCOPE')
    config = dict(scope='D/M/C0/C1_UNSW_ONLY', parent_commit=args.parent_commit,
                  method=dict(p=4, kernel=paper['correction']['kernel'], lambda_value=.25, heads=list(HEADS),
                              cuts=[paper['heads'][h]['cut'] for h in HEADS[:3]] + [paper['ensemble']['cut']],
                              scales=paper['correction']['scales'], guard='SYN_AND_NOT_ACK_ALL_DEVICES',
                              head_sha256={h: paper['heads'][h]['head_sha256'] for h in HEADS[:3]},
                              decision='strict score > cut; arithmetic mean float64 seed order 27,127,227'),
                  geometry=old_radii['geometry'], context_radii=protocol, windows=provenance['windows'],
                  reference_identity=dict(dense=dict(rows=13247, uid_sha256=recorded['commission_uid_sha256']),
                                          full=paper['references'][POOL], history_rows=52835),
                  query_identity=dict(rows=provenance['query_rows'], uid_sha256=query_provenance['ordered_uid_sha256']),
                  views=qp['views'], history_packs=hist['packs'][POOL],
                  m=dict(salt='paper04_refbudget_m13247_v1_20261112',
                         quotas=[dict(device='unsw-attack-traces-2018:' + mac, protocol=k, dense=d, history=h)
                                 for mac, k, d, h in QUOTAS]),
                  c0=dict(rows=61146, history_rows=47899, atol=2e-10, rtol=0),
                  c1=dict(expected_low=43128, expected_high=46139, quota='ceil(n/2)'),
                  resource=dict(partition='amd', first_wall_seconds=3600, first_memory_mib=8192,
                                eval_max_wall_seconds=10800, eval_max_memory_mib=12288,
                                sample_per_pattern=96, forecast_margin_fraction=.68,
                                history_pair_upper_bound=1859901))
    require(config['query_identity'] == dict(rows=admission['roles'][POOL]['rows'],
                uid_sha256=admission['roles'][POOL]['ordered_uid_sha256']), 'QUERY_ROW_BINDING')
    inputs = {}

    def add(name, role, spec, remote, local=None):
        inputs[name] = dict(role=role, remote=unique(list(map(relative, remote))),
                            local=unique(local if local is not None else list(map(relative, remote))))
        if 'sha256' in spec:
            inputs[name]['sha256'] = spec['sha256']
        if 'bytes' in spec:
            inputs[name]['bytes'] = spec['bytes']

    def conventional(name, role, spec, *additional):
        add(name, role, spec, [spec['path'], *additional])

    conventional('dense_rows', 'reference', dense_spec['rows'])
    conventional('dense_arrays', 'reference', dense_spec['e3'])
    for pack in hist['packs'][POOL]:
        for name in (pack['rows'], pack['arrays']):
            a = hist['assets'][name]
            require(inventory[name]['status'] == 'PASS', 'HISTORY_INVENTORY_ENTRY')
            add(name, 'reference', a, [inventory[name]['path'], *a['candidates']], a['candidates'])
    for name, path, spec in [
        ('dense_context', DENSE, dense_pref['pools'][POOL]['reference_context']),
        ('history_context', HISTORY, full_pref['pools'][POOL]['history_context']),
        ('dense_geometry', DENSE, dense_result['pools'][POOL]['large_artifacts']),
        ('full_geometry', HISTORY, full_result['pools'][POOL]['artifact']),
    ]:
        add(name, 'reference' if name.endswith('_context') else 'query', spec, [path + spec['file']])
    e3 = old_assets['calibration']['normalizer']
    e3_norms = [p for p, h in dense_result['all_input_pins'].items() if h == e3['sha256']]
    add('e3_normalizer', 'reference', e3, [*e3_norms, e3['path']], [e3['path']])
    add('context_normalizer', 'reference', c_normalizer, [TRAIN + 'context_normalizer.npz'])
    for name, key in [('prepared_rows', 'rows'), ('query_e3', 'e3'), ('query_q', 'q14')]:
        a = query_provenance[key]
        alternatives = [p for p, h in dense_result['all_input_pins'].items() if h == a['sha256']]
        add(name, 'query', a, [*alternatives, a['path']], [a['path']])
    a = query_provenance['feature_uids']
    # The actual row alignment is also validated against the admitted metadata and q14 witness.
    # This local binding is a provenance snapshot, not a required second copy on HPC.
    require(sha(PROJECT / a['path']) == a['sha256'], 'FEATURE_UID_BINDING_SHA')
    evidence[a['path']] = a['sha256']
    for key, name, stem in [('rows', 'query_rows', 'rows'), ('array', 'query_arrays', 'array'),
                            ('scores', 'accepted_scores', 'scores')]:
        add(name, 'query', dict(sha256=qp[key + '_sha256']), [P4 + 'artifacts/' + qp[stem + '_file']])
    add('query_context', 'query', source_features['arrays'][POOL], [SOURCE + 'features8/' + POOL + '.npy'])
    view = read(EVAL + 'ASSET_PLAN.json')[POOL + '_replay']
    view_paths = read(EVAL + 'INVENTORY.json')['files'][POOL + '_replay']['candidates']
    add('query_view_witness', 'query', view, [*view_paths, view['relative']])
    conventional('source_raw_scores', 'query', old_ab['pools'][POOL]['scores'])
    add('query_context_uids', 'query', {}, [SOURCE + 'metadata/' + POOL + '.npz'])
    inputs['query_context_uids']['semantic'] = 'ordered UID equality to frozen query identity'

    for name, source in VENDOR.items():
        original = (PROJECT / source).read_bytes()
        canonical = original.replace(b'\r\n', b'\n')
        require(b'\r' not in canonical, 'BARE_CR:' + source)
        path = HERE / 'vendor' / name
        if path.exists():
            require(path.read_bytes() == canonical, 'LOCAL_VENDOR_DIFFERS:' + name)
        else:
            path.write_bytes(canonical)
        evidence[source] = dict(worktree_sha256=hashlib.sha256(original).hexdigest(), archived_sha256=sha(path),
                                archived_path='vendor/' + name)
    write_once(HERE / 'CONFIG.json', config)
    write_once(HERE / 'INPUT_PINS.json', dict(inputs=inputs, sources=evidence,
               derived_query_metadata_note='Context admission NPZ is verified semantically on every row; byte SHA is observed on HPC and recorded.'))
    metrics = controls['METRICS.json']
    pairs = controls['PAIRED_CHANGES.json']
    write_once(HERE / 'evidence' / 'BASELINE_EXPECTED.json', dict(
        metrics=[r for r in metrics if r['pool'] == POOL and r['config'] in ('RAW', 'P4_MAIN', 'P4_COMMISSION_3D')],
        pairs=[r for r in pairs if r['pool'] == POOL and (r['left'], r['right']) in
               (('RAW', 'P4_MAIN'), ('P4_MAIN', 'P4_COMMISSION_3D'))],
        source_sha256={name: old_result['outputs_sha256'][name] for name in
                       ('METRICS.json', 'PAIRED_CHANGES.json', 'VERIFICATION.json')}))
    write_once(HERE / 'evidence' / 'REUSED_CIC_EDGE.json', dict(
        evidence='accepted p4 controls, copied without recalculation',
        original_receipt=paper['adopted_result_inputs'][ACCEPTED + 'controls/COMPLETE.json'],
        metrics=[r for r in metrics if r['pool'] != POOL and r['config'] in ('RAW', 'P4_MAIN', 'P4_COMMISSION_3D')],
        pairs=[r for r in pairs if r['pool'] != POOL and (r['left'], r['right']) in
               (('RAW', 'P4_MAIN'), ('P4_MAIN', 'P4_COMMISSION_3D'))]))
    print('FROZEN_INPUT_PINS', len(inputs), 'PROVENANCE', len(evidence), 'HISTORY_PACKS', len(config['history_packs']))


if __name__ == '__main__':
    main()
