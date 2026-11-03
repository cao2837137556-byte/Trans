"""Replay each predeclared modern head before applying the unchanged module.

Completed QUERY_TAIL supplies verified prepared q14 and the original normalizer;
it never supplies a modern head's cut or score. Both candidates use the same
registered reference policies and source-only module fitting procedure.
"""
import argparse
import hashlib
from pathlib import Path

import numpy as np
import torch
from indexed_features_v1 import take
import query_tail_core_v2 as k
import query_tail_prepare_v2 as prepare
import constrained_onboarding_query_tail_adapter_v2 as prior
import modern_head_evaluate_v1 as evaluation

c = k.c


def fit_identity(fit_rows):
    ordered = hashlib.sha256()
    for row in fit_rows:
        ordered.update((row['uid']+'\n').encode())
    return dict(ordered_uid_sha256=ordered.hexdigest(),
                weight_sha256=hashlib.sha256(k.weights(fit_rows).tobytes()).hexdigest())


def verify_endpoint(folder, family, seed, config, design, norm, fit_rows, training, identity=None):
    c.verify(folder)
    receipt = c.read(Path(folder)/'endpoint.json')
    c.require(receipt.get('status') == 'COMPLETE' and receipt.get('family') == family and
              receipt.get('seed') == seed and receipt.get('dimension') == 782, 'MODERN_ADAPTER_ENDPOINT')
    c.require(receipt.get('synthetic_only') is False and receipt.get('reference_used') is False and
              receipt.get('CAL_used') is False and receipt.get('DEV_used') is False,
              'MODERN_ADAPTER_ENDPOINT_SCOPE')
    c.require(receipt.get('rows') == prior.EXPECTED_COUNTS['FIT'] and
              receipt.get('uid_sha256') == design['data']['fit_cal_identity']['FIT']['uid_sha256'],
              'MODERN_ADAPTER_FIT_IDENTITY')
    identity = fit_identity(fit_rows) if identity is None else identity
    c.require(all(receipt.get(key) == value for key, value in identity.items()),
              'MODERN_ADAPTER_FIT_ORDER_WEIGHT')
    c.require(receipt.get('normalizer_digest') == c.digest([v.tolist() for v in norm]) and
              receipt.get('config_digest') == c.digest(config), 'MODERN_ADAPTER_ENDPOINT_PROVENANCE')
    c.require(receipt in training.get('endpoints', []), 'MODERN_ADAPTER_T_ENDPOINT_JOIN')
    return receipt


def verify_fit_scores(folder, rows, logits, family):
    with np.load(Path(folder)/'scores.npz', allow_pickle=False) as saved:
        c.require(saved['uid'].tolist() == [r['uid'] for r in rows], 'MODERN_ADAPTER_FIT_SCORE_UID')
        for j, suffix in enumerate(evaluation.SUFFIXES):
            expected = logits[:, j] if j < 3 else evaluation.ensemble([logits[:, n] for n in range(3)])
            c.require(prior._exact_equal(expected, saved[family+'_'+suffix]),
                      'MODERN_ADAPTER_FIT_SCORE_BITWISE:'+suffix)


