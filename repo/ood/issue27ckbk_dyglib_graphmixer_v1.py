"""DyGLib GraphMixer core with a source-local anonymous-node adapter.

The TimeEncoder, FeedForwardNet, MLPMixer, and temporal-message path are adapted
from DyGLib commit ``3aacc36b94b8d2d8293d70a74fdf6d39089b4163``:
https://github.com/yule-BUAA/DyGLib

DyGLib is MIT licensed, Copyright (c) 2023 Yu Le.  The full license text is
stored in ``repo/ood/third_party/DYGLIB_LICENSE.txt``.

The original GraphMixer Full node encoder consumes stable node raw features.
Those features do not exist under this experiment's anonymous source-local
identity contract.  ``AnonymousGraphMixer`` therefore keeps the mature
temporal-message Mixer unchanged in shape and replaces only that input adapter
with eight explicitly causal, identity-free statistics.  ``message_only``
removes this adapter for the preregistered ablation.
"""

from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn


UPSTREAM_REPOSITORY = "https://github.com/yule-BUAA/DyGLib"
UPSTREAM_COMMIT = "3aacc36b94b8d2d8293d70a74fdf6d39089b4163"
UPSTREAM_LICENSE = "MIT"


class TimeEncoder(nn.Module):
    """DyGLib fixed cosine time encoding used by GraphMixer."""

    def __init__(self, time_dim: int, parameter_requires_grad: bool = False):
        super().__init__()
        self.time_dim = int(time_dim)
        self.w = nn.Linear(1, self.time_dim)
        values = 1 / 10 ** np.linspace(0, 9, self.time_dim, dtype=np.float32)
        self.w.weight = nn.Parameter(torch.from_numpy(values).reshape(self.time_dim, 1))
        self.w.bias = nn.Parameter(torch.zeros(self.time_dim))
        self.w.weight.requires_grad = bool(parameter_requires_grad)
        self.w.bias.requires_grad = bool(parameter_requires_grad)

    def forward(self, timestamps: torch.Tensor) -> torch.Tensor:
        return torch.cos(self.w(timestamps.unsqueeze(dim=2)))


