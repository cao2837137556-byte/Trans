from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tarfile
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Iterable

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR
import frontend100_negative_recipe_rescoring as resc


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(WORKTREE_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def format_command(cmd: list[str]) -> str:
    return " ".join(f'"{x}"' if " " in x else x for x in cmd)


def make_source_root_bundle(run_dir: Path, source_root: Path) -> Path:
    target = run_dir / "source_root"
    required_relpaths = [
        Path("runs/frontend100_crosscapture_stage1_2026-03-25/data/id_source_100.csv"),
        Path("runs/frontend100_crosscapture_stage1_2026-03-25/data/ood_benign_source_100.csv"),
        Path("runs/frontend100_joint_eval_stage1_2026-03-31/data/attack_source_100.csv"),
        Path("runs/frontend100_joint_eval_stage1_2026-03-31/extract_attack_34_1/iot23_34_1_malicious_first30000.tsv"),
        Path("runs/frontend100_joint_eval_stage2_2026-04-01/attack_manifest_stage2.json"),
    ]
    for rel in required_relpaths:
        copy_file(source_root / rel, target / rel)

    stage2_manifest_path = target / "runs/frontend100_joint_eval_stage2_2026-04-01/attack_manifest_stage2.json"
    stage2_manifest = json.loads(stage2_manifest_path.read_text(encoding="utf-8-sig"))
    idx = resc.build_stage2_indices(stage2_manifest)
    idx_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_manifest": str(stage2_manifest_path),
        "all": idx["all"].tolist(),
        "high": idx["high"].tolist(),
        "mixed": idx["mixed"].tolist(),
    }
    write_text(
        target / "runs/frontend100_joint_eval_stage2_2026-04-01/attack_indices_stage2.json",
        json.dumps(idx_payload, indent=2, ensure_ascii=False),
    )
    return target


def write_watch_hint(run_dir: Path, remote_run_dir: str) -> None:
    lines = [
        "# HPC Watch Files",
        "",
        "After job submission, open these files directly in the remote workspace tree:",
        f"- `{remote_run_dir}/latest_slurm.out`",
        f"- `{remote_run_dir}/latest_slurm.err`",
        "",
        "Backup copies also exist here:",
        f"- `{remote_run_dir}/stdout.log`",
        f"- `{remote_run_dir}/stderr.log`",
        "",
        "The submit step also writes:",
        f"- `{remote_run_dir}/last_job_id.txt`",
    ]
    write_text(run_dir / "watch_files.md", "\n".join(lines) + "\n")


def build_command(args: argparse.Namespace, source_root_remote: str) -> list[str]:
    cmd = [
        "$PYTHON_BIN",
        "-u",
        f"runs/{args.run_tag}/repo/ood/frontend100_modern_tabular_baselines.py",
        "--run-tag",
        args.run_tag,
        "--source-root",
        source_root_remote,
        "--stage2-indices-json",
        f"{source_root_remote}/runs/frontend100_joint_eval_stage2_2026-04-01/attack_indices_stage2.json",
        "--models",
        args.model,
        "--seeds",
        args.seeds,
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--lr",
        str(args.lr),
        "--weight-decay",
        str(args.weight_decay),
        "--patience",
        str(args.patience),
        "--val-ratio",
        str(args.val_ratio),
        "--calibration-budget",
        str(args.calibration_budget),
        "--scan-points",
        str(args.scan_points),
        "--benchmark-repeats",
        str(args.benchmark_repeats),
        "--device",
        args.device,
        "--skip-register",
    ]
    if args.model == "ft_transformer_ae":
        cmd.extend(
            [
                "--ft-d-token",
                str(args.ft_d_token),
                "--ft-n-heads",
                str(args.ft_n_heads),
                "--ft-n-blocks",
                str(args.ft_n_blocks),
                "--ft-attn-dropout",
                str(args.ft_attn_dropout),
                "--ft-ffn-dropout",
                str(args.ft_ffn_dropout),
            ]
        )
    elif args.model == "rtdl_resnet_ae":
        cmd.extend(
            [
                "--resnet-d-hidden",
                str(args.resnet_d_hidden),
                "--resnet-n-blocks",
                str(args.resnet_n_blocks),
                "--resnet-dropout",
                str(args.resnet_dropout),
            ]
        )
    else:
        raise ValueError(f"Unsupported model: {args.model}")
    cmd.extend(
        [
            "--latent-dim",
            str(args.latent_dim),
            "--decoder-hidden",
            str(args.decoder_hidden),
        ]
    )
    return cmd


