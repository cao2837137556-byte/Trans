#!/usr/bin/env bash
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
set -euo pipefail
# Inert template: explicit reviewed paths and authorization are required at submission.
: "${QREF_ROOT:?set package root}"
: "${QREF_CACHE:?set original pinned LEARN_DEV cache}"
: "${QREF_OUTPUT:?set a new output directory}"
: "${QREF_AUTHORIZATION:?set explicit execution authorization JSON}"
: "${QREF_PYTHON:?set validated Python runtime}"
cd "$QREF_ROOT"
exec "$QREF_PYTHON" repo/ood/legacy_qref_runner_v1.py run --root "$QREF_ROOT" --cache "$QREF_CACHE" --out "$QREF_OUTPUT" --authorization "$QREF_AUTHORIZATION" --execute
