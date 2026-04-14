from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc
import frontend100_timescale_tokenizer_v1_3 as tv3

FAMILIES = ["MI_dir", "HH", "HH_jit", "HpHp"]
SCALES = ["5", "3", "1", "0.1", "0.01"]
LONG_SCALE_IDXS = [0, 1, 2]
SHORT_SCALE_IDXS = [3, 4]
SCALE_LOSS_PROFILES = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "short_focus": np.asarray([0.50, 0.50, 0.75, 1.50, 1.75], dtype=np.float32),
}


def parse_header_family_scale(header: str) -> Tuple[str, str]:
    for family in ["MI_dir", "HH_jit", "HH", "HpHp"]:
        prefix = f"{family}_"
        if header.startswith(prefix):
            rest = header[len(prefix) :]
            for scale in SCALES:
                if rest.startswith(f"{scale}_"):
                    return family, scale
    raise ValueError(f"Unrecognized semantic header: {header}")


def build_semantic_token_specs(headers: List[str]) -> Tuple[List[Dict], Dict[str, List[int]], Dict[str, int]]:
    groups: Dict[Tuple[str, str], List[int]] = {(family, scale): [] for scale in SCALES for family in FAMILIES}
    scale_feature_indices: Dict[str, List[int]] = {scale: [] for scale in SCALES}
    family_dims: Dict[str, int] = {}
    token_specs: List[Dict] = []
    for i, header in enumerate(headers):
        family, scale = parse_header_family_scale(header)
        groups[(family, scale)].append(i)
        scale_feature_indices[scale].append(i)
    token_idx = 0
    for scale_idx, scale in enumerate(SCALES):
        for family_idx, family in enumerate(FAMILIES):
            indices = groups[(family, scale)]
            if not indices:
                raise ValueError(f"Missing semantic token for family={family}, scale={scale}")
            dim = len(indices)
            if family not in family_dims:
                family_dims[family] = dim
            elif family_dims[family] != dim:
                raise ValueError(f"Family dimension mismatch for {family}")
            token_specs.append(
                {
                    "token_idx": token_idx,
                    "family": family,
                    "scale": scale,
                    "family_idx": family_idx,
                    "scale_idx": scale_idx,
                    "indices": indices,
                    "dim": dim,
                }
            )
            token_idx += 1
    return token_specs, scale_feature_indices, family_dims


class SemanticTokenAutoencoderBase(nn.Module):
    def __init__(self, token_specs: List[Dict], family_dims: Dict[str, int], input_dim: int, d_model: int = 64):
        super().__init__()
        self.token_specs = token_specs
        self.input_dim = int(input_dim)
        self.num_tokens = int(len(token_specs))
        dims = [int(family_dims[family]) for family in FAMILIES]
        self.family_in_proj = nn.ModuleList([nn.Linear(dim, d_model) for dim in dims])
        self.family_out_proj = nn.ModuleList([nn.Linear(d_model, dim) for dim in dims])
        self.family_emb = nn.Embedding(len(FAMILIES), d_model)
        self.scale_emb = nn.Embedding(len(SCALES), d_model)
        self.pos = nn.Parameter(torch.zeros(1, self.num_tokens, d_model))
        self.norm = nn.LayerNorm(d_model)
        self.register_buffer("family_ids", torch.tensor([spec["family_idx"] for spec in token_specs], dtype=torch.long))
        self.register_buffer("scale_ids", torch.tensor([spec["scale_idx"] for spec in token_specs], dtype=torch.long))

    def _encode_tokens(self, x: torch.Tensor) -> torch.Tensor:
        tokens = []
        for spec in self.token_specs:
            chunk = x[:, spec["indices"]]
            tokens.append(self.family_in_proj[spec["family_idx"]](chunk))
        h = torch.stack(tokens, dim=1)
        h = h + self.family_emb(self.family_ids).unsqueeze(0) + self.scale_emb(self.scale_ids).unsqueeze(0) + self.pos
        return self.norm(h)

    def _decode_flat(self, h: torch.Tensor) -> torch.Tensor:
        out = h.new_zeros((h.size(0), self.input_dim))
        for token_i, spec in enumerate(self.token_specs):
            out[:, spec["indices"]] = self.family_out_proj[spec["family_idx"]](h[:, token_i, :])
        return out


