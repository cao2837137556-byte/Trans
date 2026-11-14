"""Bind recalibration to the accepted p4 inputs. This builder reads no query arrays."""
import subprocess
from pathlib import Path

from common_round1 import HERE, ROOT, dump, load, require, sha

PROJECT = HERE.parents[1]
EVAL = 'runs/device_context_evaluation_v1_20261105'
TRAIN = 'runs/device_context_head_training_v2_20261105'
DENSE = 'runs/context_geometry_attribution_v2_20261106'
FULL = 'runs/same_bank_context_v6_20261106'
P4 = 'runs/p4_complete_bank_v1_20261111'
ACCEPT = 'runs/p4_tabm_acceptance_v1_20261111/controls'
EDGE = 'runs/edge_formal_evaluation_resume_v2_20261104'
EDGE_SEAL = 'runs/edge_query_selection_v1_20261103/seal20k/QUERY_SELECTION_SEAL.json'
PAPER = 'runs/mainline_docs/paper_writing_v1/paper_main_configuration_p4_codex_20261112.json'
PROTOCOL = 'runs/mainline_docs/collab/20261113_same_information_threshold_recalibration_protocol_draft_codex.md'
HEADS = ('27', '127', '227')
POOLS = ('CIC_DEV', 'UNSW_DEV', 'EDGE')
MODEL_MODULES = (
    'context_core', 'query_tail_core_v2', 'continuous_model_v3', 'continuous_common_v3',
    'legacy_qref_data_v1', 'legacy_qref_common_v1', 'legacy_qref_model_v1',
    'legacy_unsw_archival_common_v1', 'legacy_unsw_archival_runtime_v1', 'legacy_unsw_archival_runtime_v2',
)


def relative(s):
    prefix = ROOT.as_posix() + '/'
    return s[len(prefix):] if s.startswith(prefix) else s


