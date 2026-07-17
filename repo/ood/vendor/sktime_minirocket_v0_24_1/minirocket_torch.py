"""Batched PyTorch execution port of sktime MiniRocketMultivariate v0.24.1.

The algorithmic parameterization is retained from the BSD-3-Clause upstream
implementation.  Only the Numba convolution backend and sktime estimator shell
are replaced.  Convolution weights are fixed; only biases are fitted from the
provided training windows.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import torch
import torch.nn.functional as F


KERNEL_INDICES = np.asarray(
    [
        (a, b, c)
        for a in range(9)
        for b in range(a + 1, 9)
        for c in range(b + 1, 9)
    ],
    dtype=np.int32,
)
if KERNEL_INDICES.shape != (84, 3):  # pragma: no cover - import invariant
    raise RuntimeError("MiniRocket fixed kernel enumeration drift")


def _fit_dilations(
    n_timepoints: int,
    num_features: int,
    max_dilations_per_kernel: int,
) -> tuple[np.ndarray, np.ndarray]:
    if n_timepoints < 9:
        raise ValueError(f"MiniRocket requires at least 9 timepoints, got {n_timepoints}")
    num_features_per_kernel = max(1, int(num_features) // 84)
    true_max = min(num_features_per_kernel, int(max_dilations_per_kernel))
    multiplier = num_features_per_kernel / true_max
    max_exponent = np.log2((n_timepoints - 1) / (9 - 1))
    dilations, counts = np.unique(
        np.logspace(0, max_exponent, true_max, base=2).astype(np.int32),
        return_counts=True,
    )
    counts = (counts * multiplier).astype(np.int32)
    remainder = num_features_per_kernel - int(counts.sum())
    index = 0
    while remainder > 0:
        counts[index] += 1
        remainder -= 1
        index = (index + 1) % len(counts)
    return dilations.astype(np.int32), counts.astype(np.int32)


def _quantiles(count: int) -> np.ndarray:
    golden = (np.sqrt(5.0) + 1.0) / 2.0
    return np.asarray([(index * golden) % 1.0 for index in range(1, count + 1)], dtype=np.float32)


def _array_hash(arrays: Iterable[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        value = np.ascontiguousarray(array)
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class MiniRocketParameters:
    dilations: np.ndarray
    features_per_dilation: np.ndarray
    channel_mask: np.ndarray
    biases: tuple[np.ndarray, ...]
    requested_features: int
    actual_features: int
    seed: int
    parameter_sha256: str


class MiniRocketMultivariateTorch:
    """Almost-deterministic MiniRocket transform for float32 3-D arrays.

    Input shape is ``(instances, channels, timepoints)``.  Outputs use the
    upstream PPV features and have ``actual_features`` columns.
    """

    def __init__(
        self,
        num_features: int = 3360,
        max_dilations_per_kernel: int = 16,
        seed: int = 27,
        batch_size: int = 256,
    ) -> None:
        if num_features < 84:
            raise ValueError("MiniRocket needs at least 84 requested features")
        self.num_features = int(num_features)
        self.max_dilations_per_kernel = int(max_dilations_per_kernel)
        self.seed = int(seed)
        self.batch_size = int(batch_size)
        self.parameters: MiniRocketParameters | None = None

    @staticmethod
    def _weights(channel_mask: np.ndarray) -> torch.Tensor:
        n_combinations, channels = channel_mask.shape
        if n_combinations != 84:
            raise ValueError(f"expected 84 channel masks, got {n_combinations}")
        temporal = np.full((84, 9), -1.0, dtype=np.float32)
        for kernel, positions in enumerate(KERNEL_INDICES.tolist()):
            temporal[kernel, positions] = 2.0
        weights = channel_mask[:, :, None].astype(np.float32) * temporal[:, None, :]
        return torch.from_numpy(np.ascontiguousarray(weights.reshape(84, channels, 9)))

    @staticmethod
    def _convolve(x: torch.Tensor, weights: torch.Tensor, dilation: int) -> torch.Tensor:
        padding = ((9 - 1) * int(dilation)) // 2
        return F.conv1d(x, weights, bias=None, stride=1, padding=padding, dilation=int(dilation))

    def fit(self, x: np.ndarray) -> "MiniRocketMultivariateTorch":
        values = np.asarray(x, dtype=np.float32)
        if values.ndim != 3 or len(values) == 0 or not np.isfinite(values).all():
            raise ValueError(f"invalid MiniRocket fit input: {values.shape}")
        n_instances, n_channels, n_timepoints = values.shape
        dilations, per_dilation = _fit_dilations(
            n_timepoints,
            self.num_features,
            self.max_dilations_per_kernel,
        )
        # Match sktime v0.24.1 exactly: all channel combinations are sampled
        # first, then the bias fitter resets the RNG to the same seed and
        # samples one training instance per dilation/kernel combination.
        rng = np.random.RandomState(self.seed)
        max_channels = min(int(n_channels), 9)
        max_exponent = np.log2(max_channels + 1)
        channel_counts = (
            2
            ** rng.uniform(
                0,
                max_exponent,
                int(len(dilations)) * 84,
            )
        ).astype(np.int32).reshape(len(dilations), 84)
        masks: list[np.ndarray] = []
        for dilation_index in range(len(dilations)):
            mask = np.zeros((84, n_channels), dtype=np.float32)
            for kernel, width in enumerate(channel_counts[dilation_index].tolist()):
                chosen = rng.choice(n_channels, int(width), replace=False)
                mask[kernel, chosen] = 1.0
            masks.append(mask)

        bias_groups: list[np.ndarray] = []
        quantiles = _quantiles(84 * int(per_dilation.sum()))
        quantile_offset = 0
        bias_rng = np.random.RandomState(self.seed)
        tensor = torch.from_numpy(np.ascontiguousarray(values))
        with torch.no_grad():
            for dilation_index, (dilation, count) in enumerate(zip(dilations.tolist(), per_dilation.tolist())):
                mask = masks[dilation_index]
                weights = self._weights(mask)
                chosen_instances = bias_rng.randint(0, n_instances, size=84)
                selected = tensor[torch.from_numpy(chosen_instances.astype(np.int64))]
                convolution = self._convolve(selected, weights, int(dilation)).cpu().numpy()
                group = np.empty((84, int(count)), dtype=np.float32)
                for kernel in range(84):
                    series = convolution[kernel, kernel]
                    qs = quantiles[quantile_offset : quantile_offset + int(count)]
                    group[kernel] = np.quantile(series, qs).astype(np.float32)
                    quantile_offset += int(count)
                bias_groups.append(group)
        channel_mask = np.stack(masks, axis=0).astype(np.float32)
        actual = 84 * int(per_dilation.sum())
        parameter_hash = _array_hash(
            [dilations, per_dilation, channel_mask, *bias_groups]
        )
        self.parameters = MiniRocketParameters(
            dilations=dilations,
            features_per_dilation=per_dilation,
            channel_mask=channel_mask,
            biases=tuple(bias_groups),
            requested_features=self.num_features,
            actual_features=actual,
            seed=self.seed,
            parameter_sha256=parameter_hash,
        )
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.parameters is None:
            raise RuntimeError("MiniRocket transform called before fit")
        values = np.asarray(x, dtype=np.float32)
        if values.ndim != 3 or not np.isfinite(values).all():
            raise ValueError(f"invalid MiniRocket transform input: {values.shape}")
        params = self.parameters
        if values.shape[1] != params.channel_mask.shape[2]:
            raise ValueError(
                f"MiniRocket channel drift: {values.shape[1]} != {params.channel_mask.shape[2]}"
            )
        output = np.empty((len(values), params.actual_features), dtype=np.float32)
        with torch.no_grad():
            for start in range(0, len(values), self.batch_size):
                stop = min(len(values), start + self.batch_size)
                tensor = torch.from_numpy(np.ascontiguousarray(values[start:stop]))
                feature_offset = 0
                for dilation_index, (dilation, count, group) in enumerate(
                    zip(
                        params.dilations.tolist(),
                        params.features_per_dilation.tolist(),
                        params.biases,
                    )
                ):
                    mask = params.channel_mask[dilation_index]
                    weights = self._weights(mask)
                    convolution = self._convolve(tensor, weights, int(dilation))
                    padding = ((9 - 1) * int(dilation)) // 2
                    for kernel in range(84):
                        current = convolution[:, kernel, :]
                        if (dilation_index + kernel) % 2 == 1 and padding > 0:
                            current = current[:, padding:-padding]
                        bias = torch.from_numpy(group[kernel]).to(current.device)
                        ppv = (current[:, :, None] > bias[None, None, :]).float().mean(dim=1)
                        end = feature_offset + int(count)
                        output[start:stop, feature_offset:end] = ppv.cpu().numpy()
                        feature_offset = end
                if feature_offset != params.actual_features:
                    raise RuntimeError("MiniRocket feature assembly drift")
        if not np.isfinite(output).all() or np.any(output < 0.0) or np.any(output > 1.0):
            raise RuntimeError("MiniRocket produced invalid PPV features")
        return output

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        return self.fit(x).transform(x)
