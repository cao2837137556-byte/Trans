"""CKBY: DROCC local training on the frozen 51-D feature snapshot (seed 27).

Implements the FROZEN prereg
(runs/mainline_docs/ckby_drocc_record_capacity_baseline_preregistered_20260807.md)
section 2.1/2.2 exactly: a line-by-line reimplementation of the official
microsoft/EdgeML DROCCTrainer (pytorch/edgeml_pytorch/trainer/drocc_trainer.py,
master, verified 2026-08-07) without the edgeml dependency.

Benign-only: trains on the 14,013 LEGAL benign fit rows only.  No attack or
held-OOD data touches training, checkpoint selection, or operating points.
Report pools are never read by this script.

Segmented execution: --start-epoch/--end-epoch with a checkpoint file carries
model/optimizer/RNG state across process invocations so a long CPU run can be
split into shell-friendly segments; the result is identical to one continuous
run (the DataLoader shuffle generator state is persisted and restored).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

SEED = 27
INPUT_DIM = 51
HIDDEN_DIM = 128          # official main_tabular.py MLP hidden dim
LR = 1e-3                 # official Adam initial lr
LAMDA = 1.0               # official tabular default adversarial weight
GAMMA = 2.0               # official projection outer-ring multiplier
RADIUS = 7.0              # frozen rule: r ~= sqrt(input_dim) = sqrt(51) ~= 7.14 -> 7
ASCENT_STEP_SIZE = 0.001  # official default
ASCENT_NUM_STEPS = 50     # official default
ONLY_CE_EPOCHS = 50       # official default
TOTAL_EPOCHS = 200        # official tabular setting
BATCH_SIZE = 256          # official tabular setting
FIT_BENIGN_ROWS = 14_013
SELECT_BENIGN_ROWS = 7_000


class MLP(torch.nn.Module):
    """Official main_tabular.py MLP: Linear(d,128) -> ReLU -> Linear(128,1)."""

    def __init__(self, input_dim: int = INPUT_DIM, hidden_dim: int = HIDDEN_DIM):
        super().__init__()
        self.fc1 = torch.nn.Linear(input_dim, hidden_dim)
        self.fc2 = torch.nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc2(F.relu(self.fc1(x)))


def adjust_learning_rate(epoch, total_epochs, only_ce_epochs, learning_rate, optimizer):
    """Official main_tabular.py piecewise schedule (epoch-shifted by only_ce)."""
    # We don't want to consider the only-ce-based epochs for the lr scheduler.
    epoch = epoch - only_ce_epochs
    drocc_epochs = total_epochs - only_ce_epochs
    lr = learning_rate * 0.001
    if epoch <= 0.90 * drocc_epochs:
        lr = learning_rate * 0.01
    if epoch <= 0.60 * drocc_epochs:
        lr = learning_rate * 0.1
    if epoch <= 0.30 * drocc_epochs:
        lr = learning_rate
    for group in optimizer.param_groups:
        group["lr"] = lr


def one_class_adv_loss(model, x_train_data, radius, gamma, ascent_step_size, ascent_num_steps):
    """Line-by-line port of official DROCCTrainer.one_class_adv_loss."""
    batch_size = len(x_train_data)
    # 1) sample initial points at random around the positive training points
    x_adv = torch.randn(x_train_data.shape).detach().requires_grad_()
    x_adv_sampled = x_adv + x_train_data

    for step in range(ascent_num_steps):
        with torch.enable_grad():
            new_targets = torch.zeros(batch_size, 1)
            new_targets = torch.squeeze(new_targets)
            new_targets = new_targets.to(torch.float)

            logits = model(x_adv_sampled)
            logits = torch.squeeze(logits, dim=1)
            new_loss = F.binary_cross_entropy_with_logits(logits, new_targets)

            grad = torch.autograd.grad(new_loss, [x_adv_sampled])[0]
            grad_norm = torch.norm(grad, p=2, dim=tuple(range(1, grad.dim())))
            grad_norm = grad_norm.view(-1, *[1] * (grad.dim() - 1))
            # Numerical guard (documented deviation, no algorithm change): on
            # float32-saturated points the official 0/0 division yields NaN and
            # poisons the weights.  +1e-12 leaves every non-degenerate point
            # bit-identical and keeps zero-gradient points stationary.
            grad_normalized = grad / (grad_norm + 1e-12)
            with torch.no_grad():
                x_adv_sampled.add_(ascent_step_size * grad_normalized)

            if (step + 1) % 10 == 0:
                # project onto the annulus N_i(r): radius <= ||h|| <= gamma*radius
                h = x_adv_sampled - x_train_data
                norm_h = torch.sqrt(torch.sum(h**2, dim=tuple(range(1, h.dim()))))
                alpha = torch.clamp(norm_h, radius, gamma * radius)
                proj = (alpha / (norm_h + 1e-12)).view(-1, *[1] * (h.dim() - 1))
                h = proj * h
                x_adv_sampled = x_train_data + h

    adv_pred = model(x_adv_sampled)
    adv_pred = torch.squeeze(adv_pred, dim=1)
    adv_loss = F.binary_cross_entropy_with_logits(adv_pred, new_targets * 0)
    return adv_loss


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def main() -> None:
    started = time.time()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start-epoch", type=int, default=0)
    parser.add_argument("--end-epoch", type=int, default=TOTAL_EPOCHS)
    args = parser.parse_args()
    if not (0 <= args.start_epoch < args.end_epoch <= TOTAL_EPOCHS):
        raise RuntimeError("invalid epoch segment")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ckpt_path = out / "ckby_drocc_train_checkpoint.pt"

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    with np.load(Path(args.snapshot), allow_pickle=False) as snap:
        uids = snap["uid"].astype(str)
        x_all = snap["x"]
        label = snap["label"]
        source = snap["source"].astype(str)
        recorded_index = snap["recorded_index"]
        global_pool = snap["global_pool"].astype(str)

    snapshot_sha = sha256_file(Path(args.snapshot))

    fit_mask = (global_pool == "fit") & (label == 0)
    if int(fit_mask.sum()) != FIT_BENIGN_ROWS:
        raise RuntimeError(f"benign fit cardinality drift: {int(fit_mask.sum())}")
    select_mask = global_pool == "select_benign"
    if int(select_mask.sum()) != SELECT_BENIGN_ROWS:
        raise RuntimeError(f"benign select cardinality drift: {int(select_mask.sum())}")

    fit_x = x_all[fit_mask].astype(np.float32)
    fit_source = source[fit_mask]
    fit_index = recorded_index[fit_mask]

    # --- Per-source temporal tail 10% validation split (FROZEN section 2.2).
    # Rule: within each source, order by recorded_index (temporal order within
    # the capture); val_n = max(1, floor(0.1 * n)); the tail val_n rows form the
    # validation set, the rest train.  Every source uses this rule; no source
    # needed the hash fallback (recorded_index exists for all rows).
    val_mask = np.zeros(len(fit_x), dtype=bool)
    split_audit = []
    for src in sorted(set(fit_source.tolist())):
        rows = np.where(fit_source == src)[0]
        order = rows[np.argsort(fit_index[rows], kind="stable")]
        val_n = max(1, int(np.floor(0.1 * len(order))))
        val_rows = order[-val_n:]
        val_mask[val_rows] = True
        split_audit.append(
            {"source": src, "rows": int(len(order)), "val_rows": int(val_n),
             "rule": "temporal_tail_by_recorded_index"}
        )
    train_x = fit_x[~val_mask]
    val_x = fit_x[val_mask]

    # --- Fit-only standardization over ALL 14,013 benign fit rows (train+val),
    # matching the official load_data convention; std floored at 1e-4.
    mean = fit_x.mean(axis=0)
    std = fit_x.std(axis=0) + 1e-4

    def norm(a: np.ndarray) -> torch.Tensor:
        return torch.from_numpy(((a - mean) / std).astype(np.float32))

    train_t = norm(train_x)
    val_t = norm(val_x)
    train_labels = torch.ones(len(train_t), dtype=torch.float32)
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        TensorDataset(train_t, train_labels),
        batch_size=BATCH_SIZE,
        shuffle=True,
        generator=generator,
    )

    model = MLP()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    best_val = float("inf")
    best_epoch = -1
    best_state = None
    log_rows: list[dict] = []
    wall_accum = 0.0

    if args.start_epoch > 0:
        if not ckpt_path.is_file():
            raise RuntimeError(f"missing segment checkpoint: {ckpt_path}")
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        if int(ck["completed_epoch"]) != args.start_epoch - 1:
            raise RuntimeError(
                f"checkpoint at epoch {ck['completed_epoch']}, "
                f"cannot start segment at {args.start_epoch}"
            )
        model.load_state_dict(ck["model_state"])
        optimizer.load_state_dict(ck["optimizer_state"])
        generator.set_state(ck["generator_state"])
        torch.set_rng_state(ck["torch_rng_state"])
        best_val = float(ck["best_val"])
        best_epoch = int(ck["best_epoch"])
        best_state = ck["best_state"]
        log_rows = ck["log_rows"]
        wall_accum = float(ck["wall_accum"])

    for epoch in range(args.start_epoch, args.end_epoch):
        model.train()
        adjust_learning_rate(epoch, TOTAL_EPOCHS, ONLY_CE_EPOCHS, LR, optimizer)
        ce_sum = 0.0
        adv_sum = 0.0
        n_batches = 0
        for data, target in train_loader:
            n_batches += 1
            optimizer.zero_grad()
            logits = torch.squeeze(model(data), dim=1)
            ce_loss = F.binary_cross_entropy_with_logits(logits, target)
            ce_sum += float(ce_loss)
            if epoch >= ONLY_CE_EPOCHS:
                pos = data[target == 1]
                adv_loss = one_class_adv_loss(
                    model, pos, RADIUS, GAMMA, ASCENT_STEP_SIZE, ASCENT_NUM_STEPS
                )
                adv_sum += float(adv_loss)
                loss = ce_loss + adv_loss * LAMDA
            else:
                loss = ce_loss
            loss.backward()
            optimizer.step()

        # Benign-only validation: mean BCE of normal points (label = 1).
        model.eval()
        with torch.no_grad():
            val_logits = torch.squeeze(model(val_t), dim=1)
            val_ce = float(
                F.binary_cross_entropy_with_logits(
                    val_logits, torch.ones(len(val_t), dtype=torch.float32)
                )
            )
        if val_ce < best_val:  # ties keep the earlier epoch
            best_val = val_ce
            best_epoch = epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        log_rows.append(
            {"epoch": epoch, "ce_loss": ce_sum / n_batches,
             "adv_loss": adv_sum / n_batches, "val_ce": val_ce,
             "lr": optimizer.param_groups[0]["lr"]}
        )
        wall_now = wall_accum + (time.time() - started)
        tmp = ckpt_path.with_suffix(".tmp")
        torch.save(
            {
                "completed_epoch": epoch,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "generator_state": generator.get_state(),
                "torch_rng_state": torch.get_rng_state(),
                "best_val": best_val,
                "best_epoch": best_epoch,
                "best_state": best_state,
                "log_rows": log_rows,
                "wall_accum": wall_now,
            },
            tmp,
        )
        tmp.replace(ckpt_path)
        print(
            f"epoch={epoch} ce={ce_sum / n_batches:.6f} "
            f"adv={adv_sum / n_batches:.6f} val_ce={val_ce:.6f} "
            f"best={best_val:.6f}@{best_epoch} wall={wall_now:.1f}s",
            flush=True,
        )

    wall_total = wall_accum + (time.time() - started)
    if args.end_epoch < TOTAL_EPOCHS:
        print(f"CKBY_SEGMENT_DONE epochs={args.start_epoch}-{args.end_epoch - 1} "
              f"wall={wall_total:.1f}s")
        return

    # --- Finalize (runs once, at the last segment).
    model.load_state_dict(best_state)
    model_path = out / "ckby_drocc_model_seed27.pt"
    torch.save(model.state_dict(), model_path)
    model_sha = sha256_file(model_path)

    # Operating points from the 7,000 LEGAL benign select rows only.
    select_t = norm(x_all[select_mask].astype(np.float32))
    model.eval()
    with torch.no_grad():
        select_scores = torch.squeeze(model(select_t), dim=1).numpy().astype(np.float64)
    if not np.isfinite(select_scores).all():
        raise RuntimeError("nonfinite select score")
    # Alarm rule: score BELOW threshold = alarm.  OP-1 = 1% benign budget
    # (1st percentile), OP-0.1 = 0.1% budget (0.1st percentile).
    op1 = float(np.percentile(select_scores, 1.0))
    op01 = float(np.percentile(select_scores, 0.1))
    np.save(out / "ckby_drocc_select_scores_seed27.npy", select_scores)

    with open(out / "ckby_drocc_train_log_seed27.csv", "w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["epoch", "ce_loss", "adv_loss", "val_ce", "lr"]
        )
        writer.writeheader()
        writer.writerows(log_rows)

    run_spec = {
        "issue": "issue27ckby_drocc_local_seed27",
        "prereg": "ckby_drocc_record_capacity_baseline_preregistered_20260807.md",
        "erratum": "ckby_preregistered_erratum_1_feature_snapshot_contract_20260807.md",
        "seed": SEED,
        "snapshot": str(args.snapshot),
        "snapshot_sha256": snapshot_sha,
        "hyperparameters": {
            "input_dim": INPUT_DIM, "hidden_dim": HIDDEN_DIM, "optimizer": "Adam",
            "lr": LR, "lr_schedule": "official epoch-shifted piecewise: full lr for first 30% of adv epochs, then 0.1/0.01/0.001 at 60/90/100%",
            "lamda": LAMDA, "gamma": GAMMA, "radius": RADIUS,
            "ascent_step_size": ASCENT_STEP_SIZE,
            "ascent_num_steps": ASCENT_NUM_STEPS,
            "only_ce_epochs": ONLY_CE_EPOCHS, "total_epochs": TOTAL_EPOCHS,
            "batch_size": BATCH_SIZE,
        },
        "split": {
            "rule": "per-source temporal tail 10% by recorded_index; "
                    "val_n = max(1, floor(0.1*n)); no hash fallback needed",
            "sources": split_audit,
            "train_rows": int(len(train_t)), "val_rows": int(len(val_t)),
        },
        "standardization": {
            "fit_rows": FIT_BENIGN_ROWS, "std_floor": 1e-4,
            "mean_sha256": sha256_array(mean), "std_sha256": sha256_array(std),
        },
        "checkpoint": {
            "rule": "lowest benign validation CE; ties keep earlier epoch",
            "best_epoch": best_epoch, "best_val_ce": best_val,
            "model_sha256": model_sha,
        },
        "operating_points": {
            "alarm_direction": "score < threshold",
            "op1_percentile_1pct": op1, "op01_percentile_0p1pct": op01,
            "select_rows": SELECT_BENIGN_ROWS,
        },
        "wall_seconds": wall_total,
        "status": "CKBY_DROCC_TRAINING_COMPLETE",
    }
    with open(out / "ckby_drocc_run_spec_seed27.json", "w") as handle:
        json.dump(run_spec, handle, indent=2)
    print(json.dumps({k: v for k, v in run_spec.items() if k != "split"},
                     indent=2, default=str))
    print(f"split_sources={len(split_audit)} train={len(train_t)} val={len(val_t)}")


if __name__ == "__main__":
    main()
