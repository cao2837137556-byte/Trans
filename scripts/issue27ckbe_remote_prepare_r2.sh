#!/bin/bash
# CKBE r2 was superseded because its wheelhouse omitted PyG runtime deps.
# Keep an explicit failure rather than letting a stale handoff create partial
# state on the cluster.
set -euo pipefail

echo "CKBE r2 is superseded by r3; use issue27ckbe_remote_prepare_r3.sh" >&2
exit 2