class StructuredFrontendTransformerAE(SemanticTokenAutoencoderBase):
    def __init__(self, token_specs: List[Dict], family_dims: Dict[str, int], input_dim: int, d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__(token_specs=token_specs, family_dims=family_dims, input_dim=input_dim, d_model=d_model)
        enc = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=max(128, d_model * 4),
            dropout=0.0,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(enc, num_layers=int(num_layers))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self._decode_flat(self.encoder(self._encode_tokens(x)))


class StructuredFrontendTokenMLPAE(SemanticTokenAutoencoderBase):
    def __init__(self, token_specs: List[Dict], family_dims: Dict[str, int], input_dim: int, d_model: int = 64, bottleneck: int = 192):
        super().__init__(token_specs=token_specs, family_dims=family_dims, input_dim=input_dim, d_model=d_model)
        flat_dim = self.num_tokens * d_model
        bottleneck = int(min(max(64, bottleneck), max(128, flat_dim)))
        self.bottleneck = nn.Sequential(
            nn.LayerNorm(flat_dim),
            nn.Linear(flat_dim, bottleneck),
            nn.GELU(),
            nn.Linear(bottleneck, flat_dim),
            nn.GELU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self._encode_tokens(x)
        b, s, d = h.shape
        h = self.bottleneck(h.reshape(b, s * d)).reshape(b, s, d)
        return self._decode_flat(h)


def _scale_mse(err: torch.Tensor, scale_feature_indices: Dict[str, List[int]]) -> torch.Tensor:
    return torch.stack([err[:, scale_feature_indices[scale]].mean(dim=1) for scale in SCALES], dim=1)


def train_model(model: nn.Module, x_train: np.ndarray, epochs: int, batch_size: int, lr: float, device: str, scale_feature_indices: Dict[str, List[int]], scale_weights: np.ndarray) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    weights = torch.as_tensor(scale_weights, dtype=torch.float32, device=device).view(1, -1)
    weights = weights / torch.clamp(weights.mean(), min=1e-6)
    ds = TensorDataset(torch.from_numpy(x_train.astype(np.float32)))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    losses: List[float] = []
    model.train()
    for _ in range(int(epochs)):
        total = 0.0
        count = 0
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            out = model(xb)
            err = (out - xb) ** 2
            loss = torch.mean(_scale_mse(err, scale_feature_indices) * weights)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        losses.append(total / max(1, count))
    return losses


def score_model_per_scale(model: nn.Module, x: np.ndarray, batch_size: int, device: str, scale_feature_indices: Dict[str, List[int]]) -> np.ndarray:
    model.to(device)
    model.eval()
    out = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            err = (model(xb) - xb) ** 2
            rmse = [torch.sqrt(torch.mean(err[:, scale_feature_indices[scale]], dim=1)) for scale in SCALES]
            out.append(torch.stack(rmse, dim=1).detach().cpu().numpy())
    return np.concatenate(out, axis=0).astype(np.float64)


def aggregate_scale_scores(per_scale: np.ndarray, mode: str, id_mean: np.ndarray | None = None, id_std: np.ndarray | None = None) -> np.ndarray:
    x = np.asarray(per_scale, dtype=np.float64)
    if mode == "short_mean":
        return x[:, SHORT_SCALE_IDXS].mean(axis=1)
    if mode.startswith("z_short_mean_minus_long_mean_a"):
        if id_mean is None or id_std is None:
            raise ValueError(f"{mode} requires id_mean and id_std")
        alpha = float(mode.split("_a", 1)[1])
        z = (x - id_mean.reshape(1, -1)) / np.maximum(id_std.reshape(1, -1), 1e-6)
        return z[:, SHORT_SCALE_IDXS].mean(axis=1) - alpha * z[:, LONG_SCALE_IDXS].mean(axis=1)
    raise ValueError(mode)


def load_reference_rows() -> List[Dict]:
    refs = tv3.load_reference_rows()
    p = WORKTREE_ROOT / "runs" / "frontend100_timescale_tokenizer_v1_3_smoke_2026-04-13" / "timescale_tokenizer_v1_3_results.csv"
    if p.exists():
        df = pd.read_csv(p)
        keep = {
            "timescale_transformer_short_focus_z_short_mean_minus_long_mean_a1.50",
            "timescale_token_mlp_short_focus_z_short_mean_minus_long_mean_a1.50",
        }
        ref = df[df["object_label"].isin(keep)].copy()
        ref["source_mode"] = "reused_timescale_v1_3_reference"
        refs.extend(ref.to_dict("records"))
    return refs


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"] == "fixed_id_q99") & (df["selection_feasible"].astype(bool))].copy()
    plt.figure(figsize=(11.0, 7.0))
    colors = {
        "structured_frontend_transformer_v1": "#1f77b4",
        "structured_frontend_token_mlp_control": "#ff7f0e",
        "flat_ae_100d_control": "#2ca02c",
        "timescale_transformer_v1_3": "#17becf",
        "timescale_token_mlp_control": "#bcbd22",
        "da": "#d62728",
        "transformer": "#7f7f7f",
        "transformer_tailreg": "#9467bd",
        "latent_swap_spike_mix_no_compact": "#8c564b",
    }
    for _, r in fixed.iterrows():
        x = float(r["ood_alarm_ratio_eval"])
        y = float(r["attack_detection_high_purity"])
        fam = str(r["detector_family"])
        plt.scatter(x, y, c=colors.get(fam, "#7f7f7f"), marker="o", s=88)
        plt.text(x + 0.004, y + 0.006, str(r["object_label"]), fontsize=7)
    plt.xlabel("OOD benign alarm ratio (fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Structured semantic-token frontend v1 fixed trade-off")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Frontend100 StructuredFrontend-v1 with 20 semantic tokens (`4 families x 5 scales`), dual family/scale embeddings, and contrast scorers on top of the original 100D source; path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Structured semantic-token frontend v1 for frontend100.")
    ap.add_argument("--run-tag", default=f"frontend100_structured_frontend_v1_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument(
        "--header-path",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master" / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_id_7_6" / "feature_headers.txt",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-samples", type=int, default=8000)
    ap.add_argument("--id-eval-samples", type=int, default=5000)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--num-layers", type=int, default=2)
    ap.add_argument("--nhead", type=int, default=4)
    ap.add_argument("--token-mlp-bottleneck", type=int, default=192)
    ap.add_argument("--flat-hidden-dim", type=int, default=256)
    ap.add_argument("--flat-bottleneck", type=int, default=64)
    ap.add_argument("--smoke-fit-n", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    tv3.set_seed(args.seed)
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "structured_frontend_v1_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    headers = [ln.strip() for ln in args.header_path.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    token_specs, scale_feature_indices, family_dims = build_semantic_token_specs(headers)

    source = args.source_root
    data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    fit_n = int(args.train_samples if args.smoke_fit_n <= 0 else min(args.train_samples, args.smoke_fit_n))
    id_rows_needed = fit_n + args.id_eval_samples
    x_id_src = pd.read_csv(data / "id_source_100.csv", header=None, nrows=id_rows_needed).to_numpy(np.float32)
    x_ood_src = pd.read_csv(data / "ood_benign_source_100.csv", header=None).to_numpy(np.float32)
    attack_csv = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv"
    x_attack_src = pd.read_csv(attack_csv, header=None).to_numpy(np.float32)
    stage2 = tv3.load_json(source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    stage2_idx = resc.build_stage2_indices(stage2)

    x_train = x_id_src[:fit_n]
    x_id = x_id_src[fit_n : fit_n + args.id_eval_samples]
    mean = x_train.mean(axis=0)
    std = np.maximum(x_train.std(axis=0), 1e-6)
    z_train = tv3.standardize_flat(x_train, mean, std)
    z_id = tv3.standardize_flat(x_id, mean, std)
    z_ood = tv3.standardize_flat(x_ood_src, mean, std)
    z_attack = tv3.standardize_flat(x_attack_src, mean, std)
    high = stage2_idx["high"]
    mixed = stage2_idx["mixed"]

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    rows.extend(load_reference_rows())
    loss_profiles = [
        ("uniform", SCALE_LOSS_PROFILES["uniform"], "uniform scale reconstruction loss"),
        ("short_focus", SCALE_LOSS_PROFILES["short_focus"], "short-focused scale reconstruction loss"),
    ]
    score_modes = [
        ("short_mean", "mean over short scales 0.1/0.01"),
        ("z_short_mean_minus_long_mean_a1.25", "ID-z normalized short mean minus 1.25 x long mean"),
        ("z_short_mean_minus_long_mean_a1.50", "ID-z normalized short mean minus 1.50 x long mean"),
    ]
    score_bank: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    model_builders = [
        ("structured_frontend_transformer_v1", lambda: StructuredFrontendTransformerAE(token_specs, family_dims, z_train.shape[1], d_model=args.d_model, nhead=args.nhead, num_layers=args.num_layers)),
        ("structured_frontend_token_mlp_control", lambda: StructuredFrontendTokenMLPAE(token_specs, family_dims, z_train.shape[1], d_model=args.d_model, bottleneck=args.token_mlp_bottleneck)),
        ("flat_ae_100d_control", lambda: tv3.FlatAE(input_dim=z_train.shape[1], hidden_dim=args.flat_hidden_dim, bottleneck=args.flat_bottleneck)),
    ]

    for loss_name, scale_weights, loss_desc in loss_profiles:
        for detector_family, builder in model_builders:
            print(f"[fit] {detector_family} loss={loss_name}", flush=True)
            model = builder()
            losses = train_model(model, z_train, args.epochs, args.batch_size, args.lr, args.device, scale_feature_indices, scale_weights)
            id_scales = score_model_per_scale(model, z_id, args.batch_size, args.device, scale_feature_indices)
            ood_scales = score_model_per_scale(model, z_ood, args.batch_size, args.device, scale_feature_indices)
            attack_scales = score_model_per_scale(model, z_attack, args.batch_size, args.device, scale_feature_indices)
            id_mean = id_scales.mean(axis=0)
            id_std = np.maximum(id_scales.std(axis=0), 1e-6)
            for mode, mode_desc in score_modes:
                short_name = detector_family.replace("structured_frontend_", "").replace("_control", "")
                obj = f"{short_name}_{loss_name}_{mode}"
                sid = aggregate_scale_scores(id_scales, mode, id_mean=id_mean, id_std=id_std)
                sood = aggregate_scale_scores(ood_scales, mode, id_mean=id_mean, id_std=id_std)
                satt = aggregate_scale_scores(attack_scales, mode, id_mean=id_mean, id_std=id_std)
                score_bank[obj] = (sid, sood[args.calibration_budget :], satt[high])
                rows.extend(
                    tv3.eval_scores(
                        object_label=obj,
                        detector_family=detector_family,
                        score_label=mode,
                        seed=args.seed,
                        score_id=sid,
                        score_ood=sood,
                        score_attack=satt,
                        high_idx=high,
                        mixed_idx=mixed,
                        budget=args.calibration_budget,
                        scan_points=args.scan_points,
                        extra={
                            "source_mode": "computed_now",
                            "loss_profile": loss_name,
                            "loss_profile_desc": loss_desc,
                            "scale_weights": ",".join(f"{float(v):.2f}" for v in scale_weights),
                            "num_tokens": len(token_specs) if detector_family != "flat_ae_100d_control" else 1,
                            "family_dims": json.dumps(family_dims, ensure_ascii=False),
                            "score_mode_desc": mode_desc,
                        },
                    )
                )
            diagnostics.append(
                {
                    "object_label": f"{detector_family}_{loss_name}",
                    "detector_family": detector_family,
                    "loss_profile": loss_name,
                    "scale_weights": ",".join(f"{float(v):.2f}" for v in scale_weights),
                    "train_loss_start": float(losses[0]),
                    "train_loss_end": float(losses[-1]),
                    "train_loss_min": float(np.min(losses)),
                    "num_tokens": len(token_specs) if detector_family != "flat_ae_100d_control" else 1,
                    "family_dims": json.dumps(family_dims, ensure_ascii=False),
                }
            )

    df = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "structured_frontend_v1_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag.to_csv(out / "structured_frontend_v1_diagnostics.csv", index=False)

    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & (df["selection_feasible"].astype(bool))].copy()
    ours = fixed[
        fixed["detector_family"].isin(
            ["structured_frontend_transformer_v1", "structured_frontend_token_mlp_control", "flat_ae_100d_control"]
        )
    ].copy()
    results_md = "# Structured Frontend v1 Results\n\n"
    results_md += tv3.md_table(
        fixed[
            [
                "object_label",
                "detector_family",
                "loss_profile",
                "score_label",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
            ]
        ].sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).fillna("")
    )
    (out / "structured_frontend_v1_results.md").write_text(results_md, encoding="utf-8")

    plot_tradeoff(df, plot_dir / "fixed_tradeoff_structured_frontend_v1.png")
    if not ours.empty:
        best = ours.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).iloc[0]
        sid, sood_eval, satt_high = score_bank[str(best["object_label"])]
        tv3.plot_distribution(
            sid,
            sood_eval,
            satt_high,
            float(np.quantile(sid, 0.99)),
            plot_dir / "score_distribution_best_model.png",
            f"{best['object_label']} score distribution (fixed q99)",
        )

    summary = "# Frontend100 Structured Frontend v1 Summary\n\n"
    summary += "- Single-seed minimal experiment on original frontend100.\n"
    summary += "- Reconstruct the same 100D source into `20 semantic tokens = 4 families x 5 scales`, not just `5 x 20` timescale tokens.\n"
    summary += "- Dual embeddings are added: family embedding + scale embedding.\n"
    summary += "- Controls: structured token-MLP and flat 100D AE under the same scale-aware scoring rules.\n"
    summary += "- Scorers are deliberately fixed to the already-validated short-vs-long contrast family.\n\n"
    summary += "## Fixed q99 Results\n\n"
    summary += tv3.md_table(
        fixed[
            [
                "object_label",
                "detector_family",
                "loss_profile",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
            ]
        ].sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).fillna("")
    )
    summary += "\n## Interpretation\n\n"
    if not ours.empty:
        best = ours.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).iloc[0]
        summary += f"- Best structured-frontend point: `{best['object_label']}` with alarm `{best['ood_alarm_ratio_eval']:.4f}` and detection `{best['attack_detection_high_purity']:.4f}`.\n"
    summary += "- Core question: whether semantic purity (`family x scale`) makes Transformer benefit more than the older 5-timescale grouping.\n"
    summary += "- Success criterion: beat the strongest tokenizer-side B-line fixed point without losing the low-alarm property.\n"
    (out / "structured_frontend_v1_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_structured_frontend_v1",
        "run_tag": args.run_tag,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "device": args.device,
        "header_path": str(args.header_path),
        "families": FAMILIES,
        "scales": SCALES,
        "num_tokens": len(token_specs),
        "family_dims": family_dims,
        "score_modes": [m for m, _ in score_modes],
        "loss_profiles": {k: [float(v) for v in vals] for k, vals in SCALE_LOSS_PROFILES.items()},
        "smoke_fit_n": int(args.smoke_fit_n),
        "outputs": {
            "results": str(out / "structured_frontend_v1_results.csv"),
            "diagnostics": str(out / "structured_frontend_v1_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "structured_frontend_v1_config_manifest.json").write_text(json.dumps(tv3.clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(tv3.clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] structured frontend v1 output: {out}", flush=True)


if __name__ == "__main__":
    main()
