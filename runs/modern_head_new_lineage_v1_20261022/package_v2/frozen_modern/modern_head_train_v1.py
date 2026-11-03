"""Source-FIT-only fixed endpoint training; sequential callers bound residency."""
from collections.abc import Sequence
import hashlib
from importlib.metadata import version
import math
from pathlib import Path
import platform
import shutil
import time
import numpy as np
import torch
import modern_head_models_v1 as m

c, k = m.c, m.k
scores = m.scores
default_training_config = m.default_training_config


class IndexRows(Sequence):
    """An index view, not a materialized copy of full Python metadata."""
    def __init__(self, rows, indices): self.rows, self.indices = rows, indices
    def __len__(self): return len(self.indices)
    def __getitem__(self, index):
        if isinstance(index, slice): return IndexRows(self.rows, self.indices[index])
        return self.rows[int(self.indices[index])]


def fit_inputs(rows, values, q, norm, indices, synthetic):
    ix = np.asarray(indices)
    c.require(ix.ndim == 1 and np.issubdtype(ix.dtype, np.integer) and len(ix) > 0 and
              len(np.unique(ix)) == len(ix) and np.all(ix >= 0) and np.all(ix < len(rows)), 'MODERN_FIT_INDICES')
    c.require(len(rows) == len(values) == len(q) and values.ndim == 2 and values.shape[1] >= 768 and
              values.dtype == np.float32 and q.shape == (len(rows), 14) and q.dtype == np.float32,
              'MODERN_INPUT_SCHEMA')
    selected = IndexRows(rows, ix)
    c.require(all(r['partition'] == 'LEARN' and r['fit_role'] == 'FIT' and
                  r['use'] != 'REFERENCE' and r['label'] in (0, 1) for r in selected), 'MODERN_FIT_ONLY')
    c.require(len(ix) <= 256 if synthetic else len(ix) == 617908, 'MODERN_FIT_SIZE')
    labels = np.asarray([r['label'] for r in selected], dtype=np.float32)
    weights = k.weights(selected)
    # UID identity includes sorted membership and actual optimizer traversal order.
    ordered = hashlib.sha256(); seen = set()
    for row in selected:
        uid = row['uid']; c.require(uid not in seen, 'MODERN_DUPLICATE_FIT_UID')
        seen.add(uid); ordered.update((uid+'\n').encode())
    identity = dict(rows=len(ix), uid_sha256=c.uid_sha(seen), ordered_uid_sha256=ordered.hexdigest(),
                    weight_sha256=hashlib.sha256(weights.tobytes()).hexdigest(),
                    label_sha256=hashlib.sha256(labels.tobytes()).hexdigest(),
                    indices_sha256=hashlib.sha256(ix.astype('<i8').tobytes()).hexdigest(),
                    normalizer_digest=c.digest([v.tolist() for v in norm]))
    del seen
    return ix, labels, weights, identity


def versions(family):
    result = dict(python=platform.python_version(), numpy=np.__version__, torch=torch.__version__)
    if family == 'TabM':
        m.official_tabm()
        result.update(tabm='0.0.3', tabm_source_sha256=m.TABM_SHA,
                      tabm_license_sha256=m.TABM_LICENSE_SHA, rtdl_num_embeddings=version('rtdl-num-embeddings'))
    if family == 'LightGBM':
        result['lightgbm'] = version('lightgbm')
        c.require(result['lightgbm'] == '4.6.0', 'LIGHTGBM_VERSION')
    return result


