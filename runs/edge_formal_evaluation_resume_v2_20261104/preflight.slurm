#!/usr/bin/env bash
#SBATCH --job-name=edge-formal-preflight
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8192M
#SBATCH --time=00:30:00
#SBATCH --tmp=32768
#SBATCH --no-requeue
#SBATCH --output=preflight-%j.out
#SBATCH --error=preflight-%j.err
set -euo pipefail
umask 077
exec /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -X utf8 -B /public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_evaluation_resume_v2_20261104/checkout/runs/edge_formal_evaluation_resume_v2_20261104/job_entry.py --preflight
