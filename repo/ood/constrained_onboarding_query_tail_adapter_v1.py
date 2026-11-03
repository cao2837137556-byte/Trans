"""Verified completed QUERY_TAIL -> constrained onboarding input adapter.

This is inference-only. It never trains a head, decodes PCAP, constructs E3,
recalibrates a cut, or accepts old early-prefix features. Missing remote caches
are an explicit preparation error, not a successful empty development run.
"""
import argparse
from pathlib import Path

import numpy as np
import torch

import query_tail_core_v2 as k
import query_tail_prepare_v2 as p
import query_tail_train_v2 as t
import constrained_onboarding_reference_v1 as reference

c = k.c
PROTOCOL_SHA256 = '2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5'
INPUT_VERSION = 'continuous-input-core-repair-design-v3-20260929'
SUFFIXES = ('27', '127', '227', 'ensemble')
EXPECTED_COUNTS = {'LEARN': 766727, 'FIT': 617908, 'CAL': 148819,
                   'CIC_DEV': 179886, 'UNSW_DEV': 148316}
# These identities are copied from the sealed v2r1 parent_pins.json. Reference
# and feature files are separately pinned by the fixed design's manifests.
PARENT_PINS = {
    'P_COMPLETE.json': '1c4b1235207dfd401311bef6bee37b2ed7f978fb800fb7aef982c39b10cab3c4',
    'T_COMPLETE.json': 'c81003aa5492adc1432303de4bd53f68ee4d319a646b2b6778deca6f38f958bd',
    'calibration/base_logits.npz': '0a5c7e8939e9fc8856f8e04d3b19ba08151886ce9f0fd4e5079487cc535bcde1',
    'calibration/thresholds.json': '08373843dd01305c61c3cc7b30e8d629994726932ff47bd8bcbbd7f1eb3e10fd',
    'CIC_DEV/scores.npz': '384f712efbc691364fb3c57080e5546077f1098a037c958686122d49da9cb264',
    'CIC_DEV/decisions.npz': 'ac9cae38ab2d82c61d75e758b2dd8443f3029b22e7b3030a873f50e8b0e09b08',
    'UNSW_DEV/scores.npz': 'b88e56fb9b9920743383b4bb8c972d98d9498fbff2008aefd175ed3dbd2d5648',
    'UNSW_DEV/decisions.npz': '0fdc69e0ba809bf1dfbe54b75bb5d810ad963256fe48c94057786cd1554afc49',
}


def _required_files(parent, head_run, design_path):
    needed = [Path(design_path)]
    for name in ('P_COMPLETE.json', 'T_COMPLETE.json', 'inputs/SHA256SUMS',
                 'features/SHA256SUMS', 'normalizers/SHA256SUMS',
                 'normalizers/RECENT.npz', 'spool/snapshots.sqlite'):
        needed.append(parent/name)
    for role in ('LEARN', 'CIC_DEV', 'UNSW_DEV', 'SOURCE_REFS', 'UNSW_REFS'):
        needed.extend([parent/'inputs'/(role+'.jsonl.gz'), parent/'features'/(role+'.npy')])
    for name in ('P_COMPLETE.json', 'T_COMPLETE.json', 'K_COMPLETE.json',
                 'SHA256SUMS', 'prepared/SHA256SUMS', 'prepared/receipt.json',
                 'prepared/normalizer.npz', 'prepared/FIT.npz', 'prepared/CAL.npz',
                 'thresholds.json', 'decision.json'):
        needed.append(head_run/name)
    for role in k.ROLES:
        for suffix in ('.jsonl.gz', '_q.npy', '_window.npy'):
            needed.append(head_run/'prepared'/(role+suffix))
    for pool in ('CAL', 'CIC_DEV', 'UNSW_DEV'):
        for name in ('scores.npz', 'decisions.npz', 'SHA256SUMS'):
            needed.append(head_run/pool/name)
    missing = [str(path) for path in needed if not path.is_file()]
    c.require(not missing, 'PREPARATION_REQUIRED: completed QUERY_TAIL run and original '
              'Job177891 RECENT caches required; missing=' + repr(missing))