def train(config, rows, values, q, norm, indices, family, seed, out, progress, synthetic=False):
    hp = m.validate_config(config, synthetic)
    c.require(family in m.FAMILIES and seed in c.SEEDS, 'MODERN_TRAIN_SCOPE')
    ix, labels, weights, identity = fit_inputs(rows, values, q, norm, indices, synthetic)
    environment = versions(family)
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    start_time = time.monotonic()
    if family == 'LightGBM':
        model, details = _train_tree(config, values, q, norm, ix, labels, weights, seed, out, progress)
        filename = 'lightgbm.txt'; score_definition = 'binary raw margin'
    else:
        model, details = _train_neural(config, values, q, norm, ix, labels, weights, family, seed, out, progress)
        filename = 'head.npz'
        score_definition = ('classifier logit' if family == 'MLP_QUERY_BCE' else
                            'logsumexp(logsigmoid(member_logits.float64))-logsumexp(logsigmoid(-member_logits.float64))')
    endpoint = dict(status='COMPLETE', family=family, seed=seed, dimension=782,
                    config_digest=c.digest(config), head_sha256=c.sha(out/filename),
                    synthetic_only=synthetic, reference_used=False, DEV_used=False, CAL_used=False,
                    input_normalization='fixed source FIT E3 mean/scale; unchanged q14',
                    score_definition=score_definition, versions=environment,
                    training_seconds=time.monotonic()-start_time,
                    timing_boundary='model construction / FIT matrix construction through final model serialization',
                    **identity, **details)
    c.write(out/'endpoint.json', endpoint); c.seal(out); c.verify(out)
    return model


def _train_neural(config, values, q, norm, ix, labels, weights, family, seed, out, progress):
    hp = config['training']; n = len(ix); batch_size = hp['batch_size']
    model = m.classifier(family, seed, config)
    c.save_arrays(out/'initial.npz', **{name:v.detach().numpy() for name,v in model.state_dict().items()})
    opt = dict(hp['optimizer_mlp' if family == 'MLP_QUERY_BCE' else 'optimizer_tabm'])
    opt['betas'] = tuple(opt['betas']); optimizer = torch.optim.AdamW(model.parameters(), **opt)
    generator = torch.Generator(device='cpu').manual_seed(seed)
    total = hp['epochs']*math.ceil(n/batch_size); updates = 0; orders = []
    for epoch in range(hp['epochs']):
        model.train(); order = torch.randperm(n, generator=generator).numpy()
        orders.append(hashlib.sha256(order.tobytes()).hexdigest())
        loss_sum = 0.; visits = 0
        if progress is not None: progress.stage = 'T_'+family+'_'+str(seed)+'_epoch'+str(epoch+1)
        for begin in range(0, n, batch_size):
            local = order[begin:begin+batch_size]
            optimizer.zero_grad(set_to_none=True)
            prediction = model(k.normalized(values, q, ix[local], norm, 782))
            target = torch.from_numpy(labels[local])
            loss = (k.objective(prediction.flatten(), target, weights[local], n) if family == 'MLP_QUERY_BCE'
                    else m.tabm_weighted_bce(prediction, target, weights[local], n))
            c.require(bool(torch.isfinite(loss)), 'MODERN_NONFINITE_LOSS')
            loss.backward()
            c.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()),
                      'MODERN_INVALID_GRADIENT')
            optimizer.step()
            c.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), 'MODERN_INVALID_PARAMETER')
            updates += 1; visits += len(local); loss_sum += float(loss.detach())*len(local)/n
            if progress is not None:
                progress.optimizer_updates = updates; progress.tick(updates, total)
        c.require(visits == n, 'MODERN_FULL_FIT_VISITS')
        c.write(out/('epoch_%02d.json' % (epoch+1)), dict(epoch=epoch+1, updates=updates, fit_visits=visits,
                weighted_bce=loss_sum, loss_aggregation='sum(batch_loss*batch_rows/FIT_rows)',
                order_sha256=orders[-1]))
    c.require(updates == total, 'MODERN_UPDATE_COUNT')
    c.save_arrays(out/'head.npz', **{name:v.detach().numpy() for name,v in model.state_dict().items()})
    details = dict(epochs=hp['epochs'], updates=updates, order_hashes=orders,
                   initial_sha256=c.sha(out/'initial.npz'), parameters=sum(p.numel() for p in model.parameters()),
                   internal_members=32 if family == 'TabM' else 1,
                   objective='member-wise weighted BCE then mean' if family == 'TabM' else 'weighted BCE',
                   endpoint_selection='final fixed epoch only')
    return model.eval().requires_grad_(False), details


