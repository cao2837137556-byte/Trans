"""Current reconstructed-cache adapter; frozen head science and v3 onboarding.

The original modern contract remains byte-identical. The separately sealed
supplement registers MLP pairing and the new input lineage, not new recipes.
"""
import gc
import importlib
import importlib.metadata
import platform
import sys
import time
from pathlib import Path
import package_io as io

FAMILIES = ('MLP_QUERY_BCE', 'TabM', 'LightGBM')
SEEDS = (27, 127, 227)
SUFFIXES = ('27', '127', '227', 'ensemble')
POOLS = ('CAL', 'CIC_DEV', 'UNSW_DEV', 'FIT')


def boot(config, strict_versions=True):
    root = Path(config['onboarding_package']).resolve()
    io.pin(root / 'code_manifest.json', config['onboarding_code_manifest_sha256'])
    io.verify_manifest(root, root / 'code_manifest.json')
    io.require(io.read(root / 'config.json') == config['source_config'], 'SOURCE_CONFIG_DRIFT')
    deps = io.ROOT / 'extra_deps'
    receipt = io.read(io.ROOT / 'dependency_install_receipt.json')
    io.require(receipt['status'] == 'INSTALLED_OFFLINE_NOT_EXPERIMENT', 'DEPENDENCY_INSTALL_REQUIRED')
    for name, digest in receipt['files'].items():
        path = (deps / name).resolve()
        io.require(path.is_relative_to(deps.resolve()), 'DEPENDENCY_ESCAPE')
        io.pin(path, digest)
    for name, digest in receipt['wheels'].items():
        io.pin(io.ROOT / 'wheelhouse' / name, digest)
    sys.path.insert(0, str(deps)); sys.path.insert(0, str(root))
    old = importlib.import_module('new_onboarding_adapter')
    io.require(Path(old.__file__).resolve().parent == root, 'ONBOARDING_ADAPTER_SHADOW')
    lc, modules, design = old.bootstrap(config['source_config'], strict_versions=strict_versions)
    sys.path.insert(0, str(io.ROOT / 'frozen_modern'))
    models = importlib.import_module('modern_head_models_v1')
    train = importlib.import_module('modern_head_train_v1')
    evaluate = importlib.import_module('modern_head_evaluate_v1')
    prior = importlib.import_module('modern_head_onboarding_v1')
    for module in (models, train, evaluate, prior):
        io.require(Path(module.__file__).resolve().parent == io.ROOT / 'frozen_modern', 'MODERN_IMPORT_SHADOW')
    for name, digest in io.read(io.ROOT / 'inheritance.json')['shared_dependencies'].items():
        shared = importlib.import_module(name[:-3])
        io.pin(Path(shared.__file__), digest)
    config_head = io.read(io.ROOT / 'experiment_contract.json')
    models.validate_config(config_head); evaluate.validate_config(config_head, design)
    io.pin(io.ROOT / 'protocol.json', '2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5')
    if strict_versions:
        io.require(sys.version_info[:2] == (3, 9), 'PY39_REQUIRED')
        for name, version in config['versions'].items():
            io.require(importlib.metadata.version(name).split('+')[0] == version, 'DEPENDENCY_VERSION:' + name)
        models.official_tabm()
    import torch
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    return dict(old=old, lc=lc, modules=modules, design=design, models=models,
                train=train, evaluate=evaluate, prior=prior, contract=config_head,
                c=modules['query_tail_core_v2'].c)


def runtime():
    import torch
    import numpy as np
    return dict(python=platform.python_version(), numpy=np.__version__, torch=torch.__version__,
                torch_config=torch.__config__.show(), cpu_capability=torch.backends.cpu.get_cpu_capability(),
                machine=platform.machine(), threads=4)


