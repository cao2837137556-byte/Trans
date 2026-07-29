[CmdletBinding()]
param(
    [string]$BundleName = 'issue27ckbv_postformal_recovery_amd154917_20260729_r20',
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

function Get-RelativePathCompat {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string]$ChildPath
    )
    $RootFull = [System.IO.Path]::GetFullPath($RootPath)
    $ChildFull = [System.IO.Path]::GetFullPath($ChildPath)
    $Prefix = $RootFull + [System.IO.Path]::DirectorySeparatorChar
    if (-not $ChildFull.StartsWith(
        $Prefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "path is outside bundle root: $ChildFull"
    }
    return $ChildFull.Substring($Prefix.Length).Replace('\', '/')
}

$RelativePathProbe = Get-RelativePathCompat `
    -RootPath $BundleRoot `
    -ChildPath (Join-Path $BundleRoot 'payload/probe.txt')
if ($RelativePathProbe -ne 'payload/probe.txt') {
    throw "PowerShell relative-path compatibility gate failed: $RelativePathProbe"
}
$OutsidePathRejected = $false
try {
    $null = Get-RelativePathCompat `
        -RootPath $BundleRoot `
        -ChildPath (Join-Path (Split-Path $BundleRoot -Parent) 'outside.txt')
}
catch {
    $OutsidePathRejected = $true
}
if (-not $OutsidePathRejected) {
    throw 'PowerShell relative-path confinement negative gate failed'
}

$PayloadFiles = @(
    'repo/ood/issue27ckbv_postformal_recovery_v1.py',
    'scripts/issue27ckbv_validate_and_pack_seed27.sh',
    'scripts/issue27ckbv_recover_postformal_154917.sh',
    'runs/mainline_docs/ckbv_r20_run_grounded_pool_recovery_20260729.md',
    'runs/mainline_docs/hpc_failure_ledger_and_launch_gate_20260725.md'
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
# CKBV r20 post-formal run-grounded recovery

This bundle appends run-grounded evidence rows to the already-emitted raw51
sensitivity audit for AMD job 154917: the fit pool's role decomposition
(support_train 385 + id_calib 809 + ood_val 2,604 = 3,413) and the raw51
target-materialization record (325,067 frozen / 323,714 observable / 1,353
masked on the hydraulic-1 source). It does not submit Slurm work, train a
model, decode a PCAP, change a score, or select a gate. See
payload/runs/mainline_docs/ckbv_r20_run_grounded_pool_recovery_20260729.md
and ledger section 18 in
payload/runs/mainline_docs/hpc_failure_ledger_and_launch_gate_20260725.md.

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
# Use the Windows bsdtar explicitly: a GNU tar earlier in PATH misreads the
# drive-letter colon in D:\... archive paths as a remote host and aborts.
$TarExe = Join-Path $env:SystemRoot 'System32\tar.exe'
if (-not (Test-Path -LiteralPath $TarExe -PathType Leaf)) {
    $TarExe = 'tar'
}
$RecoveryProgram = Join-Path `
    $BundleRoot `
    'payload/repo/ood/issue27ckbv_postformal_recovery_v1.py'
$CompileProbe = @"
from pathlib import Path
path = Path(r'''$RecoveryProgram''')
compile(path.read_text(encoding='utf-8'), str(path), 'exec')
"@
& $Python.Source -B -c $CompileProbe
if ($LASTEXITCODE -ne 0) {
    throw 'recovery Python compile failed'
}
& $Python.Source -B `
    $RecoveryProgram `
    --mode contract-unit
if ($LASTEXITCODE -ne 0) {
    throw 'recovery contract-unit failed'
}

$ForbiddenBytecode = @(
    Get-ChildItem -LiteralPath $BundleRoot -Recurse -Force |
        Where-Object {
            $_.Name -eq '__pycache__' -or
            $_.Extension -eq '.pyc' -or
            $_.Extension -eq '.pyo'
        }
)
if ($ForbiddenBytecode.Count -ne 0) {
    throw (
        'forbidden Python bytecode in bundle staging: ' +
        (($ForbiddenBytecode | ForEach-Object FullName) -join ', ')
    )
}

$Files = Get-ChildItem -LiteralPath $BundleRoot -Recurse -File |
    Where-Object { $_.Name -ne 'SHA256SUMS' } |
    Sort-Object FullName
$HashLines = foreach ($File in $Files) {
    $Relative = Get-RelativePathCompat `
        -RootPath $BundleRoot `
        -ChildPath $File.FullName
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
    & $TarExe -czf $ArchiveName $BundleName
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
    'ckbv_recovery_clean_' + [guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Force -Path $ExtractRoot | Out-Null
try {
    & $TarExe -xzf $Archive -C $ExtractRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'clean extraction failed'
    }
    $CleanBundle = Join-Path $ExtractRoot $BundleName
    & $Python.Source -B `
        (Join-Path $CleanBundle 'payload/repo/ood/issue27ckbv_postformal_recovery_v1.py') `
        --mode contract-unit
    if ($LASTEXITCODE -ne 0) {
        throw 'clean-extract recovery contract-unit failed'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $CleanBundle 'SHA256SUMS'))) {
        throw 'clean-extract SHA256SUMS missing'
    }
    $CleanForbiddenBytecode = @(
        Get-ChildItem -LiteralPath $CleanBundle -Recurse -Force |
            Where-Object {
                $_.Name -eq '__pycache__' -or
                $_.Extension -eq '.pyc' -or
                $_.Extension -eq '.pyo'
            }
    )
    if ($CleanForbiddenBytecode.Count -ne 0) {
        throw 'clean-extract contract generated forbidden Python bytecode'
    }
}
finally {
    Remove-Item -LiteralPath $ExtractRoot -Recurse -Force
}

$Info = Get-Item -LiteralPath $Archive
Write-Output 'CKBV_POSTFORMAL_RECOVERY_BUNDLE_PASS'
Write-Output "BUNDLE=$Archive"
Write-Output "SIZE_BYTES=$($Info.Length)"
Write-Output "SHA256=$ArchiveDigest"
Write-Output "COMMIT=$CommitSha"
