"""Compatibility boundary for the vendored basic TabM configuration.

The frozen paper04 environment intentionally has no ``rtdl_num_embeddings``
package and must not install one during an experiment.  Upstream TabM imports
the three supported embedding class names even when ``num_embeddings=None``.
These sentinels make that no-embedding path importable while failing closed if
an experiment accidentally tries to instantiate an embedding.

No TabM algorithm, layer, initializer, training rule, or inference rule is
implemented here.
"""

from __future__ import annotations

import torch.nn as nn


class _UnavailableEmbedding(nn.Module):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__()
        del args, kwargs
        raise RuntimeError(
            "Numerical embeddings are disabled in the frozen paper04 runtime; "
            "use TabM with num_embeddings=None"
        )


class LinearReLUEmbeddings(_UnavailableEmbedding):
    pass


class PiecewiseLinearEmbeddings(_UnavailableEmbedding):
    pass


class PeriodicEmbeddings(_UnavailableEmbedding):
    pass