def _train_tree(config, values, q, norm, ix, labels, weights, seed, out, progress):
    import lightgbm as lgb
    params = m.lightgbm_parameters(config, seed); rounds = config['training']['lightgbm']['num_boost_round']
    # The sole full FIT feature matrix is float32; no all-pool dense copy is constructed.
    matrix = np.empty((len(ix), 782), dtype=np.float32)
    for begin in range(0, len(ix), 1024):
        part = ix[begin:begin+1024]; matrix[begin:begin+len(part)] = k.normalized(values, q, part, norm, 782).numpy()
        if progress is not None:
            progress.stage = 'T_LIGHTGBM_FIT_MATRIX'; progress.tick(begin+len(part), len(ix))
    scaled = m.lightgbm_weights(weights)
    dataset = lgb.Dataset(matrix, label=labels, weight=scaled, params=params, free_raw_data=True)
    dataset.construct(); del matrix
    evaluations = []; counter = [0]
    def callback(env):
        counter[0] += 1
        evaluations.append(dict(iteration=env.iteration+1,
                                training_binary_logloss=float(env.evaluation_result_list[0][2])))
        if progress is not None:
            progress.stage = 'T_LightGBM_'+str(seed); progress.optimizer_updates = counter[0]
            progress.tick(counter[0], rounds)
    callback.order = 20
    model = lgb.train(params, dataset, num_boost_round=rounds, valid_sets=[dataset], valid_names=['FIT'],
                      callbacks=[callback], keep_training_booster=True)
    # The native booster may stop adding trees when no legal split remains.
    # LightGBM 4.6.0 can still invoke all Python callbacks in that case, so
    # callback visits and retained tree iterations must be reported separately.
    effective = model.current_iteration()
    c.require(0 < counter[0] <= rounds and 0 < effective <= counter[0], 'TREE_ITERATION_ACCOUNTING')
    native_stop = effective < rounds
    accounting = dict(requested_rounds=rounds, callback_iterations=counter[0],
                      effective_tree_iterations=effective, native_stop=native_stop,
                      native_stop_definition='fewer retained tree iterations than the requested fixed budget',
                      early_stopping=False)
    c.require(np.isfinite([r['training_binary_logloss'] for r in evaluations]).all(), 'TREE_NONFINITE_LOSS')
    model.save_model(str(out/'lightgbm.txt'), num_iteration=-1)
    c.write(out/'training_log.json', dict(rows=evaluations, params=params, **accounting,
            no_split_note='The requested budget is passed unchanged to LightGBM; native inability to split is permitted. Callback visits do not count retained trees.'))
    # Release native training dataset before scoring other pools.
    model.free_dataset()
    details = dict(boosting_rounds=rounds, updates=counter[0], **accounting,
                   boosting_rounds_definition='requested budget; not retained tree iterations',
                   updates_definition='Python callback iterations; not retained tree iterations',
                   tree_count=model.num_trees(), parameters=None, parameter_count_note='tree ensemble; report tree count',
                   fit_matrix_bytes=len(ix)*782*4, training_weight_scale='N*w; mean 1',
                   scaled_weight_sha256=hashlib.sha256(scaled.tobytes()).hexdigest(),
                   endpoint_selection='fixed requested boosting budget with legal native stop; no validation early stop', objective='weighted binary logloss')
    return model, details


