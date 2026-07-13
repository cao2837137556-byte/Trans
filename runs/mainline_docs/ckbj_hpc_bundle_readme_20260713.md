# CKBJ formal M1 v2 — upload, submit, inspect, and pull back

This is a **Stage-B-only** bundle. CKBI job `150547` and its four-source TGN
report cache are reused. It submits one seed-27 metrics job and never submits
CKBI, CKBF, an environment task, a preflight, or seeds 37/47.

## Windows PowerShell upload

```powershell
$Bundle = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckbj_m1_v2_seed27_20260713_upload_bundle.tar.gz'
$RemoteHost = 'jiangxinwei.zr@172.24.3.168'
$RemoteDir = '/public/home/jiangxinwei.zr/work/paper04/m1_transfer/issue27ckbj_m1_v2_seed27_20260713'
Get-FileHash $Bundle -Algorithm SHA256
ssh $RemoteHost "mkdir -p '$RemoteDir'"
scp $Bundle "${RemoteHost}:${RemoteDir}/"
```

## HPC unpack, verify, and submit once

```bash
set -euo pipefail
REMOTE=/public/home/jiangxinwei.zr/work/paper04/m1_transfer/issue27ckbj_m1_v2_seed27_20260713
cd "$REMOTE"
tar -xzf issue27ckbj_m1_v2_seed27_20260713_upload_bundle.tar.gz
cd issue27ckbj_m1_v2_seed27_20260713
sha256sum -c SHA256SUMS
M1_PARTITION=intel bash payload/scripts/issue27ckbj_install_and_submit_formal_v2.sh
```

The final command prints `CKBJ_JOB_ID=<number>` and saves the same ID in
`ckbj_formal_seed27_job_id.txt`. Do not submit an AMD duplicate concurrently;
the report-only C1 extension has one immutable destination.

## Inspect while queued or running

```bash
REMOTE=/public/home/jiangxinwei.zr/work/paper04/m1_transfer/issue27ckbj_m1_v2_seed27_20260713
cd "$REMOTE/issue27ckbj_m1_v2_seed27_20260713"
bash payload/scripts/issue27ckbj_status_formal_v2.sh
```

## Validate and pack after completion

```bash
REMOTE=/public/home/jiangxinwei.zr/work/paper04/m1_transfer/issue27ckbj_m1_v2_seed27_20260713
cd "$REMOTE/issue27ckbj_m1_v2_seed27_20260713"
bash payload/scripts/issue27ckbj_validate_and_pack_formal_v2.sh
```

## Windows PowerShell pullback

Replace `<JOBID>` only with the numeric `CKBJ_JOB_ID` printed at submission.

```powershell
$RemoteHost = 'jiangxinwei.zr@172.24.3.168'
$RemoteDir = '/public/home/jiangxinwei.zr/work/paper04/m1_transfer/issue27ckbj_m1_v2_seed27_20260713/issue27ckbj_m1_v2_seed27_20260713/pullback'
$LocalDir = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer\pullback\issue27ckbj_m1_v2_seed27_20260713'
New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
scp "${RemoteHost}:${RemoteDir}/issue27ckbj_tgn_m1_strict_formal_v2_2026-07-13_hpc_seed27_<JOBID>_pullback.tar.gz*" "$LocalDir/"
Get-FileHash "$LocalDir\issue27ckbj_tgn_m1_strict_formal_v2_2026-07-13_hpc_seed27_<JOBID>_pullback.tar.gz" -Algorithm SHA256
```

The pullback validator checks provenance and completeness only. `PASS` does
not mean the scientific result is good; the scientific decision remains the
content of `m1_single_seed_go_no_go.json`.
