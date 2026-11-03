#!/usr/bin/env bash
source /public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/scripts/00_env_issue27ckc.sh
export LD_LIBRARY_PATH=/share/software/CST/installed/MCR/bin/glnxa64:${LD_LIBRARY_PATH:-}
export PYTHONPATH="$MODERN_HEAD_ROOT/extra_deps:$MODERN_HEAD_ROOT/repo/ood"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=27 PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export MODERN_HEAD_PYTHON=/public/home/jiangxinwei.zr/work/kitsune/env/kitsune_py39/bin/python
test -x "$MODERN_HEAD_PYTHON"