def load(folder, family, seed, config):
    folder = Path(folder); c.verify(folder)
    r = c.read(folder/'endpoint.json')
    m.validate_config(config, r.get('synthetic_only') is True)
    c.require(r['status'] == 'COMPLETE' and r['family'] == family and r['seed'] == seed and
              r['config_digest'] == c.digest(config) and r['dimension'] == 782, 'MODERN_ENDPOINT_IDENTITY')
    c.require(r['reference_used'] is False and r['DEV_used'] is False and r['CAL_used'] is False,
              'MODERN_ENDPOINT_TRAIN_SCOPE')
    environment = versions(family)
    c.require(r['versions'] == environment, 'MODERN_REPLAY_ENVIRONMENT')
    if family == 'LightGBM':
        import lightgbm as lgb
        c.pin(folder/'lightgbm.txt', r['head_sha256'])
        model = lgb.Booster(model_file=str(folder/'lightgbm.txt'))
        c.require(model.num_feature() == 782 and model.current_iteration() == r['effective_tree_iterations'],
                  'MODERN_TREE_ENDPOINT')
        return model
    model = m.classifier(family, seed, config)
    c.pin(folder/'head.npz', r['head_sha256'])
    with np.load(folder/'head.npz', allow_pickle=False) as saved:
        c.require(set(saved.files) == set(model.state_dict()), 'MODERN_HEAD_KEYS')
        state = {key:torch.from_numpy(saved[key].copy()) for key in saved.files}
        c.require(all(torch.isfinite(v).all() for v in state.values()), 'MODERN_HEAD_NONFINITE')
        model.load_state_dict(state)
    return model.eval().requires_grad_(False)


class ReuseIneligible(RuntimeError):
    """Verified source is unsuitable for reuse; caller may train a new endpoint."""
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def reuse_mlp_preconditions(original_folder, original_design, config, rows, values,
                            q, norm, indices, replay_receipt):
    """Read-only complete adoption check, before announcing REUSE_VERIFIED.

    Missing reuse metadata or incompatible recipes return TRAIN_REQUIRED. Seal,
    hash, unreadable model data, and nonfinite weights remain hard failures and
    must not be converted to a retraining fallback. No destination is created.
    """
    def ineligible(reason): return dict(status='TRAIN_REQUIRED', reason=reason)
    source = Path(original_folder); c.verify(source)
    old = c.read(source/'endpoint.json')
    synthetic = config.get('synthetic_only') is True
    hp = m.validate_config(config, synthetic)
    _, _, _, identity = fit_inputs(rows, values, q, norm, indices, synthetic)
    fields = ('seed', 'status', 'arm', 'dimension', 'design_digest', 'synthetic_only',
              'reference_used', 'DEV_used', 'objective', 'rows', 'uid_sha256',
              'weight_sha256', 'normalizer_digest', 'epochs', 'updates',
              'head_sha256', 'initial_sha256', 'order_hashes')
    if not isinstance(old, dict): return ineligible('MLP_REUSE_SOURCE_METADATA_INVALID')
    absent = [field for field in fields if field not in old]
    if absent: return ineligible('MLP_REUSE_SOURCE_METADATA_MISSING:'+','.join(absent))
    seed = old['seed']
    c.pin(source/'head.npz', old['head_sha256']); c.pin(source/'initial.npz', old['initial_sha256'])
    expected_optimizer = {key:value for key,value in hp['optimizer_mlp'].items()
                          if key not in ('foreach', 'amsgrad')}
    old_hp = original_design.get('training', {}) if isinstance(original_design, dict) else {}
    if not isinstance(old_hp, dict): return ineligible('MLP_REUSE_RECIPE')
    if not (old_hp.get('epochs') == hp['epochs'] and old_hp.get('batch_size') == hp['batch_size'] and
            old_hp.get('optimizer_parent_values') == expected_optimizer): return ineligible('MLP_REUSE_RECIPE')
    if not (seed in c.SEEDS and old['status'] == 'COMPLETE' and old['arm'] == 'QUERY_BCE' and old['dimension'] == 782 and
              old['design_digest'] == c.digest(original_design) and old['synthetic_only'] == synthetic and
              old['reference_used'] is False and old['DEV_used'] is False and old['objective'] == 'BCE'):
        return ineligible('MLP_REUSE_SOURCE_ENDPOINT')
    for field in ('rows', 'uid_sha256', 'weight_sha256', 'normalizer_digest'):
        if old[field] != identity[field]: return ineligible('MLP_REUSE_IDENTITY:'+field)
    if not (old['epochs'] == hp['epochs'] and old['updates'] == hp['epochs']*math.ceil(len(indices)/hp['batch_size']) and
            isinstance(old['order_hashes'], list) and len(old['order_hashes']) == hp['epochs']):
        return ineligible('MLP_REUSE_ENDPOINT_BUDGET')
    if not (isinstance(replay_receipt, dict) and
              replay_receipt.get('status') == 'PASS' and replay_receipt.get('runtime_compatible') is True and
              bool(replay_receipt.get('runtime_fingerprint')) and
              replay_receipt.get('score_and_decision_bitwise') == dict(CAL=True, CIC_DEV=True, UNSW_DEV=True) and
              replay_receipt.get('original_head_sha256') == old['head_sha256'] and
              replay_receipt.get('original_endpoint_sha256') == c.sha(source/'endpoint.json') and
              replay_receipt.get('original_design_digest') == c.digest(original_design) and
              replay_receipt.get('seed') == seed and
              replay_receipt.get('ordered_uid_sha256') == identity['ordered_uid_sha256']):
        return ineligible('MLP_REUSE_PROOF_REQUIRED')
    model = m.classifier('MLP_QUERY_BCE', seed, config)
    with np.load(source/'head.npz', allow_pickle=False) as saved:
        state = model.state_dict()
        if set(saved.files) != set(state): return ineligible('MLP_REUSE_HEAD_KEYS')
        if not all(saved[name].shape == tuple(state[name].shape) for name in saved.files):
            return ineligible('MLP_REUSE_HEAD_SHAPES')
        model.load_state_dict({name:torch.from_numpy(saved[name].copy()) for name in saved.files})
    c.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), 'MLP_REUSE_NONFINITE')
    return dict(status='PASS', seed=seed, identity=identity,
                source_endpoint_sha256=c.sha(source/'endpoint.json'))


