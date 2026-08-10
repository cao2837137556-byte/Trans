# CKCZ seed-27 upload bundle builder.
# Stages only the reviewed CKCZ payload, normalizes text to LF, executes the
# 18-test contract suite, verifies immutable sidecars, archives, extracts into
# a second temporary root, and independently verifies every bundled SHA-256.
$ErrorActionPreference = 'Stop'

$Worktree = 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline'
$OutDir = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
$BundleName = 'issue27ckcz_endpoint_pair_conflict_diagnostic_20260810'
$Archive = Join-Path $OutDir ($BundleName + '_upload_bundle.tar.gz')
$Utf8NoBom = New-Object Text.UTF8Encoding($false)

$Copies = @(
  @{ Src = 'repo\ood\issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py'; Dst = 'payload\repo\ood\issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py' },
  @{ Src = 'repo\ood\issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py'; Dst = 'payload\repo\ood\issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py' },
  @{ Src = 'scripts\issue27ckcz_endpoint_pair_conflict_diagnostic_formal.slurm'; Dst = 'payload\scripts\issue27ckcz_endpoint_pair_conflict_diagnostic_formal.slurm' },
  @{ Src = 'scripts\issue27ckcz_install_and_submit.sh'; Dst = 'payload\scripts\issue27ckcz_install_and_submit.sh' },
  @{ Src = 'scripts\issue27ckcz_validate_and_pack_seed27.sh'; Dst = 'payload\scripts\issue27ckcz_validate_and_pack_seed27.sh' },
  @{ Src = 'runs\mainline_docs\ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md'; Dst = 'payload\runs\mainline_docs\ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md' },
  @{ Src = 'runs\mainline_docs\ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md.sha256'; Dst = 'payload\runs\mainline_docs\ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md.sha256' },
  @{ Src = 'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv'; Dst = 'payload\runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv' },
  @{ Src = 'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv.sha256'; Dst = 'payload\runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv.sha256' },
  @{ Src = 'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv'; Dst = 'payload\runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv' },
  @{ Src = 'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv.sha256'; Dst = 'payload\runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv.sha256' },
  @{ Src = 'runs\mainline_docs\ckcz_attack_family_scope_clarification_20260809.md'; Dst = 'payload\runs\mainline_docs\ckcz_attack_family_scope_clarification_20260809.md' },
  @{ Src = 'runs\mainline_docs\ckcz_implementation_ready_for_kimi_review_20260809.md'; Dst = 'payload\runs\mainline_docs\ckcz_implementation_ready_for_kimi_review_20260809.md' },
  @{ Src = 'runs\mainline_docs\ckcz_implementation_kimi_final_review_20260809.md'; Dst = 'payload\runs\mainline_docs\ckcz_implementation_kimi_final_review_20260809.md' }
)

function Assert-SafeTempPath([string]$Path, [string]$ExpectedLeaf) {
  $resolved = [IO.Path]::GetFullPath($Path)
  $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
  if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "refusing non-temp recursive target: $resolved"
  }
  if ([IO.Path]::GetFileName($resolved) -ne $ExpectedLeaf) {
    throw "refusing unexpected temp leaf: $resolved"
  }
  return $resolved
}

function Remove-SafeTemp([string]$Path, [string]$ExpectedLeaf) {
  $resolved = Assert-SafeTempPath $Path $ExpectedLeaf
  if (Test-Path -LiteralPath $resolved) {
    Remove-Item -LiteralPath $resolved -Recurse -Force
  }
}

function Write-LfUtf8([string]$Path, [string]$Text) {
  $normalized = $Text -replace "`r`n", "`n" -replace "`r", ''
  [IO.File]::WriteAllText($Path, $normalized, $Utf8NoBom)
}

function Assert-FileSha([string]$Path, [string]$Expected) {
  $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $Expected) { throw "SHA-256 drift: $Path actual=$actual expected=$Expected" }
}

$StageLeaf = $BundleName + '_staging'
$VerifyLeaf = $BundleName + '_verify'
$Staging = Assert-SafeTempPath (Join-Path $env:TEMP $StageLeaf) $StageLeaf
$VerifyStaging = Assert-SafeTempPath (Join-Path $env:TEMP $VerifyLeaf) $VerifyLeaf
$Root = Join-Path $Staging $BundleName
$VerifyRoot = Join-Path $VerifyStaging $BundleName
$TarExe = Join-Path $env:SystemRoot 'System32\tar.exe'

Remove-SafeTemp $Staging $StageLeaf
Remove-SafeTemp $VerifyStaging $VerifyLeaf
New-Item -ItemType Directory -Force -Path $Root | Out-Null

