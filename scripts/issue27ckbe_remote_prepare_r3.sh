#!/bin/bash
# CKBE r3 is superseded: cluster policy requires the pre-provisioned project
# runtime and prohibits user-managed package installation.
set -euo pipefail

echo "CKBE r3 is superseded. Source the pre-provisioned 00_env_issue27ckc.sh and run the direct plan/canary protocol." >&2
exit 2
