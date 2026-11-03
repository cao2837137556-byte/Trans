"""Fixed 782-dimensional head recipes and bounded scoring; no data discovery."""
import importlib
import importlib.util
import math
from pathlib import Path
import sys
import numpy as np
import torch
from torch.nn import functional as F
import query_tail_core_v2 as k

c = k.c
FAMILIES = ('MLP_QUERY_BCE', 'TabM', 'LightGBM')
TABM_SHA = 'fb8ed71b4d0a5e0a64725e57b7b3fb5b423776b09a9f68f2263ba6e85e25f64f'
TABM_LICENSE_SHA = 'efd022bf9d1ab09f23d14b79598717119f2fd0ab466e6a089e38829568b4264e'


def default_training_config():
    return dict(epochs=40, batch_size=256, numerical_threads=4, prediction_batch_size=256,
                optimizer_mlp=dict(lr=.0003, weight_decay=.0001, betas=[.9, .999], eps=1e-8,
                                   foreach=False, amsgrad=False),
                optimizer_tabm=dict(lr=.002, weight_decay=.0003, betas=[.9, .999], eps=1e-8,
                                    foreach=False, amsgrad=False),
                tabm=dict(k=32, n_blocks=3, d_block=512, dropout=.1, activation='ReLU',
                          arch_type='tabm', start_scaling_init='random-signs', num_embeddings=None),
                lightgbm=dict(num_boost_round=500, boosting_type='gbdt', objective='binary',
                              metric='binary_logloss', num_leaves=31, max_depth=-1,
                              learning_rate=.05, min_data_in_leaf=20, max_bin=255,
                              lambda_l1=0., lambda_l2=0., min_sum_hessian_in_leaf=.001,
                              feature_fraction=.9, bagging_fraction=.8, bagging_freq=1,
                              feature_pre_filter=True, deterministic=True, force_col_wise=True,
                              num_threads=4, verbosity=-1, boost_from_average=True,
                              is_unbalance=False, scale_pos_weight=1., sigmoid=1.))


def validate_config(config, synthetic=False):
    c.require(config.get('schema') == 'modern-head-comparison-v1', 'MODERN_CONFIG_SCHEMA')
    c.require(config.get('families') == list(FAMILIES) and config.get('seeds') == list(c.SEEDS),
              'MODERN_COMPARISON_SCOPE')
    hp = config['training']; expected = default_training_config()
    if synthetic:
        c.require(config.get('synthetic_only') is True and type(hp['epochs']) is int and
                  1 <= hp['epochs'] <= 2 and type(hp['batch_size']) is int and
                  1 <= hp['batch_size'] <= 256 and
                  1 <= hp['lightgbm']['num_boost_round'] <= 3, 'MODERN_SYNTHETIC_BOUNDS')
        expected['epochs'] = hp['epochs']; expected['batch_size'] = hp['batch_size']
        expected['lightgbm']['num_boost_round'] = hp['lightgbm']['num_boost_round']
    else:
        c.require(config.get('synthetic_only') is False, 'MODERN_PRODUCTION_FLAG')
    c.require(hp == expected, 'MODERN_FROZEN_RECIPE')
    return hp


def official_tabm():
    """Import actual dependency first; never place the old shim directory on sys.path."""
    from importlib.metadata import version
    dep = importlib.import_module('rtdl_num_embeddings')
    c.require(version('rtdl-num-embeddings') == '0.0.12', 'RTDL_VERSION')
    folder = Path(__file__).resolve().parent/'vendor'/'tabm_v0_0_3'
    c.require(Path(dep.__file__).resolve().parent != folder, 'RTDL_COMPATIBILITY_SHIM_FORBIDDEN')
    path = c.pin(folder/'tabm.py', TABM_SHA); c.pin(folder/'LICENSE', TABM_LICENSE_SHA)
    name = '_modern_official_tabm_v0_0_3'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    result = sys.modules[name]
    c.require(result.__version__ == '0.0.3' and Path(result.__file__).resolve() == path.resolve(),
              'TABM_MODULE_IDENTITY')
    return result