def _endpoint(folder, arm, seed, design, norm):
    receipt = c.read(folder/'endpoint.json')
    dimension = 768 if arm == 'RECENT_TAIL' else 782
    c.require(receipt.get('status') == 'COMPLETE' and receipt.get('arm') == arm and
              receipt.get('seed') == seed and receipt.get('dimension') == dimension,
              'ADAPTER_ENDPOINT_IDENTITY')
    c.require(receipt.get('synthetic_only') is False and
              receipt.get('reference_used') is False and receipt.get('DEV_used') is False,
              'ADAPTER_ENDPOINT_DATA_SCOPE')
    c.require(receipt.get('rows') == EXPECTED_COUNTS['FIT'] and receipt.get('epochs') == 40 and
              receipt.get('updates') == design['training']['updates_per_head'] and
              receipt.get('uid_sha256') == design['data']['fit_cal_identity']['FIT']['uid_sha256'],
              'ADAPTER_ENDPOINT_FIT')
    c.require(receipt.get('normalizer_digest') == c.digest([v.tolist() for v in norm]) and
              receipt.get('design_digest') == c.digest(design), 'ADAPTER_ENDPOINT_PROVENANCE')
    c.require(receipt.get('objective') == ('BCE' if arm == 'QUERY_BCE' else 'BCE+TAIL') and
              receipt.get('diagnostics_enabled') is True, 'ADAPTER_ENDPOINT_OBJECTIVE')
    c.pin(folder/'head.npz', receipt['head_sha256'])
    return receipt


def _prepared_inputs(parent, head_run, design, indices, norm):
    folder = head_run/'prepared'
    complete = c.read(head_run/'P_COMPLETE.json')
    c.require(complete.get('status') == 'COMPLETE' and
              complete.get('design_sha256') == k.DESIGN_SHA and
              complete.get('rows') == 1094929, 'ADAPTER_P_NOT_COMPLETE')
    c.pin(folder/'SHA256SUMS', complete['prepared_seal'])
    c.verify(folder)
    receipt = c.read(folder/'receipt.json')
    c.require(receipt.get('status') == 'COMPLETE' and
              receipt.get('feature_manifest') == design['provenance']['feature_manifest_sha256'] and
              receipt.get('spool_sha256') == design['provenance']['spool_sha256'],
              'ADAPTER_PREPARED_PROVENANCE')
    pins = p.manifest(parent/'inputs', design['provenance']['input_manifest_sha256'])
    q = {}
    for role in k.ROLES:
        c.pin(folder/(role+'.jsonl.gz'), pins[role+'.jsonl.gz'])
        values = np.load(folder/(role+'_q.npy'), mmap_mode='r', allow_pickle=False)
        _q_schema(values, EXPECTED_COUNTS[role])
        q[role] = values
    for split in ('FIT', 'CAL'):
        with np.load(folder/(split+'.npz'), allow_pickle=False) as saved:
            c.require(np.array_equal(saved['indices'], indices[split]), 'ADAPTER_PREPARED_SPLIT')
    with np.load(folder/'normalizer.npz', allow_pickle=False) as saved:
        c.require(np.array_equal(saved['mean'], norm[0]) and np.array_equal(saved['scale'], norm[1]),
                  'ADAPTER_PREPARED_NORMALIZER')
    return q


def _q_schema(values, count):
    c.require(values.shape == (count, 14) and values.dtype == np.float32, 'ADAPTER_Q_SCHEMA')
    for start in range(0, count, 4096):
        part = values[start:start+4096]
        c.require(np.isfinite(part).all() and np.all((part >= 0) & (part <= 1)), 'ADAPTER_Q_RANGE')


def _bundle_rows(rows, e3, q14, logits=None):
    uids = [row['uid'] for row in rows]
    c.require(len(set(uids)) == len(rows), 'ADAPTER_DUPLICATE_UID')
    item = dict(rows=rows, e3=e3, q14=q14, feature_uids=uids, q_uids=uids)
    if logits is not None:
        c.require(logits.shape == (len(rows), 3) and np.isfinite(logits).all(), 'ADAPTER_LOGITS')
        item['logits'] = logits
    return item


def _exact_equal(left, right):
    """Actual bitwise reproduction, including dtype and signed zero."""
    return left.dtype == right.dtype and left.shape == right.shape and left.tobytes() == right.tobytes()


