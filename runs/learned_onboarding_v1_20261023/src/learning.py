"""Explicit, deterministic V1 training endpoints. Importing this module never fits data."""
import hashlib
import io
import math
from pathlib import Path
import sys
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from common import SPEC_SHA256, uid_hash
from tasks import hierarchical_weights, build_task_distribution, sample_indices, uniform_stream


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _setup():
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)


def _state_hash(state):
    buffer = io.BytesIO()
    torch.save({k: v.detach().cpu() for k, v in state.items()}, buffer)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _finite_model(model, gradients=False):
    for parameter in model.parameters():
        require(bool(torch.isfinite(parameter).all()), 'NONFINITE_PARAMETER')
        if gradients and parameter.grad is not None:
            require(bool(torch.isfinite(parameter.grad).all()), 'NONFINITE_GRADIENT')


def _old_classifier():
    ood = Path(__file__).resolve().parents[3] / 'repo' / 'ood'
    if str(ood) not in sys.path:
        sys.path.insert(0, str(ood))
    from query_tail_core_v2 import classifier
    return classifier(27, 782)


def _check_aux_input(rows, e3, q14, indices):
    ix = np.asarray(indices, dtype=np.int64)
    require(ix.ndim == 1 and len(ix) and len(set(ix.tolist())) == len(ix)
            and np.all((ix >= 0) & (ix < len(rows))), 'AUX_INDICES')
    require(e3.shape == (len(rows), 768) and q14.shape == (len(rows), 14), 'AUX_FEATURE_SHAPE')
    require(all(rows[int(i)].get('partition') == 'LEARN' and
                rows[int(i)].get('fit_role') == 'FIT' for i in ix), 'AUX_FIT_ONLY')
    require(len({rows[int(i)]['uid'] for i in ix}) == len(ix), 'AUX_DUPLICATE_UID')
    return ix


def auxiliary_normalizer(rows, e3, fit_indices, block=4096):
    """Train-group-only weighted population moments, accumulated in float64."""
    ix = np.asarray(fit_indices, dtype=np.int64)
    selected = [rows[int(i)] for i in ix]
    labels = np.asarray([r['label'] for r in selected])
    require(set(labels.tolist()) == {0, 1}, 'AUX_BOTH_CLASSES')
    weight = np.zeros(len(ix), dtype=np.float64)
    for label in (0, 1):
        positions = np.flatnonzero(labels == label)
        weight[positions] = .5 * hierarchical_weights([selected[int(i)] for i in positions],
                                                        include_component=False)
    mean = np.zeros(768, dtype=np.float64)
    for start in range(0, len(ix), block):
        batch = np.asarray(e3[ix[start:start+block]], dtype=np.float64)
        require(np.isfinite(batch).all(), 'AUX_NONFINITE_E3')
        w = weight[start:start+block, None]
        mean += np.sum(batch * w, axis=0, dtype=np.float64)
    variance = np.zeros(768, dtype=np.float64)
    for start in range(0, len(ix), block):
        batch = np.asarray(e3[ix[start:start+block]], dtype=np.float64)
        delta = batch - mean
        variance += np.sum(delta * delta * weight[start:start+block, None],
                           axis=0, dtype=np.float64)
    scale = np.sqrt(variance)
    zero = scale == 0
    scale[zero] = 1.0
    return mean, scale, int(np.count_nonzero(zero)), weight


def _aux_batch(e3, q14, indices, mean, scale):
    z = np.asarray(e3[indices], dtype=np.float64)
    q = np.asarray(q14[indices], dtype=np.float64)
    require(z.shape[1:] == (768,) and q.shape[1:] == (14,) and
            np.isfinite(z).all() and np.isfinite(q).all() and
            np.all((q >= 0) & (q <= 1)), 'AUX_FEATURE_INVALID')
    return np.concatenate(((z - mean) / scale, q), axis=1).astype(np.float32)