def write_job_slurm(run_dir: Path, args: argparse.Namespace) -> None:
    remote_run_dir = f"$REMOTE_PROJECT_ROOT/runs/{args.run_tag}"
    source_root_remote = f"{remote_run_dir}/source_root"
    cmd = build_command(args, source_root_remote)
    lines = f"""\
#!/usr/bin/env bash
#SBATCH -J {args.job_name}
#SBATCH -p {args.partition}
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c {args.cpus}
#SBATCH --mem={args.mem_gb}G
#SBATCH -t {args.time_limit}
#SBATCH -o slurm-%j.out
#SBATCH -e slurm-%j.err

set -uo pipefail

RUN_TAG="{args.run_tag}"
REMOTE_PROJECT_ROOT="${{REMOTE_PROJECT_ROOT:-{args.remote_project_root}}}"
PYTHON_BIN="${{PYTHON_BIN:-{args.python_bin}}}"
RUN_DIR="$REMOTE_PROJECT_ROOT/runs/$RUN_TAG"
SOURCE_ROOT="$RUN_DIR/source_root"
export RUN_TAG REMOTE_PROJECT_ROOT PYTHON_BIN SOURCE_ROOT

mkdir -p "$RUN_DIR" "$RUN_DIR/manifests" "$RUN_DIR/package"
: > "$RUN_DIR/stdout.log"
: > "$RUN_DIR/stderr.log"
exec > >(tee -a "$RUN_DIR/stdout.log")
exec 2> >(tee -a "$RUN_DIR/stderr.log" >&2)

echo "[start] $(date '+%F %T')"
echo "[run_dir] $RUN_DIR"
echo "[python] $PYTHON_BIN"
echo "[source_root] $SOURCE_ROOT"
echo "[pwd_before_cd] $(pwd)"

cd "$REMOTE_PROJECT_ROOT"
echo "[pwd_after_cd] $(pwd)"

"$PYTHON_BIN" --version > "$RUN_DIR/env_freeze.txt"
"$PYTHON_BIN" -m pip freeze >> "$RUN_DIR/env_freeze.txt" || true

git rev-parse HEAD > "$RUN_DIR/git_commit.txt" || true

CMD=(
{textwrap.indent(chr(10).join(cmd), "  ")}
)

printf '%s\\n' "${{CMD[*]}}" > "$RUN_DIR/command.txt"
echo "[command] ${{CMD[*]}}"

set +e
"${{CMD[@]}}"
CMD_STATUS=$?
set -e

echo "[command_exit] status=$CMD_STATUS"

python - <<'PY'
import json, os, time
run_dir = os.path.join(os.environ['REMOTE_PROJECT_ROOT'], 'runs', os.environ['RUN_TAG'])
job = {{
  'job_id': os.environ.get('SLURM_JOB_ID'),
  'job_name': os.environ.get('SLURM_JOB_NAME'),
  'node_list': os.environ.get('SLURM_JOB_NODELIST'),
  'submit_dir': os.environ.get('SLURM_SUBMIT_DIR'),
  'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
  'python_bin': os.environ.get('PYTHON_BIN'),
  'source_root': os.environ.get('SOURCE_ROOT'),
  'stdout_log': os.path.join(run_dir, 'stdout.log'),
  'stderr_log': os.path.join(run_dir, 'stderr.log'),
  'slurm_out_pattern': os.path.join(run_dir, f"slurm-{{os.environ.get('SLURM_JOB_ID', 'unknown')}}.out"),
  'slurm_err_pattern': os.path.join(run_dir, f"slurm-{{os.environ.get('SLURM_JOB_ID', 'unknown')}}.err"),
  'input_mode': 'bundled_source_root_with_stage2_indices'
}}
with open(os.path.join(run_dir, 'job_info.json'), 'w', encoding='utf-8') as f:
    json.dump(job, f, indent=2)
PY

for f in config.json modern_tabular_manifest.json modern_tabular_summary.md summary.md job_info.json stdout.log stderr.log command.txt git_commit.txt env_freeze.txt; do
  if [[ -f "$RUN_DIR/$f" ]]; then
    cp "$RUN_DIR/$f" "$RUN_DIR/manifests/" || true
  fi
done

BUNDLE="$RUN_DIR/package/{args.run_tag}_bundle.tar.gz"
items=()
for f in summary.md config.json command.txt modern_tabular_results.csv modern_tabular_aggregate.csv modern_tabular_diagnostics.csv modern_tabular_training_history.csv modern_tabular_costs.csv modern_tabular_costs_aggregate.csv modern_tabular_results.md modern_tabular_summary.md modern_tabular_manifest.json git_commit.txt env_freeze.txt stdout.log stderr.log job_info.json watch_files.md; do
  if [[ -e "$RUN_DIR/$f" ]]; then
    items+=("$f")
  fi
done
for d in manifests modern_tabular_plots; do
  if [[ -e "$RUN_DIR/$d" ]]; then
    items+=("$d")
  fi
done
if [[ ${{#items[@]}} -gt 0 ]]; then
  tar -czf "$BUNDLE" -C "$RUN_DIR" "${{items[@]}}"
  echo "[bundle] $BUNDLE"
else
  echo "[bundle] skipped because no artifacts were produced"
fi

echo "[finish] $(date '+%F %T') exit_code=$CMD_STATUS"
exit $CMD_STATUS
"""
    write_text(run_dir / "job.slurm", lines)
    write_text(run_dir / "command.txt", format_command(cmd) + "\n")