def prepare_modern(parent, prepared_run, head_run, design_path, config_path, family, progress=None):
    """Return the existing runner's schema after exact saved-head reproduction."""
    import modern_head_models_v1 as models
    import modern_head_train_v1 as trainer
    parent, prepared_run, head_run = (Path(p).resolve() for p in (parent, prepared_run, head_run))
    design_path, config_path = Path(design_path).resolve(), Path(config_path).resolve()
    config = c.read(config_path)
    design = c.read(c.pin(design_path, k.DESIGN_SHA))
    evaluation.validate_config(config, design)
    c.require(config['synthetic_only'] is False and family in evaluation.ONBOARDING_FAMILIES,
              'MODERN_ADAPTER_FIXED_CANDIDATES')
    prior._required_files(parent, prepared_run, design_path)
    for rel, digest in prior.PARENT_PINS.items(): c.pin(parent/rel, digest)
    parent_complete = c.read(parent/'P_COMPLETE.json')
    c.require(parent_complete.get('status') == 'COMPLETE' and parent_complete.get('rows') == 1095200 and
              parent_complete.get('feature_seal') == design['provenance']['feature_manifest_sha256'],
              'MODERN_ADAPTER_PARENT_COMPLETE')
    c.verify(prepared_run); c.verify(head_run)
    old_training = c.read(prepared_run/'T_COMPLETE.json')
    old_finished = c.read(prepared_run/'K_COMPLETE.json')
    c.require(old_training.get('status') == old_finished.get('status') == 'COMPLETE' and
              old_training.get('total_updates') == 869040, 'MODERN_ADAPTER_PREPARED_COMPLETE')
    c.pin(prepared_run/'decision.json', old_finished['decision_sha256'])
    finished, training, preparation = (c.read(head_run/(name+'_COMPLETE.json')) for name in ('K', 'T', 'P'))
    c.require(all(v.get('status') == 'COMPLETE' and v.get('config_digest') == c.digest(config)
                  for v in (finished, training, preparation)), 'MODERN_ADAPTER_COMPLETION_IDENTITY')
    c.pin(head_run/'decision.json', finished['decision_sha256'])
    c.pin(head_run/'comparison_summary.json', finished['summary_sha256'])
    c.pin(prepared_run/'prepared/SHA256SUMS', preparation['prepared_seal'])
    decision = c.read(head_run/'decision.json')
    c.require(decision.get('automatic_promotion') is False and decision.get('selected_family') is None and
              tuple(decision.get('onboarding_families', ())) == evaluation.ONBOARDING_FAMILIES,
              'MODERN_ADAPTER_NO_TARGET_SELECTION')
    metadata, indices = prepare.load_metadata(parent, design)
    c.require(all(len(metadata[r]) == prior.EXPECTED_COUNTS[r] for r in k.ROLES) and
              all(len(indices[s]) == prior.EXPECTED_COUNTS[s] for s in ('FIT', 'CAL')),
              'MODERN_ADAPTER_PRODUCTION_COUNTS')
    values, norm = prepare.arrays(parent, design, verify=True, progress=progress)
    q = prior._prepared_inputs(parent, prepared_run, design, indices, norm)
    cal_rows = [metadata['LEARN'][int(i)] for i in indices['CAL']]
    fit_rows = [metadata['LEARN'][int(i)] for i in indices['FIT']]
    cutoff = c.read(head_run/'thresholds.json')
    c.require(cutoff.get('source') == 'ORIGINAL_SOURCE_CAL_NORMAL_ONLY' and
              cutoff.get('comparator') == 'strict >' and cutoff.get('budget') == .01 and
              cutoff.get('normal_rows') == 33147 and cutoff.get('config_digest') == c.digest(config) and
              cutoff.get('gates_digest') == c.digest(config['gates']) and
              cutoff.get('normal_uid_sha256') == c.uid_sha(r['uid'] for r in cal_rows if r['label'] == 0),
              'MODERN_ADAPTER_CAL_CONTRACT')
    cuts = np.asarray([cutoff['cuts'][family+'_'+str(seed)] for seed in c.SEEDS], dtype=np.float64)
    ensemble_cut = float(cutoff['cuts'][family+'_ensemble'])
    c.require(np.isfinite(cuts).all() and np.isfinite(ensemble_cut), 'MODERN_ADAPTER_FINITE_CUTS')
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    # Verify all endpoint provenance before any pool prediction. Each model is
    # loaded and released in turn to avoid three heavyweight live heads.
    folders = [head_run/'endpoints'/(family+'_'+str(seed)) for seed in c.SEEDS]
    identity = fit_identity(fit_rows)
    for seed, folder in zip(c.SEEDS, folders):
        verify_endpoint(folder, family, seed, config, design, norm, fit_rows, training, identity)
    pools = {}
    for pool in ('CAL', 'CIC_DEV', 'UNSW_DEV', 'FIT'):
        role = 'LEARN' if pool in ('FIT', 'CAL') else pool
        ix = indices[pool] if role == 'LEARN' else np.arange(len(metadata[role]), dtype=np.int64)
        rows = [metadata[role][int(i)] for i in ix]
        columns = []
        for seed, folder in zip(c.SEEDS, folders):
            if progress is not None: progress.stage = 'MODERN_ONBOARDING_REPLAY_'+family+'_'+pool+'_'+str(seed)
            model = trainer.load(folder, family, seed, config)
            columns.append(models.scores(model, family, values[role], q[role], ix, norm, progress))
            del model
        logits = np.column_stack(columns)
        recent_decisions = None
        if pool == 'FIT':
            verify_fit_scores(head_run/pool, rows, logits, family)
        else:
            recent = prior._recent(parent, pool, rows)
            c.require(all(cutoff['cuts']['RECENT_'+s] == recent['cuts'][s] for s in evaluation.SUFFIXES),
                      'MODERN_ADAPTER_RECENT_CUT_DRIFT')
            recent_decisions = prior._verify_saved_pool(head_run/pool, rows, logits, family, cuts, ensemble_cut, recent)
            if pool == 'CAL':
                replay_cuts = evaluation.calibrate(rows, {family+'_'+s: columns[j] for j, s in enumerate(evaluation.SUFFIXES[:3])})
                replay_cuts[family+'_ensemble'] = evaluation.calibrate(rows, {family+'_ensemble': evaluation.ensemble(columns)})[family+'_ensemble']
                c.require(all(replay_cuts[family+'_'+s] == cutoff['cuts'][family+'_'+s] for s in evaluation.SUFFIXES),
                          'MODERN_ADAPTER_CAL_REPRODUCTION')
        e3 = take(values[role], ix, slice(0, 768)) if role == 'LEARN' else values[role][:, :768]
        qq = take(q[role], ix) if role == 'LEARN' else q[role]
        pools[pool] = prior._bundle_rows(rows, e3, qq, logits)
        if recent_decisions is not None: pools[pool]['recent_decisions'] = recent_decisions
    refs = prior._references(parent, design)
    pools['CIC_DEV']['banks'] = {'OLD_BANK': refs['DEV']}
    pools['UNSW_DEV']['banks'] = {'OLD_BANK': refs['EXTERNAL_ARCHIVAL_EVALUATION']}
    manifests = {str(parent/rel): digest for rel, digest in prior.PARENT_PINS.items()}
    for source, names in ((parent, ('inputs/SHA256SUMS', 'features/SHA256SUMS', 'normalizers/SHA256SUMS')),
                          (prepared_run, ('SHA256SUMS', 'prepared/SHA256SUMS', 'P_COMPLETE.json')),
                          (head_run, ('SHA256SUMS', 'P_COMPLETE.json', 'T_COMPLETE.json', 'K_COMPLETE.json', 'thresholds.json'))):
        for name in names: manifests[str(source/name)] = c.sha(source/name)
    manifests.update({str(design_path): k.DESIGN_SHA, str(config_path): c.sha(config_path),
                      str(parent/'spool/snapshots.sqlite'): design['provenance']['spool_sha256']})
    return dict(schema='constrained-onboarding-bundle-v1', synthetic_only=False, head_family=family,
        normalizer=norm, input_version=prior.INPUT_VERSION, protocol_sha256=prior.PROTOCOL_SHA256,
        provenance=dict(adapter='modern-head-onboarding-v1', input_sha256=manifests,
            verified_current_parent=True, protected_paths=[str(p) for p in (parent, prepared_run, head_run, design_path, config_path)],
            normalizer_sha256=c.sha(parent/'normalizers/RECENT.npz'),
            source='VERIFIED_RECENT_AND_QUERY_TAIL_PREPARATION_WITH_FIXED_MODERN_HEAD',
            frozen_head_replay='FIT_CAL_CIC_DEV_UNSW_DEV_BITWISE',
            numpy_version=np.__version__, torch_version=torch.__version__, threads=4,
            no_training=True, no_pcap_decode=True, no_e3_forward=True),
        source_fit=pools['FIT'], source_cal=pools['CAL'], source_references=refs['LEARN'],
        cuts=cuts, ensemble_cut=ensemble_cut, targets={name: pools[name] for name in ('CIC_DEV', 'UNSW_DEV')})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'prepared-run', 'head-run', 'design', 'config', 'protocol', 'banks-manifest', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--family', required=True, choices=evaluation.ONBOARDING_FAMILIES)
    args = parser.parse_args(argv)
    c.pin(args.protocol, prior.PROTOCOL_SHA256)
    c.require(not Path(args.output).exists(), 'NO_OVERWRITE:'+args.output)
    bundle = prepare_modern(args.parent, args.prepared_run, args.head_run, args.design, args.config, args.family)
    from constrained_onboarding_runner_v2 import attach_reference_banks, run_development
    attach_reference_banks(bundle, args.banks_manifest)
    c.require(all(set(data['banks']) == {'OLD_BANK', 'B0', 'B1', 'B2'} for data in bundle['targets'].values()),
              'MODERN_ONBOARDING_ALL_POLICIES_REQUIRED')
    bundle['provenance']['protected_paths'].extend([str(Path(p).resolve()) for p in (args.protocol, args.banks_manifest)])
    return run_development(bundle, args.output, args.protocol)


if __name__ == '__main__':
    main()