def fit_auxiliary_head(rows, e3, q14, fit_indices, output_dir,
                       synthetic=False, epochs=40, guard=None):
    """Fit one isolated G0/G1 head; explicit call only, final epoch is endpoint."""
    require(synthetic or epochs == 40, 'PRODUCTION_EPOCHS_FIXED')
    require(epochs > 0, 'EPOCHS')
    ix = _check_aux_input(rows, e3, q14, fit_indices)
    mean, scale, zero_count, weights = auxiliary_normalizer(rows, e3, ix)
    _setup()
    model = _old_classifier().cpu()
    init_hash = _state_hash(model.state_dict())
    optimizer = torch.optim.AdamW(model.parameters(), lr=.0003, weight_decay=.0001,
                                  betas=(.9, .999), eps=1e-8, foreach=False, amsgrad=False)
    generator = torch.Generator(device='cpu').manual_seed(27)
    out = Path(output_dir)
    require(not out.exists() or not any(out.iterdir()), 'OUTPUT_NOT_EMPTY')
    out.mkdir(parents=True, exist_ok=True)
    common = {'schema': 'learned-onboarding-aux-v1', 'synthetic_only': bool(synthetic),
              'fit_uids': [rows[int(i)]['uid'] for i in ix], 'mean': mean,
              'scale': scale, 'zero_std_count': zero_count, 'seed': 27,
              'epochs': epochs, 'batch_size': 256, 'init_hash': init_hash,
              'spec_sha256': SPEC_SHA256, 'status': 'SYNTHETIC_ONLY' if synthetic else 'COMPLETE',
              'head_id': out.name, 'fit_uid_hash': uid_hash([rows[int(i)]['uid'] for i in ix], ordered=True),
              'normalizer_uid_hash': uid_hash([rows[int(i)]['uid'] for i in ix], ordered=True)}
    torch.save({**common, 'state_dict': model.state_dict(), 'updates': 0}, out / 'init.pt')
    logs = []
    updates = 0
    start_time = time.monotonic()
    for epoch in range(epochs):
        order = torch.randperm(len(ix), generator=generator).numpy()
        epoch_loss = 0.0
        for start in range(0, len(ix), 256):
            positions = order[start:start+256]
            selected = ix[positions]
            x = torch.from_numpy(_aux_batch(e3, q14, selected, mean, scale))
            y = torch.tensor([rows[int(i)]['label'] for i in selected], dtype=torch.float32)
            w = torch.as_tensor(weights[positions], dtype=torch.float64)
            optimizer.zero_grad(set_to_none=True)
            logits = model(x).flatten()
            require(bool(torch.isfinite(logits).all()), 'NONFINITE_AUX_LOGITS')
            per = F.binary_cross_entropy_with_logits(logits, y, reduction='none')
            loss = torch.sum(per * w) * (len(ix) / len(selected))
            require(bool(torch.isfinite(loss)), 'NONFINITE_AUX_LOSS')
            loss.backward()
            _finite_model(model, gradients=True)
            optimizer.step()
            _finite_model(model)
            updates += 1
            epoch_loss += float(loss.detach())
            if guard is not None:
                guard(stage='auxiliary', update=updates, epoch=epoch+1)
        logs.append({'epoch': epoch+1, 'updates': updates,
                     'loss_sum': epoch_loss, 'elapsed_seconds': time.monotonic()-start_time})
    final_hash = _state_hash(model.state_dict())
    checkpoint = {**common, 'state_dict': model.state_dict(), 'updates': updates,
                  'final_hash': final_hash, 'logs': logs}
    torch.save(checkpoint, out / 'final.pt')
    return {'checkpoint': str(out / 'final.pt'), 'updates': updates,
            'init_hash': init_hash, 'final_hash': final_hash,
            'synthetic_only': bool(synthetic), 'zero_std_count': zero_count,
            'fit_count': len(ix), 'logs': logs}


def load_auxiliary_head(checkpoint, allow_synthetic=False):
    item = torch.load(checkpoint, map_location='cpu', weights_only=False)
    require(item['schema'] == 'learned-onboarding-aux-v1' and
            item['spec_sha256'] == SPEC_SHA256 and
            item['status'] == ('SYNTHETIC_ONLY' if item['synthetic_only'] else 'COMPLETE') and
            (allow_synthetic or not item['synthetic_only']) and
            item['updates'] == item['epochs'] * math.ceil(len(item['fit_uids']) / 256) and
            (item['synthetic_only'] or item['epochs'] == 40) and
            item['fit_uid_hash'] == uid_hash(item['fit_uids'], ordered=True) and
            item['normalizer_uid_hash'] == item['fit_uid_hash'] and
            item['final_hash'] == _state_hash(item['state_dict']), 'AUX_CHECKPOINT_SCOPE')
    require(np.asarray(item['mean']).shape == np.asarray(item['scale']).shape == (768,) and
            np.isfinite(item['mean']).all() and np.isfinite(item['scale']).all() and
            np.all(np.asarray(item['scale']) > 0), 'AUX_NORMALIZER_INVALID')
    _setup()
    model = _old_classifier().cpu()
    model.load_state_dict(item['state_dict'])
    _finite_model(model)
    model.eval()
    return model, np.asarray(item['mean'], np.float64), np.asarray(item['scale'], np.float64), item