def _verify_saved_pool(folder, rows, logits, arm, cuts, ensemble_cut, recent):
    expected_uid = [r['uid'] for r in rows]
    ensemble = np.stack([logits[:, i] for i in range(3)]).mean(0, dtype=np.float64)
    predictions = np.column_stack([logits > cuts, ensemble > ensemble_cut])
    with np.load(folder/'scores.npz', allow_pickle=False) as saved:
        c.require(saved['uid'].tolist() == expected_uid, 'ADAPTER_SCORED_UID_ORDER')
        for j, suffix in enumerate(SUFFIXES):
            result = logits[:, j] if j < 3 else ensemble
            c.require(_exact_equal(result, saved[arm+'_'+suffix]), 'ADAPTER_SCORE_NOT_BITWISE:'+suffix)
            c.require(_exact_equal(recent[suffix], saved['RECENT_'+suffix]), 'ADAPTER_RECENT_SCORE_DRIFT')
    recent_cuts = recent['cuts']
    recent_decisions = np.column_stack([recent[suffix] > recent_cuts[suffix] for suffix in SUFFIXES])
    with np.load(folder/'decisions.npz', allow_pickle=False) as saved:
        c.require(saved['uid'].tolist() == expected_uid, 'ADAPTER_DECISION_UID_ORDER')
        for j, suffix in enumerate(SUFFIXES):
            c.require(_exact_equal(predictions[:, j], saved[arm+'_'+suffix]), 'ADAPTER_HEAD_DECISION_DRIFT')
            c.require(_exact_equal(recent_decisions[:, j], saved['RECENT_'+suffix]), 'ADAPTER_RECENT_DECISION_DRIFT')
    return recent_decisions


def _recent(parent, pool, rows):
    path = parent/'calibration/base_logits.npz' if pool == 'CAL' else parent/pool/'scores.npz'
    result = {'cuts': c.read(parent/'calibration/thresholds.json')['tau']['RECENT']}
    with np.load(path, allow_pickle=False) as saved:
        for suffix in SUFFIXES:
            result[suffix] = saved['RECENT_'+suffix].copy()
            c.require(result[suffix].shape == (len(rows),) and np.isfinite(result[suffix]).all(),
                      'ADAPTER_PARENT_RECENT_SCHEMA')
    ensemble = np.stack([result[s] for s in SUFFIXES[:3]]).mean(0, dtype=np.float64)
    c.require(_exact_equal(ensemble, result['ensemble']), 'ADAPTER_PARENT_RECENT_ENSEMBLE')
    if pool != 'CAL':
        with np.load(parent/pool/'decisions.npz', allow_pickle=False) as saved:
            c.require(saved['uid'].tolist() == [r['uid'] for r in rows], 'ADAPTER_PARENT_UID_ORDER')
            for suffix in SUFFIXES:
                c.require(_exact_equal(result[suffix] > result['cuts'][suffix], saved['RECENT_'+suffix]),
                          'ADAPTER_PARENT_RECENT_DECISION')
    return result


def _references(parent, design):
    pins = p.manifest(parent/'inputs', design['provenance']['input_manifest_sha256'])
    feature_pins = p.manifest(parent/'features', design['provenance']['feature_manifest_sha256'])
    result = {}
    for role, count, partition_counts in (
            ('SOURCE_REFS', 179, {'LEARN': 104, 'DEV': 75}),
            ('UNSW_REFS', 92, {'EXTERNAL_ARCHIVAL_EVALUATION': 92})):
        rr = list(c.rows(c.pin(parent/'inputs'/(role+'.jsonl.gz'), pins[role+'.jsonl.gz'])))
        from collections import Counter
        c.require(len(rr) == count and Counter(r['partition'] for r in rr) == partition_counts and
                  all(r['use'] == 'REFERENCE' and r['label'] == 0 for r in rr), 'ADAPTER_REFERENCE_SCOPE')
        c.require(len({r['uid'] for r in rr}) == count, 'ADAPTER_REFERENCE_UID')
        # Add explicit original slots before taking source/DEV subsets.
        rr = [dict(row, parent_slot=i) for i, row in enumerate(rr)]
        path = c.pin(parent/'features'/(role+'.npy'), feature_pins[role+'.npy'])
        values = np.load(path, mmap_mode='r', allow_pickle=False)
        c.require(values.shape == (count, 794) and values.dtype == np.float32 and
                  np.isfinite(values).all(), 'ADAPTER_REFERENCE_RECENT_FEATURES')
        q = reference.extract_old_bank_q14(parent/'spool/snapshots.sqlite', rr,
                                           design['provenance']['spool_sha256'])
        _q_schema(q, count)
        for partition in partition_counts:
            ix = np.asarray([i for i, r in enumerate(rr) if r['partition'] == partition], dtype=np.int64)
            result[partition] = _bundle_rows([rr[int(i)] for i in ix], values[ix, :768], q[ix])
    return result


