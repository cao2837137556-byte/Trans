import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim


class TransformerModel(nn.Module):
    def __init__(self, d_model=64, nhead=4, num_layers=1, dim_feedforward=128):
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
        self.output_net = nn.Linear(d_model, 1)

    def forward(self, x):
        # x: [batch, num_features, 1]
        x = self.input_net(x)
        x = self.transformer(x)
        return self.output_net(x)


class TransformerDetector:
    def __init__(self, params):
        self.params = params
        self.input_dim = params.n_visible
        self.hidden_ratio = getattr(params, "hidden_ratio", 0.75)
        raw_lr = getattr(params, "learning_rate", 1e-5)
        self.learning_rate = min(raw_lr, 1e-3)
        self.tailreg_enabled = bool(getattr(params, "tailreg_enabled", False))
        self.tailreg_lambda = float(getattr(params, "tailreg_lambda", 0.1))
        self.tailreg_k = float(getattr(params, "tailreg_k", 2.0))
        self.tailreg_warmup = int(getattr(params, "tailreg_warmup", 512))
        self.tailreg_ema_alpha = float(getattr(params, "tailreg_ema_alpha", 0.01))
        self.count = 0
        self.fitted = False
        self.train_step = 0
        self.train_mse_ema = None
        self.train_mse2_ema = None
        self.tail_target_last = None
        self.tail_penalty_last = 0.0
        # Online min-max normalization stats.
        self.norm_min = np.ones(self.input_dim, dtype=np.float64) * np.inf
        self.norm_max = np.ones(self.input_dim, dtype=np.float64) * -np.inf

        nhead = 4
        d_model = max(8, min(128, self.input_dim))
        if d_model % nhead != 0:
            d_model = max(nhead, d_model - (d_model % nhead))
        dim_feedforward = max(32, d_model, int(d_model * 4 * self.hidden_ratio))

        self.model = TransformerModel(
            d_model=d_model,
            nhead=nhead,
            num_layers=1,
            dim_feedforward=dim_feedforward,
        )
        self.criterion = nn.MSELoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)

    def get_state(self):
        return {
            "input_dim": int(self.input_dim),
            "hidden_ratio": float(self.hidden_ratio),
            "learning_rate": float(self.learning_rate),
            "tailreg_enabled": bool(self.tailreg_enabled),
            "tailreg_lambda": float(self.tailreg_lambda),
            "tailreg_k": float(self.tailreg_k),
            "tailreg_warmup": int(self.tailreg_warmup),
            "tailreg_ema_alpha": float(self.tailreg_ema_alpha),
            "count": int(self.count),
            "fitted": bool(self.fitted),
            "train_step": int(self.train_step),
            "train_mse_ema": None if self.train_mse_ema is None else float(self.train_mse_ema),
            "train_mse2_ema": None if self.train_mse2_ema is None else float(self.train_mse2_ema),
            "tail_target_last": None if self.tail_target_last is None else float(self.tail_target_last),
            "tail_penalty_last": float(self.tail_penalty_last),
            "norm_min": self.norm_min.astype(np.float64),
            "norm_max": self.norm_max.astype(np.float64),
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
        }

    def load_state(self, state):
        self.count = int(state.get("count", 0))
        self.fitted = bool(state.get("fitted", False))
        self.tailreg_enabled = bool(state.get("tailreg_enabled", self.tailreg_enabled))
        self.tailreg_lambda = float(state.get("tailreg_lambda", self.tailreg_lambda))
        self.tailreg_k = float(state.get("tailreg_k", self.tailreg_k))
        self.tailreg_warmup = int(state.get("tailreg_warmup", self.tailreg_warmup))
        self.tailreg_ema_alpha = float(state.get("tailreg_ema_alpha", self.tailreg_ema_alpha))
        self.train_step = int(state.get("train_step", 0))
        self.train_mse_ema = state.get("train_mse_ema", None)
        self.train_mse2_ema = state.get("train_mse2_ema", None)
        self.tail_target_last = state.get("tail_target_last", None)
        self.tail_penalty_last = float(state.get("tail_penalty_last", 0.0))
        if "norm_min" in state:
            self.norm_min = np.asarray(state["norm_min"], dtype=np.float64)
        if "norm_max" in state:
            self.norm_max = np.asarray(state["norm_max"], dtype=np.float64)
        if "model_state_dict" in state:
            self.model.load_state_dict(state["model_state_dict"])
        if "optimizer_state_dict" in state:
            self.optimizer.load_state_dict(state["optimizer_state_dict"])
        return self

    def _update_minmax(self, x):
        self.norm_max[x > self.norm_max] = x[x > self.norm_max]
        self.norm_min[x < self.norm_min] = x[x < self.norm_min]

    def preprocess(self, x, update_stats=False):
        # Train updates min/max; execute only normalizes with frozen stats.
        x = np.asarray(x, dtype=np.float64)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        if update_stats:
            self._update_minmax(x)
            self.fitted = True
        elif not self.fitted:
            return np.zeros_like(x)
        denom = self.norm_max - self.norm_min + 1e-16
        x = (x - self.norm_min) / denom
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        return x

    def train(self, x):
        x = self.preprocess(x, update_stats=True)
        input_tensor = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)
        target = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)

        self.optimizer.zero_grad()
        self.model.train()
        output = self.model(input_tensor)
        recon_loss = self.criterion(output, target)
        total_loss = recon_loss
        tail_penalty = recon_loss.new_tensor(0.0)
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
            tail_excess = torch.relu(recon_loss - recon_loss.new_tensor(tail_target))
            tail_penalty = tail_excess * tail_excess
            total_loss = recon_loss + self.tailreg_lambda * tail_penalty

        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        mse_value = float(recon_loss.detach().item())
        if self.train_mse_ema is None or self.train_mse2_ema is None:
            self.train_mse_ema = mse_value
            self.train_mse2_ema = mse_value * mse_value
        else:
            alpha = self.tailreg_ema_alpha
            self.train_mse_ema = (1.0 - alpha) * float(self.train_mse_ema) + alpha * mse_value
            self.train_mse2_ema = (1.0 - alpha) * float(self.train_mse2_ema) + alpha * (mse_value * mse_value)
        self.train_step += 1
        self.tail_penalty_last = float(tail_penalty.detach().item())

        rmse = float(np.sqrt(mse_value))
        if np.isnan(rmse):
            return 1e-6
        return rmse + 1e-6

    def execute(self, x):
        self.count += 1
        x = self.preprocess(x, update_stats=False)

        self.model.eval()
        with torch.no_grad():
            input_tensor = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)
            output = self.model(input_tensor)
            target = torch.tensor(x, dtype=torch.float32).view(1, self.input_dim, 1)

            loss = self.criterion(output, target)
            rmse = torch.sqrt(loss).item()

            if self.count % 100 == 0 and np.isnan(rmse):
                print("NaN detected in RMSE")

            if np.isnan(rmse):
                return 1e-6

            return rmse + 1e-6