def score_auxiliary_head(checkpoint, e3, q14, allow_synthetic=False, batch_size=256):
    model, mean, scale, _ = load_auxiliary_head(checkpoint, allow_synthetic=allow_synthetic)
    require(type(batch_size) is int and batch_size > 0, 'AUX_BATCH_SIZE')
    require(e3.shape[0] == q14.shape[0] and e3.shape[1] == 768 and q14.shape[1] == 14,
            'AUX_SCORE_SHAPE')
    scores = np.empty(e3.shape[0], dtype=np.float64)
    with torch.no_grad():
        for start in range(0, len(scores), batch_size):
            ix = slice(start, min(start+batch_size, len(scores)))
            scores[ix] = model(torch.from_numpy(_aux_batch(e3, q14, ix, mean, scale))).flatten().numpy()
    return scores


def correction_model(seed=27):
    torch.manual_seed(seed)
    model = nn.Sequential(nn.Linear(50, 32), nn.ReLU(), nn.Linear(32, 16),
                          nn.ReLU(), nn.Linear(16, 1), nn.Sigmoid())
    require(sum(p.numel() for p in model.parameters()) == 2177, 'MODULE_PARAMETERS')
    return model


def _features(batch, query_only):
    features = np.asarray(batch['features'], dtype=np.float32)
    mask = np.asarray(batch['candidate_mask'], dtype=bool)
    require(features.ndim == 3 and features.shape[2] == 50 and
            mask.shape == features.shape[:2] and np.isfinite(features).all(), 'BATCH_FEATURES')
    if query_only:
        features = features.copy()
        features[:, :, 14:46] = 0
        features[:, :, 47] = 0
    return torch.from_numpy(features), torch.from_numpy(mask)


def _loss(model, batch, query_only):
    features, mask = _features(batch, query_only)
    labels = np.asarray(batch['labels'])
    margins = np.asarray(batch['margins'], np.float64)
    scales = np.asarray(batch['scales'], np.float64)
    n, k = features.shape[:2]
    require(labels.shape == margins.shape == scales.shape == (n,) and
            np.isfinite(margins).all() and np.isfinite(scales).all() and
            np.all(scales >= 0) and np.isin(labels, [0, 1]).all(), 'BATCH_TASKS')
    a = model(features.reshape(n*k, 50)).reshape(n, k)
    require(bool(torch.isfinite(a).all()), 'NONFINITE_MODULE_OUTPUT')
    loss_terms = []
    for i in range(n):
        valid = torch.nonzero(mask[i], as_tuple=False).flatten().tolist()
        if scales[i] == 0 or not valid:
            loss_terms.append(a[i, 0] * 0.0)
            continue
        m = float(margins[i])
        if labels[i] == 0:
            require(len(valid) == 1, 'NORMAL_OWN_BANK_ONLY')
            delta = .25 * a[i, valid[0]]
            target = min(max(m + .01, 0.0), .25) if m > 0 else 0.0
            loss_terms.append((delta-target).square() + .01*delta.square())
        else:
            delta = .25 * a[i, valid]
            per_bank = F.softplus(delta - m) + delta.square()
            # torch.max returns the first sorted-bank index on an exact tie.
            loss_terms.append(torch.max(per_bank, dim=0).values)
    return torch.stack(loss_terms).mean()


