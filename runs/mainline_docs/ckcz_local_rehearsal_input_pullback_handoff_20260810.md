# CKCZ 本地全流程彩排：严格 55-NPZ 输入拉回交接（2026-08-10）

状态：**READ-ONLY INPUT PACKAGING — NO HPC JOB — NO SCIENTIFIC VERDICT**

目标：只从两个冻结 manifest 与两个冻结 allowlist 做 exact join，拉回 Gotham 24 + auxiliary 31
个 NPZ 和 2 个 manifest。禁止手写 cache key，禁止复制完整 cache 目录，禁止接触 Gotham 其余
5 个非 allowlisted NPZ。

## 1. 已登录 HPC Bash：生成严格输入包

整段粘贴。该命令不提交 Slurm，只读现有冻结 cache：

```bash
(
set -euo pipefail
WORK=/public/home/jiangxinwei.zr/work
BASE="$WORK/paper04/worktrees/kitnet-exp-mainline"
RUN="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
R2_ROOT="$WORK/upload_issue27ckcz_r2_20260810/issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r2"
ALLOW_ROOT="$R2_ROOT/payload/runs/mainline_docs"
ARCHIVE="$WORK/ckcz_rehearsal_inputs_20260810.tar.gz"
STAGE=$(mktemp -d /tmp/ckcz_rehearsal_inputs_20260810.XXXXXX)
cleanup() {
  case "$STAGE" in
    /tmp/ckcz_rehearsal_inputs_20260810.*) rm -rf -- "$STAGE" ;;
    *) echo "refusing unsafe rehearsal temp cleanup: $STAGE" >&2; return 2 ;;
  esac
}
trap cleanup EXIT
ROOT="$STAGE/ckcz_rehearsal_inputs_20260810"

test -d "$RUN/gotham_causal_cache"
test -d "$RUN/auxiliary_causal_cache"
test -s "$RUN/ckbu_gotham_unified_causal_manifest.csv"
test -s "$RUN/ckbu_auxiliary_unified_causal_manifest.csv"
test -s "$ALLOW_ROOT/ckcz_gotham_source_allowlist_20260809.csv"
test -s "$ALLOW_ROOT/ckcz_auxiliary_source_allowlist_20260809.csv"
test "$(sha256sum "$ALLOW_ROOT/ckcz_gotham_source_allowlist_20260809.csv" | awk '{print $1}')" = \
  65b4804109914d50c3efb6b9ae40d2b7d7befc903be571a92ebee90624ab6de7
test "$(sha256sum "$ALLOW_ROOT/ckcz_auxiliary_source_allowlist_20260809.csv" | awk '{print $1}')" = \
  be4ad12a9b0807b15b120d91ec2f9519a1743120ef0e9f04e0d8bab573252c49

python - "$RUN" "$ALLOW_ROOT" "$ROOT" <<'PY'
import csv
import hashlib
import shutil
import sys
from pathlib import Path

run, allow_root, out = map(Path, sys.argv[1:])
out.mkdir(parents=True, exist_ok=False)

specs = (
    (
        "gotham",
        run / "ckbu_gotham_unified_causal_manifest.csv",
        allow_root / "ckcz_gotham_source_allowlist_20260809.csv",
        run / "gotham_causal_cache",
        24,
        317523,
        "aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22",
    ),
    (
        "auxiliary",
        run / "ckbu_auxiliary_unified_causal_manifest.csv",
        allow_root / "ckcz_auxiliary_source_allowlist_20260809.csv",
        run / "auxiliary_causal_cache",
        31,
        18600,
        "f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


selected = []
for kind, manifest_path, allow_path, cache_dir, expected_sources, expected_rows, manifest_sha in specs:
    if sha256(manifest_path) != manifest_sha:
        raise RuntimeError(f"{kind} manifest SHA drift")
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    with allow_path.open(newline="", encoding="utf-8") as handle:
        allow_rows = list(csv.DictReader(handle))
    required = {"source_group", "source_cache_key", "target_rows", "cache_sha256"}
    if not manifest_rows or not required.issubset(manifest_rows[0]):
        raise RuntimeError(f"{kind} manifest schema drift")
    if not allow_rows or set(allow_rows[0]) != {"source_group"}:
        raise RuntimeError(f"{kind} allowlist schema drift")
    by_source = {}
    cache_keys = set()
    for row in manifest_rows:
        source = row["source_group"]
        key = row["source_cache_key"]
        if source in by_source or key in cache_keys:
            raise RuntimeError(f"{kind} manifest key collision")
        by_source[source] = row
        cache_keys.add(key)
    allowed_sources = [row["source_group"] for row in allow_rows]
    if len(allowed_sources) != expected_sources or len(set(allowed_sources)) != expected_sources:
        raise RuntimeError(f"{kind} allowlist count/uniqueness drift")
    destination = out / f"{kind}_causal_cache"
    destination.mkdir()
    rows_total = 0
    for source in sorted(allowed_sources):
        if source not in by_source:
            raise RuntimeError(f"{kind} allowlist is not an exact manifest subset: {source}")
        row = by_source[source]
        key = row["source_cache_key"]
        if Path(key).name != key or not key or any(marker in source.lower() for marker in ("cooler-motor", "seed37", "seed47")):
            raise RuntimeError(f"unsafe/final-marked {kind} manifest row: {source}")
        source_path = cache_dir / f"{key}.npz"
        if not source_path.is_file():
            raise RuntimeError(f"missing {kind} allowlisted cache: {source}")
        actual = sha256(source_path)
        if actual != row["cache_sha256"].lower():
            raise RuntimeError(f"{kind} cache SHA drift: {source}")
        target_path = destination / source_path.name
        shutil.copy2(source_path, target_path)
        if sha256(target_path) != actual:
            raise RuntimeError(f"{kind} copied cache SHA drift: {source}")
        rows_total += int(row["target_rows"])
        selected.append({"cache_kind": kind, **{name: row[name] for name in sorted(required)}})
    if rows_total != expected_rows:
        raise RuntimeError(f"{kind} target-row drift: {rows_total}/{expected_rows}")
    shutil.copy2(manifest_path, out / manifest_path.name)

if len(selected) != 55:
    raise RuntimeError(f"selected cache count drift: {len(selected)}/55")
with (out / "selected_cache_audit.csv").open("w", newline="", encoding="utf-8") as handle:
    fields = ["cache_kind", "source_group", "source_cache_key", "target_rows", "cache_sha256"]
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(selected)
files = sorted(path for path in out.rglob("*") if path.is_file())
with (out / "SHA256SUMS").open("w", encoding="utf-8", newline="") as handle:
    for path in files:
        handle.write(f"{sha256(path)}  {path.relative_to(out).as_posix()}\n")
print(f"CKCZ_REHEARSAL_INPUT_SELECTION_PASS npz=55 manifests=2 selected_rows={len(selected)}")
PY

test "$(find "$ROOT/gotham_causal_cache" -maxdepth 1 -type f -name '*.npz' | wc -l)" -eq 24
test "$(find "$ROOT/auxiliary_causal_cache" -maxdepth 1 -type f -name '*.npz' | wc -l)" -eq 31
( cd "$ROOT" && sha256sum -c SHA256SUMS )
rm -f -- "$ARCHIVE" "$ARCHIVE.sha256"
tar -C "$STAGE" -czf "$ARCHIVE" ckcz_rehearsal_inputs_20260810
( cd "$WORK" && sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256" )
printf 'CKCZ_REHEARSAL_ARCHIVE=%s\nCKCZ_REHEARSAL_BYTES=%s\n' \
  "$ARCHIVE" "$(stat -c %s "$ARCHIVE")"
cat "$ARCHIVE.sha256"
)
```