def prepare_query_tail(parent, head_run, design_path, arm='QUERY_TAIL', progress=None):
    """Return in-memory inputs from a completed original v2r1 chain.

    Replaying frozen heads is intentional: CAL and both development pools must
    reproduce saved scores bit for bit before new-module effects can be measured.
    Source FIT scores are newly inferred for source-only logit scaling.
    """
    c.require(arm in k.ARMS, 'ADAPTER_ARM')
    parent, head_run, design_path = Path(parent).resolve(), Path(head_run).resolve(), Path(design_path).resolve()
    _required_files(parent, head_run, design_path)
    design = c.read(c.pin(design_path, k.DESIGN_SHA))
    for rel, digest in PARENT_PINS.items():
        c.pin(parent/rel, digest)
    parent_complete = c.read(parent/'P_COMPLETE.json')
    c.require(parent_complete['status'] == 'COMPLETE' and parent_complete['rows'] == 1095200 and
              parent_complete['feature_seal'] == design['provenance']['feature_manifest_sha256'],
              'ADAPTER_PARENT_NOT_COMPLETE')
    c.verify(head_run)
    finished = c.read(head_run/'K_COMPLETE.json')
    c.require(finished.get('status') == 'COMPLETE', 'ADAPTER_K_NOT_COMPLETE')
    c.pin(head_run/'decision.json', finished['decision_sha256'])
    training = c.read(head_run/'T_COMPLETE.json')
    c.require(training.get('status') == 'COMPLETE' and training.get('total_updates') == 869040,
              'ADAPTER_T_NOT_COMPLETE')
    metadata, indices = p.load_metadata(parent, design)
    c.require(all(len(metadata[r]) == EXPECTED_COUNTS[r] for r in k.ROLES) and
              all(len(indices[s]) == EXPECTED_COUNTS[s] for s in ('FIT', 'CAL')), 'ADAPTER_PRODUCTION_COUNTS')
    values, norm = p.arrays(parent, design, verify=True, progress=progress)
    q = _prepared_inputs(parent, head_run, design, indices, norm)
    cutoff = c.read(head_run/'thresholds.json')
    c.require(cutoff.get('source') == 'ORIGINAL_SOURCE_CAL_NORMAL_ONLY' and cutoff.get('comparator') == 'strict >' and
              cutoff.get('budget') == .01 and cutoff.get('normal_rows') == 33147,
              'ADAPTER_THRESHOLD_CONTRACT')
    cal_rows = [metadata['LEARN'][int(i)] for i in indices['CAL']]
    c.require(cutoff['normal_uid_sha256'] == c.uid_sha(r['uid'] for r in cal_rows if r['label'] == 0),
              'ADAPTER_THRESHOLD_NORMAL_UID')
    cuts = np.asarray([cutoff['cuts'][arm+'_'+str(seed)] for seed in c.SEEDS], dtype=np.float64)
    ensemble_cut = float(cutoff['cuts'][arm+'_ensemble'])
    c.require(np.isfinite(cuts).all() and np.isfinite(ensemble_cut), 'ADAPTER_FINITE_CUTS')
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    models = []
    for seed in c.SEEDS:
        folder = head_run/'endpoints'/(arm+'_'+str(seed))
        receipt = _endpoint(folder, arm, seed, design, norm)
        c.require(receipt in training.get('endpoints', []), 'ADAPTER_T_ENDPOINT_JOIN')
        models.append(t.load(folder, arm, seed, design))
    dimension = 768 if arm == 'RECENT_TAIL' else 782
    pools = {}
    for pool in ('CAL', 'CIC_DEV', 'UNSW_DEV', 'FIT'):
        role = 'LEARN' if pool in ('FIT', 'CAL') else pool
        ix = indices[pool] if role == 'LEARN' else np.arange(len(metadata[role]), dtype=np.int64)
        rows = [metadata[role][int(i)] for i in ix]
        if progress is not None:
            progress.stage = 'ONBOARDING_HEAD_REPLAY_'+pool
        logits = np.column_stack([k.scores(model, values[role], q[role], ix, norm, dimension, progress)
                                  for model in models])
        recent_decisions = None
        if pool != 'FIT':
            recent = _recent(parent, pool, rows)
            c.require(all(cutoff['cuts']['RECENT_'+s] == recent['cuts'][s] for s in SUFFIXES),
                      'ADAPTER_RECENT_CUT_DRIFT')
            recent_decisions = _verify_saved_pool(head_run/pool, rows, logits, arm, cuts, ensemble_cut, recent)
        # Copy only the needed 768 columns for split source rows; target arrays
        # remain read-only mapped views. No extra 794-column source allocation.
        e3 = values[role][ix, :768] if role == 'LEARN' else values[role][:, :768]
        qq = q[role][ix] if role == 'LEARN' else q[role]
        pools[pool] = _bundle_rows(rows, e3, qq, logits)
        if recent_decisions is not None:
            pools[pool]['recent_decisions'] = recent_decisions
    refs = _references(parent, design)
    pools['CIC_DEV']['banks'] = {'OLD_BANK': refs['DEV']}
    pools['UNSW_DEV']['banks'] = {'OLD_BANK': refs['EXTERNAL_ARCHIVAL_EVALUATION']}
    manifests = {str(parent/rel): digest for rel, digest in PARENT_PINS.items()}
    for rel in ('inputs/SHA256SUMS', 'features/SHA256SUMS', 'normalizers/SHA256SUMS'):
        manifests[str(parent/rel)] = c.sha(parent/rel)
    for rel in ('SHA256SUMS', 'P_COMPLETE.json', 'T_COMPLETE.json', 'K_COMPLETE.json',
                'prepared/SHA256SUMS', 'thresholds.json'):
        manifests[str(head_run/rel)] = c.sha(head_run/rel)
    manifests[str(design_path)] = k.DESIGN_SHA
    manifests[str(parent/'spool/snapshots.sqlite')] = design['provenance']['spool_sha256']
    return dict(schema='constrained-onboarding-bundle-v1', synthetic_only=False, head_family=arm,
                normalizer=norm, input_version=INPUT_VERSION, protocol_sha256=PROTOCOL_SHA256,
                provenance=dict(adapter='constrained-onboarding-query-tail-adapter-v1', input_sha256=manifests,
                                verified_current_parent=True,
                                protected_paths=[str(parent), str(head_run), str(design_path)],
                                normalizer_sha256=c.sha(parent/'normalizers/RECENT.npz'),
                                source='VERIFIED_JOB177891_RECENT_AND_COMPLETED_QUERY_TAIL_V2R1',
                                frozen_head_replay='CAL_CIC_DEV_UNSW_DEV_BITWISE',
                                numpy_version=np.__version__, torch_version=torch.__version__,
                                threads=4, no_training=True, no_pcap_decode=True, no_e3_forward=True),
                source_fit=pools['FIT'], source_cal=pools['CAL'], source_references=refs['LEARN'],
                cuts=cuts, ensemble_cut=ensemble_cut,
                targets={name: pools[name] for name in ('CIC_DEV', 'UNSW_DEV')})