def source_state(config, context, full=False):
    s = config['source_config']; lc, c = context['lc'], context['c']
    oldrun, cache = Path(s['head_run']), Path(s['cache'])
    marker = lc.read(lc.pin(oldrun / 'QUERY_LINEAGE_COMPLETE.json', s['head_complete_sha256']))
    binding = lc.read(lc.pin(oldrun / 'cache_binding.json', s['head_cache_binding_sha256']))
    lc.pin(cache / 'CACHE_REBUILD_COMPLETE.json', s['cache_marker_sha256'])
    if full:
        lc.verify_run_complete(oldrun, s['head_complete_sha256'])
        actual = lc.bind_cache(cache, s['cache_marker_sha256'], context['design'], c)
        lc.require(actual == binding, 'CURRENT_CACHE_BINDING_DRIFT')
    lc.require(binding['lineage'] == marker['lineage'] == lc.LINEAGE and
               binding['parent_parity'] == 'PARENT_PARITY_UNAVAILABLE', 'NEW_LINEAGE_REQUIRED')
    for stage in ('P', 'T', 'K'):
        lc.pin(oldrun / ('LINEAGE_' + stage + '_COMPLETE.json'), marker[stage + '_sha256'])
    p = lc.read(oldrun / 'LINEAGE_P_COMPLETE.json')
    lc.verify(oldrun / 'prepared', p['prepared_seal_sha256'])
    return oldrun, cache, marker, binding


def banks(config, context):
    c = context['c']; path = Path(config['banks_manifest']).resolve()
    io.pin(path, config['banks_manifest_sha256'])
    spec = io.read(path)
    io.require(set(spec) == {'pools'} and set(spec['pools']) == {'CIC_DEV', 'UNSW_DEV'}, 'BANK_POOLS')
    identities = {}
    for pool, policies in spec['pools'].items():
        io.require(set(policies) == {'B0', 'B1', 'B2'}, 'BANK_POLICIES')
        for policy, item in policies.items():
            folder = (path.parent / item['path']).resolve()
            io.require(folder.is_relative_to((path.parent / 'encoded' / pool).resolve()), 'BANK_ESCAPE')
            record = io.read(io.pin(folder / 'receipt.json', item['receipt_sha256']))
            io.require(record['status'] == 'COMPLETE' and record['synthetic_only'] is False and
                       record['real_recent_features'] is True and record['policy'] == policy, 'REAL_BANK_REQUIRED')
            binding = io.read(io.pin(Path(config['source_config']['head_run']) / 'cache_binding.json',
                                    config['source_config']['head_cache_binding_sha256']))
            verify_encoded_bank(folder, record, binding['normalizer_files']['RECENT.npz'], context)
            identities[pool + '/' + policy] = item['receipt_sha256']
    return identities


def verify_encoded_bank(folder, record, normalizer_sha256, context):
    """Use encode_selected's actual receipt contract; it emits no SHA256SUMS.

    The immutable banks_manifest pins receipt.json. The receipt in turn pins
    every emitted payload plus the source normalizer. Ancestor preparation and
    runtime digests remain provenance; no decoder/model re-execution is needed.
    """
    import numpy as np
    c = context['c']; folder = Path(folder)
    reference = context['modules']['constrained_onboarding_reference_v2']
    io.require(record['input_version'] == context['modules']['constrained_onboarding_query_tail_adapter_v2'].INPUT_VERSION and
               record['normalizer_sha256'] == normalizer_sha256 and
               record['e3_dimensions'] == 768 and record['q14_dimensions'] == 14 and
               record['model_training'] is False and record['classifier_scoring'] is False,
               'BANK_PRODUCER_CONTRACT')
    for name, field in (('bank.npz', 'bank_npz_sha256'), ('references.jsonl.gz', 'metadata_sha256'),
                        ('tensor_receipts.jsonl.gz', 'tensor_receipts_sha256'), ('environment.json', 'environment_sha256')):
        io.pin(folder / name, record[field])
    rows = list(c.rows(folder / 'references.jsonl.gz')); uids = [r['uid'] for r in rows]
    io.require(len(rows) == record['rows'] and len(set(uids)) == len(rows) and
               reference.digest(uids) == record['selected_uid_sha256'] and
               all(r['label'] == 0 and r['use'] == 'REFERENCE' for r in rows), 'BANK_METADATA_IDENTITY')
    with np.load(folder / 'bank.npz', allow_pickle=False) as saved:
        io.require(saved['uid'].tolist() == uids, 'BANK_ARRAY_UID_JOIN')
        for name, width in (('e3', 768), ('q14', 14)):
            x = saved[name]
            io.require(x.shape == (len(rows), width) and x.dtype == np.float32 and np.isfinite(x).all(),
                       'BANK_ARRAY_SCHEMA:' + name)