def classifier(family, seed, config):
    c.require(family in FAMILIES and seed in c.SEEDS, 'MODERN_HEAD_SCOPE')
    if family == 'MLP_QUERY_BCE':
        return k.classifier(seed, 782)
    c.require(family == 'TabM', 'TREE_HAS_NO_TORCH_CLASSIFIER')
    torch.manual_seed(seed)
    return official_tabm().TabM.make(n_num_features=782, cat_cardinalities=None,
                                    d_out=1, **config['training']['tabm'])


def tabm_weighted_bce(member_logits, labels, batch_weights, full_size):
    """Each member receives the same source weights; average member losses last."""
    z = member_logits.squeeze(-1) if member_logits.ndim == 3 else member_logits
    c.require(z.ndim == 2 and z.shape[1] == 32 and len(z) == len(labels) == len(batch_weights) > 0,
              'TABM_LOSS_SHAPE')
    target = labels[:, None].expand_as(z)
    losses = F.binary_cross_entropy_with_logits(z, target, reduction='none')
    weights = torch.as_tensor(batch_weights, dtype=torch.float64, device=z.device)
    return (losses*weights[:, None]).sum(0).mean()*(full_size/len(z))


def tabm_mean_probability_logit(member_logits):
    """Stable log(mean(sigmoid(z))) - log(mean(sigmoid(-z))); no clipping."""
    z = member_logits.squeeze(-1) if member_logits.ndim == 3 else member_logits
    c.require(z.ndim == 2 and z.shape[1] == 32 and bool(torch.isfinite(z).all()), 'TABM_SCORE_SHAPE')
    z = z.to(torch.float64)
    result = torch.logsumexp(F.logsigmoid(z), 1)-torch.logsumexp(F.logsigmoid(-z), 1)
    c.require(bool(torch.isfinite(result).all()), 'TABM_NONFINITE_SCORE')
    return result


def lightgbm_parameters(config, seed):
    c.require(seed in c.SEEDS, 'TREE_SEED')
    parameters = dict(config['training']['lightgbm']); parameters.pop('num_boost_round')
    for field in ('seed', 'data_random_seed', 'feature_fraction_seed', 'bagging_seed',
                  'drop_seed', 'extra_seed'):
        parameters[field] = seed
    return parameters


def lightgbm_weights(weights):
    result = np.asarray(weights, dtype=np.float64)*len(weights)
    c.require(result.ndim == 1 and np.isfinite(result).all() and np.all(result > 0) and
              math.isclose(float(result.mean()), 1., abs_tol=1e-12), 'TREE_WEIGHT_SCALE')
    return result


def scores(model, family, values, q, indices, norm, progress=None):
    c.require(family in FAMILIES, 'MODERN_SCORE_FAMILY')
    indices = np.asarray(indices, dtype=np.int64)
    c.require(indices.ndim == 1 and np.all(indices >= 0) and np.all(indices < len(values)), 'SCORE_INDICES')
    # MLP keeps the exact original 1024-row scoring operation and float32 output.
    if family == 'MLP_QUERY_BCE':
        return k.scores(model, values, q, indices, norm, 782, progress)
    result = np.empty(len(indices), dtype=np.float64)
    with torch.inference_mode():
        for start in range(0, len(indices), 256):
            ix = indices[start:start+256]
            x = k.normalized(values, q, ix, norm, 782)
            prediction = (tabm_mean_probability_logit(model(x)).numpy() if family == 'TabM'
                          else model.predict(x.numpy(), raw_score=True, num_threads=4))
            c.require(np.asarray(prediction).shape == (len(ix),), 'MODERN_PREDICTION_SHAPE')
            result[start:start+len(ix)] = prediction
            if progress is not None: progress.tick(start+len(ix), len(indices))
    c.require(np.isfinite(result).all(), 'MODERN_SCORES_NONFINITE')
    return result