def train_modules(tasks, get_batch, output_dir, hard_uids,
                  synthetic=False, steps=4000, guard=None):
    """Train three arms with shared PCG64 uniform stream and fixed endpoints."""
    require(synthetic or steps == 4000, 'PRODUCTION_STEPS_FIXED')
    require(steps > 0, 'STEPS')
    ordered, p0, ph = build_task_distribution(tasks, hard_uids)
    uniforms = uniform_stream(steps, 256)
    schedules = {'L_STANDARD': sample_indices(p0, uniforms),
                 'L_HARD': sample_indices(ph, uniforms),
                 'L_QUERY_ONLY': sample_indices(ph, uniforms)}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    receipts = {}
    _setup()
    for arm in ('L_STANDARD', 'L_HARD', 'L_QUERY_ONLY'):
        directory = out / arm
        require(not directory.exists() or not any(directory.iterdir()), 'OUTPUT_NOT_EMPTY')
        directory.mkdir(parents=True, exist_ok=True)
        model = correction_model().cpu()
        init_hash = _state_hash(model.state_dict())
        query_only = arm == 'L_QUERY_ONLY'
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001,
                                      betas=(.9, .999), eps=1e-8, foreach=False)
        common = {'schema': 'learned-onboarding-module-v1', 'arm': arm, 'seed': 27,
                  'synthetic_only': bool(synthetic), 'query_only': query_only,
                  'init_hash': init_hash, 'steps': steps, 'batch_size': 256,
                  'spec_sha256': SPEC_SHA256,
                  'status': 'SYNTHETIC_ONLY' if synthetic else 'COMPLETE'}
        torch.save({**common, 'state_dict': model.state_dict(), 'updates': 0}, directory / 'init.pt')
        log = []
        start_time = time.monotonic()
        for step in range(steps):
            indices = schedules[arm][step*256:(step+1)*256].tolist()
            batch = get_batch(indices)
            selected = [ordered[i] for i in indices]
            require(np.array_equal(np.asarray(batch['labels']),
                                   np.asarray([t['label'] for t in selected])), 'BATCH_LABEL_IDENTITY')
            if all('s' in t for t in selected):
                require(np.array_equal(np.asarray(batch['scales'], np.float64),
                                       np.asarray([t['s'] for t in selected], np.float64)),
                        'BATCH_SCALE_IDENTITY')
            if all(all(k in t for k in ('score', 't', 's')) for t in selected):
                expected = [0.0 if t['s'] == 0 else (t['score']-t['t'])/t['s'] for t in selected]
                require(np.allclose(np.asarray(batch['margins'], np.float64), expected,
                                    rtol=0, atol=1e-12), 'BATCH_MARGIN_IDENTITY')
            if all('banks' in t for t in selected):
                require(np.array_equal(np.asarray(batch['candidate_mask']).sum(axis=1),
                                       np.asarray([len(t['banks']) if t.get('s', 1) > 0 else 0
                                                   for t in selected])),
                        'BATCH_BANK_COUNT')
            optimizer.zero_grad(set_to_none=True)
            loss = _loss(model, batch, query_only)
            require(bool(torch.isfinite(loss)), 'NONFINITE_MODULE_LOSS')
            loss.backward()
            _finite_model(model, gradients=True)
            grad = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0))
            require(math.isfinite(grad), 'NONFINITE_GRAD_NORM')
            optimizer.step()
            _finite_model(model)
            if guard is not None:
                guard(stage=arm, update=step+1)
            if (step+1) % 100 == 0 or step+1 == steps:
                log.append({'update': step+1, 'loss': float(loss.detach()),
                            'grad_norm': grad, 'elapsed_seconds': time.monotonic()-start_time})
        final_hash = _state_hash(model.state_dict())
        checkpoint = {**common, 'state_dict': model.state_dict(), 'updates': steps,
                      'final_hash': final_hash, 'log': log}
        torch.save(checkpoint, directory / 'final.pt')
        receipts[arm] = {'checkpoint': str(directory / 'final.pt'), 'updates': steps,
                         'init_hash': init_hash, 'final_hash': final_hash,
                         'synthetic_only': bool(synthetic), 'log': log}
    return receipts


def load_module(checkpoint, allow_synthetic=False):
    item = torch.load(checkpoint, map_location='cpu', weights_only=False)
    require(item['schema'] == 'learned-onboarding-module-v1' and
            item['spec_sha256'] == SPEC_SHA256 and
            item['status'] == ('SYNTHETIC_ONLY' if item['synthetic_only'] else 'COMPLETE') and
            item['arm'] in ('L_STANDARD', 'L_HARD', 'L_QUERY_ONLY') and
            item['query_only'] == (item['arm'] == 'L_QUERY_ONLY') and
            item['updates'] == item['steps'] and
            (item['synthetic_only'] or item['steps'] == 4000) and
            (allow_synthetic or not item['synthetic_only']) and
            item['final_hash'] == _state_hash(item['state_dict']), 'MODULE_CHECKPOINT_SCOPE')
    _setup()
    model = correction_model().cpu()
    model.load_state_dict(item['state_dict'])
    _finite_model(model)
    model.eval()
    return model, item


