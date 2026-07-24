param(
    [string]$RepoRoot = 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline',
    [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer',
    [string]$BundleName = 'issue27ckbu_parallel_resume_seed27_dual_20260724_r2'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$bundleRoot = Join-Path $TransferRoot $BundleName
$stageRoot = Join-Path $bundleRoot $BundleName
$archive = Join-Path $TransferRoot "${BundleName}_upload_bundle.tar.gz"
$archiveHash = "$archive.sha256"

foreach ($path in @($bundleRoot, $archive, $archiveHash)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing bundle artifact: $path"
    }
}

$payloadFiles = @(
    'repo/ood/issue27ckbu_parallel_cache_resume_v1.py',
    'repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py',
    'repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py',
    'runs/mainline_docs/ckbu_parallel_resume_runtime_fix_20260724.md',
    'scripts/issue27ckbu_install_and_submit_parallel_resume_dual.sh',
    'scripts/issue27ckbu_status_parallel_resume_dual.sh',
    'scripts/issue27ckbu_unified_process_rescue_parallel_resume.slurm',
    'scripts/issue27ckbu_validate_and_pack_parallel_resume_seed27.sh'
)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
New-Item -ItemType Directory -Path $stageRoot | Out-Null

foreach ($relative in $payloadFiles) {
    $source = Join-Path $RepoRoot ($relative -replace '/', '\')
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing payload source: $source"
    }
    $target = Join-Path $stageRoot ("payload\" + ($relative -replace '/', '\'))
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    [System.IO.File]::WriteAllBytes(
        $target,
        [System.IO.File]::ReadAllBytes($source)
    )
}

$commit = (& git -C $RepoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-f]{40}$') {
    throw "Cannot resolve repository commit"
}
[System.IO.File]::WriteAllText(
    (Join-Path $stageRoot 'bundle_commit.txt'),
    "$commit`n",
    $utf8NoBom
)

$readme = @'
# CKBU parallel-resume seed-27 HPC bundle

This bundle is the LF-only replacement for the superseded r1 archive.
It preserves the registered CKBU science and changes execution only:
validated predecessor-cache reuse plus bounded source-level parallelism.

Run only `payload/scripts/issue27ckbu_install_and_submit_parallel_resume_dual.sh`
from this extracted directory on the HPC login node. It submits one isolated
AMD job and one isolated Intel job after all inline validation gates pass.
'@
[System.IO.File]::WriteAllText(
    (Join-Path $stageRoot 'README_run_on_hpc.md'),
    ($readme -replace "`r`n", "`n") + "`n",
    $utf8NoBom
)

$checksumFiles = @(
    'bundle_commit.txt',
    'README_run_on_hpc.md'
) + ($payloadFiles | ForEach-Object { "payload/$_" })

foreach ($relative in $checksumFiles) {
    $path = Join-Path $stageRoot ($relative -replace '/', '\')
    $bytes = [System.IO.File]::ReadAllBytes($path)
    if ($bytes -contains 13) {
        throw "Text payload is not LF-only: $relative"
    }
}

$checksumLines = foreach ($relative in ($checksumFiles | Sort-Object)) {
    $path = Join-Path $stageRoot ($relative -replace '/', '\')
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $relative"
}
[System.IO.File]::WriteAllText(
    (Join-Path $stageRoot 'SHA256SUMS'),
    ($checksumLines -join "`n") + "`n",
    $utf8NoBom
)

Push-Location $bundleRoot
try {
    & tar -czf $archive $BundleName
    if ($LASTEXITCODE -ne 0) {
        throw "tar archive creation failed"
    }
}
finally {
    Pop-Location
}

$verifyRoot = Join-Path $bundleRoot '_verify_extract'
New-Item -ItemType Directory -Path $verifyRoot | Out-Null
& tar -xzf $archive -C $verifyRoot
if ($LASTEXITCODE -ne 0) {
    throw "tar archive verification extraction failed"
}

$verifiedStage = Join-Path $verifyRoot $BundleName
foreach ($relative in $checksumFiles) {
    $expectedLine = $checksumLines |
        Where-Object { $_ -like "*  $relative" } |
        Select-Object -First 1
    $expected = ($expectedLine -split '\s+')[0]
    $path = Join-Path $verifiedStage ($relative -replace '/', '\')
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Post-extraction hash mismatch: $relative"
    }
    if ([System.IO.File]::ReadAllBytes($path) -contains 13) {
        throw "Post-extraction CR byte found: $relative"
    }
}

$archiveSha = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    $archiveHash,
    "$archiveSha  $(Split-Path -Leaf $archive)`n",
    $utf8NoBom
)

Write-Output "CKBU_BUNDLE=$archive"
Write-Output "CKBU_BUNDLE_SHA256=$archiveSha"
Write-Output "CKBU_BUNDLE_BYTES=$((Get-Item -LiteralPath $archive).Length)"
Write-Output "CKBU_BUNDLE_COMMIT=$commit"
