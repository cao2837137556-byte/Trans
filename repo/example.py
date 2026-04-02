import numpy as np
import os
import json
from pathlib import Path
import KitNET as kit
import time
import matplotlib.pyplot as plt
from paths import DATA_DIR, OUTPUT_DIR
from csv_input import load_numeric_csv

input_file = DATA_DIR / "my_gold_mirai.csv"
label_file = DATA_DIR / "my_gold_labels.npy"

maxAE = 10
FMgrace = 5000
ADgrace = 95000

print(f"Reading data: {input_file} ...")
try:
    X, load_info = load_numeric_csv(input_file, auto_drop_index_col0=True)
    print(
        "Loaded data. "
        f"Shape {X.shape} raw_dim={load_info['raw_dim']} "
        f"used_dim={load_info['used_dim']} dropped_col0={load_info['dropped_col0']}"
    )
except FileNotFoundError:
    print(f"Missing file: {input_file}")
    raise SystemExit(1)

print(f"Reading labels: {label_file} ...")
try:
    labels = np.load(label_file)
    if len(labels) != len(X):
        print(f"Label length mismatch: labels={len(labels)} data={len(X)}")
        raise SystemExit(1)
except FileNotFoundError:
    print(f"Missing file: {label_file}")
    raise SystemExit(1)

attack_indices = np.where(labels == 1)[0]
attack_start = int(attack_indices[0]) if len(attack_indices) > 0 else None

print("Init KitNET (Transformer)...")
load_ckpt = os.environ.get("KITNET_LOAD_CKPT", "").strip()
if load_ckpt:
    print(f"Loading checkpoint: {load_ckpt}")
    K = kit.KitNET.load_checkpoint(load_ckpt)
else:
    K = kit.KitNET(X.shape[1], maxAE, FMgrace, ADgrace)

print("Running model...")
RMSEs = np.zeros(X.shape[0])
start = time.time()

for i in range(X.shape[0]):
    if i % 10000 == 0:
        print(f"  -> Progress: {i} / {X.shape[0]}")
    RMSEs[i] = K.process(X[i,])

stop = time.time()
print(f"Total time: {stop - start:.2f} s")
save_ckpt = os.environ.get("KITNET_SAVE_CKPT", "").strip()
if save_ckpt:
    ckpt_path = K.save_checkpoint(save_ckpt)
    print(f"Saved checkpoint: {ckpt_path}")

run_tag = os.environ.get("RUN_TAG", "manual")
out_dir = Path("runs") / run_tag
out_dir.mkdir(parents=True, exist_ok=True)

output_file = out_dir / "rmse.npy"
np.save(output_file, RMSEs)
print(f"Saved: {output_file}")
(out_dir / "input_load_info.json").write_text(json.dumps(load_info, indent=2), encoding="utf-8")

exec_start = FMgrace + ADgrace + 1
y_true = labels[exec_start:]
y_score = RMSEs[exec_start:]

try:
    from sklearn.metrics import roc_auc_score, average_precision_score

    roc_auc = roc_auc_score(y_true, y_score)
    pr_auc = average_precision_score(y_true, y_score)
    print(f"ROC-AUC: {roc_auc:.6f}")
    print(f"PR-AUC: {pr_auc:.6f}")
    metrics_lines = [f"ROC-AUC: {roc_auc:.6f}", f"PR-AUC: {pr_auc:.6f}"]
except ImportError:
    print("Missing sklearn. Install with: pip install scikit-learn")
    metrics_lines = ["Missing sklearn. Install with: pip install scikit-learn"]

(out_dir / "auc.txt").write_text("\n".join(metrics_lines) + "\n", encoding="utf-8")

plt.figure(figsize=(10,5))
plt.plot(range(exec_start, len(RMSEs)), RMSEs[exec_start:], label="Anomaly Score (RMSE)")
plt.yscale("log")
plt.title("KitNET Result (Extended Training)")
plt.xlabel("Packet Index")
plt.ylabel("RMSE (Log Scale)")
plt.axvline(x=FMgrace+ADgrace, color="g", linestyle="--", label="Training Ends (100k)")
if attack_start is not None:
    plt.axvline(
        x=attack_start,
        color="r",
        linestyle="--",
        label=f"Attack Starts ({attack_start})",
    )
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig(out_dir / "rmse.png", dpi=150, bbox_inches="tight")
plt.show()