class FeedForwardNet(nn.Module):
    """DyGLib two-layer GELU feed-forward block."""

    def __init__(self, input_dim: int, dim_expansion_factor: float, dropout: float = 0.0):
        super().__init__()
        hidden = max(1, int(float(dim_expansion_factor) * int(input_dim)))
        self.ffn = nn.Sequential(
            nn.Linear(int(input_dim), hidden), nn.GELU(), nn.Dropout(float(dropout)),
            nn.Linear(hidden, int(input_dim)), nn.Dropout(float(dropout)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.ffn(x)


class MLPMixer(nn.Module):
    """DyGLib GraphMixer token/channel mixing block."""

    def __init__(
        self, num_tokens: int, num_channels: int,
        token_dim_expansion_factor: float = 0.5,
        channel_dim_expansion_factor: float = 4.0,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.token_norm = nn.LayerNorm(int(num_tokens))
        self.token_feedforward = FeedForwardNet(
            int(num_tokens), float(token_dim_expansion_factor), float(dropout),
        )
        self.channel_norm = nn.LayerNorm(int(num_channels))
        self.channel_feedforward = FeedForwardNet(
            int(num_channels), float(channel_dim_expansion_factor), float(dropout),
        )

    def forward(self, input_tensor: torch.Tensor) -> torch.Tensor:
        hidden = self.token_norm(input_tensor.permute(0, 2, 1))
        output = self.token_feedforward(hidden).permute(0, 2, 1) + input_tensor
        hidden = self.channel_norm(output)
        return self.channel_feedforward(hidden) + output


class AnonymousGraphMixer(nn.Module):
    """GraphMixer temporal-message core under an anonymous-node contract.

    Inputs are already source-local, causal histories.  Node IDs and source IDs
    never enter this module.  ``node_stats`` has shape ``[batch, 2, 8]`` and is
    ignored when ``message_only`` is true.
    """

    def __init__(
        self,
        edge_feat_dim: int = 9,
        time_feat_dim: int = 16,
        num_tokens: int = 20,
        num_layers: int = 2,
        token_dim_expansion_factor: float = 0.5,
        channel_dim_expansion_factor: float = 4.0,
        dropout: float = 0.1,
        output_dim: int = 32,
        message_only: bool = False,
    ):
        super().__init__()
        self.edge_feat_dim = int(edge_feat_dim)
        self.time_feat_dim = int(time_feat_dim)
        self.num_tokens = int(num_tokens)
        self.num_channels = self.edge_feat_dim
        self.output_dim = int(output_dim)
        self.message_only = bool(message_only)
        self.time_encoder = TimeEncoder(self.time_feat_dim, parameter_requires_grad=False)
        self.projection_layer = nn.Linear(self.edge_feat_dim + self.time_feat_dim, self.num_channels)
        self.mlp_mixers = nn.ModuleList([
            MLPMixer(
                self.num_tokens, self.num_channels,
                float(token_dim_expansion_factor), float(channel_dim_expansion_factor), float(dropout),
            )
            for _ in range(int(num_layers))
        ])
        node_dim = 0 if self.message_only else 8
        self.node_norm = nn.Identity() if self.message_only else nn.LayerNorm(8)
        self.output_layer = nn.Linear(self.num_channels + node_dim, self.output_dim)

    def encode_endpoint(
        self,
        edge_tokens: torch.Tensor,
        time_gaps_seconds: torch.Tensor,
        valid_mask: torch.Tensor,
        node_stats: torch.Tensor,
    ) -> torch.Tensor:
        if edge_tokens.ndim != 3 or edge_tokens.shape[1:] != (self.num_tokens, self.edge_feat_dim):
            raise ValueError("edge_tokens must have shape [batch, num_tokens, edge_feat_dim]")
        if time_gaps_seconds.shape != edge_tokens.shape[:2] or valid_mask.shape != edge_tokens.shape[:2]:
            raise ValueError("time gaps and masks must match the token axes")
        if node_stats.shape != (edge_tokens.shape[0], 8):
            raise ValueError("node_stats must have shape [batch, 8]")
        if bool((time_gaps_seconds < 0).any()):
            raise ValueError("future event entered GraphMixer history")
        time_features = self.time_encoder(time_gaps_seconds.float())
        time_features = time_features.masked_fill(~valid_mask.bool().unsqueeze(-1), 0.0)
        edge_features = edge_tokens.float().masked_fill(~valid_mask.bool().unsqueeze(-1), 0.0)
        combined = self.projection_layer(torch.cat([edge_features, time_features], dim=-1))
        for mixer in self.mlp_mixers:
            combined = mixer(combined)
        # This follows GraphMixer's fixed-token mean.  Padding remains explicit
        # in the mask audit and cannot contain future/current-event features.
        message_embedding = torch.mean(combined, dim=1)
        if self.message_only:
            joined = message_embedding
        else:
            joined = torch.cat([message_embedding, self.node_norm(node_stats.float())], dim=1)
        return self.output_layer(joined)

    def forward(
        self,
        edge_tokens: torch.Tensor,
        time_gaps_seconds: torch.Tensor,
        valid_mask: torch.Tensor,
        node_stats: torch.Tensor,
    ) -> torch.Tensor:
        if edge_tokens.ndim != 4 or edge_tokens.shape[1] != 2:
            raise ValueError("edge_tokens must have shape [batch, 2, num_tokens, edge_feat_dim]")
        outputs = []
        for endpoint in range(2):
            outputs.append(self.encode_endpoint(
                edge_tokens[:, endpoint], time_gaps_seconds[:, endpoint],
                valid_mask[:, endpoint], node_stats[:, endpoint],
            ))
        return torch.cat(outputs, dim=1)


def anonymous_node_statistics(
    incident: int,
    outgoing: int,
    incoming: int,
    unique_neighbours: int,
    reciprocal_neighbours: int,
    milliseconds_since_last: int | None,
) -> np.ndarray:
    """Return the preregistered eight identity-free causal node statistics."""

    total = max(0, int(incident))
    denominator = float(max(1, total))
    unique = max(0, int(unique_neighbours))
    gap = 0.0 if milliseconds_since_last is None else math.log1p(max(0, int(milliseconds_since_last))) / 20.0
    return np.asarray([
        math.log1p(total), math.log1p(max(0, int(outgoing))), math.log1p(max(0, int(incoming))),
        math.log1p(unique), float(max(0, int(outgoing))) / denominator,
        float(max(0, int(incoming))) / denominator, gap,
        float(max(0, int(reciprocal_neighbours))) / float(max(1, unique)),
    ], dtype=np.float32)


__all__ = [
    "AnonymousGraphMixer", "FeedForwardNet", "MLPMixer", "TimeEncoder",
    "UPSTREAM_COMMIT", "UPSTREAM_LICENSE", "UPSTREAM_REPOSITORY",
    "anonymous_node_statistics",
]
