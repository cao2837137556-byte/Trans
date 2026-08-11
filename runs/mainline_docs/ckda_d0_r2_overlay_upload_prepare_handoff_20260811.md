# CKDA D0 r2 overlay upload and prepare handoff (2026-08-11)

## Authorization boundary

Kimi overlay review commit `ebd7534` authorizes overlay upload and remote r2
preparation.  The commands below do not invoke `sbatch`.  HPC resubmission
still requires a new explicit user authorization after the terminal marker
`CKDA_D0_R2_REMOTE_PREPARE_PASS` is observed.

## Local PowerShell: verify and upload the 145,185-byte overlay

```powershell
$ErrorActionPreference = 'Stop'
$ckdaOverlay = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckda_d0_representation_compatibility_20260811_r2_repair_overlay.tar.gz'
$ckdaExpected = '6dc832e59b4fc6e716f85dd7810e275c9c9b261dcd3fda4c086cac607e57e140'
$ckdaActual = (Get-FileHash -LiteralPath $ckdaOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
$ckdaSidecar = ((Get-Content -LiteralPath "$ckdaOverlay.sha256" -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
if ((Get-Item -LiteralPath $ckdaOverlay).Length -ne 145185) { throw 'CKDA r2 overlay byte mismatch' }
if ($ckdaActual -ne $ckdaExpected -or $ckdaSidecar -ne $ckdaExpected) { throw 'CKDA r2 overlay SHA mismatch' }
scp $ckdaOverlay "$ckdaOverlay.sha256" school-hpc:/public/home/jiangxinwei.zr/work/
if ($LASTEXITCODE -ne 0) { throw "CKDA r2 overlay upload failed: exit $LASTEXITCODE" }
"CKDA_D0_R2_OVERLAY_UPLOAD_PASS bytes=145185 sha256=$ckdaActual"
```

## HPC Bash: reconstruct, verify, and atomically install r2

This path deliberately extracts the immutable r1 archive again rather than
copying the already-executed r1 directory, because login checks created
unhashed runtime files such as `__pycache__` and the job-id record there.

```bash
(
set -euo pipefail

WORK=/public/home/jiangxinwei.zr/work
BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
R1_NAME=issue27ckda_d0_representation_compatibility_20260811
R2_NAME=issue27ckda_d0_representation_compatibility_20260811_r2
R1_ARCHIVE="$WORK/issue27ckda_d0_representation_compatibility_20260811_upload_bundle.tar.gz"
OVERLAY="$WORK/issue27ckda_d0_representation_compatibility_20260811_r2_repair_overlay.tar.gz"
R2="$WORK/$R2_NAME"
STAGE="$WORK/.${R2_NAME}.prepare.$$"

test -s "$R1_ARCHIVE"
test "$(stat -c %s "$R1_ARCHIVE")" = 665814425
test "$(sha256sum "$R1_ARCHIVE" | awk '{print $1}')" = c979638ecf430946cdd9e2614b082c42bc5f78f6cadd4bf545ff88afd70aade9
test -s "$OVERLAY"
test "$(stat -c %s "$OVERLAY")" = 145185
test "$(sha256sum "$OVERLAY" | awk '{print $1}')" = 6dc832e59b4fc6e716f85dd7810e275c9c9b261dcd3fda4c086cac607e57e140
(cd "$WORK" && sha256sum -c "$(basename "$OVERLAY").sha256")
test ! -e "$R2"
test ! -e "$STAGE"

mkdir "$STAGE"
tar -xzf "$R1_ARCHIVE" -C "$STAGE"
mv "$STAGE/$R1_NAME" "$STAGE/$R2_NAME"
tar -xzf "$OVERLAY" -C "$STAGE"

cd "$STAGE/$R2_NAME"
sha256sum -c SHA256SUMS
test "$(tr -d '\r\n' < bundle_commit.txt)" = c4276bd3074dccb900c361d09772ae4bc97eb656
test "$(sha256sum payload/vendor/netFound/src/modules/netFoundModels.py | awk '{print $1}')" = a66834ea194a291ebbf563027df5e995f57ce8033699b8bc8e78f071de931526

source "$BASE/scripts/00_env_issue27ckc.sh"
python - "$STAGE/$R2_NAME/payload/vendor/netFound" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
audit = json.loads((root / "PY39_COMPAT_AUDIT.json").read_text(encoding="utf-8"))
assert audit["status"] == "CKDA_NETFOUND_PY39_COMPAT_PASS"
assert audit["replacement_count"] == 1
assert audit["semantic_change"] == "NONE_SYNTAX_EQUIVALENT_IF_ELIF"
count = 0
for path in sorted((root / "src").rglob("*.py")):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
    count += 1
assert count == 17 == audit["python39_ast_files"]
print("CKDA_D0_NETFOUND_PY39_REMOTE_GATE_PASS", count, audit["patched_file_sha256"])
PY

mv "$STAGE/$R2_NAME" "$R2"
rmdir "$STAGE"
printf 'CKDA_D0_R2_REMOTE_PREPARE_PASS root=%s commit=%s\n' "$R2" c4276bd3074dccb900c361d09772ae4bc97eb656
)
```

No job is submitted by either block.

## Explicit r2 resubmission authorization

The user explicitly authorized `CKDA D0 r2` resubmission on 2026-08-11 after
observing `CKDA_D0_R2_REMOTE_PREPARE_PASS`.  The authorization applies only to
the reviewed r2 root and one AMD submission through its hash-gated installer:

```bash
(
set -euo pipefail
R2=/public/home/jiangxinwei.zr/work/issue27ckda_d0_representation_compatibility_20260811_r2
test -d "$R2"
test "$(tr -d '\r\n' < "$R2/bundle_commit.txt")" = c4276bd3074dccb900c361d09772ae4bc97eb656
cd "$R2"
export CKDA_D0_SUBMIT_AUTHORIZATION=YES
bash payload/scripts/issue27ckda_d0_install_and_submit.sh
)
```

No other partition, seed, candidate, FINAL source, or repeat submission is
authorized by this record.