def data(config, context, progress=None):
    oldrun, cache, marker, binding = source_state(config, context)
    p = context['modules']['query_tail_prepare_v2']; lc = context['lc']
    metadata, indices = p.load_metadata(cache, context['design'])
    values, norm = lc.load_arrays(cache, binding, context['design'], progress)
    q = context['old'].validate_prepared(cache, oldrun, binding, marker, context['design'],
                                       indices, norm, lc, context['modules'])
    return metadata, indices, values, q, norm, binding


def prepare(config, context, progress):
    c = context['c']; run = Path(config['run']); s = config['source_config']
    progress.stage = 'VERIFY_RECONSTRUCTED_INPUTS'; progress.tick(0, 1, force=True)
    oldrun, cache, marker, binding = source_state(config, context, full=True)
    # Existing input was never sealed with this complete runtime fingerprint.
    # Do not manufacture retrospective evidence to claim reuse.
    old_manifest = {line.split('  ', 1)[1] for line in (oldrun / 'SHA256SUMS').read_text().splitlines()}
    has_runtime = 'numeric_runtime.json' in old_manifest
    reason = ('BASELINE_NUMERIC_RUNTIME_FINGERPRINT_UNAVAILABLE' if not has_runtime
              else 'RETRAIN_FIXED_BASELINE_REUSE_NOT_CLAIMED')
    c.write(run / 'heads/reuse_plan.json', dict(status='TRAIN_REQUIRED', reason=reason,
        runtime_fingerprint_sealed=has_runtime, new_training_endpoints=9,
        historical_weights_used=False))
    c.write(run / 'heads/numeric_runtime.json', runtime())
    compact = context['lc'].read(oldrun / 'compact_metadata_receipt.json')
    context['lc'].verify(oldrun / 'training_metadata', compact['seal_sha256'])
    c.write(run / 'heads/P_COMPLETE.json', dict(status='COMPLETE', lineage='NEW_RECONSTRUCTION_LINEAGE',
        parent_parity='PARENT_PARITY_UNAVAILABLE', config_digest=c.digest(context['contract']),
        registration_sha256=io.sha(io.ROOT / 'supplementary_registration.json'),
        prepared_seal_sha256=io.sha(oldrun / 'prepared/SHA256SUMS'),
        cache_binding_sha256=s['head_cache_binding_sha256'], cache_marker_sha256=s['cache_marker_sha256'],
        source_query_complete_sha256=s['head_complete_sha256'],
        compact_metadata_seal_sha256=compact['seal_sha256'], no_e3_forward=True, no_pcap_decode=True))
    progress.tick(1, 1, force=True)


def train_one(config, context, family, seed, progress):
    import numpy as np
    oldrun, cache, marker, binding = source_state(config, context)
    c = context['c']; run = Path(config['run'])
    done = c.read(run / 'heads/P_COMPLETE.json')
    c.require(done['config_digest'] == c.digest(context['contract']) and
              done['cache_binding_sha256'] == config['source_config']['head_cache_binding_sha256'], 'P_BINDING')
    compact = c.read(oldrun / 'compact_metadata_receipt.json')
    context['lc'].verify(oldrun / 'training_metadata', done['compact_metadata_seal_sha256'])
    rows = context['modules']['training_metadata_v1'].Rows(oldrun / 'training_metadata',
        expected_source_sha256=compact['source_sha256'],
        expected_uid_sha256=context['design']['data']['uid_sha256']['LEARN'])
    try:
        values = np.load(c.pin(cache / 'features/LEARN.npy', binding['feature_files']['LEARN.npy']),
                         mmap_mode='r', allow_pickle=False)
        q = np.load(oldrun / 'prepared/LEARN_q.npy', mmap_mode='r', allow_pickle=False)
        with np.load(oldrun / 'prepared/FIT.npz', allow_pickle=False) as saved:
            fit = saved['indices'].copy()
        with np.load(oldrun / 'prepared/normalizer.npz', allow_pickle=False) as saved:
            norm = saved['mean'].copy(), saved['scale'].copy()
        context['train'].train(context['contract'], rows, values, q, norm, fit, family, seed,
                              run / 'heads/endpoints' / (family + '_' + str(seed)), progress)
    finally:
        rows.close()