def main():
    provenance = {}
    pins = {}

    def receipt(name, expected=None):
        file = PROJECT / name
        digest = sha(file)
        require(expected is None or expected == digest, 'RECEIPT_SHA:' + name)
        provenance[name] = digest
        return load(file)

    def add(name, role, spec, remote, local=()):
        pins[name] = dict(role=role, sha256=spec['sha256'],
                          remote=list(dict.fromkeys(relative(x) for x in remote)),
                          local=list(dict.fromkeys(local or (relative(x) for x in remote))))
        if 'bytes' in spec:
            pins[name]['bytes'] = spec['bytes']

    paper = receipt(PAPER, '06d43dfb05b77dd6a87fdf6acd4af1af0913c292bc1e84e728b5b93f31464b5c')
    provenance[PROTOCOL] = sha(PROJECT / PROTOCOL)
    acceptance = receipt(ACCEPT + '/COMPLETE.json', paper['adopted_result_inputs'][ACCEPT + '/COMPLETE.json'])
    require(acceptance['status'] == 'PASS', 'P4_ACCEPTANCE')
    baseline = receipt(ACCEPT + '/METRICS.json', acceptance['outputs_sha256']['METRICS.json'])
    queries = receipt(ACCEPT + '/QUERY_ASSETS.json', acceptance['outputs_sha256']['QUERY_ASSETS.json'])
    refs = receipt(ACCEPT + '/REFERENCE_BANKS.json', acceptance['outputs_sha256']['REFERENCE_BANKS.json'])
    old = receipt(EVAL + '/OLD_ASSETS.json')
    normalizer = receipt(EVAL + '/NORMALIZER.json')
    head_accept = receipt(EVAL + '/FINAL_TRAINING_ACCEPTANCE.json')
    delivery = receipt(EVAL + '/TRAINING_DELIVERY.json')
    hist = receipt(FULL + '/HISTORY_INPUTS.json')
    hist_inventory = receipt(FULL + '/HISTORY_INVENTORY.json')
    hist_context = receipt(FULL + '/PREFLIGHT_RESULT.json')
    dense_context = receipt(DENSE + '/PREFLIGHT_RESULT.json')
    dense_done = receipt(DENSE + '/DIAGNOSE_RESULT.json')
    binding = receipt('runs/dense_reference_matrix_v1_20261027/preparation/frozen_final/bindings.json')
    edge_card = receipt(EVAL + '/EDGE_CARD.json')
    edge_manifest = receipt(EDGE + '/retrieved/RESULT_MANIFEST.json')
    edge_seal = receipt(EDGE_SEAL)
    cut = [paper['heads'][h]['cut'] for h in HEADS] + [paper['ensemble']['cut']]
    require(head_accept['ensembles']['FUSION790']['cut'] == cut[-1] and head_accept['result'] == 'PASS',
            'FROZEN_ENSEMBLE')
    for idx, h in enumerate(HEADS):
        a = head_accept['heads']['FUSION790_' + h]
        require(a['cut'] == cut[idx] and a['head_sha256'] == paper['heads'][h]['head_sha256'], 'FROZEN_HEAD:' + h)
        add('head_' + h, 'reference', dict(sha256=a['head_sha256']),
            [TRAIN + '/heads/FUSION790_' + h + '/train/head.npz'])
    for module in MODEL_MODULES:
        name = module + '.py'
        add('model:' + module, 'reference', dict(sha256=delivery['pins'][name]), [TRAIN + '/' + name])
    a = old['calibration']['normalizer']
    alternatives = [p for p, digest in dense_done['all_input_pins'].items() if digest == a['sha256']]
    add('e3_normalizer', 'reference', a, [*alternatives, a['path']], [a['path']])
    add('context_normalizer', 'reference', normalizer, [TRAIN + '/context_normalizer.npz'])
    for pool in POOLS:
        require(refs[pool]['full_bank'] == paper['references'][pool], 'REF_BANK_IDENTITY:' + pool)
        ctx = dense_context['pools'][pool]['reference_context']
        add(pool + ':dense_context', 'reference', ctx, [DENSE + '/' + ctx['file']])
        for field, f in [('rows', 'rows'), ('array', 'array'), ('scores', 'scores')]:
            a = queries[pool]
            add(pool + ':query_' + field, 'query', dict(sha256=a[f + '_sha256']),
                [P4 + '/artifacts/' + a[f + '_file']])
        if pool == 'EDGE':
            continue
        a = old['pools'][pool]['dense_bank']
        for key in ('rows', 'e3'):
            pin = a[key]
            alt = [p for p, digest in dense_done['all_input_pins'].items() if digest == pin['sha256']]
            add(pool + ':dense_' + key, 'reference', pin, [pin['path'], *alt], [pin['path']])
        require(a['e3']['key'] == 'e3' and a['q14']['key'] == 'q14', 'DENSE_SCHEMA')
        for h in hist['packs'][pool]:
            for key in (h['rows'], h['arrays']):
                spec = hist['assets'][key]
                add(key, 'reference', spec, [hist_inventory[key]['path'], *spec['candidates']], spec['candidates'])
        ctx = hist_context['pools'][pool]['history_context']
        add(pool + ':history_context', 'reference', ctx, [FULL + '/' + ctx['file']])
    edge_encode_rel = 'outputs/gate_182089/encoded/COMPLETE.json'
    edge_encode = edge_manifest['files'][edge_encode_rel]
    edge_local = EDGE + '/retrieved/' + edge_encode_rel
    edge_index = receipt(edge_local, edge_encode['sha256'])
    add('EDGE:encoded_complete', 'reference', edge_encode, [EDGE + '/' + edge_encode_rel], [edge_local])
    ref_meta = edge_seal['references']
    add('EDGE:reference_rows', 'reference', dict(sha256=ref_meta['source_sha256']),
        [ref_meta['source_path'], EDGE + '/checkout/' + ref_meta['source_path']])
    require(edge_index['status'] == 'COMPLETE' and edge_index['rows'] == 64124, 'EDGE_ENCODE_SEAL')
    config = dict(
        scope='FUSION790_SAME_REFERENCE_INFORMATION', parent_commit=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=PROJECT, text=True).strip(),
        method=dict(heads=[*HEADS, 'ensemble'], p=4, kernel='g(s)=1-(1-s)^4', lambda_value=.25,
                    cuts=cut, scales=paper['correction']['scales'], guard='SYN_AND_NOT_ACK_ALL_DEVICES'),
        calibration=dict(budget=.01, groups=['device', 'capture_id', 'component_id'], with_guard='conditional_1pct'),
        reference=refs, query=queries,
        query_counts={'CIC_DEV': [179886, 175097, 3334], 'UNSW_DEV': [148316, 146997, 1319], 'EDGE': [60000, 60000, 0]},
        windows={p['pool_id']: p['windows'] for p in binding['pools'] if p['pool_id'] in POOLS[:2]},
        history_packs=hist['packs'], edge_cutoff=edge_card['reference']['cutoff_ns'],
        edge_last_frame=edge_card['reference']['original_prefix_frames'][1],
        model_modules=list(MODEL_MODULES), partition='amd', memory_mib=8192, wall_seconds=3600,
    )
    require(sum(refs[p]['full_bank']['rows'] for p in POOLS) == 79069, 'REF_TOTAL')
    dump(HERE / 'CONFIG.json', config)
    dump(HERE / 'INPUT_PINS.json', dict(inputs=pins, sources=provenance))
    dump(HERE / 'EXPECTED_BASELINE.json', [x for x in baseline if x['config'] in ('RAW', 'P4_MAIN')])
    print('REFERENCE_ROWS',79069,'QUERY_ROWS',388202,'PINNED_ASSETS',len(pins))


if __name__ == '__main__':
    main()
