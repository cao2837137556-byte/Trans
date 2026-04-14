from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim


class TransformerModel(nn.Module):
    def __init__(self, d_model=64, nhead=4, num_layers=1, dim_feedforward=128, output_dim=1):
        super(TransformerModel, self).__init__()
        self.input_net = nn.Linear(1, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            batch_first=True,
            dropout=0.0,
            dim_feedforward=dim_feedforward,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.output_net = nn.Linear(d_model, output_dim)

    def encode(self, x):
        # x: [batch, num_features, 1]
        h = self.input_net(x)
        h = self.transformer(h)
        pooled = torch.mean(h, dim=1)
        return h, pooled

    def forward(self, x, return_latent=False):
        h, pooled = self.encode(x)
        out = self.output_net(h)
        if return_latent:
            return out, pooled
        return out


class TransformerDetector:
    VALID_UNC_SCORE_MODES = {"combined_nll", "error_only", "uncertainty_only"}

    def __init__(self, params):
        self.params = params
        self.input_dim = params.n_visible
        self.hidden_ratio = getattr(params, "hidden_ratio", 0.75)
        raw_lr = getattr(params, "learning_rate", 1e-5)
        self.learning_rate = min(raw_lr, 1e-3)

        self.mae_enabled = bool(getattr(params, "mae_enabled", False))
        self.mae_mask_ratio = float(np.clip(getattr(params, "mae_mask_ratio", 0.0), 0.0, 0.95))

        self.tailreg_enabled = bool(getattr(params, "tailreg_enabled", False))
        self.tailreg_lambda = float(getattr(params, "tailreg_lambda", 0.1))
        self.tailreg_k = float(getattr(params, "tailreg_k", 2.0))
        self.tailreg_warmup = int(getattr(params, "tailreg_warmup", 512))
        self.tailreg_ema_alpha = float(getattr(params, "tailreg_ema_alpha", 0.01))

        self.uncertainty_enabled = bool(getattr(params, "uncertainty_enabled", False))
        self.uncertainty_logvar_min = float(getattr(params, "uncertainty_logvar_min", -8.0))
        self.uncertainty_logvar_max = float(getattr(params, "uncertainty_logvar_max", 8.0))
        if self.uncertainty_logvar_min > self.uncertainty_logvar_max:
            self.uncertainty_logvar_min, self.uncertainty_logvar_max = (
                self.uncertainty_logvar_max,
                self.uncertainty_logvar_min,
            )
        self.uncertainty_score_mode = str(getattr(params, "uncertainty_score_mode", "combined_nll")).lower()
        if self.uncertainty_score_mode not in self.VALID_UNC_SCORE_MODES:
            self.uncertainty_score_mode = "combined_nll"

        self.latent_contrastive_enabled = bool(getattr(params, "latent_contrastive_enabled", False))
        self.latent_pooling = str(getattr(params, "latent_pooling", "mean")).lower()
        if self.latent_pooling not in {"mean"}:
            self.latent_pooling = "mean"
        self.latent_contrastive_mode = str(getattr(params, "latent_contrastive_mode", "v1")).lower()
        if self.latent_contrastive_mode not in {"v1", "compact_v2", "compact_v3", "covreg_v1", "covreg_v2"}:
            self.latent_contrastive_mode = "v1"
        self.latent_margin = float(getattr(params, "latent_margin", 1.0))
        self.latent_lambda = float(getattr(params, "latent_lambda", 0.1))
        self.latent_compact_enabled = bool(
            getattr(params, "latent_compact_enabled", self.latent_contrastive_mode in {"compact_v2", "compact_v3"})
        )
        self.latent_lambda_compact = float(
            getattr(
                params,
                "latent_lambda_compact",
                0.05 if self.latent_contrastive_mode in {"compact_v2", "compact_v3"} else 0.0,
            )
        )
        self.latent_covreg_v2_enabled = bool(
            getattr(params, "latent_covreg_v2_enabled", self.latent_contrastive_mode == "covreg_v2")
        )
        self.latent_covreg_enabled = bool(
            getattr(params, "latent_covreg_enabled", self.latent_contrastive_mode in {"covreg_v1", "covreg_v2"})
        )
        self.latent_lambda_var = float(getattr(params, "latent_lambda_var", 0.0))
        self.latent_lambda_corr = float(getattr(params, "latent_lambda_corr", 0.0))
        self.latent_var_min = float(getattr(params, "latent_var_min", 0.2))
        self.latent_var_max = float(getattr(params, "latent_var_max", 2.0))
        if self.latent_var_min > self.latent_var_max:
            self.latent_var_min, self.latent_var_max = self.latent_var_max, self.latent_var_min
        self.latent_covreg_buffer_size = int(max(2, int(getattr(params, "latent_covreg_buffer_size", 64))))
        self.latent_covreg_use_layernorm = bool(getattr(params, "latent_covreg_use_layernorm", True))
        self.latent_covreg_ema_momentum = float(np.clip(float(getattr(params, "latent_covreg_ema_momentum", 0.99)), 0.0, 0.9999))
        self.latent_covreg_alpha_scale = float(max(0.0, float(getattr(params, "latent_covreg_alpha_scale", 0.1))))
        self.latent_covreg_lambda_tail = float(max(0.0, float(getattr(params, "latent_covreg_lambda_tail", 0.1))))
        self.latent_covreg_lambda_neg = float(max(0.0, float(getattr(params, "latent_covreg_lambda_neg", 0.5))))
        self.latent_covreg_lambda_floor = float(max(0.0, float(getattr(params, "latent_covreg_lambda_floor", 0.01))))
        self.latent_covreg_tau_mode = str(getattr(params, "latent_covreg_tau_mode", "mean2std")).lower()
        if self.latent_covreg_tau_mode not in {"mean2std"}:
            self.latent_covreg_tau_mode = "mean2std"
        self.latent_covreg_tau_k = float(max(0.0, float(getattr(params, "latent_covreg_tau_k", 2.0))))
        self.latent_covreg_margin_neg = float(max(0.0, float(getattr(params, "latent_covreg_margin_neg", 1.0))))
        self.latent_covreg_var_floor = float(max(0.0, float(getattr(params, "latent_covreg_var_floor", 1e-3))))
        self.latent_center_ema_alpha = float(getattr(params, "latent_center_ema_alpha", 0.01))
        self.latent_center_ema_alpha = float(np.clip(self.latent_center_ema_alpha, 1e-6, 1.0))
        self.latent_warmup_steps = int(max(0, int(getattr(params, "latent_warmup_steps", 0))))

        default_swap = 0.6 if self.latent_contrastive_mode in {"compact_v2", "compact_v3"} else 0.0
        default_permute = 0.25 if self.latent_contrastive_mode in {"compact_v2", "compact_v3"} else 0.4
        default_spike = 0.15 if self.latent_contrastive_mode in {"compact_v2", "compact_v3"} else 0.3
        default_replace = 0.0 if self.latent_contrastive_mode in {"compact_v2", "compact_v3"} else 0.3
        self.neg_prob_swap = float(getattr(params, "latent_neg_prob_swap", default_swap))
        self.neg_prob_permute = float(getattr(params, "latent_neg_prob_permute", default_permute))
        self.neg_prob_spike = float(getattr(params, "latent_neg_prob_spike", default_spike))
        self.neg_prob_replace = float(getattr(params, "latent_neg_prob_replace", default_replace))
        prob_sum = self.neg_prob_swap + self.neg_prob_permute + self.neg_prob_spike + self.neg_prob_replace
        if prob_sum <= 0.0:
            if self.latent_contrastive_mode in {"compact_v2", "compact_v3"}:
                self.neg_prob_swap, self.neg_prob_permute, self.neg_prob_spike, self.neg_prob_replace = 0.6, 0.25, 0.15, 0.0
            else:
                self.neg_prob_swap, self.neg_prob_permute, self.neg_prob_spike, self.neg_prob_replace = 0.0, 0.4, 0.3, 0.3
        else:
            inv = 1.0 / prob_sum
            self.neg_prob_swap *= inv
            self.neg_prob_permute *= inv
            self.neg_prob_spike *= inv
            self.neg_prob_replace *= inv

        self.count = 0
        self.fitted = False
        self.train_step = 0
        self.train_mse_ema = None
        self.train_mse2_ema = None
        self.tail_target_last = None
        self.tail_penalty_last = 0.0
        self.latent_margin_loss_last = 0.0
        self.latent_compact_loss_last = 0.0
        self.latent_distance_last = 0.0
        self.latent_distance_exec_last = 0.0
        self.latent_center_distance_last = 0.0
        self.latent_center_distance_exec_last = 0.0
        self.latent_warmup_scale_last = 0.0
        self.latent_lambda_margin_eff_last = 0.0
        self.latent_lambda_compact_eff_last = 0.0
        self.latent_lambda_var_eff_last = 0.0
        self.latent_lambda_corr_eff_last = 0.0
        self.latent_center_l2_last = 0.0
        self.latent_center_absmax_last = 0.0
        self.latent_center_updates = 0
        self.latent_center = None
        self.latent_covreg_buffer = []
        self.latent_var_hinge_loss_last = 0.0
        self.latent_var_upper_loss_last = 0.0
        self.latent_var_lower_loss_last = 0.0
        self.latent_corr_loss_last = 0.0
        self.latent_var_mean_last = 0.0
        self.latent_var_min_last = 0.0
        self.latent_var_max_last = 0.0
        self.latent_var_inrange_ratio_last = 0.0
        self.latent_corr_offdiag_abs_mean_last = 0.0
        self.latent_corr_offdiag_sq_mean_last = 0.0
        self.latent_covreg_naninf_events = 0
        self.latent_covreg_v2_mu_ema = None
        self.latent_covreg_v2_cov_ema = None
        self.latent_covreg_v2_updates = 0
        self.latent_covreg_v2_score_mean_ema = None
        self.latent_covreg_v2_score2_ema = None
        self.latent_covreg_v2_tail_loss_last = 0.0
        self.latent_covreg_v2_neg_loss_last = 0.0
        self.latent_covreg_v2_floor_loss_last = 0.0
        self.latent_covreg_v2_tau_ref_last = 0.0
        self.latent_covreg_v2_pos_score_mean_last = 0.0
        self.latent_covreg_v2_neg_score_mean_last = 0.0
        self.latent_covreg_v2_tail_hit_rate_last = 0.0
        self.latent_covreg_v2_neg_violation_rate_last = 0.0
        self.latent_covreg_v2_alpha_last = 0.0
        self.latent_covreg_v2_trace_last = 0.0
        self.latent_covreg_v2_diag_min_last = 0.0
        self.latent_covreg_v2_diag_median_last = 0.0
        self.latent_covreg_v2_diag_max_last = 0.0
        self.latent_covreg_v2_diag_condition_proxy_last = 0.0
        self.latent_covreg_v2_floor_hit_ratio_last = 0.0
        self.latent_covreg_v2_cholesky_failures = 0
        self.latent_covreg_v2_cholesky_total = 0
        self.latent_covreg_v2_jitter_last = 0.0
        self.neg_type_last = "none"
        self.neg_type_counts = {
            "cross_window_swap": 0,
            "permute_block": 0,
            "spike_scale": 0,
            "subvector_replace": 0,
        }

        # Uncertainty diagnostics.
        self.uncertainty_naninf_train_events = 0
        self.uncertainty_naninf_exec_events = 0
        self.uncertainty_logvar_train_min_seen = np.inf
        self.uncertainty_logvar_train_max_seen = -np.inf
        self.uncertainty_logvar_exec_min_seen = np.inf
        self.uncertainty_logvar_exec_max_seen = -np.inf
        self.last_error_score = 0.0
        self.last_uncertainty_score = 0.0
        self.last_combined_score = 0.0

        # Online min-max normalization stats.
        self.norm_min = np.ones(self.input_dim, dtype=np.float64) * np.inf
        self.norm_max = np.ones(self.input_dim, dtype=np.float64) * -np.inf
        # Online raw-feature moments for variance-aware negative construction.
        self.raw_stat_count = 0
        self.raw_feature_mean = np.zeros(self.input_dim, dtype=np.float64)
        self.raw_feature_m2 = np.zeros(self.input_dim, dtype=np.float64)

        nhead = 4
        d_model = max(8, min(128, self.input_dim))
        if d_model % nhead != 0:
            d_model = max(nhead, d_model - (d_model % nhead))
        dim_feedforward = max(32, d_model, int(d_model * 4 * self.hidden_ratio))
        output_dim = 2 if self.uncertainty_enabled else 1

        self.model = TransformerModel(
            d_model=d_model,
            nhead=nhead,
            num_layers=1,
            dim_feedforward=dim_feedforward,
            output_dim=output_dim,
        )
        self.criterion = nn.MSELoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)

    def set_uncertainty_score_mode(self, mode: str) -> None:
        mode = str(mode).lower()
        if mode in self.VALID_UNC_SCORE_MODES:
            self.uncertainty_score_mode = mode

    def _finite_or_none(self, x: float):
        return None if not np.isfinite(x) else float(x)

    def _state_float_or_default(self, value, default):
        if value is None:
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def get_uncertainty_diagnostics(self):
        return {
            "enabled": bool(self.uncertainty_enabled),
            "score_mode": self.uncertainty_score_mode,
            "logvar_min": float(self.uncertainty_logvar_min),
            "logvar_max": float(self.uncertainty_logvar_max),
            "nan_inf_train_events": int(self.uncertainty_naninf_train_events),
            "nan_inf_exec_events": int(self.uncertainty_naninf_exec_events),
            "logvar_train_min_seen": self._finite_or_none(self.uncertainty_logvar_train_min_seen),
            "logvar_train_max_seen": self._finite_or_none(self.uncertainty_logvar_train_max_seen),
            "logvar_exec_min_seen": self._finite_or_none(self.uncertainty_logvar_exec_min_seen),
            "logvar_exec_max_seen": self._finite_or_none(self.uncertainty_logvar_exec_max_seen),
            "last_error_score": float(self.last_error_score),
            "last_uncertainty_score": float(self.last_uncertainty_score),
            "last_combined_score": float(self.last_combined_score),
        }

    def _neg_usage_ratios(self):
        total = float(sum(int(v) for v in self.neg_type_counts.values()))
        if total <= 0.0:
            return {k: 0.0 for k in self.neg_type_counts}
        return {k: float(int(v) / total) for k, v in self.neg_type_counts.items()}

    def _latent_warmup_scale(self) -> float:
        if self.latent_warmup_steps <= 0:
            return 1.0
        return float(np.clip(float(self.train_step) / float(self.latent_warmup_steps), 0.0, 1.0))

    def _latent_get_or_init_center(self, h_pos: torch.Tensor, create_if_missing: bool):
        center = self.latent_center
        if center is None:
            if not create_if_missing:
                return None
            with torch.no_grad():
                center_new = torch.mean(h_pos.detach(), dim=0)
                center_new = torch.nan_to_num(center_new, nan=0.0, posinf=0.0, neginf=0.0)
                self.latent_center = center_new.detach().cpu()
                self.latent_center_updates += 1
                self.latent_center_l2_last = float(torch.norm(self.latent_center, p=2).item())
                self.latent_center_absmax_last = float(torch.max(torch.abs(self.latent_center)).item())
            center = self.latent_center
        return center.detach().to(h_pos.device)

    def _latent_update_center_ema(self, h_pos: torch.Tensor) -> None:
        if not self.latent_compact_enabled:
            return
        with torch.no_grad():
            center_old = self._latent_get_or_init_center(h_pos, create_if_missing=True)
            if center_old is None:
                return
            center_new = torch.mean(h_pos.detach(), dim=0)
            center_new = torch.nan_to_num(center_new, nan=0.0, posinf=0.0, neginf=0.0)
            alpha = float(self.latent_center_ema_alpha)
            if self.latent_contrastive_mode == "compact_v3":
                # v3 uses decay-style EMA: c_t = alpha*c_{t-1} + (1-alpha)*batch_mean_detach
                center_next = alpha * center_old + (1.0 - alpha) * center_new
            else:
                center_next = (1.0 - alpha) * center_old + alpha * center_new
            self.latent_center = center_next.detach().cpu()
            self.latent_center_updates += 1
            self.latent_center_l2_last = float(torch.norm(self.latent_center, p=2).item())
            self.latent_center_absmax_last = float(torch.max(torch.abs(self.latent_center)).item())

    def _latent_compact_terms(self, h_pos: torch.Tensor, create_center: bool):
        center = self._latent_get_or_init_center(h_pos, create_if_missing=create_center)
        if center is None:
            return h_pos.new_tensor(0.0), h_pos.new_tensor(float("nan"))
        if self.latent_contrastive_mode == "compact_v3":
            # cosine compactness: L_compact = 1 - cos(h_pos, c)
            c = center.unsqueeze(0)
            num = torch.sum(h_pos * c, dim=1)
            den = torch.clamp(torch.norm(h_pos, p=2, dim=1) * torch.norm(c, p=2, dim=1), min=1e-8)
            cos = torch.clamp(num / den, -1.0, 1.0)
            cos_dist = 1.0 - cos
            compact_loss = torch.mean(cos_dist)
            center_dist = torch.mean(cos_dist)
        else:
            delta = h_pos - center.unsqueeze(0)
            sq_dist = torch.sum(delta * delta, dim=1)
            compact_loss = torch.mean(sq_dist)
            center_dist = torch.mean(torch.sqrt(torch.clamp(sq_dist, min=0.0)))
        return compact_loss, center_dist

    def _latent_covreg_batch(self, h_pos: torch.Tensor) -> torch.Tensor:
        # KitNET trains online with one sample at a time; a detached rolling buffer
        # provides an effective batch while keeping gradients on the current sample.
        parts = [t.detach().to(h_pos.device) for t in self.latent_covreg_buffer if t is not None]
        parts.append(h_pos)
        h = torch.cat(parts, dim=0)
        if self.latent_covreg_use_layernorm:
            h = F.layer_norm(h, normalized_shape=(h.shape[1],), eps=1e-5)
        return h

    def _latent_covreg_terms(self, h_pos: torch.Tensor):
        if not self.latent_covreg_enabled:
            zero = h_pos.new_tensor(0.0)
            return zero, zero, zero, zero, zero, zero, zero, zero, zero, zero
        h = self._latent_covreg_batch(h_pos)
        if h.shape[0] < 2:
            zero = h_pos.new_tensor(0.0)
            return zero, zero, zero, zero, zero, zero, zero, zero, zero, zero

        var = torch.var(h, dim=0, unbiased=False)
        var = torch.nan_to_num(var, nan=0.0, posinf=float(self.latent_var_max), neginf=0.0)
        var_min_t = h_pos.new_tensor(float(self.latent_var_min))
        var_max_t = h_pos.new_tensor(float(self.latent_var_max))
        loss_upper = torch.mean(torch.relu(var - var_max_t))
        loss_lower = torch.mean(torch.relu(var_min_t - var))
        loss_var = loss_upper + loss_lower

        hc = h - torch.mean(h, dim=0, keepdim=True)
        std = torch.sqrt(torch.clamp(torch.var(h, dim=0, unbiased=False, keepdim=True), min=1e-6))
        hz = hc / std
        corr = torch.matmul(hz.t(), hz) / max(1, int(h.shape[0]))
        corr = torch.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
        eye = torch.eye(corr.shape[0], dtype=torch.bool, device=corr.device)
        offdiag = corr[~eye]
        if offdiag.numel() == 0:
            loss_corr = h_pos.new_tensor(0.0)
            offdiag_abs = h_pos.new_tensor(0.0)
            offdiag_sq = h_pos.new_tensor(0.0)
        else:
            offdiag_sq = torch.mean(offdiag * offdiag)
            offdiag_abs = torch.mean(torch.abs(offdiag))
            loss_corr = offdiag_sq
        inrange = torch.mean(((var >= var_min_t) & (var <= var_max_t)).to(h_pos.dtype))
        return loss_var, loss_upper, loss_lower, loss_corr, torch.mean(var), torch.min(var), torch.max(var), inrange, offdiag_abs, offdiag_sq

    def _latent_update_covreg_buffer(self, h_pos: torch.Tensor) -> None:
        if not self.latent_covreg_enabled:
            return
        self.latent_covreg_buffer.append(h_pos.detach().cpu())
        if len(self.latent_covreg_buffer) > self.latent_covreg_buffer_size:
            self.latent_covreg_buffer = self.latent_covreg_buffer[-self.latent_covreg_buffer_size :]

    def _latent_update_covreg_v2_ema(self, h_pos: torch.Tensor) -> None:
        if not (self.latent_covreg_enabled and self.latent_covreg_v2_enabled):
            return
        with torch.no_grad():
            h = torch.mean(h_pos.detach(), dim=0)
            h = torch.nan_to_num(h, nan=0.0, posinf=0.0, neginf=0.0).cpu()
            d = int(h.numel())
            if d <= 0:
                return
            if self.latent_covreg_v2_mu_ema is None or self.latent_covreg_v2_cov_ema is None:
                self.latent_covreg_v2_mu_ema = h.clone()
                self.latent_covreg_v2_cov_ema = torch.eye(d, dtype=torch.float32) * 1e-3
                self.latent_covreg_v2_updates = 1
            else:
                mu_old = self.latent_covreg_v2_mu_ema.to(dtype=torch.float32)
                cov_old = self.latent_covreg_v2_cov_ema.to(dtype=torch.float32)
                if mu_old.numel() != d or cov_old.shape != (d, d):
                    self.latent_covreg_v2_mu_ema = h.clone()
                    self.latent_covreg_v2_cov_ema = torch.eye(d, dtype=torch.float32) * 1e-3
                    self.latent_covreg_v2_updates = 1
                else:
                    mom = float(self.latent_covreg_ema_momentum)
                    delta = h - mu_old
                    mu_new = mom * mu_old + (1.0 - mom) * h
                    cov_new = mom * cov_old + (1.0 - mom) * torch.outer(delta, delta)
                    cov_new = 0.5 * (cov_new + cov_new.t())
                    cov_new = torch.nan_to_num(cov_new, nan=0.0, posinf=1e6, neginf=-1e6)
                    self.latent_covreg_v2_mu_ema = mu_new.detach().cpu()
                    self.latent_covreg_v2_cov_ema = cov_new.detach().cpu()
                    self.latent_covreg_v2_updates += 1

            cov = self.latent_covreg_v2_cov_ema.to(dtype=torch.float32)
            diag = torch.clamp(torch.diag(cov), min=0.0)
            if diag.numel() > 0:
                diag_min = float(torch.min(diag).item())
                diag_med = float(torch.median(diag).item())
                diag_max = float(torch.max(diag).item())
                self.latent_covreg_v2_trace_last = float(torch.trace(cov).item())
                self.latent_covreg_v2_diag_min_last = diag_min
                self.latent_covreg_v2_diag_median_last = diag_med
                self.latent_covreg_v2_diag_max_last = diag_max
                self.latent_covreg_v2_diag_condition_proxy_last = float(diag_max / max(diag_min, 1e-12))

    def _latent_covreg_v2_score_proxy(self, h: torch.Tensor):
        if self.latent_covreg_v2_mu_ema is None or self.latent_covreg_v2_cov_ema is None:
            return None, None
        mu = self.latent_covreg_v2_mu_ema.detach().to(device=h.device, dtype=h.dtype)
        cov = self.latent_covreg_v2_cov_ema.detach().to(device=h.device, dtype=h.dtype)
        if cov.ndim != 2 or cov.shape[0] != cov.shape[1] or mu.numel() != cov.shape[0] or h.shape[1] != cov.shape[0]:
            return None, None
        eye = torch.eye(cov.shape[0], dtype=h.dtype, device=h.device)
        diag = torch.clamp(torch.diag(cov), min=1e-12)
        alpha = torch.clamp(torch.median(diag) * h.new_tensor(float(self.latent_covreg_alpha_scale)), min=1e-8)
        sigma = cov + alpha * eye
        sigma = 0.5 * (sigma + sigma.t())
        sigma = torch.nan_to_num(sigma, nan=0.0, posinf=1e6, neginf=-1e6)
        self.latent_covreg_v2_cholesky_total += 1
        chol = None
        jitter_used = None
        for jitter in (1e-6, 1e-5, 1e-4):
            try:
                chol_candidate, info = torch.linalg.cholesky_ex(sigma + h.new_tensor(jitter) * eye)
                if int(info.detach().cpu().item()) == 0:
                    chol = chol_candidate
                    jitter_used = float(jitter)
                    break
            except RuntimeError:
                chol = None
        if chol is None:
            self.latent_covreg_v2_cholesky_failures += 1
            self.latent_covreg_naninf_events += 1
            return None, {"alpha": float(alpha.detach().cpu().item()), "jitter": None}
        delta = h - mu.unsqueeze(0)
        y = torch.linalg.solve_triangular(chol, delta.t(), upper=False)
        score = torch.sum(y * y, dim=0)
        score = torch.nan_to_num(score, nan=0.0, posinf=1e6, neginf=0.0)
        self.latent_covreg_v2_alpha_last = float(alpha.detach().cpu().item())
        self.latent_covreg_v2_jitter_last = float(jitter_used)
        self.latent_covreg_v2_floor_hit_ratio_last = float(torch.mean((diag < alpha).to(torch.float32)).detach().cpu().item())
        return score, {"alpha": float(alpha.detach().cpu().item()), "jitter": float(jitter_used)}

    def _latent_covreg_v2_update_score_stats(self, score_pos: torch.Tensor) -> None:
        with torch.no_grad():
            val = float(torch.mean(score_pos.detach()).cpu().item())
            val2 = val * val
            if not np.isfinite(val):
                self.latent_covreg_naninf_events += 1
                return
            mom = float(self.latent_covreg_ema_momentum)
            if self.latent_covreg_v2_score_mean_ema is None or self.latent_covreg_v2_score2_ema is None:
                self.latent_covreg_v2_score_mean_ema = val
                self.latent_covreg_v2_score2_ema = val2
            else:
                self.latent_covreg_v2_score_mean_ema = mom * float(self.latent_covreg_v2_score_mean_ema) + (1.0 - mom) * val
                self.latent_covreg_v2_score2_ema = mom * float(self.latent_covreg_v2_score2_ema) + (1.0 - mom) * val2

    def _latent_covreg_v2_terms(self, h_pos: torch.Tensor, h_neg: torch.Tensor):
        zero = h_pos.new_tensor(0.0)
        score_pos, _ = self._latent_covreg_v2_score_proxy(h_pos)
        score_neg, _ = self._latent_covreg_v2_score_proxy(h_neg)
        if score_pos is None or score_neg is None:
            return zero, zero, zero, zero, zero, zero, zero, zero

        if self.latent_covreg_v2_score_mean_ema is None or self.latent_covreg_v2_score2_ema is None:
            tau_ref = torch.mean(score_pos.detach())
        else:
            mean = float(self.latent_covreg_v2_score_mean_ema)
            var = max(float(self.latent_covreg_v2_score2_ema) - mean * mean, 0.0)
            tau_ref = h_pos.new_tensor(mean + float(self.latent_covreg_tau_k) * float(np.sqrt(var)))

        self._latent_covreg_v2_update_score_stats(score_pos)
        active = int(self.latent_covreg_v2_updates) >= int(max(0, self.latent_warmup_steps))
        if active:
            tail_excess = torch.relu(score_pos - tau_ref.detach())
            loss_tail = torch.mean(tail_excess * tail_excess)
            neg_excess = torch.relu(tau_ref.detach() + h_pos.new_tensor(float(self.latent_covreg_margin_neg)) - score_neg)
            loss_neg = torch.mean(neg_excess * neg_excess)
        else:
            loss_tail = zero
            loss_neg = zero

        h_batch = self._latent_covreg_batch(h_pos)
        if h_batch.shape[0] >= 2 and float(self.latent_covreg_lambda_floor) > 0.0:
            var = torch.var(h_batch, dim=0, unbiased=False)
            floor = h_pos.new_tensor(float(self.latent_covreg_var_floor))
            floor_gap = torch.relu(floor - var)
            loss_floor = torch.mean(floor_gap * floor_gap)
        else:
            loss_floor = zero

        tail_hit = torch.mean((score_pos > tau_ref.detach()).to(h_pos.dtype))
        neg_violation = torch.mean((score_neg < (tau_ref.detach() + h_pos.new_tensor(float(self.latent_covreg_margin_neg)))).to(h_pos.dtype))
        return (
            loss_tail,
            loss_neg,
            loss_floor,
            tau_ref.detach(),
            torch.mean(score_pos.detach()),
            torch.mean(score_neg.detach()),
            tail_hit.detach(),
            neg_violation.detach(),
        )

    def get_latent_contrastive_diagnostics(self):
        return {
            "enabled": bool(self.latent_contrastive_enabled),
            "mode": self.latent_contrastive_mode,
            "pooling": self.latent_pooling,
            "margin": float(self.latent_margin),
            "lambda": float(self.latent_lambda),
            "compact_enabled": bool(self.latent_compact_enabled),
            "lambda_compact": float(self.latent_lambda_compact),
            "covreg_enabled": bool(self.latent_covreg_enabled),
            "covreg_v2_enabled": bool(self.latent_covreg_v2_enabled),
            "lambda_var": float(self.latent_lambda_var),
            "lambda_corr": float(self.latent_lambda_corr),
            "var_min": float(self.latent_var_min),
            "var_max": float(self.latent_var_max),
            "covreg_buffer_size": int(self.latent_covreg_buffer_size),
            "covreg_use_layernorm": bool(self.latent_covreg_use_layernorm),
            "covreg_ema_momentum": float(self.latent_covreg_ema_momentum),
            "covreg_alpha_scale": float(self.latent_covreg_alpha_scale),
            "covreg_lambda_tail": float(self.latent_covreg_lambda_tail),
            "covreg_lambda_neg": float(self.latent_covreg_lambda_neg),
            "covreg_lambda_floor": float(self.latent_covreg_lambda_floor),
            "covreg_tau_mode": self.latent_covreg_tau_mode,
            "covreg_tau_k": float(self.latent_covreg_tau_k),
            "covreg_margin_neg": float(self.latent_covreg_margin_neg),
            "covreg_var_floor": float(self.latent_covreg_var_floor),
            "center_ema_alpha": float(self.latent_center_ema_alpha),
            "warmup_steps": int(self.latent_warmup_steps),
            "neg_probabilities": {
                "cross_window_swap": float(self.neg_prob_swap),
                "permute_block": float(self.neg_prob_permute),
                "spike_scale": float(self.neg_prob_spike),
                "subvector_replace": float(self.neg_prob_replace),
            },
            "neg_type_counts": {k: int(v) for k, v in self.neg_type_counts.items()},
            "neg_type_ratios": self._neg_usage_ratios(),
            "latent_margin_loss_last": float(self.latent_margin_loss_last),
            "latent_compact_loss_last": float(self.latent_compact_loss_last),
            "latent_var_hinge_loss_last": float(self.latent_var_hinge_loss_last),
            "latent_var_upper_loss_last": float(self.latent_var_upper_loss_last),
            "latent_var_lower_loss_last": float(self.latent_var_lower_loss_last),
            "latent_corr_loss_last": float(self.latent_corr_loss_last),
            "latent_var_mean_last": float(self.latent_var_mean_last),
            "latent_var_min_last": float(self.latent_var_min_last),
            "latent_var_max_last": float(self.latent_var_max_last),
            "latent_var_inrange_ratio_last": float(self.latent_var_inrange_ratio_last),
            "latent_corr_offdiag_abs_mean_last": float(self.latent_corr_offdiag_abs_mean_last),
            "latent_corr_offdiag_sq_mean_last": float(self.latent_corr_offdiag_sq_mean_last),
            "latent_covreg_naninf_events": int(self.latent_covreg_naninf_events),
            "latent_covreg_v2_updates": int(self.latent_covreg_v2_updates),
            "latent_covreg_v2_tail_loss_last": float(self.latent_covreg_v2_tail_loss_last),
            "latent_covreg_v2_neg_loss_last": float(self.latent_covreg_v2_neg_loss_last),
            "latent_covreg_v2_floor_loss_last": float(self.latent_covreg_v2_floor_loss_last),
            "latent_covreg_v2_tau_ref_last": float(self.latent_covreg_v2_tau_ref_last),
            "latent_covreg_v2_pos_score_mean_last": float(self.latent_covreg_v2_pos_score_mean_last),
            "latent_covreg_v2_neg_score_mean_last": float(self.latent_covreg_v2_neg_score_mean_last),
            "latent_covreg_v2_tail_hit_rate_last": float(self.latent_covreg_v2_tail_hit_rate_last),
            "latent_covreg_v2_neg_violation_rate_last": float(self.latent_covreg_v2_neg_violation_rate_last),
            "latent_covreg_v2_alpha_last": float(self.latent_covreg_v2_alpha_last),
            "latent_covreg_v2_trace_last": float(self.latent_covreg_v2_trace_last),
            "latent_covreg_v2_diag_min_last": float(self.latent_covreg_v2_diag_min_last),
            "latent_covreg_v2_diag_median_last": float(self.latent_covreg_v2_diag_median_last),
            "latent_covreg_v2_diag_max_last": float(self.latent_covreg_v2_diag_max_last),
            "latent_covreg_v2_diag_condition_proxy_last": float(self.latent_covreg_v2_diag_condition_proxy_last),
            "latent_covreg_v2_floor_hit_ratio_last": float(self.latent_covreg_v2_floor_hit_ratio_last),
            "latent_covreg_v2_cholesky_failures": int(self.latent_covreg_v2_cholesky_failures),
            "latent_covreg_v2_cholesky_total": int(self.latent_covreg_v2_cholesky_total),
            "latent_covreg_v2_jitter_last": float(self.latent_covreg_v2_jitter_last),
            "latent_distance_last": float(self.latent_distance_last),
            "latent_distance_exec_last": float(self.latent_distance_exec_last),
            "latent_center_distance_last": float(self.latent_center_distance_last),
            "latent_center_distance_exec_last": float(self.latent_center_distance_exec_last),
            "warmup_scale_last": float(self.latent_warmup_scale_last),
            "lambda_margin_eff_last": float(self.latent_lambda_margin_eff_last),
            "lambda_compact_eff_last": float(self.latent_lambda_compact_eff_last),
            "lambda_var_eff_last": float(self.latent_lambda_var_eff_last),
            "lambda_corr_eff_last": float(self.latent_lambda_corr_eff_last),
            "center_updates": int(self.latent_center_updates),
            "center_l2_last": float(self.latent_center_l2_last),
            "center_absmax_last": float(self.latent_center_absmax_last),
            "neg_type_last": self.neg_type_last,
        }

    def get_state(self):
        return {
            "input_dim": int(self.input_dim),
            "hidden_ratio": float(self.hidden_ratio),
            "learning_rate": float(self.learning_rate),
            "mae_enabled": bool(self.mae_enabled),
            "mae_mask_ratio": float(self.mae_mask_ratio),
            "tailreg_enabled": bool(self.tailreg_enabled),
            "tailreg_lambda": float(self.tailreg_lambda),
            "tailreg_k": float(self.tailreg_k),
            "tailreg_warmup": int(self.tailreg_warmup),
            "tailreg_ema_alpha": float(self.tailreg_ema_alpha),
            "uncertainty_enabled": bool(self.uncertainty_enabled),
            "uncertainty_logvar_min": float(self.uncertainty_logvar_min),
            "uncertainty_logvar_max": float(self.uncertainty_logvar_max),
            "uncertainty_score_mode": str(self.uncertainty_score_mode),
            "uncertainty_naninf_train_events": int(self.uncertainty_naninf_train_events),
            "uncertainty_naninf_exec_events": int(self.uncertainty_naninf_exec_events),
            "uncertainty_logvar_train_min_seen": self._finite_or_none(self.uncertainty_logvar_train_min_seen),
            "uncertainty_logvar_train_max_seen": self._finite_or_none(self.uncertainty_logvar_train_max_seen),
            "uncertainty_logvar_exec_min_seen": self._finite_or_none(self.uncertainty_logvar_exec_min_seen),
            "uncertainty_logvar_exec_max_seen": self._finite_or_none(self.uncertainty_logvar_exec_max_seen),
            "latent_contrastive_enabled": bool(self.latent_contrastive_enabled),
            "latent_contrastive_mode": str(self.latent_contrastive_mode),
            "latent_pooling": str(self.latent_pooling),
            "latent_margin": float(self.latent_margin),
            "latent_lambda": float(self.latent_lambda),
            "latent_compact_enabled": bool(self.latent_compact_enabled),
            "latent_lambda_compact": float(self.latent_lambda_compact),
            "latent_covreg_enabled": bool(self.latent_covreg_enabled),
            "latent_covreg_v2_enabled": bool(self.latent_covreg_v2_enabled),
            "latent_lambda_var": float(self.latent_lambda_var),
            "latent_lambda_corr": float(self.latent_lambda_corr),
            "latent_var_min": float(self.latent_var_min),
            "latent_var_max": float(self.latent_var_max),
            "latent_covreg_buffer_size": int(self.latent_covreg_buffer_size),
            "latent_covreg_use_layernorm": bool(self.latent_covreg_use_layernorm),
            "latent_covreg_ema_momentum": float(self.latent_covreg_ema_momentum),
            "latent_covreg_alpha_scale": float(self.latent_covreg_alpha_scale),
            "latent_covreg_lambda_tail": float(self.latent_covreg_lambda_tail),
            "latent_covreg_lambda_neg": float(self.latent_covreg_lambda_neg),
            "latent_covreg_lambda_floor": float(self.latent_covreg_lambda_floor),
            "latent_covreg_tau_mode": str(self.latent_covreg_tau_mode),
            "latent_covreg_tau_k": float(self.latent_covreg_tau_k),
            "latent_covreg_margin_neg": float(self.latent_covreg_margin_neg),
            "latent_covreg_var_floor": float(self.latent_covreg_var_floor),
            "latent_center_ema_alpha": float(self.latent_center_ema_alpha),
            "latent_warmup_steps": int(self.latent_warmup_steps),
            "latent_neg_prob_swap": float(self.neg_prob_swap),
            "latent_neg_prob_permute": float(self.neg_prob_permute),
            "latent_neg_prob_spike": float(self.neg_prob_spike),
            "latent_neg_prob_replace": float(self.neg_prob_replace),
            "latent_margin_loss_last": float(self.latent_margin_loss_last),
            "latent_compact_loss_last": float(self.latent_compact_loss_last),
            "latent_var_hinge_loss_last": float(self.latent_var_hinge_loss_last),
            "latent_var_upper_loss_last": float(self.latent_var_upper_loss_last),
            "latent_var_lower_loss_last": float(self.latent_var_lower_loss_last),
            "latent_corr_loss_last": float(self.latent_corr_loss_last),
            "latent_var_mean_last": float(self.latent_var_mean_last),
            "latent_var_min_last": float(self.latent_var_min_last),
            "latent_var_max_last": float(self.latent_var_max_last),
            "latent_var_inrange_ratio_last": float(self.latent_var_inrange_ratio_last),
            "latent_corr_offdiag_abs_mean_last": float(self.latent_corr_offdiag_abs_mean_last),
            "latent_corr_offdiag_sq_mean_last": float(self.latent_corr_offdiag_sq_mean_last),
            "latent_covreg_naninf_events": int(self.latent_covreg_naninf_events),
            "latent_covreg_v2_updates": int(self.latent_covreg_v2_updates),
            "latent_covreg_v2_mu_ema": None
            if self.latent_covreg_v2_mu_ema is None
            else self.latent_covreg_v2_mu_ema.detach().cpu().numpy().astype(np.float32),
            "latent_covreg_v2_cov_ema": None
            if self.latent_covreg_v2_cov_ema is None
            else self.latent_covreg_v2_cov_ema.detach().cpu().numpy().astype(np.float32),
            "latent_covreg_v2_score_mean_ema": None if self.latent_covreg_v2_score_mean_ema is None else float(self.latent_covreg_v2_score_mean_ema),
            "latent_covreg_v2_score2_ema": None if self.latent_covreg_v2_score2_ema is None else float(self.latent_covreg_v2_score2_ema),
            "latent_covreg_v2_tail_loss_last": float(self.latent_covreg_v2_tail_loss_last),
            "latent_covreg_v2_neg_loss_last": float(self.latent_covreg_v2_neg_loss_last),
            "latent_covreg_v2_floor_loss_last": float(self.latent_covreg_v2_floor_loss_last),
            "latent_covreg_v2_tau_ref_last": float(self.latent_covreg_v2_tau_ref_last),
            "latent_covreg_v2_pos_score_mean_last": float(self.latent_covreg_v2_pos_score_mean_last),
            "latent_covreg_v2_neg_score_mean_last": float(self.latent_covreg_v2_neg_score_mean_last),
            "latent_covreg_v2_tail_hit_rate_last": float(self.latent_covreg_v2_tail_hit_rate_last),
            "latent_covreg_v2_neg_violation_rate_last": float(self.latent_covreg_v2_neg_violation_rate_last),
            "latent_covreg_v2_alpha_last": float(self.latent_covreg_v2_alpha_last),
            "latent_covreg_v2_trace_last": float(self.latent_covreg_v2_trace_last),
            "latent_covreg_v2_diag_min_last": float(self.latent_covreg_v2_diag_min_last),
            "latent_covreg_v2_diag_median_last": float(self.latent_covreg_v2_diag_median_last),
            "latent_covreg_v2_diag_max_last": float(self.latent_covreg_v2_diag_max_last),
            "latent_covreg_v2_diag_condition_proxy_last": float(self.latent_covreg_v2_diag_condition_proxy_last),
            "latent_covreg_v2_floor_hit_ratio_last": float(self.latent_covreg_v2_floor_hit_ratio_last),
            "latent_covreg_v2_cholesky_failures": int(self.latent_covreg_v2_cholesky_failures),
            "latent_covreg_v2_cholesky_total": int(self.latent_covreg_v2_cholesky_total),
            "latent_covreg_v2_jitter_last": float(self.latent_covreg_v2_jitter_last),
            "latent_distance_last": float(self.latent_distance_last),
            "latent_distance_exec_last": float(self.latent_distance_exec_last),
            "latent_center_distance_last": float(self.latent_center_distance_last),
            "latent_center_distance_exec_last": float(self.latent_center_distance_exec_last),
            "latent_warmup_scale_last": float(self.latent_warmup_scale_last),
            "latent_lambda_margin_eff_last": float(self.latent_lambda_margin_eff_last),
            "latent_lambda_compact_eff_last": float(self.latent_lambda_compact_eff_last),
            "latent_lambda_var_eff_last": float(self.latent_lambda_var_eff_last),
            "latent_lambda_corr_eff_last": float(self.latent_lambda_corr_eff_last),
            "latent_center_updates": int(self.latent_center_updates),
            "latent_center_l2_last": float(self.latent_center_l2_last),
            "latent_center_absmax_last": float(self.latent_center_absmax_last),
            "latent_center": None
            if self.latent_center is None
            else self.latent_center.detach().cpu().numpy().astype(np.float32),
            "neg_type_last": str(self.neg_type_last),
            "neg_type_counts": {k: int(v) for k, v in self.neg_type_counts.items()},
            "count": int(self.count),
            "fitted": bool(self.fitted),
            "train_step": int(self.train_step),
            "train_mse_ema": None if self.train_mse_ema is None else float(self.train_mse_ema),
            "train_mse2_ema": None if self.train_mse2_ema is None else float(self.train_mse2_ema),
            "tail_target_last": None if self.tail_target_last is None else float(self.tail_target_last),
            "tail_penalty_last": float(self.tail_penalty_last),
            "norm_min": self.norm_min.astype(np.float64),
            "norm_max": self.norm_max.astype(np.float64),
            "raw_stat_count": int(self.raw_stat_count),
            "raw_feature_mean": self.raw_feature_mean.astype(np.float64),
            "raw_feature_m2": self.raw_feature_m2.astype(np.float64),
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
        }

    def load_state(self, state):
        self.count = int(state.get("count", 0))
        self.fitted = bool(state.get("fitted", False))
        self.mae_enabled = bool(state.get("mae_enabled", self.mae_enabled))
        self.mae_mask_ratio = float(state.get("mae_mask_ratio", self.mae_mask_ratio))
        self.tailreg_enabled = bool(state.get("tailreg_enabled", self.tailreg_enabled))
        self.tailreg_lambda = float(state.get("tailreg_lambda", self.tailreg_lambda))
        self.tailreg_k = float(state.get("tailreg_k", self.tailreg_k))
        self.tailreg_warmup = int(state.get("tailreg_warmup", self.tailreg_warmup))
        self.tailreg_ema_alpha = float(state.get("tailreg_ema_alpha", self.tailreg_ema_alpha))
        self.uncertainty_enabled = bool(state.get("uncertainty_enabled", self.uncertainty_enabled))
        self.uncertainty_logvar_min = float(state.get("uncertainty_logvar_min", self.uncertainty_logvar_min))
        self.uncertainty_logvar_max = float(state.get("uncertainty_logvar_max", self.uncertainty_logvar_max))
        self.set_uncertainty_score_mode(state.get("uncertainty_score_mode", self.uncertainty_score_mode))
        self.uncertainty_naninf_train_events = int(state.get("uncertainty_naninf_train_events", 0))
        self.uncertainty_naninf_exec_events = int(state.get("uncertainty_naninf_exec_events", 0))
        self.latent_contrastive_enabled = bool(state.get("latent_contrastive_enabled", self.latent_contrastive_enabled))
        self.latent_contrastive_mode = str(state.get("latent_contrastive_mode", self.latent_contrastive_mode))
        if self.latent_contrastive_mode not in {"v1", "compact_v2", "compact_v3", "covreg_v1", "covreg_v2"}:
            self.latent_contrastive_mode = "v1"
        self.latent_pooling = str(state.get("latent_pooling", self.latent_pooling))
        if self.latent_pooling not in {"mean"}:
            self.latent_pooling = "mean"
        self.latent_margin = float(state.get("latent_margin", self.latent_margin))
        self.latent_lambda = float(state.get("latent_lambda", self.latent_lambda))
        self.latent_compact_enabled = bool(state.get("latent_compact_enabled", self.latent_compact_enabled))
        self.latent_lambda_compact = float(state.get("latent_lambda_compact", self.latent_lambda_compact))
        self.latent_covreg_enabled = bool(state.get("latent_covreg_enabled", self.latent_covreg_enabled))
        self.latent_covreg_v2_enabled = bool(state.get("latent_covreg_v2_enabled", self.latent_covreg_v2_enabled))
        self.latent_lambda_var = float(state.get("latent_lambda_var", self.latent_lambda_var))
        self.latent_lambda_corr = float(state.get("latent_lambda_corr", self.latent_lambda_corr))
        self.latent_var_min = float(state.get("latent_var_min", self.latent_var_min))
        self.latent_var_max = float(state.get("latent_var_max", self.latent_var_max))
        if self.latent_var_min > self.latent_var_max:
            self.latent_var_min, self.latent_var_max = self.latent_var_max, self.latent_var_min
        self.latent_covreg_buffer_size = int(max(2, int(state.get("latent_covreg_buffer_size", self.latent_covreg_buffer_size))))
        self.latent_covreg_use_layernorm = bool(state.get("latent_covreg_use_layernorm", self.latent_covreg_use_layernorm))
        self.latent_covreg_ema_momentum = float(np.clip(float(state.get("latent_covreg_ema_momentum", self.latent_covreg_ema_momentum)), 0.0, 0.9999))
        self.latent_covreg_alpha_scale = float(max(0.0, float(state.get("latent_covreg_alpha_scale", self.latent_covreg_alpha_scale))))
        self.latent_covreg_lambda_tail = float(max(0.0, float(state.get("latent_covreg_lambda_tail", self.latent_covreg_lambda_tail))))
        self.latent_covreg_lambda_neg = float(max(0.0, float(state.get("latent_covreg_lambda_neg", self.latent_covreg_lambda_neg))))
        self.latent_covreg_lambda_floor = float(max(0.0, float(state.get("latent_covreg_lambda_floor", self.latent_covreg_lambda_floor))))
        self.latent_covreg_tau_mode = str(state.get("latent_covreg_tau_mode", self.latent_covreg_tau_mode)).lower()
        if self.latent_covreg_tau_mode not in {"mean2std"}:
            self.latent_covreg_tau_mode = "mean2std"
        self.latent_covreg_tau_k = float(max(0.0, float(state.get("latent_covreg_tau_k", self.latent_covreg_tau_k))))
        self.latent_covreg_margin_neg = float(max(0.0, float(state.get("latent_covreg_margin_neg", self.latent_covreg_margin_neg))))
        self.latent_covreg_var_floor = float(max(0.0, float(state.get("latent_covreg_var_floor", self.latent_covreg_var_floor))))
        self.latent_center_ema_alpha = float(state.get("latent_center_ema_alpha", self.latent_center_ema_alpha))
        self.latent_center_ema_alpha = float(np.clip(self.latent_center_ema_alpha, 1e-6, 1.0))
        self.latent_warmup_steps = int(max(0, int(state.get("latent_warmup_steps", self.latent_warmup_steps))))
        self.neg_prob_swap = float(state.get("latent_neg_prob_swap", self.neg_prob_swap))
        self.neg_prob_permute = float(state.get("latent_neg_prob_permute", self.neg_prob_permute))
        self.neg_prob_spike = float(state.get("latent_neg_prob_spike", self.neg_prob_spike))
        self.neg_prob_replace = float(state.get("latent_neg_prob_replace", self.neg_prob_replace))
        prob_sum = self.neg_prob_swap + self.neg_prob_permute + self.neg_prob_spike + self.neg_prob_replace
        if prob_sum <= 0.0:
            if self.latent_contrastive_mode in {"compact_v2", "compact_v3"}:
                self.neg_prob_swap, self.neg_prob_permute, self.neg_prob_spike, self.neg_prob_replace = 0.6, 0.25, 0.15, 0.0
            else:
                self.neg_prob_swap, self.neg_prob_permute, self.neg_prob_spike, self.neg_prob_replace = 0.0, 0.4, 0.3, 0.3
        else:
            inv = 1.0 / prob_sum
            self.neg_prob_swap *= inv
            self.neg_prob_permute *= inv
            self.neg_prob_spike *= inv
            self.neg_prob_replace *= inv
        self.latent_margin_loss_last = float(state.get("latent_margin_loss_last", self.latent_margin_loss_last))
        self.latent_compact_loss_last = float(state.get("latent_compact_loss_last", self.latent_compact_loss_last))
        self.latent_var_hinge_loss_last = float(state.get("latent_var_hinge_loss_last", self.latent_var_hinge_loss_last))
        self.latent_var_upper_loss_last = float(state.get("latent_var_upper_loss_last", self.latent_var_upper_loss_last))
        self.latent_var_lower_loss_last = float(state.get("latent_var_lower_loss_last", self.latent_var_lower_loss_last))
        self.latent_corr_loss_last = float(state.get("latent_corr_loss_last", self.latent_corr_loss_last))
        self.latent_var_mean_last = float(state.get("latent_var_mean_last", self.latent_var_mean_last))
        self.latent_var_min_last = float(state.get("latent_var_min_last", self.latent_var_min_last))
        self.latent_var_max_last = float(state.get("latent_var_max_last", self.latent_var_max_last))
        self.latent_var_inrange_ratio_last = float(state.get("latent_var_inrange_ratio_last", self.latent_var_inrange_ratio_last))
        self.latent_corr_offdiag_abs_mean_last = float(state.get("latent_corr_offdiag_abs_mean_last", self.latent_corr_offdiag_abs_mean_last))
        self.latent_corr_offdiag_sq_mean_last = float(state.get("latent_corr_offdiag_sq_mean_last", self.latent_corr_offdiag_sq_mean_last))
        self.latent_covreg_naninf_events = int(state.get("latent_covreg_naninf_events", self.latent_covreg_naninf_events))
        self.latent_covreg_v2_updates = int(state.get("latent_covreg_v2_updates", self.latent_covreg_v2_updates))
        mu_state = state.get("latent_covreg_v2_mu_ema", None)
        self.latent_covreg_v2_mu_ema = None if mu_state is None else torch.tensor(np.asarray(mu_state, dtype=np.float32).reshape(-1), dtype=torch.float32)
        cov_state = state.get("latent_covreg_v2_cov_ema", None)
        self.latent_covreg_v2_cov_ema = None if cov_state is None else torch.tensor(np.asarray(cov_state, dtype=np.float32), dtype=torch.float32)
        self.latent_covreg_v2_score_mean_ema = state.get("latent_covreg_v2_score_mean_ema", self.latent_covreg_v2_score_mean_ema)
        self.latent_covreg_v2_score2_ema = state.get("latent_covreg_v2_score2_ema", self.latent_covreg_v2_score2_ema)
        self.latent_covreg_v2_tail_loss_last = float(state.get("latent_covreg_v2_tail_loss_last", self.latent_covreg_v2_tail_loss_last))
        self.latent_covreg_v2_neg_loss_last = float(state.get("latent_covreg_v2_neg_loss_last", self.latent_covreg_v2_neg_loss_last))
        self.latent_covreg_v2_floor_loss_last = float(state.get("latent_covreg_v2_floor_loss_last", self.latent_covreg_v2_floor_loss_last))
        self.latent_covreg_v2_tau_ref_last = float(state.get("latent_covreg_v2_tau_ref_last", self.latent_covreg_v2_tau_ref_last))
        self.latent_covreg_v2_pos_score_mean_last = float(state.get("latent_covreg_v2_pos_score_mean_last", self.latent_covreg_v2_pos_score_mean_last))
        self.latent_covreg_v2_neg_score_mean_last = float(state.get("latent_covreg_v2_neg_score_mean_last", self.latent_covreg_v2_neg_score_mean_last))
        self.latent_covreg_v2_tail_hit_rate_last = float(state.get("latent_covreg_v2_tail_hit_rate_last", self.latent_covreg_v2_tail_hit_rate_last))
        self.latent_covreg_v2_neg_violation_rate_last = float(state.get("latent_covreg_v2_neg_violation_rate_last", self.latent_covreg_v2_neg_violation_rate_last))
        self.latent_covreg_v2_alpha_last = float(state.get("latent_covreg_v2_alpha_last", self.latent_covreg_v2_alpha_last))
        self.latent_covreg_v2_trace_last = float(state.get("latent_covreg_v2_trace_last", self.latent_covreg_v2_trace_last))
        self.latent_covreg_v2_diag_min_last = float(state.get("latent_covreg_v2_diag_min_last", self.latent_covreg_v2_diag_min_last))
        self.latent_covreg_v2_diag_median_last = float(state.get("latent_covreg_v2_diag_median_last", self.latent_covreg_v2_diag_median_last))
        self.latent_covreg_v2_diag_max_last = float(state.get("latent_covreg_v2_diag_max_last", self.latent_covreg_v2_diag_max_last))
        self.latent_covreg_v2_diag_condition_proxy_last = float(state.get("latent_covreg_v2_diag_condition_proxy_last", self.latent_covreg_v2_diag_condition_proxy_last))
        self.latent_covreg_v2_floor_hit_ratio_last = float(state.get("latent_covreg_v2_floor_hit_ratio_last", self.latent_covreg_v2_floor_hit_ratio_last))
        self.latent_covreg_v2_cholesky_failures = int(state.get("latent_covreg_v2_cholesky_failures", self.latent_covreg_v2_cholesky_failures))
        self.latent_covreg_v2_cholesky_total = int(state.get("latent_covreg_v2_cholesky_total", self.latent_covreg_v2_cholesky_total))
        self.latent_covreg_v2_jitter_last = float(state.get("latent_covreg_v2_jitter_last", self.latent_covreg_v2_jitter_last))
        self.latent_distance_last = float(state.get("latent_distance_last", self.latent_distance_last))
        self.latent_distance_exec_last = float(state.get("latent_distance_exec_last", self.latent_distance_exec_last))
        self.latent_center_distance_last = float(state.get("latent_center_distance_last", self.latent_center_distance_last))
        self.latent_center_distance_exec_last = float(state.get("latent_center_distance_exec_last", self.latent_center_distance_exec_last))
        self.latent_warmup_scale_last = float(state.get("latent_warmup_scale_last", self.latent_warmup_scale_last))
        self.latent_lambda_margin_eff_last = float(state.get("latent_lambda_margin_eff_last", self.latent_lambda_margin_eff_last))
        self.latent_lambda_compact_eff_last = float(state.get("latent_lambda_compact_eff_last", self.latent_lambda_compact_eff_last))
        self.latent_lambda_var_eff_last = float(state.get("latent_lambda_var_eff_last", self.latent_lambda_var_eff_last))
        self.latent_lambda_corr_eff_last = float(state.get("latent_lambda_corr_eff_last", self.latent_lambda_corr_eff_last))
        self.latent_center_updates = int(state.get("latent_center_updates", self.latent_center_updates))
        self.latent_center_l2_last = float(state.get("latent_center_l2_last", self.latent_center_l2_last))
        self.latent_center_absmax_last = float(state.get("latent_center_absmax_last", self.latent_center_absmax_last))
        center_state = state.get("latent_center", None)
        if center_state is None:
            self.latent_center = None
        else:
            center_arr = np.asarray(center_state, dtype=np.float32).reshape(-1)
            self.latent_center = torch.tensor(center_arr, dtype=torch.float32)
        self.neg_type_last = str(state.get("neg_type_last", self.neg_type_last))
        loaded_counts = state.get("neg_type_counts", {})
        if isinstance(loaded_counts, dict):
            for key in self.neg_type_counts:
                self.neg_type_counts[key] = int(loaded_counts.get(key, self.neg_type_counts[key]))
        self.uncertainty_logvar_train_min_seen = self._state_float_or_default(
            state.get("uncertainty_logvar_train_min_seen", self.uncertainty_logvar_train_min_seen),
            self.uncertainty_logvar_train_min_seen,
        )
        self.uncertainty_logvar_train_max_seen = self._state_float_or_default(
            state.get("uncertainty_logvar_train_max_seen", self.uncertainty_logvar_train_max_seen),
            self.uncertainty_logvar_train_max_seen,
        )
        self.uncertainty_logvar_exec_min_seen = self._state_float_or_default(
            state.get("uncertainty_logvar_exec_min_seen", self.uncertainty_logvar_exec_min_seen),
            self.uncertainty_logvar_exec_min_seen,
        )
        self.uncertainty_logvar_exec_max_seen = self._state_float_or_default(
            state.get("uncertainty_logvar_exec_max_seen", self.uncertainty_logvar_exec_max_seen),
            self.uncertainty_logvar_exec_max_seen,
        )

        self.train_step = int(state.get("train_step", 0))
        self.train_mse_ema = state.get("train_mse_ema", None)
        self.train_mse2_ema = state.get("train_mse2_ema", None)
        self.tail_target_last = state.get("tail_target_last", None)
        self.tail_penalty_last = float(state.get("tail_penalty_last", 0.0))
        if "norm_min" in state:
            self.norm_min = np.asarray(state["norm_min"], dtype=np.float64)
        if "norm_max" in state:
            self.norm_max = np.asarray(state["norm_max"], dtype=np.float64)
        self.raw_stat_count = int(state.get("raw_stat_count", self.raw_stat_count))
        if "raw_feature_mean" in state:
            self.raw_feature_mean = np.asarray(state["raw_feature_mean"], dtype=np.float64)
        if "raw_feature_m2" in state:
            self.raw_feature_m2 = np.asarray(state["raw_feature_m2"], dtype=np.float64)
        if "model_state_dict" in state:
            self.model.load_state_dict(state["model_state_dict"])
        if "optimizer_state_dict" in state:
            self.optimizer.load_state_dict(state["optimizer_state_dict"])
        return self

    def _update_minmax(self, x):
        self.norm_max[x > self.norm_max] = x[x > self.norm_max]
        self.norm_min[x < self.norm_min] = x[x < self.norm_min]

    def _update_raw_feature_stats(self, x):
        x = np.asarray(x, dtype=np.float64)
        self.raw_stat_count += 1
        if self.raw_stat_count == 1:
            self.raw_feature_mean = x.copy()
            self.raw_feature_m2 = np.zeros_like(x)
            return
        delta = x - self.raw_feature_mean
        self.raw_feature_mean = self.raw_feature_mean + (delta / float(self.raw_stat_count))
        delta2 = x - self.raw_feature_mean
        self.raw_feature_m2 = self.raw_feature_m2 + (delta * delta2)

    def _normalized_feature_std(self, indices: np.ndarray) -> np.ndarray:
        idx = np.asarray(indices, dtype=np.int64)
        if self.raw_stat_count <= 1:
            return np.ones(len(idx), dtype=np.float64) * 0.02
        raw_var = np.maximum(self.raw_feature_m2[idx] / float(self.raw_stat_count - 1), 0.0)
        raw_std = np.sqrt(raw_var)
        denom = np.maximum(self.norm_max[idx] - self.norm_min[idx], 1e-8)
        std_norm = raw_std / denom
        std_norm = np.nan_to_num(std_norm, nan=0.02, posinf=0.25, neginf=0.02)
        std_norm = np.clip(std_norm, 0.01, 0.25)
        return std_norm

    def preprocess(self, x, update_stats=False):
        # Train updates min/max; execute only normalizes with frozen stats.
        x = np.asarray(x, dtype=np.float64)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        if update_stats:
            self._update_raw_feature_stats(x)
            self._update_minmax(x)
            self.fitted = True
        elif not self.fitted:
            return np.zeros_like(x)
        denom = self.norm_max - self.norm_min + 1e-16
        x = (x - self.norm_min) / denom
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        return x

    def _record_logvar(self, log_var_tensor: torch.Tensor, phase: str) -> None:
        if not self.uncertainty_enabled:
            return
        if log_var_tensor.numel() == 0:
            return
        lv = torch.nan_to_num(log_var_tensor.detach(), nan=0.0, posinf=self.uncertainty_logvar_max, neginf=self.uncertainty_logvar_min)
        lv_min = float(torch.min(lv).item())
        lv_max = float(torch.max(lv).item())
        if phase == "train":
            self.uncertainty_logvar_train_min_seen = min(self.uncertainty_logvar_train_min_seen, lv_min)
            self.uncertainty_logvar_train_max_seen = max(self.uncertainty_logvar_train_max_seen, lv_max)
        else:
            self.uncertainty_logvar_exec_min_seen = min(self.uncertainty_logvar_exec_min_seen, lv_min)
            self.uncertainty_logvar_exec_max_seen = max(self.uncertainty_logvar_exec_max_seen, lv_max)

    def _uncertainty_terms(self, output: torch.Tensor, target: torch.Tensor, phase: str):
        if output.shape[-1] < 2:
            mu = output[..., :1]
            log_var = torch.zeros_like(mu)
        else:
            mu = output[..., :1]
            log_var = output[..., 1:2]

        mu = torch.nan_to_num(mu, nan=0.0, posinf=0.0, neginf=0.0)
        log_var = torch.nan_to_num(
            log_var,
            nan=0.0,
            posinf=self.uncertainty_logvar_max,
            neginf=self.uncertainty_logvar_min,
        )
        log_var = torch.clamp(log_var, min=self.uncertainty_logvar_min, max=self.uncertainty_logvar_max)
        self._record_logvar(log_var, phase=phase)

        sq_err = (target - mu) * (target - mu)
        # Stable Gaussian NLL:
        # 0.5 * exp(-log_var) * (x - mu)^2 + 0.5 * log_var
        nll_elem = 0.5 * torch.exp(-log_var) * sq_err + 0.5 * log_var

        mse = torch.mean(sq_err)
        rmse = torch.sqrt(torch.clamp(mse, min=0.0))
        uncertainty = torch.mean(torch.exp(log_var))
        combined_nll = torch.mean(nll_elem)

        return {
            "mse": mse,
            "rmse": rmse,
            "uncertainty": uncertainty,
            "combined_nll": combined_nll,
        }

    def _sample_neg_type(self) -> str:
        r = np.random.rand()
        if r < self.neg_prob_swap:
            return "cross_window_swap"
        if r < self.neg_prob_swap + self.neg_prob_permute:
            return "permute_block"
        if r < self.neg_prob_swap + self.neg_prob_permute + self.neg_prob_spike:
            return "spike_scale"
        return "subvector_replace"

    def _make_hard_negative(self, input_tensor: torch.Tensor, record: bool = True):
        neg = input_tensor.detach().clone()
        d = int(self.input_dim)
        neg_type = self._sample_neg_type()

        if d <= 1:
            neg_type = "spike_scale"

        if neg_type == "cross_window_swap":
            if d < 4:
                neg_type = "spike_scale"
            else:
                block = max(2, min(d // 3, max(2, d // 10)))
                left_hi = max(1, (d // 2) - block + 1)
                right_lo = min(max(d // 2, 0), max(0, d - block))
                right_hi = max(right_lo, d - block)
                left_start = int(np.random.randint(0, left_hi))
                right_start = int(np.random.randint(right_lo, right_hi + 1))
                left_seg = neg[:, left_start : left_start + block, :].clone()
                right_seg = neg[:, right_start : right_start + block, :].clone()
                if block > 2:
                    right_seg = torch.roll(right_seg, shifts=1, dims=1)
                neg[:, left_start : left_start + block, :] = torch.clamp(0.75 * right_seg + 0.25 * left_seg, 0.0, 1.0)
                neg[:, right_start : right_start + block, :] = torch.clamp(0.75 * left_seg + 0.25 * right_seg, 0.0, 1.0)
        elif neg_type == "permute_block":
            block = max(2, min(d, max(3, d // 8)))
            start = int(np.random.randint(0, max(1, d - block + 1)))
            segment = neg[:, start : start + block, :].clone()
            perm = torch.randperm(block, device=neg.device)
            neg[:, start : start + block, :] = segment[:, perm, :]
        elif neg_type == "spike_scale":
            k = max(1, min(d, int(np.ceil(0.05 * d))))
            idx = np.random.choice(d, size=k, replace=False)
            idx_t = torch.tensor(idx, dtype=torch.long, device=neg.device)
            std_norm = self._normalized_feature_std(idx)
            std_t = torch.tensor(std_norm, dtype=neg.dtype, device=neg.device)
            scale = torch.tensor(
                np.random.uniform(1.08, 1.35, size=k),
                dtype=neg.dtype,
                device=neg.device,
            )
            offset = torch.tensor(
                np.random.uniform(2.0, 3.0, size=k) * np.random.choice([-1.0, 1.0], size=k),
                dtype=neg.dtype,
                device=neg.device,
            )
            vals = neg[:, idx_t, 0] * scale + offset * std_t
            neg[:, idx_t, 0] = torch.clamp(vals, 0.0, 1.0)
        else:
            seg = max(1, min(d, int(np.ceil(0.15 * d))))
            if seg >= d:
                seg = max(1, d // 2)
            start = int(np.random.randint(0, max(1, d - seg + 1)))
            src = int(np.random.randint(0, max(1, d - seg + 1)))
            if d - seg > 0 and abs(src - start) < max(1, seg // 2):
                src = int((src + seg) % (d - seg + 1))
            source = neg[:, src : src + seg, :].clone()
            noise = 0.02 * torch.randn_like(source)
            neg[:, start : start + seg, :] = torch.clamp(source + noise, 0.0, 1.0)
            neg_type = "subvector_replace"

        if record:
            self.neg_type_last = neg_type
            if neg_type in self.neg_type_counts:
                self.neg_type_counts[neg_type] += 1
        return neg, neg_type

    def _latent_margin_terms(self, h_pos: torch.Tensor, h_neg: torch.Tensor):
        dist = torch.norm(h_pos - h_neg, p=2, dim=1)
        dist_mean = torch.mean(dist)
        margin_term = torch.relu(h_pos.new_tensor(self.latent_margin) - dist_mean)
        return dist_mean, margin_term

    def probe_latent_metrics(self, x):
        if not self.latent_contrastive_enabled:
            return {
                "neg_distance": np.nan,
                "center_distance": np.nan,
                "neg_center_distance": np.nan,
                "neg_type": "disabled",
            }
        x = self.preprocess(x, update_stats=False)
        input_tensor = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)
        neg_tensor, neg_type = self._make_hard_negative(input_tensor, record=False)
        self.model.eval()
        with torch.no_grad():
            _, h_pos = self.model(input_tensor, return_latent=True)
            _, h_neg = self.model(neg_tensor, return_latent=True)
            neg_dist, _ = self._latent_margin_terms(h_pos, h_neg)
            compact_loss, center_dist = self._latent_compact_terms(h_pos, create_center=False)
            _, neg_center_dist = self._latent_compact_terms(h_neg, create_center=False)
            _ = compact_loss
            neg_value = float(neg_dist.item())
            center_value = float(center_dist.item()) if torch.isfinite(center_dist) else float("nan")
            neg_center_value = float(neg_center_dist.item()) if torch.isfinite(neg_center_dist) else float("nan")
        self.latent_distance_exec_last = neg_value
        if np.isfinite(center_value):
            self.latent_center_distance_exec_last = center_value
        return {
            "neg_distance": neg_value,
            "center_distance": center_value,
            "neg_center_distance": neg_center_value,
            "neg_type": str(neg_type),
        }

    def probe_latent_distance(self, x):
        metrics = self.probe_latent_metrics(x)
        return float(metrics["neg_distance"]), str(metrics["neg_type"])

    def probe_negative_score(self, x):
        x = self.preprocess(x, update_stats=False)
        input_tensor = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)
        neg_tensor, neg_type = self._make_hard_negative(input_tensor, record=False)

        self.model.eval()
        with torch.no_grad():
            output, _ = self.model(neg_tensor, return_latent=True)
            target = neg_tensor
            if self.uncertainty_enabled:
                terms = self._uncertainty_terms(output, target, phase="exec")
                if self.uncertainty_score_mode == "error_only":
                    score = float(terms["rmse"].item())
                elif self.uncertainty_score_mode == "uncertainty_only":
                    score = float(terms["uncertainty"].item())
                else:
                    score = float(terms["combined_nll"].item())
            else:
                loss = self.criterion(output, target)
                score = float(torch.sqrt(loss).item())
        if not np.isfinite(score):
            return 1e-6, str(neg_type)
        return float(score + 1e-6), str(neg_type)

    def train(self, x):
        x = self.preprocess(x, update_stats=True)
        input_tensor = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)
        target = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)
        train_input = input_tensor
        if self.mae_enabled and self.mae_mask_ratio > 0.0:
            keep = (torch.rand_like(input_tensor) > self.mae_mask_ratio).to(input_tensor.dtype)
            if torch.sum(keep).item() <= 0:
                keep[:, np.random.randint(0, self.input_dim), :] = 1.0
            train_input = input_tensor * keep

        self.optimizer.zero_grad()
        self.model.train()
        output, h_pos = self.model(train_input, return_latent=True)

        if self.uncertainty_enabled:
            terms = self._uncertainty_terms(output, target, phase="train")
            recon_loss = terms["mse"]
            primary_loss = terms["combined_nll"]
        else:
            recon_loss = self.criterion(output, target)
            primary_loss = recon_loss

        total_loss = primary_loss
        latent_margin_loss = primary_loss.new_tensor(0.0)
        latent_compact_loss = primary_loss.new_tensor(0.0)
        latent_var_hinge_loss = primary_loss.new_tensor(0.0)
        latent_var_upper_loss = primary_loss.new_tensor(0.0)
        latent_var_lower_loss = primary_loss.new_tensor(0.0)
        latent_corr_loss = primary_loss.new_tensor(0.0)
        latent_var_mean = primary_loss.new_tensor(0.0)
        latent_var_min_batch = primary_loss.new_tensor(0.0)
        latent_var_max_batch = primary_loss.new_tensor(0.0)
        latent_var_inrange = primary_loss.new_tensor(0.0)
        latent_corr_offdiag_abs = primary_loss.new_tensor(0.0)
        latent_corr_offdiag_sq = primary_loss.new_tensor(0.0)
        latent_distance = primary_loss.new_tensor(0.0)
        latent_center_distance = primary_loss.new_tensor(float("nan"))
        latent_v2_tail_loss = primary_loss.new_tensor(0.0)
        latent_v2_neg_loss = primary_loss.new_tensor(0.0)
        latent_v2_floor_loss = primary_loss.new_tensor(0.0)
        latent_v2_tau_ref = primary_loss.new_tensor(0.0)
        latent_v2_pos_score_mean = primary_loss.new_tensor(0.0)
        latent_v2_neg_score_mean = primary_loss.new_tensor(0.0)
        latent_v2_tail_hit_rate = primary_loss.new_tensor(0.0)
        latent_v2_neg_violation_rate = primary_loss.new_tensor(0.0)
        warmup_scale = 1.0
        lambda_margin_eff = 0.0
        lambda_compact_eff = 0.0
        lambda_var_eff = 0.0
        lambda_corr_eff = 0.0
        lambda_tail_eff = 0.0
        lambda_neg_eff = 0.0
        lambda_floor_eff = 0.0
        if self.latent_contrastive_enabled:
            neg_tensor, _ = self._make_hard_negative(target, record=True)
            _, h_neg = self.model(neg_tensor, return_latent=True)
            latent_distance, latent_margin_loss = self._latent_margin_terms(h_pos, h_neg)
            if self.latent_compact_enabled:
                latent_compact_loss, latent_center_distance = self._latent_compact_terms(h_pos, create_center=True)
            if self.latent_covreg_enabled and self.latent_covreg_v2_enabled:
                (
                    latent_v2_tail_loss,
                    latent_v2_neg_loss,
                    latent_v2_floor_loss,
                    latent_v2_tau_ref,
                    latent_v2_pos_score_mean,
                    latent_v2_neg_score_mean,
                    latent_v2_tail_hit_rate,
                    latent_v2_neg_violation_rate,
                ) = self._latent_covreg_v2_terms(h_pos, h_neg)
            elif self.latent_covreg_enabled:
                (
                    latent_var_hinge_loss,
                    latent_var_upper_loss,
                    latent_var_lower_loss,
                    latent_corr_loss,
                    latent_var_mean,
                    latent_var_min_batch,
                    latent_var_max_batch,
                    latent_var_inrange,
                    latent_corr_offdiag_abs,
                    latent_corr_offdiag_sq,
                ) = self._latent_covreg_terms(h_pos)
            warmup_scale = self._latent_warmup_scale()
            lambda_margin_eff = float(self.latent_lambda) * warmup_scale
            lambda_compact_eff = float(self.latent_lambda_compact) * warmup_scale
            lambda_var_eff = float(self.latent_lambda_var) * warmup_scale
            lambda_corr_eff = float(self.latent_lambda_corr) * warmup_scale
            lambda_tail_eff = float(self.latent_covreg_lambda_tail) if self.latent_covreg_v2_enabled else 0.0
            lambda_neg_eff = float(self.latent_covreg_lambda_neg) if self.latent_covreg_v2_enabled else 0.0
            lambda_floor_eff = float(self.latent_covreg_lambda_floor) if self.latent_covreg_v2_enabled else 0.0
            total_loss = (
                total_loss
                + total_loss.new_tensor(lambda_margin_eff) * latent_margin_loss
                + total_loss.new_tensor(lambda_compact_eff) * latent_compact_loss
                + total_loss.new_tensor(lambda_var_eff) * latent_var_hinge_loss
                + total_loss.new_tensor(lambda_corr_eff) * latent_corr_loss
                + total_loss.new_tensor(lambda_tail_eff) * latent_v2_tail_loss
                + total_loss.new_tensor(lambda_neg_eff) * latent_v2_neg_loss
                + total_loss.new_tensor(lambda_floor_eff) * latent_v2_floor_loss
            )

        tail_penalty = primary_loss.new_tensor(0.0)
        self.tail_target_last = None

        if (
            self.tailreg_enabled
            and self.train_step >= self.tailreg_warmup
            and self.train_mse_ema is not None
            and self.train_mse2_ema is not None
        ):
            mean = float(self.train_mse_ema)
            var = max(float(self.train_mse2_ema) - mean * mean, 0.0)
            std = float(np.sqrt(var))
            tail_target = mean + self.tailreg_k * std
            self.tail_target_last = float(tail_target)
            tail_excess = torch.relu(primary_loss - primary_loss.new_tensor(tail_target))
            tail_penalty = tail_excess * tail_excess
            total_loss = primary_loss + self.tailreg_lambda * tail_penalty

        if not torch.isfinite(total_loss):
            if self.uncertainty_enabled:
                self.uncertainty_naninf_train_events += 1
            if self.latent_covreg_enabled:
                self.latent_covreg_naninf_events += 1
            self.train_step += 1
            return 1e-6

        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        base_value = float(primary_loss.detach().item())
        if self.train_mse_ema is None or self.train_mse2_ema is None:
            self.train_mse_ema = base_value
            self.train_mse2_ema = base_value * base_value
        else:
            alpha = self.tailreg_ema_alpha
            self.train_mse_ema = (1.0 - alpha) * float(self.train_mse_ema) + alpha * base_value
            self.train_mse2_ema = (1.0 - alpha) * float(self.train_mse2_ema) + alpha * (base_value * base_value)
        self.train_step += 1
        self.tail_penalty_last = float(tail_penalty.detach().item())
        self.latent_margin_loss_last = float(latent_margin_loss.detach().item())
        self.latent_compact_loss_last = float(latent_compact_loss.detach().item())
        self.latent_var_hinge_loss_last = float(latent_var_hinge_loss.detach().item())
        self.latent_var_upper_loss_last = float(latent_var_upper_loss.detach().item())
        self.latent_var_lower_loss_last = float(latent_var_lower_loss.detach().item())
        self.latent_corr_loss_last = float(latent_corr_loss.detach().item())
        self.latent_var_mean_last = float(latent_var_mean.detach().item())
        self.latent_var_min_last = float(latent_var_min_batch.detach().item())
        self.latent_var_max_last = float(latent_var_max_batch.detach().item())
        self.latent_var_inrange_ratio_last = float(latent_var_inrange.detach().item())
        self.latent_corr_offdiag_abs_mean_last = float(latent_corr_offdiag_abs.detach().item())
        self.latent_corr_offdiag_sq_mean_last = float(latent_corr_offdiag_sq.detach().item())
        self.latent_distance_last = float(latent_distance.detach().item())
        self.latent_center_distance_last = float(latent_center_distance.detach().item()) if torch.isfinite(latent_center_distance) else float("nan")
        self.latent_warmup_scale_last = float(warmup_scale)
        self.latent_lambda_margin_eff_last = float(lambda_margin_eff)
        self.latent_lambda_compact_eff_last = float(lambda_compact_eff)
        self.latent_lambda_var_eff_last = float(lambda_var_eff)
        self.latent_lambda_corr_eff_last = float(lambda_corr_eff)
        self.latent_covreg_v2_tail_loss_last = float(latent_v2_tail_loss.detach().item())
        self.latent_covreg_v2_neg_loss_last = float(latent_v2_neg_loss.detach().item())
        self.latent_covreg_v2_floor_loss_last = float(latent_v2_floor_loss.detach().item())
        self.latent_covreg_v2_tau_ref_last = float(latent_v2_tau_ref.detach().item())
        self.latent_covreg_v2_pos_score_mean_last = float(latent_v2_pos_score_mean.detach().item())
        self.latent_covreg_v2_neg_score_mean_last = float(latent_v2_neg_score_mean.detach().item())
        self.latent_covreg_v2_tail_hit_rate_last = float(latent_v2_tail_hit_rate.detach().item())
        self.latent_covreg_v2_neg_violation_rate_last = float(latent_v2_neg_violation_rate.detach().item())
        if self.latent_contrastive_enabled and self.latent_compact_enabled:
            self._latent_update_center_ema(h_pos)
        if self.latent_contrastive_enabled and self.latent_covreg_enabled and self.latent_covreg_v2_enabled:
            self._latent_update_covreg_v2_ema(h_pos)
        if self.latent_contrastive_enabled and self.latent_covreg_enabled:
            self._latent_update_covreg_buffer(h_pos)

        if self.uncertainty_enabled:
            score = base_value
        else:
            score = float(np.sqrt(float(recon_loss.detach().item())))
        if not np.isfinite(score):
            if self.uncertainty_enabled:
                self.uncertainty_naninf_train_events += 1
            return 1e-6
        return score + 1e-6

    def execute(self, x):
        self.count += 1
        x = self.preprocess(x, update_stats=False)

        self.model.eval()
        with torch.no_grad():
            input_tensor = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)
            output, h_pos = self.model(input_tensor, return_latent=True)
            target = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)

            if self.latent_contrastive_enabled:
                neg_tensor, _ = self._make_hard_negative(input_tensor, record=False)
                _, h_neg = self.model(neg_tensor, return_latent=True)
                latent_dist, _ = self._latent_margin_terms(h_pos, h_neg)
                self.latent_distance_exec_last = float(latent_dist.item())
                _, center_dist = self._latent_compact_terms(h_pos, create_center=False)
                self.latent_center_distance_exec_last = float(center_dist.item()) if torch.isfinite(center_dist) else float("nan")

            if self.uncertainty_enabled:
                terms = self._uncertainty_terms(output, target, phase="exec")
                error_score = float(terms["rmse"].item())
                unc_score = float(terms["uncertainty"].item())
                combined_score = float(terms["combined_nll"].item())
                self.last_error_score = error_score
                self.last_uncertainty_score = unc_score
                self.last_combined_score = combined_score

                if self.uncertainty_score_mode == "error_only":
                    score = error_score
                elif self.uncertainty_score_mode == "uncertainty_only":
                    score = unc_score
                else:
                    score = combined_score
            else:
                loss = self.criterion(output, target)
                score = float(torch.sqrt(loss).item())

            if self.count % 100 == 0 and not np.isfinite(score):
                print("NaN/Inf detected in execute score")
            if not np.isfinite(score):
                if self.uncertainty_enabled:
                    self.uncertainty_naninf_exec_events += 1
                return 1e-6
            return score + 1e-6