def baseline(oldrun, pool, rows, context):
    import numpy as np
    c = context['c']; old = context['modules']['constrained_onboarding_query_tail_adapter_v2']
    cutoff = c.read(oldrun / 'thresholds.json')
    with np.load(oldrun / pool / 'scores.npz', allow_pickle=False) as saved:
        c.require(saved['uid'].tolist() == [r['uid'] for r in rows], 'BASELINE_SCORE_UID')
        scores = {'RECENT_' + s: saved['RECENT_' + s].copy() for s in SUFFIXES}
    c.require(old._exact_equal(context['evaluate'].ensemble([scores['RECENT_' + s] for s in SUFFIXES[:3]]),
                               scores['RECENT_ensemble']), 'BASELINE_ENSEMBLE')
    with np.load(oldrun / pool / 'decisions.npz', allow_pickle=False) as saved:
        c.require(saved['uid'].tolist() == [r['uid'] for r in rows], 'BASELINE_DECISION_UID')
        for name, score in scores.items():
            c.require(np.array_equal(score > cutoff['cuts'][name], saved[name]), 'BASELINE_DECISION_DRIFT')
    return scores


def evaluate(config, context, progress):
    import numpy as np
    from continuous_evaluate_v3 import report
    c, ev, train, models = (context[k] for k in ('c', 'evaluate', 'train', 'models'))
    head = Path(config['run']) / 'heads'; oldrun = Path(config['source_config']['head_run'])
    contract = context['contract']
    metadata, indices, arrays, q, norm, binding = data(config, context, progress)
    endpoints = [c.read(head / 'endpoints' / (f + '_' + str(s)) / 'endpoint.json') for f in FAMILIES for s in SEEDS]
    c.write(head / 'T_COMPLETE.json', dict(status='COMPLETE', config_digest=c.digest(contract), endpoints=endpoints))
    gates, checks, summary, timings = {f: {} for f in FAMILIES}, {f: [] for f in FAMILIES}, {}, {}
    cuts = None
    for pool in POOLS:
        role = 'LEARN' if pool in ('FIT', 'CAL') else pool
        ix = indices[pool] if role == 'LEARN' else np.arange(len(metadata[role]), dtype=np.int64)
        rows = [metadata[role][int(i)] for i in ix]
        scores = baseline(oldrun, pool, rows, context) if pool != 'FIT' else {}
        for family in FAMILIES:
            for seed in SEEDS:
                progress.stage = 'SCORE_' + pool + '_' + family + '_' + str(seed)
                started = time.monotonic()
                model = train.load(head / 'endpoints' / (family + '_' + str(seed)), family, seed, contract)
                scores[family + '_' + str(seed)] = models.scores(model, family, arrays[role], q[role], ix, norm, progress)
                timings[pool + '_' + family + '_' + str(seed)] = dict(rows=len(rows), seconds=time.monotonic()-started)
                del model
            scores[family + '_ensemble'] = ev.ensemble([scores[family + '_' + str(s)] for s in SEEDS])
        if pool == 'CAL':
            cuts = ev.calibrate(rows, scores)
            prior_cuts = c.read(oldrun / 'thresholds.json')['cuts']
            c.require(all(cuts['RECENT_' + s] == prior_cuts['RECENT_' + s] for s in SUFFIXES), 'R0_CAL_REPRODUCTION')
            c.write(head / 'thresholds.json', dict(cuts=cuts, source='ORIGINAL_SOURCE_CAL_NORMAL_ONLY',
                budget=.01, comparator='strict >', normal_rows=sum(r['label'] == 0 for r in rows),
                normal_uid_sha256=c.uid_sha(r['uid'] for r in rows if r['label'] == 0),
                config_digest=c.digest(contract), gates_digest=c.digest(contract['gates']),
                lineage='NEW_RECONSTRUCTION_LINEAGE', target_calibration=False,
                seed_order=list(SEEDS), ensemble='np.stack(seed_vectors).mean(axis=0,dtype=float64)'))
        folder = head / pool; folder.mkdir()
        c.save_arrays(folder / 'scores.npz', uid=np.asarray([r['uid'] for r in rows]), **scores)
        if pool != 'FIT':
            decisions = {name: value > cuts[name] for name, value in scores.items()}
            reports = {}
            for j, (name, prediction) in enumerate(decisions.items()):
                progress.stage = 'REPORT_' + pool; progress.tick(j, len(decisions), force=True)
                reports[name] = report(rows, prediction, decisions['RECENT_' + name.rsplit('_', 1)[1]])
            c.save_arrays(folder / 'decisions.npz', uid=np.asarray([r['uid'] for r in rows]), **decisions)
            c.write(folder / 'reports.json', reports)
            for family in FAMILIES:
                if pool != 'CAL': gates[family][pool] = ev.gate(contract, reports, pool, family)
                if pool in ('CAL', 'CIC_DEV'): checks[family].extend(ev.regressions(rows, decisions, pool, family))
            summary[pool] = ev.comparison_summary(reports)
            del reports, decisions
        c.seal(folder); c.verify(folder); del scores; gc.collect()
    candidates = {f: dict(common_gates=gates[f], attack_group_protection=checks[f],
        core_capability_pass=all(v['passed'] for v in gates[f].values()) and all(v['passed'] for v in checks[f])) for f in FAMILIES}
    decision = dict(families=candidates, automatic_promotion=False, selected_family=None,
        onboarding_families=list(FAMILIES), onboarding_selection='FIXED_SUPPLEMENTARY_REGISTRATION_BEFORE_NEW_RESULTS',
        independent_ID='NOT_RUN', historical_holdout='CLOSED', evidence='CONSUMED_DEVELOPMENT_ONLY',
        config_digest=c.digest(contract), registration_sha256=io.sha(io.ROOT / 'supplementary_registration.json'), retries=0)
    c.write(head / 'comparison_summary.json', dict(pools=summary, prediction_cost=timings, no_automatic_winner=True))
    c.write(head / 'decision.json', decision)
    c.write(head / 'K_COMPLETE.json', dict(status='COMPLETE', config_digest=c.digest(contract),
        decision_sha256=c.sha(head / 'decision.json'), summary_sha256=c.sha(head / 'comparison_summary.json')))
    c.seal(head); c.verify(head)
    io.write(Path(config['run']) / 'HEADS_COMPLETE.json', dict(status='COMPLETE',
        config_digest=c.digest(contract), head_seal_sha256=c.sha(head / 'SHA256SUMS'),
        registration_sha256=io.sha(io.ROOT / 'supplementary_registration.json'),
        decision_sha256=c.sha(head / 'decision.json')))