def write_submit_commands(run_dir: Path, args: argparse.Namespace, bundle_name: str) -> None:
    remote_run_dir = f"{args.remote_project_root}/runs/{args.run_tag}"
    submit_remote = (
        f"cd {remote_run_dir} && "
        f'SUBMIT_MSG=$(REMOTE_PROJECT_ROOT={args.remote_project_root} '
        f'SOURCE_ROOT={remote_run_dir}/source_root '
        f'PYTHON_BIN={args.python_bin} '
        f'sbatch job.slurm) && '
        f'JOB_ID=${{SUBMIT_MSG##* }} && '
        f'echo $JOB_ID > last_job_id.txt && '
        f'ln -sfn slurm-$JOB_ID.out latest_slurm.out && '
        f'ln -sfn slurm-$JOB_ID.err latest_slurm.err && '
        f'echo submit_message=$SUBMIT_MSG && '
        f'echo submitted_job_id=$JOB_ID && '
        f'echo watch_out={remote_run_dir}/latest_slurm.out && '
        f'echo watch_err={remote_run_dir}/latest_slurm.err'
    )
    submit = [
        "# PowerShell-safe submit sequence",
        f"ssh {args.remote_host} 'mkdir -p {args.remote_project_root}'",
        f'scp "{run_dir / bundle_name}" {args.remote_host}:{args.remote_project_root}/',
        f"ssh {args.remote_host} 'cd {args.remote_project_root} && tar -xzf {bundle_name}'",
        f"ssh {args.remote_host} '{submit_remote}'",
        f"ssh {args.remote_host} 'cd {remote_run_dir} && ls -l latest_slurm.out latest_slurm.err last_job_id.txt'",
        "# Run the next command only after latest_slurm.out / latest_slurm.err shows the job has finished and the bundle exists.",
        f'scp {args.remote_host}:{remote_run_dir}/package/{args.run_tag}_bundle.tar.gz "{run_dir / f"{args.run_tag}_bundle.tar.gz"}"',
    ]
    write_text(run_dir / "submit_commands.txt", "\n".join(submit) + "\n")


def collect_upload_entries(run_dir: Path, args: argparse.Namespace) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    entries.append((run_dir / "repo", f"runs/{args.run_tag}/repo"))
    entries.append((run_dir / "source_root", f"runs/{args.run_tag}/source_root"))
    for name in [
        "job.slurm",
        "run_spec.json",
        "config.json",
        "command.txt",
        "git_commit.txt",
        "local_smoketest_summary.md",
        "submit_commands.txt",
        "upload_manifest.txt",
        "watch_files.md",
    ]:
        path = run_dir / name
        if path.exists():
            entries.append((path, f"runs/{args.run_tag}/{name}"))

    ref_files = [
        (
            ARTIFACT_RUNS_DIR / "frontend100_locked_candidate_multiseed_2026-04-06" / "multiseed_locked_candidate_results.csv",
            "runs/frontend100_locked_candidate_multiseed_2026-04-06/multiseed_locked_candidate_results.csv",
        ),
        (
            ARTIFACT_RUNS_DIR / "frontend100_deep_svdd_baseline_2026-04-09" / "deep_svdd_results.csv",
            "runs/frontend100_deep_svdd_baseline_2026-04-09/deep_svdd_results.csv",
        ),
        (
            ARTIFACT_RUNS_DIR / "frontend100_final_candidate_audit_2026-04-08" / "final_candidate_main_table.csv",
            "runs/frontend100_final_candidate_audit_2026-04-08/final_candidate_main_table.csv",
        ),
    ]
    for src, arcname in ref_files:
        if not src.exists():
            raise FileNotFoundError(f"Missing required reference file: {src}")
        entries.append((src, arcname))
    return entries


