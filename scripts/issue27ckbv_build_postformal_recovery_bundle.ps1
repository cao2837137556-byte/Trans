[CmdletBinding()]
param(
    [string]$BundleName = 'issue27ckbv_postformal_recovery_amd154917_20260729_r17',
    [string]$OutputRoot = '',
    [string]$CommitSha = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $OutputRoot) {
    $PaperRoot = Split-Path (Split-Path $RepoRoot -Parent) -Parent
    $OutputRoot = Join-Path $PaperRoot 'supercompute_transfer'
}
if (-not $CommitSha) {
    $CommitSha = (& git -C $RepoRoot rev-parse HEAD).Trim()
}
if ($CommitSha -notmatch '^[0-9a-f]{40}$') {
    throw "invalid commit SHA: $CommitSha"
}

$BundleRoot = Join-Path $OutputRoot $BundleName
$ArchiveName = "${BundleName}_upload_bundle.tar.gz"
$Archive = Join-Path $OutputRoot $ArchiveName
$ArchiveSha = "$Archive.sha256"

if (Test-Path -LiteralPath $BundleRoot) {
    throw "bundle directory already exists: $BundleRoot"
}
if (Test-Path -LiteralPath $Archive) {
    throw "bundle archive already exists: $Archive"
}
New-Item -ItemType Directory -Force -Path $BundleRoot | Out-Null

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
function Copy-LfText {
    param([string]$RelativePath)
    $Source = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "missing required recovery payload: $RelativePath"
    }
    $Target = Join-Path $BundleRoot ('payload/' + $RelativePath)
    New-Item -ItemType Directory -Force -Path (Split-Path $Target -Parent) | Out-Null
    $Text = [System.IO.File]::ReadAllText($Source)
    $Text = $Text.Replace("`r`n", "`n").Replace("`r", "`n")
    [System.IO.File]::WriteAllText($Target, $Text, $Utf8NoBom)
}

$PayloadFiles = @(
    'repo/ood/issue27ckbv_postformal_recovery_v1.py',
    'scripts/issue27ckbv_validate_and_pack_seed27.sh',
    'scripts/issue27ckbv_recover_postformal_154917.sh',
    'runs/mainline_docs/ckbv_r17_postformal_pool_semantic_recovery_20260729.md'
)
foreach ($RelativePath in $PayloadFiles) {
    Copy-LfText $RelativePath
}

$RecoveryText = [System.IO.File]::ReadAllText(
    (Join-Path $BundleRoot 'payload/scripts/issue27ckbv_recover_postformal_154917.sh')
)
if ($RecoveryText -match '(?m)^\s*(sbatch|scancel)\b') {
    throw 'recovery bundle must not submit or cancel Slurm jobs'
}
$RecoveryPyText = [System.IO.File]::ReadAllText(
    (Join-Path $BundleRoot 'payload/repo/ood/issue27ckbv_postformal_recovery_v1.py')
)
if (-not $RecoveryPyText.Contains('ckbu_role_usage_audit.csv')) {
    throw 'recovery provenance gate is missing ckbu_role_usage_audit.csv'
}
foreach ($Token in @(
    'SOURCE_JOB_ID=154917',
    'SOURCE_PARTITION=amd',
    'CKBV_ALLOW_POSTFORMAL_FAILED=1',
    '--mode recover',
    'issue27ckbv_validate_and_pack_seed27.sh'
)) {
    if (-not $RecoveryText.Contains($Token)) {
        throw "recovery command contract missing token: $Token"
    }
}

[System.IO.File]::WriteAllText(
    (Join-Path $BundleRoot 'bundle_commit.txt'),
    "$CommitSha`n",
    $Utf8NoBom
)

$Readme = @"
# CKBV r17 post-formal recovery

This bundle repairs only the fit/select labels in the already-emitted
raw51 sensitivity audit for AMD job 154917. It does not submit Slurm work,
train a model, decode a PCAP, change a score, or select a new gate.

Run in the already logged-in VS Code HPC Bash terminal:

````bash
REMOTE=/public/home/jiangxinwei.zr/work/paper04/m1_transfer/$BundleName
cd "`$REMOTE"
sha256sum -c "$ArchiveName.sha256"
tar -xzf "$ArchiveName"
cd "$BundleName"
sha256sum -c SHA256SUMS
bash payload/scripts/issue27ckbv_recover_postformal_154917.sh
````

The validated pullback is written to:

````text
/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/runs/issue27ckbv_seed27_amd_154917_pullback.tar.gz
````
"@
[System.IO.File]::WriteAllText(
    (Join-Path $BundleRoot 'README_run_on_hpc.md'),
    $Readme.Replace("`r`n", "`n").Replace("`r", "`n"),
    $Utf8NoBom
)

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw 'python is required for recovery contract validation'
}
& $Python.Source -m py_compile `
    (Join-Path $BundleRoot 'payload/repo/ood/issue27ckbv_postformal_recovery_v1.py')
if ($LASTEXITCODE -ne 0) {
    throw 'recovery Python compile failed'
}
& $Python.Source `
    (Join-Path $BundleRoot 'payload/repo/ood/issue27ckbv_postformal_recovery_v1.py') `
    --mode contract-unit
if ($LASTEXITCODE -ne 0) {
    throw 'recovery contract-unit failed'
}

$Files = Get-ChildItem -LiteralPath $BundleRoot -Recurse -File |
    Where-Object { $_.Name -ne 'SHA256SUMS' } |
    Sort-Object FullName
$HashLines = foreach ($File in $Files) {
    $Relative = (
        [System.IO.Path]::GetRelativePath($BundleRoot, $File.FullName)
    ).Replace('\', '/')
    $Hash = (
        Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    "$Hash  $Relative"
}
[System.IO.File]::WriteAllText(
    (Join-Path $BundleRoot 'SHA256SUMS'),
    (($HashLines -join "`n") + "`n"),
    $Utf8NoBom
)

Push-Location $OutputRoot
try {
    & tar -czf $ArchiveName $BundleName
    if ($LASTEXITCODE -ne 0) {
        throw 'tar creation failed'
    }
}
finally {
    Pop-Location
}

$ArchiveDigest = (
    Get-FileHash -LiteralPath $Archive -Algorithm SHA256
).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    $ArchiveSha,
    "$ArchiveDigest  $ArchiveName`n",
    $Utf8NoBom
)

$ExtractRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    'ckbv_r17_clean_' + [guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Force -Path $ExtractRoot | Out-Null
try {
    & tar -xzf $Archive -C $ExtractRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'clean extraction failed'
    }
    $CleanBundle = Join-Path $ExtractRoot $BundleName
    & $Python.Source `
        (Join-Path $CleanBundle 'payload/repo/ood/issue27ckbv_postformal_recovery_v1.py') `
        --mode contract-unit
    if ($LASTEXITCODE -ne 0) {
        throw 'clean-extract recovery contract-unit failed'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $CleanBundle 'SHA256SUMS'))) {
        throw 'clean-extract SHA256SUMS missing'
    }
}
finally {
    Remove-Item -LiteralPath $ExtractRoot -Recurse -Force
}

$Info = Get-Item -LiteralPath $Archive
Write-Output 'CKBV_R17_RECOVERY_BUNDLE_PASS'
Write-Output "BUNDLE=$Archive"
Write-Output "SIZE_BYTES=$($Info.Length)"
Write-Output "SHA256=$ArchiveDigest"
Write-Output "COMMIT=$CommitSha"
