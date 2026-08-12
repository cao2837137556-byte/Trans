param(
  [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
)

$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$GitRoot = (git -C $Repo rev-parse --show-toplevel).Trim()
if ([IO.Path]::GetFullPath($GitRoot).TrimEnd([char[]]'\/') -ne
    [IO.Path]::GetFullPath($Repo).TrimEnd([char[]]'\/')) {
  throw "unexpected Git root: $GitRoot"
}
$Commit = (git -C $Repo rev-parse HEAD).Trim()
$BundleName = 'issue27ckda_d1_representation_probe_20260812'
$Bundle = Join-Path $TransferRoot $BundleName
$Archive = Join-Path $TransferRoot ($BundleName + '_upload_bundle.tar.gz')
$Sidecar = $Archive + '.sha256'
$Verify = Join-Path $TransferRoot ($BundleName + '_clean_verify')

foreach ($target in @($Bundle, $Archive, $Sidecar, $Verify)) {
  if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}
New-Item -ItemType Directory -Force -Path (Join-Path $Bundle 'payload') | Out-Null

function Copy-ScopedFile([string]$Relative) {
  $source = Join-Path $Repo $Relative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "missing bundle input: $Relative" }
  $destination = Join-Path $Bundle ('payload\' + $Relative)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
  Copy-Item -LiteralPath $source -Destination $destination -Force
}

$Files = @(
  'repo\ood\issue27ckda_d1_representation_probe_v1.py',
  'repo\ood\issue27ckda_d1_role_plan_v1.py',
  'repo\ood\issue27ckda_d1_benign_census_v1.py',
  'repo\ood\issue27ckda_d1_target_metadata_v1.py',
  'repo\ood\issue27ckda_d1_e3_embed_v1.py',
  'repo\ood\issue27ckda_d1_probe_runner_v1.py',
  'repo\ood\issue27ckda_d1_metrics_v1.py',
  'repo\ood\issue27ckda_d1_validate_and_pack_v1.py',
  'repo\ood\test_issue27ckda_d1_representation_probe_v1.py',
  'repo\ood\issue27ckbu_unified_tshark_causal_frontend_v1.py',
  'repo\ood\issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py',
  'scripts\issue27ckda_d1_representation_probe_formal.slurm',
  'scripts\issue27ckda_d1_install_and_submit.sh',
  'scripts\issue27ckda_d1_status.sh',
  'runs\mainline_docs\ckda_d1_frozen_representation_probe_preregistered_20260812.md',
  'runs\mainline_docs\ckda_d1_frozen_representation_probe_preregistered_20260812.md.sha256',
  'runs\mainline_docs\ckda_d1_frozen_kimi_verification_20260812.md',
  'runs\mainline_docs\ckda_d1_implementation_report_20260812.md',
  'runs\mainline_docs\ckda_d1_implementation_kimi_review_20260812.md',
  'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv',
  'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv.sha256',
  'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv',
  'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv.sha256'
)
foreach ($relative in $Files) { Copy-ScopedFile $relative }

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$TextExtensions = @('.py', '.sh', '.slurm', '.md', '.txt', '.csv', '.json')
Get-ChildItem -LiteralPath $Bundle -Recurse -File | ForEach-Object {
  if ($TextExtensions -contains $_.Extension.ToLowerInvariant()) {
    $bytes = [IO.File]::ReadAllBytes($_.FullName)
    if ($bytes -contains 0) { throw "NUL byte in text payload: $($_.FullName)" }
    $text = [Text.Encoding]::UTF8.GetString($bytes).Replace("`r`n", "`n").Replace("`r", "`n")
    [IO.File]::WriteAllText($_.FullName, $text, $Utf8NoBom)
  }
}

$Contract = Join-Path $Bundle 'payload\runs\mainline_docs\ckda_d1_frozen_representation_probe_preregistered_20260812.md'
$ContractHash = (Get-FileHash -LiteralPath $Contract -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ContractHash -ne 'ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9') {
  throw 'CKDA D1 FROZEN contract SHA drift'
}
[IO.File]::WriteAllText((Join-Path $Bundle 'bundle_commit.txt'), $Commit + "`n", $Utf8NoBom)
$Identity = [ordered]@{
  status = 'CKDA_D1_BUNDLE_IDENTITY_FROZEN'
  bundle_name = $BundleName
  commit_sha = $Commit
  contract_sha256 = $ContractHash
  d0_bundle_identity = 'issue27ckda_d0_representation_compatibility_20260811_r2'
  d0_manifest_sha256 = '9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689'
  netfound_checkpoint_sha256 = 'e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105'
  final_included = $false
  seed37_47_included = $false
}
[IO.File]::WriteAllText(
  (Join-Path $Bundle 'bundle_identity.json'),
  (($Identity | ConvertTo-Json -Depth 4).Replace("`r`n", "`n") + "`n"),
  $Utf8NoBom
)

$PayloadFiles = Get-ChildItem -LiteralPath $Bundle -Recurse -File | Where-Object { $_.Name -ne 'SHA256SUMS' } | Sort-Object FullName
$Sums = foreach ($file in $PayloadFiles) {
  $relative = $file.FullName.Substring($Bundle.Length + 1).Replace('\', '/')
  $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
}
[IO.File]::WriteAllText((Join-Path $Bundle 'SHA256SUMS'), ($Sums -join "`n") + "`n", $Utf8NoBom)

foreach ($file in Get-ChildItem -LiteralPath $Bundle -Recurse -File) {
  if ($TextExtensions -contains $file.Extension.ToLowerInvariant() -or $file.Name -eq 'SHA256SUMS') {
    if ([IO.File]::ReadAllBytes($file.FullName) -contains 13) { throw "CR byte remains: $($file.FullName)" }
  }
}

tar -czf $Archive -C $TransferRoot $BundleName
if ($LASTEXITCODE -ne 0) { throw "archive build failed: exit $LASTEXITCODE" }
$ArchiveHash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($Sidecar, "$ArchiveHash  $([IO.Path]::GetFileName($Archive))`n", $Utf8NoBom)

New-Item -ItemType Directory -Force -Path $Verify | Out-Null
tar -xzf $Archive -C $Verify
if ($LASTEXITCODE -ne 0) { throw "clean extraction failed: exit $LASTEXITCODE" }
$Extracted = Join-Path $Verify $BundleName
foreach ($line in Get-Content -LiteralPath (Join-Path $Extracted 'SHA256SUMS')) {
  if (-not $line.Trim()) { continue }
  $parts = $line -split '  ', 2
  $path = Join-Path $Extracted $parts[1].Replace('/', '\')
  $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $parts[0]) { throw "clean extraction SHA mismatch: $($parts[1])" }
}
Remove-Item -LiteralPath $Verify -Recurse -Force

[ordered]@{
  status = 'CKDA_D1_BUNDLE_BUILD_PASS'
  bundle = $Bundle
  archive = $Archive
  archive_bytes = (Get-Item -LiteralPath $Archive).Length
  archive_sha256 = $ArchiveHash
  payload_files = $PayloadFiles.Count
  commit_sha = $Commit
  contract_sha256 = $ContractHash
  clean_extract_sha_check = 'PASS'
} | ConvertTo-Json -Depth 4
