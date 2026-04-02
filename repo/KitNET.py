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
        elif name in {"da", "ae", "autoencoder"}:
            self.detector_backend = "da"
        else:
            raise ValueError(f"Unsupported detector_backend: {detector_backend}")
        self.detector_seed = detector_seed
        self.tailreg_lambda = float(tailreg_lambda)
        self.tailreg_k = float(tailreg_k)
        self.tailreg_warmup = int(tailreg_warmup)
        self.tailreg_ema_alpha = float(tailreg_ema_alpha)
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
        if self.detector_backend in {"transformer", "transformer_tailreg"}:
            class Params:
                def __init__(
                    self,
                    n_visible,
                    learning_rate,
                    hidden_ratio,
                    tailreg_enabled=False,
                    tailreg_lambda=0.1,
                    tailreg_k=2.0,
                    tailreg_warmup=512,
                    tailreg_ema_alpha=0.01,
                ):
                    self.n_visible = n_visible
                    self.learning_rate = learning_rate
                    self.hidden_ratio = hidden_ratio
                    self.tailreg_enabled = tailreg_enabled
                    self.tailreg_lambda = tailreg_lambda
                    self.tailreg_k = tailreg_k
                    self.tailreg_warmup = tailreg_warmup
                    self.tailreg_ema_alpha = tailreg_ema_alpha

            tailreg_enabled = self.detector_backend == "transformer_tailreg"

            for i in range(len(self.v)):
                params = Params(
                    n_visible=len(self.v[i]),
                    learning_rate=self.learning_rate,
                    hidden_ratio=self.hidden_ratio,
                    tailreg_enabled=tailreg_enabled,
                    tailreg_lambda=self.tailreg_lambda,
                    tailreg_k=self.tailreg_k,
                    tailreg_warmup=self.tailreg_warmup,
                    tailreg_ema_alpha=self.tailreg_ema_alpha,
                )
                self.ensembleLayer.append(trans_backend.TransformerDetector(params))
            output_params = Params(
                n_visible=len(self.v),
                learning_rate=self.learning_rate,
                hidden_ratio=self.hidden_ratio,
                tailreg_enabled=tailreg_enabled,
                tailreg_lambda=self.tailreg_lambda,
                tailreg_k=self.tailreg_k,
                tailreg_warmup=self.tailreg_warmup,
                tailreg_ema_alpha=self.tailreg_ema_alpha,
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