def write_upload_bundle(run_dir: Path, args: argparse.Namespace, bundle_name: str) -> None:
    entries = collect_upload_entries(run_dir, args)
    manifest_lines: list[str] = []
    bundle_path = run_dir / bundle_name
    with tarfile.open(bundle_path, "w:gz") as tar:
        for src, arcname in entries:
            tar.add(src, arcname=arcname, recursive=True)
            manifest_lines.append(arcname)
    write_text(run_dir / "upload_manifest.txt", "\n".join(manifest_lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare an HPC bundle for frontend100 modern tabular baseline runs.")
    ap.add_argument("--run-tag", required=True)
    ap.add_argument("--model", choices=["ft_transformer_ae", "rtdl_resnet_ae"], required=True)
    ap.add_argument("--remote-project-root", required=True)
    ap.add_argument("--remote-host", default="school-hpc")
    ap.add_argument("--python-bin", default="/public/home/jiangxinwei.zr/work/kitsune/env/kitsune_py39/bin/python")
    ap.add_argument(
        "--source-root",
        type=Path,
        default=ARTIFACT_RUNS_DIR.parents[2] / "KitNET-py-master" / "KitNET-py-master",
    )
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-6)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--benchmark-repeats", type=int, default=3)
    ap.add_argument("--ft-d-token", type=int, default=64)
    ap.add_argument("--ft-n-heads", type=int, default=8)
    ap.add_argument("--ft-n-blocks", type=int, default=3)
    ap.add_argument("--ft-attn-dropout", type=float, default=0.2)
    ap.add_argument("--ft-ffn-dropout", type=float, default=0.1)
    ap.add_argument("--resnet-d-hidden", type=int, default=256)
    ap.add_argument("--resnet-n-blocks", type=int, default=4)
    ap.add_argument("--resnet-dropout", type=float, default=0.1)
    ap.add_argument("--latent-dim", type=int, default=64)
    ap.add_argument("--decoder-hidden", type=int, default=256)
    ap.add_argument("--partition", default="amd")
    ap.add_argument("--cpus", type=int, default=16)
    ap.add_argument("--mem-gb", type=int, default=48)
    ap.add_argument("--time-limit", default="10:00:00")
    ap.add_argument("--job-name", default=None)
    args = ap.parse_args()

    if args.job_name is None:
        args.job_name = "mod_tab_ft" if args.model == "ft_transformer_ae" else "mod_tab_resnet"

    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "package").mkdir(exist_ok=True)
    (run_dir / "manifests").mkdir(exist_ok=True)

    repo_dst = run_dir / "repo"
    reset_dir(repo_dst)
    shutil.copytree(REPO_DIR, repo_dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))

    source_root_dst = run_dir / "source_root"
    reset_dir(source_root_dst)
    make_source_root_bundle(run_dir, args.source_root)

    commit = run_git("rev-parse", "HEAD")
    write_text(run_dir / "git_commit.txt", commit + "\n")
    write_watch_hint(run_dir, f"{args.remote_project_root}/runs/{args.run_tag}")

    config = {
        "stage": "frontend100_modern_tabular_baselines",
        "run_tag": args.run_tag,
        "remote_project_root": args.remote_project_root,
        "source_root": "REMOTE_PROJECT_ROOT/runs/{}/source_root".format(args.run_tag),
        "model": args.model,
        "seeds": [int(x) for x in args.seeds.split(",") if x.strip()],
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "device": args.device,
        "references": [
            "runs/frontend100_locked_candidate_multiseed_2026-04-06/multiseed_locked_candidate_results.csv",
            "runs/frontend100_deep_svdd_baseline_2026-04-09/deep_svdd_results.csv",
            "runs/frontend100_final_candidate_audit_2026-04-08/final_candidate_main_table.csv",
        ],
    }
    if args.model == "ft_transformer_ae":
        config.update(
            {
                "ft_d_token": args.ft_d_token,
                "ft_n_heads": args.ft_n_heads,
                "ft_n_blocks": args.ft_n_blocks,
                "ft_attn_dropout": args.ft_attn_dropout,
                "ft_ffn_dropout": args.ft_ffn_dropout,
                "latent_dim": args.latent_dim,
                "decoder_hidden": args.decoder_hidden,
            }
        )
    else:
        config.update(
            {
                "resnet_d_hidden": args.resnet_d_hidden,
                "resnet_n_blocks": args.resnet_n_blocks,
                "resnet_dropout": args.resnet_dropout,
                "latent_dim": args.latent_dim,
                "decoder_hidden": args.decoder_hidden,
            }
        )

    run_spec = {
        "stage": "frontend100_modern_tabular_baselines",
        "run_tag": args.run_tag,
        "model": args.model,
        "remote_project_root": args.remote_project_root,
        "python_bin": args.python_bin,
        "source_root_local": str(args.source_root),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stage2_indices_mode": "precomputed_json",
    }
    write_text(run_dir / "config.json", json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    write_text(run_dir / "run_spec.json", json.dumps(run_spec, indent=2, ensure_ascii=False) + "\n")

    write_job_slurm(run_dir, args)
    bundle_name = "upload_bundle.tar.gz"
    write_upload_bundle(run_dir, args, bundle_name)
    write_submit_commands(run_dir, args, bundle_name)

    # Refresh manifest so it includes submit/watch files written after the first tar pass.
    write_upload_bundle(run_dir, args, bundle_name)
    print(f"[done] prepared HPC bundle: {run_dir}", flush=True)


if __name__ == "__main__":
    main()