def add_arguments(parser):
    parser.add_argument('--parent', required=True, help='Complete original Job177891 runs/real_repair')
    parser.add_argument('--head-run', required=True, help='Completed v2r1 runs/query_tail directory')
    parser.add_argument('--design', required=True, help='Frozen QUERY_TAIL v2 design_contract.json')
    parser.add_argument('--arm', choices=k.ARMS, default='QUERY_TAIL')
    parser.add_argument('--protocol', required=True, help='Fixed onboarding protocol.json')
    parser.add_argument('--banks-manifest', help='Optional pinned encoded B0/B1/B2 assets manifest')
    parser.add_argument('--output', required=True, help='Fresh development output directory')
    return parser


def main(argv=None):
    args = add_arguments(argparse.ArgumentParser(description=__doc__)).parse_args(argv)
    c.pin(args.protocol, PROTOCOL_SHA256)
    output = Path(args.output).resolve()
    c.require(not output.exists(), 'NO_OVERWRITE:'+str(output))
    for source in (Path(args.parent).resolve(), Path(args.head_run).resolve()):
        c.require(not output.is_relative_to(source), 'OUTPUT_INSIDE_SEALED_INPUT')
    bundle = prepare_query_tail(args.parent, args.head_run, args.design, args.arm)
    from constrained_onboarding_runner_v1 import run_development
    if args.banks_manifest:
        from constrained_onboarding_runner_v1 import attach_reference_banks
        attach_reference_banks(bundle, args.banks_manifest)
    bundle['provenance'].setdefault('protected_paths', []).append(str(Path(args.protocol).resolve()))
    if args.banks_manifest:
        bundle['provenance']['protected_paths'].append(str(Path(args.banks_manifest).resolve()))
    return run_development(bundle, output, args.protocol)


if __name__ == '__main__':
    main()