def verified_heads(config, context):
    c = context['c']; run = Path(config['run']); head = run / 'heads'
    done = c.read(run / 'HEADS_COMPLETE.json')
    c.require(done['status'] == 'COMPLETE' and done['config_digest'] == c.digest(context['contract']) and
              done['registration_sha256'] == io.sha(io.ROOT / 'supplementary_registration.json'), 'HEADS_COMPLETE_REQUIRED')
    c.pin(head / 'SHA256SUMS', done['head_seal_sha256']); c.verify(head)
    c.pin(head / 'decision.json', done['decision_sha256'])
    # A scientific FAIL does not invalidate completed predictions or prohibit pairing.
    decision = c.read(head / 'decision.json')
    c.require(decision['automatic_promotion'] is False and decision['selected_family'] is None and
              decision['onboarding_families'] == list(FAMILIES), 'NO_TARGET_CANDIDATE_SELECTION')
    return head


def onboard(config, context, family, progress):
    import numpy as np
    from indexed_features_v1 import take
    c = context['c']; head = verified_heads(config, context)
    banks(config, context)
    runner = importlib.import_module('constrained_onboarding_runner_v3')
    io.require(Path(runner.__file__).resolve().parent == Path(config['onboarding_package']).resolve(), 'RUNNER_V3_SHADOW')
    old = context['modules']['constrained_onboarding_query_tail_adapter_v2']
    metadata, indices, values, q, norm, binding = data(config, context, progress)
    oldrun = Path(config['source_config']['head_run']); contract = context['contract']
    cut = c.read(head / 'thresholds.json'); training = c.read(head / 'T_COMPLETE.json')
    c.require(cut['source'] == 'ORIGINAL_SOURCE_CAL_NORMAL_ONLY' and cut['budget'] == .01 and
              cut['comparator'] == 'strict >' and cut['normal_rows'] == 33147 and
              cut['config_digest'] == c.digest(contract) and cut['target_calibration'] is False, 'CUT_CONTRACT')
    cuts = np.asarray([cut['cuts'][family + '_' + str(s)] for s in SEEDS]); ecut = cut['cuts'][family + '_ensemble']
    fitrows = [metadata['LEARN'][int(i)] for i in indices['FIT']]
    identity = context['prior'].fit_identity(fitrows)
    for seed in SEEDS:
        context['prior'].verify_endpoint(head / 'endpoints' / (family + '_' + str(seed)), family, seed,
            contract, context['design'], norm, fitrows, training, identity)
    del fitrows
    pools, replay = {}, {}
    for pool in POOLS:
        role = 'LEARN' if pool in ('FIT', 'CAL') else pool
        ix = indices[pool] if role == 'LEARN' else np.arange(len(metadata[role]), dtype=np.int64)
        rows = [metadata[role][int(i)] for i in ix]; columns = []
        for seed in SEEDS:
            progress.stage = 'MODULE_REPLAY_' + family + '_' + pool + '_' + str(seed)
            model = context['train'].load(head / 'endpoints' / (family + '_' + str(seed)), family, seed, contract)
            columns.append(context['models'].scores(model, family, values[role], q[role], ix, norm, progress))
            del model
        logits = np.column_stack(columns)
        if pool == 'FIT':
            context['prior'].verify_fit_scores(head / pool, rows, logits, family)
            recent_decisions = None
        else:
            base = baseline(oldrun, pool, rows, context)
            recent = {'cuts': {s: cut['cuts']['RECENT_' + s] for s in SUFFIXES}}
            recent.update({s: base['RECENT_' + s] for s in SUFFIXES})
            recent_decisions = old._verify_saved_pool(head / pool, rows, logits, family, cuts, ecut, recent)
            if pool == 'CAL':
                test = context['evaluate'].calibrate(rows, {family + '_' + s: columns[j] for j, s in enumerate(SUFFIXES[:3])})
                test.update(context['evaluate'].calibrate(rows, {family + '_ensemble': context['evaluate'].ensemble(columns)}))
                c.require(all(test[family + '_' + s] == cut['cuts'][family + '_' + s] for s in SUFFIXES), 'CAL_REPLAY_CUT')
        e3 = take(values[role], ix, slice(0, 768)) if role == 'LEARN' else values[role][:, :768]
        qq = take(q[role], ix) if role == 'LEARN' else q[role]
        pools[pool] = old._bundle_rows(rows, e3, qq, logits)
        if recent_decisions is not None: pools[pool]['recent_decisions'] = recent_decisions
        replay[pool] = dict(status='BITWISE_IDENTICAL', rows=len(rows), uid_sha256=c.uid_sha(r['uid'] for r in rows))
    refs = context['old'].old_references(Path(config['source_config']['cache']), binding, context['lc'], context['modules'])
    pools['CIC_DEV']['banks'] = {'OLD_BANK': refs['DEV']}
    pools['UNSW_DEV']['banks'] = {'OLD_BANK': refs['EXTERNAL_ARCHIVAL_EVALUATION']}
    bundle = dict(schema='constrained-onboarding-bundle-v1', synthetic_only=False, head_family=family,
        normalizer=norm, input_version=old.INPUT_VERSION, protocol_sha256=old.PROTOCOL_SHA256,
        source_fit=pools['FIT'], source_cal=pools['CAL'], source_references=refs['LEARN'],
        cuts=cuts, ensemble_cut=ecut, targets={p: pools[p] for p in ('CIC_DEV', 'UNSW_DEV')},
        provenance=dict(adapter='modern-new-lineage-v1', lineage='NEW_RECONSTRUCTION_LINEAGE',
            parent_parity='PARENT_PARITY_UNAVAILABLE', verified_current_parent=True,
            normalizer_sha256=binding['normalizer_files']['RECENT.npz'],
            protected_paths=[config['source_config']['cache'], str(oldrun), str(head), str(io.ROOT)],
            source='SEALED_SAME_CACHE_MODERN_HEADS', replay=replay, no_training=True,
            no_pcap_decode=True, no_e3_forward=True,
            registration_sha256=io.sha(io.ROOT / 'supplementary_registration.json')))
    runner.attach_reference_banks(bundle, config['banks_manifest'])
    c.require(all(set(v['banks']) == {'OLD_BANK', 'B0', 'B1', 'B2'} for v in bundle['targets'].values()), 'ALL_POLICIES_REQUIRED')
    progress.stage = 'MODULE_FIT_AND_EVALUATE_' + family; progress.tick(0, 1, force=True)
    result = runner.run_development(bundle, Path(config['run']) / 'onboarding' / family, io.ROOT / 'protocol.json')
    c.require(result['status'] == 'COMPLETE' and result.get('optimizer_updates') == 0 and
              result['automatic_model_selection'] is False, 'MODULE_EXECUTION_CONTRACT')
    progress.tick(1, 1, force=True)