def score_module(model, features, query_only=False, batch_size=256):
    x = np.asarray(features, dtype=np.float32)
    require(x.ndim == 2 and x.shape[1] == 50 and np.isfinite(x).all(), 'MODULE_SCORE_SHAPE')
    if query_only:
        x = x.copy()
        x[:, 14:46] = 0
        x[:, 47] = 0
    _setup()
    require(type(batch_size) is int and batch_size > 0, 'MODULE_BATCH_SIZE')
    result = np.empty(len(x), dtype=np.float64)
    model.eval()
    with torch.no_grad():
        for start in range(0, len(x), batch_size):
            result[start:start+batch_size] = model(torch.from_numpy(x[start:start+batch_size])).flatten().numpy()
    return result


def _replay_compare(primary, reloaded, split, base_scores, scales, cut, labels,
                    correction, direct_scores=False):
    primary = np.asarray(primary, np.float64)
    reloaded = np.asarray(reloaded, np.float64)
    split = np.asarray(split, np.float64)
    base = np.asarray(base_scores, np.float64)
    scales = np.asarray(scales, np.float64)
    labels = np.asarray(labels)
    require(primary.ndim == 1 and primary.shape == reloaded.shape == split.shape ==
            base.shape == scales.shape == labels.shape and
            np.isfinite(primary).all() and np.isfinite(reloaded).all() and
            np.isfinite(split).all() and np.isfinite(base).all() and
            np.isfinite(scales).all() and np.all(scales >= 0) and
            np.isin(labels, [0, 1]).all() and math.isfinite(float(cut)),
            'REPLAY_INPUT')
    require(np.array_equal(primary, reloaded), 'CHECKPOINT_SCORE_NOT_BITWISE')
    require(np.allclose(primary, split, rtol=1e-6, atol=1e-6), 'QUERY_BATCH_SCORE_DRIFT')
    corrected = primary if direct_scores else base - float(correction)*scales*primary
    corrected_split = split if direct_scores else base - float(correction)*scales*split
    decisions = corrected > float(cut)
    decisions_split = corrected_split > float(cut)
    require(np.array_equal(decisions, decisions_split), 'QUERY_BATCH_DECISION_DRIFT')
    attack = labels == 1
    base_detected = base > float(cut)
    added_fn = np.flatnonzero(attack & base_detected & ~decisions)
    added_fn_split = np.flatnonzero(attack & base_detected & ~decisions_split)
    require(np.array_equal(added_fn, added_fn_split), 'QUERY_BATCH_NEW_FN_DRIFT')
    return {'rows': len(primary), 'score_bitwise_reloaded': True,
            'max_abs_batch_difference': float(np.max(np.abs(primary-split))) if len(primary) else 0.0,
            'decisions_equal': True, 'added_fn_indices': added_fn.tolist()}


def verify_auxiliary_replay(checkpoint, e3, q14, cut, labels, allow_synthetic=False):
    """Post-fit head replay against FIT-only pseudo threshold; never fits data."""
    require(e3.shape[0] == q14.shape[0], 'AUX_REPLAY_SHAPE')
    primary = score_auxiliary_head(checkpoint, e3, q14, allow_synthetic)
    reloaded = score_auxiliary_head(checkpoint, e3, q14, allow_synthetic)
    split = score_auxiliary_head(checkpoint, e3, q14, allow_synthetic,
                                 batch_size=127)
    return _replay_compare(primary, reloaded, split, primary, np.zeros(len(primary)),
                           cut, labels, 0.0, direct_scores=True)


def verify_module_replay(checkpoint, features, base_scores, scales, cut, labels,
                         correction=.25, allow_synthetic=False):
    """Post-fit module replay with FIT pseudo cut or final cut supplied by caller."""
    require(math.isfinite(float(correction)) and 0 <= correction <= .25,
            'REPLAY_CORRECTION')
    model, item = load_module(checkpoint, allow_synthetic)
    primary = score_module(model, features, query_only=item['query_only'])
    fresh, _ = load_module(checkpoint, allow_synthetic)
    reloaded = score_module(fresh, features, query_only=item['query_only'])
    split = score_module(model, features, query_only=item['query_only'], batch_size=127)
    return _replay_compare(primary, reloaded, split, base_scores, scales, cut,
                           labels, correction)
