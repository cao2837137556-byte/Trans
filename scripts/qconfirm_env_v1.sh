#!/usr/bin/env bash
source /public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
export LD_LIBRARY_PATH=/share/software/CST/installed/MCR/bin/glnxa64:${LD_LIBRARY_PATH:-}
export PYTHONPATH="$QCONF_ROOT/repo/ood:/public/home/jiangxinwei.zr/work/issue27ckda_d0_representation_compatibility_20260811_r2/payload/vendor_py"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=27 PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export QCONF_PYTHON=/public/home/jiangxinwei.zr/work/kitsune/env/kitsune_py39/bin/python
test -x "$QCONF_PYTHON"