## 2. 本地 Windows PowerShell：只拉回生成的小包

```powershell
$ckczTransfer = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
$ckczArchive = Join-Path $ckczTransfer 'ckcz_rehearsal_inputs_20260810.tar.gz'
scp school-hpc:~/work/ckcz_rehearsal_inputs_20260810.tar.gz $ckczArchive
scp school-hpc:~/work/ckcz_rehearsal_inputs_20260810.tar.gz.sha256 "${ckczArchive}.sha256"
if ($LASTEXITCODE -ne 0) { throw "CKCZ rehearsal pullback failed: exit $LASTEXITCODE" }
$actual = (Get-FileHash -LiteralPath $ckczArchive -Algorithm SHA256).Hash.ToLowerInvariant()
$expected = ((Get-Content -LiteralPath "${ckczArchive}.sha256" -Raw).Trim() -split '\s+')[0]
if ($actual -ne $expected) { throw "CKCZ rehearsal archive SHA mismatch" }
"CKCZ_REHEARSAL_PULLBACK_PASS sha256=$actual bytes=$((Get-Item -LiteralPath $ckczArchive).Length)"
```

把两段完整输出发回 Codex。Codex 负责本地解包、57 个冻结输入逐项哈希、真实全流程
`bootstrap-reps=20` 工程彩排和结果销毁；用户不需要手工运行诊断代码。

注意：当前正式实现对任何 `reps>=20` 都会生成内部 verdict。彩排输出因此只能存在于受控临时目录，
不得解释、提交或保存为科学结果；Codex 将只验证工程合同，PASS 后立即安全删除成功输出。