try {
  foreach ($copy in $Copies) {
    $source = Join-Path $Worktree $copy.Src
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "missing CKCZ bundle source: $source" }
    $destination = Join-Path $Root $copy.Dst
    New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
  }

  Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
    $text = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($_.FullName))
    Write-LfUtf8 $_.FullName $text
  }

  Assert-FileSha (Join-Path $Root 'payload\runs\mainline_docs\ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md') 'dad558902f2dfe2dc0dd4bf76cbf2e9e727be9f5d22ed2e91a5267586e8d3fde'
  Assert-FileSha (Join-Path $Root 'payload\runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv') '65b4804109914d50c3efb6b9ae40d2b7d7befc903be571a92ebee90624ab6de7'
  Assert-FileSha (Join-Path $Root 'payload\runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv') 'be4ad12a9b0807b15b120d91ec2f9519a1743120ef0e9f04e0d8bab573252c49'

  $contract = Join-Path $Root 'payload\repo\ood\issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py'
  $previousNoBytecode = $env:PYTHONDONTWRITEBYTECODE
  $env:PYTHONDONTWRITEBYTECODE = '1'
  try {
    & python $contract
    if ($LASTEXITCODE -ne 0) { throw "CKCZ contract tests failed with exit $LASTEXITCODE" }
  }
  finally {
    if ($null -eq $previousNoBytecode) {
      Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    }
    else {
      $env:PYTHONDONTWRITEBYTECODE = $previousNoBytecode
    }
  }
  $forbiddenPayload = @(Get-ChildItem -LiteralPath $Root -Recurse -Force | Where-Object {
      $_.Name -eq '__pycache__' -or $_.Extension -eq '.pyc'
    })
  if ($forbiddenPayload.Count -ne 0) {
    throw "generated Python cache entered CKCZ payload: $($forbiddenPayload.FullName -join ', ')"
  }

  $head = (git -C $Worktree rev-parse HEAD).Trim()
  Write-LfUtf8 (Join-Path $Root 'bundle_commit.txt') ($head + "`n")

  $sums = New-Object System.Collections.Generic.List[string]
  Get-ChildItem -LiteralPath $Root -Recurse -File | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($Root.Length + 1) -replace '\\', '/'
    if ($relative -ne 'SHA256SUMS') {
      $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
      $sums.Add("$hash  $relative")
    }
  }
  Write-LfUtf8 (Join-Path $Root 'SHA256SUMS') (($sums -join "`n") + "`n")
  $expectedFileCount = $Copies.Count + 2  # reviewed copies + bundle_commit + SHA256SUMS
  $actualFileCount = @(Get-ChildItem -LiteralPath $Root -Recurse -File).Count
  if ($actualFileCount -ne $expectedFileCount) {
    throw "CKCZ bundle member-count drift: actual=$actualFileCount expected=$expectedFileCount"
  }

  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  $resolvedOut = [IO.Path]::GetFullPath($OutDir).TrimEnd('\')
  if ([IO.Path]::GetFullPath((Split-Path $Archive)) -ne $resolvedOut) {
    throw "archive parent drift: $Archive"
  }
  if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
  if (Test-Path -LiteralPath ($Archive + '.sha256')) { Remove-Item -LiteralPath ($Archive + '.sha256') -Force }
  & $TarExe -C $Staging -czf $Archive $BundleName
  if ($LASTEXITCODE -ne 0) { throw "tar creation failed with exit $LASTEXITCODE" }

  New-Item -ItemType Directory -Force -Path $VerifyStaging | Out-Null
  & $TarExe -C $VerifyStaging -xzf $Archive
  if ($LASTEXITCODE -ne 0) { throw "tar extraction failed with exit $LASTEXITCODE" }
  if (-not (Test-Path -LiteralPath $VerifyRoot -PathType Container)) { throw "verified archive root missing" }

  foreach ($line in Get-Content -LiteralPath (Join-Path $VerifyRoot 'SHA256SUMS')) {
    if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { throw "invalid SHA256SUMS line: $line" }
    $expected = $Matches[1]
    $relative = $Matches[2] -replace '/', '\'
    $verifiedFile = Join-Path $VerifyRoot $relative
    if (-not (Test-Path -LiteralPath $verifiedFile -PathType Leaf)) { throw "archive member missing: $relative" }
    Assert-FileSha $verifiedFile $expected
  }

  $archiveSha = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
  Write-LfUtf8 ($Archive + '.sha256') ("$archiveSha  $([IO.Path]::GetFileName($Archive))`n")
  "CKCZ_BUNDLE_VALIDATED $Archive"
  "CKCZ_BUNDLE_SHA256 $archiveSha"
  "CKCZ_BUNDLE_COMMIT $head"
}
finally {
  Remove-SafeTemp $Staging $StageLeaf
  Remove-SafeTemp $VerifyStaging $VerifyLeaf
}