def adopt_mlp(original_folder, original_design, config, rows, values, q, norm,
              indices, out, replay_receipt):
    """Adopt only if the shared read-only preconditions still pass at execution."""
    checked = reuse_mlp_preconditions(original_folder, original_design, config, rows, values,
                                     q, norm, indices, replay_receipt)
    if checked['status'] != 'PASS': raise ReuseIneligible(checked['reason'])
    source = Path(original_folder); old = c.read(source/'endpoint.json')
    seed = checked['seed']; identity = checked['identity']; synthetic = config.get('synthetic_only') is True
    model = m.classifier('MLP_QUERY_BCE', seed, config)
    with np.load(source/'head.npz', allow_pickle=False) as saved:
        model.load_state_dict({name:torch.from_numpy(saved[name].copy()) for name in saved.files})
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source/'head.npz', out/'head.npz')
    shutil.copyfile(source/'initial.npz', out/'initial.npz')
    c.write(out/'reuse_replay_receipt.json', replay_receipt)
    c.write(out/'endpoint.json', dict(status='COMPLETE', family='MLP_QUERY_BCE', seed=seed, dimension=782,
            config_digest=c.digest(config), head_sha256=c.sha(out/'head.npz'),
            initial_sha256=c.sha(out/'initial.npz'), synthetic_only=synthetic,
            reference_used=False, DEV_used=False, CAL_used=False, versions=versions('MLP_QUERY_BCE'),
            epochs=old['epochs'], updates=old['updates'], order_hashes=old['order_hashes'],
            parameters=sum(p.numel() for p in model.parameters()), internal_members=1,
            objective='weighted BCE', score_definition='classifier logit', training_seconds=0.,
            timing_boundary='no training: reused verified original QUERY_BCE endpoint',
            endpoint_selection='verified original final fixed epoch only',
            reused=True, source_endpoint_sha256=c.sha(source/'endpoint.json'),
            source_head_sha256=old['head_sha256'], source_design_digest=c.digest(original_design),
            reuse_replay_receipt_sha256=c.sha(out/'reuse_replay_receipt.json'), **identity))
    c.seal(out); c.verify(out)
    return model.eval().requires_grad_(False)
