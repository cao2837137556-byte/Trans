"""Candidate inference backend for the learned-onboarding numeric revision.

Each query executes the approved float32 network as an independent 1 x K row.
The caller still supplies its actual query batch, including its actual tail;
127-row batches are never regrouped into 256-row batches.  A query therefore
uses the same tensor shapes and layer order under either external batch size.

This backend differs from the original batched GEMM implementation.  It does
not promise bitwise equality with the old 256-row scores, and it does not
change or waive the registered score, decision, hard-set or new-FN checks.
It is a candidate only: production source validation remains necessary.

Only inference changes.  Parameters, gradients, input tensors, training/eval
flags, thread settings and the caller's autograd mode are left unchanged.
"""

import torch
from torch import nn
from torch.nn import functional as F


INFERENCE_VERSION = 'learned-onboarding-rowwise-float32-v3-20261024'


def _require(condition, reason):
    if not condition:
        raise ValueError('STABLE_INFERENCE_' + reason)


def _float32_cpu_finite(value, reason):
    _require(isinstance(value, torch.Tensor), reason + '_TENSOR')
    _require(value.device.type == 'cpu' and value.dtype == torch.float32 and
             value.layout == torch.strided, reason + '_CPU_FLOAT32')
    _require(bool(torch.isfinite(value).all()), reason + '_NONFINITE')


def _validate(model, features):
    _require(type(model) is nn.Sequential, 'SEQUENTIAL_REQUIRED')
    layers = tuple(model.children())
    kinds = tuple(type(layer) for layer in layers)
    auxiliary = (nn.Linear, nn.ReLU, nn.Linear)
    correction = (nn.Linear, nn.ReLU, nn.Linear, nn.ReLU, nn.Linear,
                  nn.Sigmoid)
    _require(kinds in (auxiliary, correction), 'NETWORK_LAYERS')
    dimensions = ((782, 128), (128, 1)) if kinds == auxiliary else (
        (50, 32), (32, 16), (16, 1))
    linear_layers = tuple(layer for layer in layers if type(layer) is nn.Linear)
    _require(tuple((layer.in_features, layer.out_features)
                   for layer in linear_layers) == dimensions,
             'NETWORK_DIMENSIONS')
    for index, layer in enumerate(linear_layers):
        prefix = 'LINEAR_' + str(index)
        _float32_cpu_finite(layer.weight, prefix + '_WEIGHT')
        _require(tuple(layer.weight.shape) ==
                 (layer.out_features, layer.in_features), prefix + '_WEIGHT_SHAPE')
        _float32_cpu_finite(layer.bias, prefix + '_BIAS')
        _require(tuple(layer.bias.shape) == (layer.out_features,),
                 prefix + '_BIAS_SHAPE')
    _float32_cpu_finite(features, 'INPUT')
    _require(features.ndim == 2 and features.shape[1] == dimensions[0][0],
             'INPUT_SHAPE')
    return layers


@torch.no_grad()
def stable_forward(model, features):
    """Return an N x 1 CPU float32 tensor without mutating model or input.

    ``features`` must be a two-dimensional CPU float32 tensor.  The accepted
    networks are the frozen auxiliary 782->128->1 ReLU network and correction
    50->32->16->1 ReLU/ReLU/Sigmoid network, with their existing biases.  Both
    train and eval flags are preserved; these approved layers have no running
    statistics, dropout or other mode-dependent inference state.

    The output is allocated once.  Each row gets fresh contiguous storage at
    offset zero before its functional layers, independent of caller slicing
    or padding.  Neither an N x K expansion nor concatenated per-row outputs
    are retained.
    """
    layers = _validate(model, features)
    output = torch.empty((features.shape[0], 1), dtype=torch.float32,
                         device='cpu')
    for position in range(features.shape[0]):
        # contiguous() alone may keep an already contiguous view's nonzero
        # storage offset.  Clone every row so caller padding/order/alignment
        # cannot select a different input-storage path inside the kernel.
        row = features[position:position + 1].clone(
            memory_format=torch.contiguous_format)
        _require(row.storage_offset() == 0 and row.is_contiguous(),
                 'ROW_STORAGE')
        for index, layer in enumerate(layers):
            if type(layer) is nn.Linear:
                row = F.linear(row, layer.weight, layer.bias)
            elif type(layer) is nn.ReLU:
                # The original layer's optional inplace flag must not mutate
                # a caller-owned row when functional inference is used.
                row = F.relu(row, inplace=False)
            else:
                row = torch.sigmoid(row)
            _float32_cpu_finite(row, 'LAYER_' + str(index) + '_OUTPUT')
        _require(tuple(row.shape) == (1, 1), 'OUTPUT_SHAPE')
        output[position].copy_(row[0])
    return output
