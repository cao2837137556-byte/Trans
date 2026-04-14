import numpy as np
import pandas as pd
from pathlib import Path
import torch
import corClust as CC
import Trans as trans_backend
import dA as da_backend


class KitNET:
    def __init__(
        self,
        n,
        max_autoencoder_size=10,
        FM_grace_period=None,
        AD_grace_period=None,
        learning_rate=0.1,
        hidden_ratio=0.75,
        detector_backend="transformer",
        detector_seed=None,
        tailreg_lambda=0.1,
        tailreg_k=2.0,
        tailreg_warmup=512,
        tailreg_ema_alpha=0.01,
        mae_mask_ratio=0.4,
        uncertainty_logvar_min=-8.0,
        uncertainty_logvar_max=8.0,
        uncertainty_score_mode="combined_nll",
        latent_margin=1.0,
        latent_lambda=0.1,
        latent_lambda_compact=0.0,
        latent_lambda_var=0.0,
        latent_lambda_corr=0.0,
        latent_var_min=0.2,
        latent_var_max=2.0,
        latent_covreg_buffer_size=64,
        latent_covreg_use_layernorm=True,
        latent_covreg_ema_momentum=0.99,
        latent_covreg_alpha_scale=0.1,
        latent_covreg_lambda_tail=0.1,
        latent_covreg_lambda_neg=0.5,
        latent_covreg_lambda_floor=0.01,
        latent_covreg_tau_mode="mean2std",
        latent_covreg_tau_k=2.0,
        latent_covreg_margin_neg=1.0,
        latent_covreg_var_floor=1e-3,
        latent_center_ema_alpha=0.01,
        latent_warmup_steps=0,
        latent_contrastive_mode="v1",
        latent_pooling="mean",
        latent_neg_prob_swap=0.0,
        latent_neg_prob_permute=0.4,
        latent_neg_prob_spike=0.3,
        latent_neg_prob_replace=0.3,
    ):
        self.AD_grace_period = AD_grace_period
        if FM_grace_period is None:
            self.FM_grace_period = AD_grace_period
        else:
            self.FM_grace_period = FM_grace_period
        if max_autoencoder_size <= 0:
            self.max_autoencoder_size = 1
        else:
            self.max_autoencoder_size = max_autoencoder_size
        self.learning_rate = learning_rate
        self.hidden_ratio = hidden_ratio
        name = str(detector_backend).lower()
        if name in {"transformer", "trans"}:
            self.detector_backend = "transformer"
        elif name in {"transformer_tailreg", "trans_tailreg", "tailreg"}:
            self.detector_backend = "transformer_tailreg"
        elif name in {"transformer_mae_v1", "transformer_mae", "trans_mae", "mae"}:
            self.detector_backend = "transformer_mae_v1"
        elif name in {"transformer_mae_tailreg_v1", "transformer_mae_tailreg", "mae_tailreg", "trans_mae_tailreg"}:
            self.detector_backend = "transformer_mae_tailreg_v1"
        elif name in {"transformer_uncertainty_v1", "transformer_uncertainty", "trans_uncertainty", "uncertainty"}:
            self.detector_backend = "transformer_uncertainty_v1"
        elif name in {
            "transformer_mae_latent_contrastive_v1",
            "transformer_mae_latent_contrastive",
            "mae_latent_contrastive",
            "trans_mae_latent_contrastive",
        }:
            self.detector_backend = "transformer_mae_latent_contrastive_v1"
        elif name in {
            "transformer_latent_contrastive_v1",
            "transformer_latent_contrastive",
            "trans_latent_contrastive",
            "latent_contrastive",
        }:
            self.detector_backend = "transformer_latent_contrastive_v1"
        elif name in {
            "transformer_latent_contrastive_compact_v2",
            "transformer_latent_compact_v2",
            "latent_contrastive_compact_v2",
            "trans_latent_compact_v2",
        }:
            self.detector_backend = "transformer_latent_contrastive_compact_v2"
        elif name in {
            "transformer_covariance_regularized_v1",
            "transformer_covreg_v1",
            "transformer_latent_covreg_v1",
            "latent_covreg_v1",
        }:
            self.detector_backend = "transformer_covariance_regularized_v1"
        elif name in {
            "transformer_covariance_regularized_v2",
            "transformer_covreg_v2",
            "transformer_latent_covreg_v2",
            "latent_covreg_v2",
        }:
            self.detector_backend = "transformer_covariance_regularized_v2"
        elif name in {"da", "ae", "autoencoder"}:
            self.detector_backend = "da"
        else:
            raise ValueError(f"Unsupported detector_backend: {detector_backend}")
        self.detector_seed = detector_seed
        self.tailreg_lambda = float(tailreg_lambda)
        self.tailreg_k = float(tailreg_k)
        self.tailreg_warmup = int(tailreg_warmup)
        self.tailreg_ema_alpha = float(tailreg_ema_alpha)
        self.mae_mask_ratio = float(mae_mask_ratio)
        self.uncertainty_logvar_min = float(uncertainty_logvar_min)
        self.uncertainty_logvar_max = float(uncertainty_logvar_max)
        if self.uncertainty_logvar_min > self.uncertainty_logvar_max:
            self.uncertainty_logvar_min, self.uncertainty_logvar_max = (
                self.uncertainty_logvar_max,
                self.uncertainty_logvar_min,
            )
        self.uncertainty_score_mode = str(uncertainty_score_mode).lower()
        self.latent_margin = float(latent_margin)
        self.latent_lambda = float(latent_lambda)
        self.latent_lambda_compact = float(latent_lambda_compact)
        self.latent_lambda_var = float(latent_lambda_var)
        self.latent_lambda_corr = float(latent_lambda_corr)
        self.latent_var_min = float(latent_var_min)
        self.latent_var_max = float(latent_var_max)
        if self.latent_var_min > self.latent_var_max:
            self.latent_var_min, self.latent_var_max = self.latent_var_max, self.latent_var_min
        self.latent_covreg_buffer_size = int(max(2, int(latent_covreg_buffer_size)))
        self.latent_covreg_use_layernorm = bool(latent_covreg_use_layernorm)
        self.latent_covreg_ema_momentum = float(np.clip(float(latent_covreg_ema_momentum), 0.0, 0.9999))
        self.latent_covreg_alpha_scale = float(max(0.0, float(latent_covreg_alpha_scale)))
        self.latent_covreg_lambda_tail = float(max(0.0, float(latent_covreg_lambda_tail)))
        self.latent_covreg_lambda_neg = float(max(0.0, float(latent_covreg_lambda_neg)))
        self.latent_covreg_lambda_floor = float(max(0.0, float(latent_covreg_lambda_floor)))
        self.latent_covreg_tau_mode = str(latent_covreg_tau_mode).lower()
        if self.latent_covreg_tau_mode not in {"mean2std"}:
            self.latent_covreg_tau_mode = "mean2std"
        self.latent_covreg_tau_k = float(max(0.0, float(latent_covreg_tau_k)))
        self.latent_covreg_margin_neg = float(max(0.0, float(latent_covreg_margin_neg)))
        self.latent_covreg_var_floor = float(max(0.0, float(latent_covreg_var_floor)))
        self.latent_center_ema_alpha = float(np.clip(float(latent_center_ema_alpha), 1e-6, 1.0))
        self.latent_warmup_steps = int(max(0, int(latent_warmup_steps)))
        self.latent_contrastive_mode = str(latent_contrastive_mode).lower()
        if self.latent_contrastive_mode not in {"v1", "compact_v2", "compact_v3", "covreg_v1", "covreg_v2"}:
            self.latent_contrastive_mode = "v1"
        self.latent_pooling = str(latent_pooling).lower()
        self.latent_neg_prob_swap = float(latent_neg_prob_swap)
        self.latent_neg_prob_permute = float(latent_neg_prob_permute)
        self.latent_neg_prob_spike = float(latent_neg_prob_spike)
        self.latent_neg_prob_replace = float(latent_neg_prob_replace)
        self.n = n
        self.FM = CC.corClust(self.n)
        self.ensembleLayer = []
        self.outputLayer = None
        self.v = []
        self.params = None
        self.packet_count = 0

    def _serialize_fm_state(self):
        return {
            "n": int(self.FM.n),
            "N": int(self.FM.N),
            "c": self.FM.c.astype(np.float64),
            "c_r": self.FM.c_r.astype(np.float64),
            "c_rs": self.FM.c_rs.astype(np.float64),
            "C": self.FM.C.astype(np.float64),
            "cluster_count": int(getattr(self.FM, "cluster_count", 0)),
        }

    def _restore_fm_state(self, state):
        self.FM.n = int(state.get("n", self.FM.n))
        self.FM.N = int(state.get("N", self.FM.N))
        if "c" in state:
            self.FM.c = np.asarray(state["c"], dtype=np.float64)
        if "c_r" in state:
            self.FM.c_r = np.asarray(state["c_r"], dtype=np.float64)
        if "c_rs" in state:
            self.FM.c_rs = np.asarray(state["c_rs"], dtype=np.float64)
        if "C" in state:
            self.FM.C = np.asarray(state["C"], dtype=np.float64)
        self.FM.cluster_count = int(state.get("cluster_count", 0))

    def get_state(self):
        return {
            "n": int(self.n),
            "max_autoencoder_size": int(self.max_autoencoder_size),
            "FM_grace_period": int(self.FM_grace_period),
            "AD_grace_period": int(self.AD_grace_period),
            "learning_rate": float(self.learning_rate),
            "hidden_ratio": float(self.hidden_ratio),
            "detector_backend": self.detector_backend,
            "detector_seed": self.detector_seed,
            "tailreg_lambda": float(self.tailreg_lambda),
            "tailreg_k": float(self.tailreg_k),
            "tailreg_warmup": int(self.tailreg_warmup),
            "tailreg_ema_alpha": float(self.tailreg_ema_alpha),
            "mae_mask_ratio": float(self.mae_mask_ratio),
            "uncertainty_logvar_min": float(self.uncertainty_logvar_min),
            "uncertainty_logvar_max": float(self.uncertainty_logvar_max),
            "uncertainty_score_mode": str(self.uncertainty_score_mode),
            "latent_margin": float(self.latent_margin),
            "latent_lambda": float(self.latent_lambda),
            "latent_lambda_compact": float(self.latent_lambda_compact),
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
            "latent_contrastive_mode": str(self.latent_contrastive_mode),
            "latent_pooling": str(self.latent_pooling),
            "latent_neg_prob_swap": float(self.latent_neg_prob_swap),
            "latent_neg_prob_permute": float(self.latent_neg_prob_permute),
            "latent_neg_prob_spike": float(self.latent_neg_prob_spike),
            "latent_neg_prob_replace": float(self.latent_neg_prob_replace),
            "packet_count": int(self.packet_count),
            "v": [list(map(int, group)) for group in self.v],
            "fm_state": self._serialize_fm_state(),
            "ensemble_states": [detector.get_state() for detector in self.ensembleLayer],
            "output_state": None if self.outputLayer is None else self.outputLayer.get_state(),
        }

    def load_state(self, state):
        self.packet_count = int(state.get("packet_count", 0))
        self.v = [list(map(int, group)) for group in state.get("v", [])]

        self.ensembleLayer = []
        self.outputLayer = None
        if self.v:
            self.createAD()
            ensemble_states = state.get("ensemble_states", [])
            for detector, detector_state in zip(self.ensembleLayer, ensemble_states):
                detector.load_state(detector_state)
            if state.get("output_state") is not None and self.outputLayer is not None:
                self.outputLayer.load_state(state["output_state"])

        if state.get("fm_state") is not None:
            self._restore_fm_state(state["fm_state"])
        return self

    def save_checkpoint(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.get_state(), path)
        return path

    @classmethod
    def load_checkpoint(cls, path, map_location="cpu"):
        try:
            state = torch.load(path, map_location=map_location, weights_only=False)
        except TypeError:
            state = torch.load(path, map_location=map_location)
        model = cls(
            n=state["n"],
            max_autoencoder_size=state["max_autoencoder_size"],
            FM_grace_period=state["FM_grace_period"],
            AD_grace_period=state["AD_grace_period"],
            learning_rate=state["learning_rate"],
            hidden_ratio=state["hidden_ratio"],
            detector_backend=state.get("detector_backend", "transformer"),
            detector_seed=state.get("detector_seed", None),
            tailreg_lambda=state.get("tailreg_lambda", 0.1),
            tailreg_k=state.get("tailreg_k", 2.0),
            tailreg_warmup=state.get("tailreg_warmup", 512),
            tailreg_ema_alpha=state.get("tailreg_ema_alpha", 0.01),
            mae_mask_ratio=state.get("mae_mask_ratio", 0.4),
            uncertainty_logvar_min=state.get("uncertainty_logvar_min", -8.0),
            uncertainty_logvar_max=state.get("uncertainty_logvar_max", 8.0),
            uncertainty_score_mode=state.get("uncertainty_score_mode", "combined_nll"),
            latent_margin=state.get("latent_margin", 1.0),
            latent_lambda=state.get("latent_lambda", 0.1),
            latent_lambda_compact=state.get("latent_lambda_compact", 0.0),
            latent_lambda_var=state.get("latent_lambda_var", 0.0),
            latent_lambda_corr=state.get("latent_lambda_corr", 0.0),
            latent_var_min=state.get("latent_var_min", 0.2),
            latent_var_max=state.get("latent_var_max", 2.0),
            latent_covreg_buffer_size=state.get("latent_covreg_buffer_size", 64),
            latent_covreg_use_layernorm=state.get("latent_covreg_use_layernorm", True),
            latent_covreg_ema_momentum=state.get("latent_covreg_ema_momentum", 0.99),
            latent_covreg_alpha_scale=state.get("latent_covreg_alpha_scale", 0.1),
            latent_covreg_lambda_tail=state.get("latent_covreg_lambda_tail", 0.1),
            latent_covreg_lambda_neg=state.get("latent_covreg_lambda_neg", 0.5),
            latent_covreg_lambda_floor=state.get("latent_covreg_lambda_floor", 0.01),
            latent_covreg_tau_mode=state.get("latent_covreg_tau_mode", "mean2std"),
            latent_covreg_tau_k=state.get("latent_covreg_tau_k", 2.0),
            latent_covreg_margin_neg=state.get("latent_covreg_margin_neg", 1.0),
            latent_covreg_var_floor=state.get("latent_covreg_var_floor", 1e-3),
            latent_center_ema_alpha=state.get("latent_center_ema_alpha", 0.01),
            latent_warmup_steps=state.get("latent_warmup_steps", 0),
            latent_contrastive_mode=state.get("latent_contrastive_mode", "v1"),
            latent_pooling=state.get("latent_pooling", "mean"),
            latent_neg_prob_swap=state.get("latent_neg_prob_swap", 0.0),
            latent_neg_prob_permute=state.get("latent_neg_prob_permute", 0.4),
            latent_neg_prob_spike=state.get("latent_neg_prob_spike", 0.3),
            latent_neg_prob_replace=state.get("latent_neg_prob_replace", 0.3),
        )
        return model.load_state(state)

    def process(self, x):
        self.packet_count += 1

        if self.packet_count <= self.FM_grace_period:
            self.FM.train(x)
            if self.packet_count == self.FM_grace_period:
                clusters = self.FM.cluster(self.max_autoencoder_size)
                print(
                    f"Feature mapping complete (Step {self.packet_count}), "
                    f"built {len(clusters)} models"
                )
                self.v = clusters
                self.createAD()
            return 1e-6

        elif self.packet_count <= self.FM_grace_period + self.AD_grace_period:
            self.trainAD(x)
            if self.packet_count % 100 == 0:
                pass
            return 1e-6

        else:
            return self.executeAD(x)

    def trainAD(self, x):
        S_l1 = np.zeros(len(self.ensembleLayer))
        for i in range(len(self.ensembleLayer)):
            xi = x[self.v[i]]
            rmse = self.ensembleLayer[i].train(xi)
            if rmse is None or np.isnan(rmse):
                rmse = 1e-6
            S_l1[i] = rmse
        if self.outputLayer is not None:
            self.outputLayer.train(S_l1)

    def executeAD(self, x):
        S_l1 = np.zeros(len(self.ensembleLayer))
        for i in range(len(self.ensembleLayer)):
            xi = x[self.v[i]]
            S_l1[i] = self.ensembleLayer[i].execute(xi)
        if self.outputLayer is None:
            return np.max(S_l1)
        return self.outputLayer.execute(S_l1)

    def createAD(self):
        if self.detector_backend in {
            "transformer",
            "transformer_tailreg",
            "transformer_mae_v1",
            "transformer_mae_tailreg_v1",
            "transformer_mae_latent_contrastive_v1",
            "transformer_uncertainty_v1",
            "transformer_latent_contrastive_v1",
            "transformer_latent_contrastive_compact_v2",
            "transformer_covariance_regularized_v1",
            "transformer_covariance_regularized_v2",
        }:
            class Params:
                def __init__(
                    self,
                    n_visible,
                    learning_rate,
                    hidden_ratio,
                    mae_enabled=False,
                    mae_mask_ratio=0.4,
                    tailreg_enabled=False,
                    tailreg_lambda=0.1,
                    tailreg_k=2.0,
                    tailreg_warmup=512,
                    tailreg_ema_alpha=0.01,
                    uncertainty_enabled=False,
                    uncertainty_logvar_min=-8.0,
                    uncertainty_logvar_max=8.0,
                    uncertainty_score_mode="combined_nll",
                    latent_contrastive_enabled=False,
                    latent_contrastive_mode="v1",
                    latent_margin=1.0,
                    latent_lambda=0.1,
                    latent_compact_enabled=False,
                    latent_lambda_compact=0.0,
                    latent_covreg_enabled=False,
                    latent_covreg_v2_enabled=False,
                    latent_lambda_var=0.0,
                    latent_lambda_corr=0.0,
                    latent_var_min=0.2,
                    latent_var_max=2.0,
                    latent_covreg_buffer_size=64,
                    latent_covreg_use_layernorm=True,
                    latent_covreg_ema_momentum=0.99,
                    latent_covreg_alpha_scale=0.1,
                    latent_covreg_lambda_tail=0.1,
                    latent_covreg_lambda_neg=0.5,
                    latent_covreg_lambda_floor=0.01,
                    latent_covreg_tau_mode="mean2std",
                    latent_covreg_tau_k=2.0,
                    latent_covreg_margin_neg=1.0,
                    latent_covreg_var_floor=1e-3,
                    latent_center_ema_alpha=0.01,
                    latent_warmup_steps=0,
                    latent_pooling="mean",
                    latent_neg_prob_swap=0.0,
                    latent_neg_prob_permute=0.4,
                    latent_neg_prob_spike=0.3,
                    latent_neg_prob_replace=0.3,
                ):
                    self.n_visible = n_visible
                    self.learning_rate = learning_rate
                    self.hidden_ratio = hidden_ratio
                    self.mae_enabled = mae_enabled
                    self.mae_mask_ratio = mae_mask_ratio
                    self.tailreg_enabled = tailreg_enabled
                    self.tailreg_lambda = tailreg_lambda
                    self.tailreg_k = tailreg_k
                    self.tailreg_warmup = tailreg_warmup
                    self.tailreg_ema_alpha = tailreg_ema_alpha
                    self.uncertainty_enabled = uncertainty_enabled
                    self.uncertainty_logvar_min = uncertainty_logvar_min
                    self.uncertainty_logvar_max = uncertainty_logvar_max
                    self.uncertainty_score_mode = uncertainty_score_mode
                    self.latent_contrastive_enabled = latent_contrastive_enabled
                    self.latent_contrastive_mode = latent_contrastive_mode
                    self.latent_margin = latent_margin
                    self.latent_lambda = latent_lambda
                    self.latent_compact_enabled = latent_compact_enabled
                    self.latent_lambda_compact = latent_lambda_compact
                    self.latent_covreg_enabled = latent_covreg_enabled
                    self.latent_covreg_v2_enabled = latent_covreg_v2_enabled
                    self.latent_lambda_var = latent_lambda_var
                    self.latent_lambda_corr = latent_lambda_corr
                    self.latent_var_min = latent_var_min
                    self.latent_var_max = latent_var_max
                    self.latent_covreg_buffer_size = latent_covreg_buffer_size
                    self.latent_covreg_use_layernorm = latent_covreg_use_layernorm
                    self.latent_covreg_ema_momentum = latent_covreg_ema_momentum
                    self.latent_covreg_alpha_scale = latent_covreg_alpha_scale
                    self.latent_covreg_lambda_tail = latent_covreg_lambda_tail
                    self.latent_covreg_lambda_neg = latent_covreg_lambda_neg
                    self.latent_covreg_lambda_floor = latent_covreg_lambda_floor
                    self.latent_covreg_tau_mode = latent_covreg_tau_mode
                    self.latent_covreg_tau_k = latent_covreg_tau_k
                    self.latent_covreg_margin_neg = latent_covreg_margin_neg
                    self.latent_covreg_var_floor = latent_covreg_var_floor
                    self.latent_center_ema_alpha = latent_center_ema_alpha
                    self.latent_warmup_steps = latent_warmup_steps
                    self.latent_pooling = latent_pooling
                    self.latent_neg_prob_swap = latent_neg_prob_swap
                    self.latent_neg_prob_permute = latent_neg_prob_permute
                    self.latent_neg_prob_spike = latent_neg_prob_spike
                    self.latent_neg_prob_replace = latent_neg_prob_replace

            tailreg_enabled = self.detector_backend in {"transformer_tailreg", "transformer_mae_tailreg_v1"}
            mae_enabled = self.detector_backend in {
                "transformer_mae_v1",
                "transformer_mae_tailreg_v1",
                "transformer_mae_latent_contrastive_v1",
            }
            uncertainty_enabled = self.detector_backend in {"transformer_uncertainty_v1"}
            latent_contrastive_enabled = self.detector_backend in {
                "transformer_mae_latent_contrastive_v1",
                "transformer_latent_contrastive_v1",
                "transformer_latent_contrastive_compact_v2",
                "transformer_covariance_regularized_v1",
                "transformer_covariance_regularized_v2",
            }
            latent_compact_enabled = self.detector_backend in {"transformer_latent_contrastive_compact_v2"}
            latent_covreg_enabled = self.detector_backend in {"transformer_covariance_regularized_v1", "transformer_covariance_regularized_v2"}
            latent_covreg_v2_enabled = self.detector_backend in {"transformer_covariance_regularized_v2"}
            if latent_compact_enabled:
                latent_mode = str(self.latent_contrastive_mode).lower()
                if latent_mode not in {"compact_v2", "compact_v3"}:
                    latent_mode = "compact_v2"
            elif latent_covreg_enabled:
                latent_mode = "covreg_v2" if latent_covreg_v2_enabled else "covreg_v1"
            else:
                latent_mode = str(self.latent_contrastive_mode)

            for i in range(len(self.v)):
                params = Params(
                    n_visible=len(self.v[i]),
                    learning_rate=self.learning_rate,
                    hidden_ratio=self.hidden_ratio,
                    mae_enabled=mae_enabled,
                    mae_mask_ratio=self.mae_mask_ratio,
                    tailreg_enabled=tailreg_enabled,
                    tailreg_lambda=self.tailreg_lambda,
                    tailreg_k=self.tailreg_k,
                    tailreg_warmup=self.tailreg_warmup,
                    tailreg_ema_alpha=self.tailreg_ema_alpha,
                    uncertainty_enabled=uncertainty_enabled,
                    uncertainty_logvar_min=self.uncertainty_logvar_min,
                    uncertainty_logvar_max=self.uncertainty_logvar_max,
                    uncertainty_score_mode=self.uncertainty_score_mode,
                    latent_contrastive_enabled=latent_contrastive_enabled,
                    latent_contrastive_mode=latent_mode,
                    latent_margin=self.latent_margin,
                    latent_lambda=self.latent_lambda,
                    latent_compact_enabled=latent_compact_enabled,
                    latent_lambda_compact=self.latent_lambda_compact,
                    latent_covreg_enabled=latent_covreg_enabled,
                    latent_covreg_v2_enabled=latent_covreg_v2_enabled,
                    latent_lambda_var=self.latent_lambda_var,
                    latent_lambda_corr=self.latent_lambda_corr,
                    latent_var_min=self.latent_var_min,
                    latent_var_max=self.latent_var_max,
                    latent_covreg_buffer_size=self.latent_covreg_buffer_size,
                    latent_covreg_use_layernorm=self.latent_covreg_use_layernorm,
                    latent_covreg_ema_momentum=self.latent_covreg_ema_momentum,
                    latent_covreg_alpha_scale=self.latent_covreg_alpha_scale,
                    latent_covreg_lambda_tail=self.latent_covreg_lambda_tail,
                    latent_covreg_lambda_neg=self.latent_covreg_lambda_neg,
                    latent_covreg_lambda_floor=self.latent_covreg_lambda_floor,
                    latent_covreg_tau_mode=self.latent_covreg_tau_mode,
                    latent_covreg_tau_k=self.latent_covreg_tau_k,
                    latent_covreg_margin_neg=self.latent_covreg_margin_neg,
                    latent_covreg_var_floor=self.latent_covreg_var_floor,
                    latent_center_ema_alpha=self.latent_center_ema_alpha,
                    latent_warmup_steps=self.latent_warmup_steps,
                    latent_pooling=self.latent_pooling,
                    latent_neg_prob_swap=self.latent_neg_prob_swap,
                    latent_neg_prob_permute=self.latent_neg_prob_permute,
                    latent_neg_prob_spike=self.latent_neg_prob_spike,
                    latent_neg_prob_replace=self.latent_neg_prob_replace,
                )
                self.ensembleLayer.append(trans_backend.TransformerDetector(params))
            output_params = Params(
                n_visible=len(self.v),
                learning_rate=self.learning_rate,
                hidden_ratio=self.hidden_ratio,
                mae_enabled=mae_enabled,
                mae_mask_ratio=self.mae_mask_ratio,
                tailreg_enabled=tailreg_enabled,
                tailreg_lambda=self.tailreg_lambda,
                tailreg_k=self.tailreg_k,
                tailreg_warmup=self.tailreg_warmup,
                tailreg_ema_alpha=self.tailreg_ema_alpha,
                uncertainty_enabled=uncertainty_enabled,
                uncertainty_logvar_min=self.uncertainty_logvar_min,
                uncertainty_logvar_max=self.uncertainty_logvar_max,
                uncertainty_score_mode=self.uncertainty_score_mode,
                latent_contrastive_enabled=latent_contrastive_enabled,
                latent_contrastive_mode=latent_mode,
                latent_margin=self.latent_margin,
                latent_lambda=self.latent_lambda,
                latent_compact_enabled=latent_compact_enabled,
                latent_lambda_compact=self.latent_lambda_compact,
                latent_covreg_enabled=latent_covreg_enabled,
                latent_covreg_v2_enabled=latent_covreg_v2_enabled,
                latent_lambda_var=self.latent_lambda_var,
                latent_lambda_corr=self.latent_lambda_corr,
                latent_var_min=self.latent_var_min,
                latent_var_max=self.latent_var_max,
                latent_covreg_buffer_size=self.latent_covreg_buffer_size,
                latent_covreg_use_layernorm=self.latent_covreg_use_layernorm,
                latent_covreg_ema_momentum=self.latent_covreg_ema_momentum,
                latent_covreg_alpha_scale=self.latent_covreg_alpha_scale,
                latent_covreg_lambda_tail=self.latent_covreg_lambda_tail,
                latent_covreg_lambda_neg=self.latent_covreg_lambda_neg,
                latent_covreg_lambda_floor=self.latent_covreg_lambda_floor,
                latent_covreg_tau_mode=self.latent_covreg_tau_mode,
                latent_covreg_tau_k=self.latent_covreg_tau_k,
                latent_covreg_margin_neg=self.latent_covreg_margin_neg,
                latent_covreg_var_floor=self.latent_covreg_var_floor,
                latent_center_ema_alpha=self.latent_center_ema_alpha,
                latent_warmup_steps=self.latent_warmup_steps,
                latent_pooling=self.latent_pooling,
                latent_neg_prob_swap=self.latent_neg_prob_swap,
                latent_neg_prob_permute=self.latent_neg_prob_permute,
                latent_neg_prob_spike=self.latent_neg_prob_spike,
                latent_neg_prob_replace=self.latent_neg_prob_replace,
            )
            self.outputLayer = trans_backend.TransformerDetector(output_params)
        else:
            for i in range(len(self.v)):
                params = da_backend.dA_params(
                    n_visible=len(self.v[i]),
                    lr=self.learning_rate,
                    corruption_level=0.0,
                    gracePeriod=0,
                    hiddenRatio=self.hidden_ratio,
                )
                if self.detector_seed is not None:
                    params.seed = int(self.detector_seed)
                self.ensembleLayer.append(da_backend.dA(params))

            output_params = da_backend.dA_params(
                n_visible=len(self.v),
                lr=self.learning_rate,
                corruption_level=0.0,
                gracePeriod=0,
                hiddenRatio=self.hidden_ratio,
            )
            if self.detector_seed is not None:
                output_params.seed = int(self.detector_seed)
            self.outputLayer = da_backend.dA(output_params)

    def set_uncertainty_score_mode(self, mode):
        mode = str(mode).lower()
        self.uncertainty_score_mode = mode
        for detector in self.ensembleLayer:
            if hasattr(detector, "set_uncertainty_score_mode"):
                detector.set_uncertainty_score_mode(mode)
        if self.outputLayer is not None and hasattr(self.outputLayer, "set_uncertainty_score_mode"):
            self.outputLayer.set_uncertainty_score_mode(mode)

    def get_uncertainty_diagnostics(self):
        if self.outputLayer is None or not hasattr(self.outputLayer, "get_uncertainty_diagnostics"):
            return {
                "backend": self.detector_backend,
                "enabled": False,
            }

        output_diag = self.outputLayer.get_uncertainty_diagnostics()
        ensemble_diags = [
            detector.get_uncertainty_diagnostics()
            for detector in self.ensembleLayer
            if hasattr(detector, "get_uncertainty_diagnostics")
        ]
        all_diags = [output_diag] + ensemble_diags

        def sum_int(key):
            total = 0
            for diag in all_diags:
                value = diag.get(key, 0)
                if value is None:
                    continue
                total += int(value)
            return int(total)

        def finite_extreme(key, fn):
            vals = []
            for diag in all_diags:
                v = diag.get(key, None)
                if v is None:
                    continue
                fv = float(v)
                if np.isfinite(fv):
                    vals.append(fv)
            if not vals:
                return None
            return float(fn(vals))

        return {
            "backend": self.detector_backend,
            "enabled": bool(output_diag.get("enabled", False)),
            "score_mode": output_diag.get("score_mode", self.uncertainty_score_mode),
            "logvar_min_cfg": float(self.uncertainty_logvar_min),
            "logvar_max_cfg": float(self.uncertainty_logvar_max),
            "nan_inf_train_events_total": sum_int("nan_inf_train_events"),
            "nan_inf_exec_events_total": sum_int("nan_inf_exec_events"),
            "logvar_train_min_seen": finite_extreme("logvar_train_min_seen", min),
            "logvar_train_max_seen": finite_extreme("logvar_train_max_seen", max),
            "logvar_exec_min_seen": finite_extreme("logvar_exec_min_seen", min),
            "logvar_exec_max_seen": finite_extreme("logvar_exec_max_seen", max),
            "output_layer": output_diag,
            "ensemble_count": int(len(ensemble_diags)),
        }

    def get_latent_contrastive_diagnostics(self):
        if self.outputLayer is None or not hasattr(self.outputLayer, "get_latent_contrastive_diagnostics"):
            return {
                "backend": self.detector_backend,
                "enabled": False,
            }

        output_diag = self.outputLayer.get_latent_contrastive_diagnostics()
        ensemble_diags = [
            detector.get_latent_contrastive_diagnostics()
            for detector in self.ensembleLayer
            if hasattr(detector, "get_latent_contrastive_diagnostics")
        ]
        all_diags = [output_diag] + ensemble_diags

        def mean_float(key):
            vals = []
            for diag in all_diags:
                v = diag.get(key, None)
                if v is None:
                    continue
                fv = float(v)
                if np.isfinite(fv):
                    vals.append(fv)
            if not vals:
                return None
            return float(np.mean(vals))

        total_counts = {
            "cross_window_swap": 0,
            "permute_block": 0,
            "spike_scale": 0,
            "subvector_replace": 0,
        }
        for diag in all_diags:
            cc = diag.get("neg_type_counts", {})
            if not isinstance(cc, dict):
                continue
            for key in total_counts:
                total_counts[key] += int(cc.get(key, 0))
        total_all = sum(total_counts.values())
        if total_all <= 0:
            ratios = {k: 0.0 for k in total_counts}
        else:
            ratios = {k: float(v / float(total_all)) for k, v in total_counts.items()}

        return {
            "backend": self.detector_backend,
            "enabled": bool(output_diag.get("enabled", False)),
            "mode": output_diag.get("mode", self.latent_contrastive_mode),
            "pooling": output_diag.get("pooling", self.latent_pooling),
            "margin": float(output_diag.get("margin", self.latent_margin)),
            "lambda": float(output_diag.get("lambda", self.latent_lambda)),
            "compact_enabled": bool(output_diag.get("compact_enabled", False)),
            "lambda_compact": float(output_diag.get("lambda_compact", self.latent_lambda_compact)),
            "covreg_enabled": bool(output_diag.get("covreg_enabled", False)),
            "lambda_var": float(output_diag.get("lambda_var", self.latent_lambda_var)),
            "lambda_corr": float(output_diag.get("lambda_corr", self.latent_lambda_corr)),
            "var_min": float(output_diag.get("var_min", self.latent_var_min)),
            "var_max": float(output_diag.get("var_max", self.latent_var_max)),
            "covreg_buffer_size": int(output_diag.get("covreg_buffer_size", self.latent_covreg_buffer_size)),
            "covreg_use_layernorm": bool(output_diag.get("covreg_use_layernorm", self.latent_covreg_use_layernorm)),
            "covreg_v2_enabled": bool(output_diag.get("covreg_v2_enabled", False)),
            "covreg_ema_momentum": float(output_diag.get("covreg_ema_momentum", self.latent_covreg_ema_momentum)),
            "covreg_alpha_scale": float(output_diag.get("covreg_alpha_scale", self.latent_covreg_alpha_scale)),
            "covreg_lambda_tail": float(output_diag.get("covreg_lambda_tail", self.latent_covreg_lambda_tail)),
            "covreg_lambda_neg": float(output_diag.get("covreg_lambda_neg", self.latent_covreg_lambda_neg)),
            "covreg_lambda_floor": float(output_diag.get("covreg_lambda_floor", self.latent_covreg_lambda_floor)),
            "covreg_tau_mode": output_diag.get("covreg_tau_mode", self.latent_covreg_tau_mode),
            "covreg_tau_k": float(output_diag.get("covreg_tau_k", self.latent_covreg_tau_k)),
            "covreg_margin_neg": float(output_diag.get("covreg_margin_neg", self.latent_covreg_margin_neg)),
            "covreg_var_floor": float(output_diag.get("covreg_var_floor", self.latent_covreg_var_floor)),
            "center_ema_alpha": float(output_diag.get("center_ema_alpha", self.latent_center_ema_alpha)),
            "warmup_steps": int(output_diag.get("warmup_steps", self.latent_warmup_steps)),
            "neg_probabilities_cfg": {
                "cross_window_swap": float(self.latent_neg_prob_swap),
                "permute_block": float(self.latent_neg_prob_permute),
                "spike_scale": float(self.latent_neg_prob_spike),
                "subvector_replace": float(self.latent_neg_prob_replace),
            },
            "neg_type_counts_total": total_counts,
            "neg_type_ratios_total": ratios,
            "latent_margin_loss_mean": mean_float("latent_margin_loss_last"),
            "latent_compact_loss_mean": mean_float("latent_compact_loss_last"),
            "latent_var_hinge_loss_mean": mean_float("latent_var_hinge_loss_last"),
            "latent_var_upper_loss_mean": mean_float("latent_var_upper_loss_last"),
            "latent_var_lower_loss_mean": mean_float("latent_var_lower_loss_last"),
            "latent_corr_loss_mean": mean_float("latent_corr_loss_last"),
            "latent_var_mean": mean_float("latent_var_mean_last"),
            "latent_var_min_mean": mean_float("latent_var_min_last"),
            "latent_var_max_mean": mean_float("latent_var_max_last"),
            "latent_var_inrange_ratio_mean": mean_float("latent_var_inrange_ratio_last"),
            "latent_corr_offdiag_abs_mean": mean_float("latent_corr_offdiag_abs_mean_last"),
            "latent_corr_offdiag_sq_mean": mean_float("latent_corr_offdiag_sq_mean_last"),
            "latent_covreg_naninf_events_mean": mean_float("latent_covreg_naninf_events"),
            "latent_covreg_v2_updates_mean": mean_float("latent_covreg_v2_updates"),
            "latent_covreg_v2_tail_loss_mean": mean_float("latent_covreg_v2_tail_loss_last"),
            "latent_covreg_v2_neg_loss_mean": mean_float("latent_covreg_v2_neg_loss_last"),
            "latent_covreg_v2_floor_loss_mean": mean_float("latent_covreg_v2_floor_loss_last"),
            "latent_covreg_v2_tau_ref_mean": mean_float("latent_covreg_v2_tau_ref_last"),
            "latent_covreg_v2_pos_score_mean": mean_float("latent_covreg_v2_pos_score_mean_last"),
            "latent_covreg_v2_neg_score_mean": mean_float("latent_covreg_v2_neg_score_mean_last"),
            "latent_covreg_v2_tail_hit_rate_mean": mean_float("latent_covreg_v2_tail_hit_rate_last"),
            "latent_covreg_v2_neg_violation_rate_mean": mean_float("latent_covreg_v2_neg_violation_rate_last"),
            "latent_covreg_v2_alpha_mean": mean_float("latent_covreg_v2_alpha_last"),
            "latent_covreg_v2_trace_mean": mean_float("latent_covreg_v2_trace_last"),
            "latent_covreg_v2_diag_min_mean": mean_float("latent_covreg_v2_diag_min_last"),
            "latent_covreg_v2_diag_median_mean": mean_float("latent_covreg_v2_diag_median_last"),
            "latent_covreg_v2_diag_max_mean": mean_float("latent_covreg_v2_diag_max_last"),
            "latent_covreg_v2_diag_condition_proxy_mean": mean_float("latent_covreg_v2_diag_condition_proxy_last"),
            "latent_covreg_v2_floor_hit_ratio_mean": mean_float("latent_covreg_v2_floor_hit_ratio_last"),
            "latent_covreg_v2_cholesky_failures_mean": mean_float("latent_covreg_v2_cholesky_failures"),
            "latent_covreg_v2_cholesky_total_mean": mean_float("latent_covreg_v2_cholesky_total"),
            "latent_covreg_v2_jitter_mean": mean_float("latent_covreg_v2_jitter_last"),
            "latent_distance_train_mean": mean_float("latent_distance_last"),
            "latent_distance_exec_mean": mean_float("latent_distance_exec_last"),
            "latent_center_distance_train_mean": mean_float("latent_center_distance_last"),
            "latent_center_distance_exec_mean": mean_float("latent_center_distance_exec_last"),
            "warmup_scale_last_mean": mean_float("warmup_scale_last"),
            "lambda_margin_eff_last_mean": mean_float("lambda_margin_eff_last"),
            "lambda_compact_eff_last_mean": mean_float("lambda_compact_eff_last"),
            "lambda_var_eff_last_mean": mean_float("lambda_var_eff_last"),
            "lambda_corr_eff_last_mean": mean_float("lambda_corr_eff_last"),
            "center_l2_last_mean": mean_float("center_l2_last"),
            "center_absmax_last_mean": mean_float("center_absmax_last"),
            "output_layer": output_diag,
            "ensemble_count": int(len(ensemble_diags)),
        }

    def probe_latent_distance(self, x):
        if not self.ensembleLayer:
            return np.nan
        distances = []
        for i in range(len(self.ensembleLayer)):
            detector = self.ensembleLayer[i]
            if not hasattr(detector, "probe_latent_distance"):
                continue
            xi = x[self.v[i]]
            d, _ = detector.probe_latent_distance(xi)
            if np.isfinite(d):
                distances.append(float(d))
        if not distances:
            return np.nan
        return float(np.mean(distances))

    def probe_latent_metrics(self, x):
        if not self.ensembleLayer:
            return {
                "neg_distance": np.nan,
                "center_distance": np.nan,
                "neg_center_distance": np.nan,
                "neg_type_counts": {},
            }
        neg_distances = []
        center_distances = []
        neg_center_distances = []
        neg_type_counts = {}
        for i in range(len(self.ensembleLayer)):
            detector = self.ensembleLayer[i]
            if not hasattr(detector, "probe_latent_metrics"):
                continue
            xi = x[self.v[i]]
            m = detector.probe_latent_metrics(xi)
            if not isinstance(m, dict):
                continue
            nd = m.get("neg_distance", np.nan)
            cd = m.get("center_distance", np.nan)
            ncd = m.get("neg_center_distance", np.nan)
            nt = str(m.get("neg_type", "unknown"))
            if np.isfinite(nd):
                neg_distances.append(float(nd))
            if np.isfinite(cd):
                center_distances.append(float(cd))
            if np.isfinite(ncd):
                neg_center_distances.append(float(ncd))
            neg_type_counts[nt] = int(neg_type_counts.get(nt, 0)) + 1
        return {
            "neg_distance": float(np.mean(neg_distances)) if neg_distances else np.nan,
            "center_distance": float(np.mean(center_distances)) if center_distances else np.nan,
            "neg_center_distance": float(np.mean(neg_center_distances)) if neg_center_distances else np.nan,
            "neg_type_counts": neg_type_counts,
        }

    def probe_negative_score(self, x):
        if not self.ensembleLayer:
            return np.nan, {}
        S_l1 = np.zeros(len(self.ensembleLayer), dtype=np.float64)
        neg_type_counts = {}
        for i in range(len(self.ensembleLayer)):
            detector = self.ensembleLayer[i]
            xi = x[self.v[i]]
            if hasattr(detector, "probe_negative_score"):
                s, nt = detector.probe_negative_score(xi)
            else:
                s = detector.execute(xi)
                nt = "fallback"
            if s is None or not np.isfinite(s):
                s = 1e-6
            S_l1[i] = float(s)
            nt = str(nt)
            neg_type_counts[nt] = int(neg_type_counts.get(nt, 0)) + 1
        if self.outputLayer is None:
            score = float(np.max(S_l1))
        else:
            score = float(self.outputLayer.execute(S_l1))
        if not np.isfinite(score):
            score = 1e-6
        return score, neg_type_counts
