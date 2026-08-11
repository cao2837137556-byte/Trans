param(
  [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer',
  [string]$OfficialRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer\ckda_d0_official_sources_20260811',
  [string]$LinuxWheelhouse = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer\ckda_d0_wheelhouse_tmp'
)

$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$GitRoot = (git -C $Repo rev-parse --show-toplevel).Trim()
if ($GitRoot -ne $Repo) { throw "unexpected Git root: $GitRoot" }
$Commit = (git -C $Repo rev-parse HEAD).Trim()
$BundleName = 'issue27ckda_d0_representation_compatibility_20260811'
$Bundle = Join-Path $TransferRoot $BundleName
$Archive = Join-Path $TransferRoot ($BundleName + '_upload_bundle.tar.gz')
$ArchiveSidecar = $Archive + '.sha256'

foreach ($target in @($Bundle, $Archive, $ArchiveSidecar)) {
  if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}
New-Item -ItemType Directory -Force -Path (Join-Path $Bundle 'payload') | Out-Null

function Copy-ScopedFile([string]$Relative) {
  $source = Join-Path $Repo $Relative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "missing repo input: $Relative" }
  $destination = Join-Path $Bundle ('payload\' + $Relative)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
  Copy-Item -LiteralPath $source -Destination $destination -Force
}

$RepoFiles = @(
  'repo\ood\issue27ckda_d0_representation_compatibility_audit_v1.py',
  'repo\ood\issue27ckda_d0_resource_pilot_v1.py',
  'repo\ood\issue27ckda_d0_validate_and_pack_v1.py',
  'repo\ood\issue27ckbu_unified_tshark_causal_frontend_v1.py',
  'scripts\issue27ckda_d0_representation_compatibility_audit_formal.slurm',
  'scripts\issue27ckda_d0_install_and_submit.sh',
  'scripts\issue27ckda_d0_status.sh',
  'runs\mainline_docs\ckda_d0_representation_compatibility_audit_preregistered_20260811.md',
  'runs\mainline_docs\ckda_d0_representation_compatibility_audit_preregistered_20260811.md.sha256',
  'runs\mainline_docs\ckda_d0_official_candidate_evidence_20260811.json',
  'runs\mainline_docs\ckda_d0_official_evidence_manifest_20260811.csv',
  'runs\mainline_docs\ckda_d0_p0_rulings_kimi_20260811.md',
  'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv',
  'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv.sha256',
  'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv',
  'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv.sha256',
  'runs\mainline_docs\ckbu_ton_raw_pcap_pilot_manifest_20260723.csv'
)
foreach ($relative in $RepoFiles) { Copy-ScopedFile $relative }

$Vendor = Join-Path $Bundle 'payload\vendor'
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null
$NetFoundSource = Join-Path $OfficialRoot 'netFound'
if (-not (Test-Path -LiteralPath (Join-Path $NetFoundSource 'src') -PathType Container)) {
  throw 'official netFound source is missing'
}
$NetFoundDest = Join-Path $Vendor 'netFound'
New-Item -ItemType Directory -Force -Path $NetFoundDest | Out-Null
Copy-Item -LiteralPath (Join-Path $NetFoundSource 'src') -Destination $NetFoundDest -Recurse -Force
Copy-Item -LiteralPath (Join-Path $NetFoundSource 'LICENSE') -Destination $NetFoundDest -Force
Copy-Item -LiteralPath (Join-Path $NetFoundSource 'configs\DefaultConfigNoTCPOptions.json') -Destination $NetFoundDest -Force
Set-Content -LiteralPath (Join-Path $NetFoundDest 'OFFICIAL_REPO_COMMIT.txt') -Value 'b3ab5a3aa72640cc725ef207fb0145b039a57d35' -Encoding ascii

$ModelDest = Join-Path $Vendor 'netFound-base'
New-Item -ItemType Directory -Force -Path $ModelDest | Out-Null
$ConfigSource = Join-Path $OfficialRoot 'weights\netFound-base-config.json'
$WeightSource = Join-Path $OfficialRoot 'weights\netFound-base-model.safetensors.complete'
if ((Get-FileHash -LiteralPath $ConfigSource -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'e22262d4b840a0055915f6c48e9c64d04e790f80e907fa9dc06df855eff05401') {
  throw 'official netFound config SHA mismatch'
}
if ((Get-Item -LiteralPath $WeightSource).Length -ne 698780900) { throw 'official netFound weight byte count mismatch' }
if ((Get-FileHash -LiteralPath $WeightSource -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105') {
  throw 'official netFound weight SHA mismatch'
}
Copy-Item -LiteralPath $ConfigSource -Destination (Join-Path $ModelDest 'config.json') -Force
Copy-Item -LiteralPath $WeightSource -Destination (Join-Path $ModelDest 'model.safetensors') -Force

Add-Type -AssemblyName System.IO.Compression.FileSystem
$VendorPy = Join-Path $Bundle 'payload\vendor_py'
New-Item -ItemType Directory -Force -Path $VendorPy | Out-Null
$WheelPatterns = @(
  'transformers-4.57.3-*.whl',
  'safetensors-0.6.2-cp38-abi3-manylinux*.whl',
  'psutil-7.1.3-cp36-abi3-manylinux*.whl',
  'huggingface_hub-0.36.2-*.whl',
  'tokenizers-0.22.2-cp39-abi3-manylinux*.whl',
  'fsspec-2025.10.0-*.whl',
  'packaging-26.3-*.whl',
  'pyyaml-6.0.3-cp39-cp39-manylinux*.whl',
  'regex-2026.1.15-cp39-cp39-manylinux*.whl',
  'tqdm-4.70.0-*.whl',
  'typing_extensions-4.16.0-*.whl',
  'filelock-3.19.1-*.whl',
  'requests-2.32.5-*.whl',
  'charset_normalizer-3.4.9-cp39-cp39-manylinux*.whl',
  'idna-3.18-*.whl',
  'urllib3-2.6.3-*.whl',
  'certifi-2026.7.22-*.whl'
)
$Wheels = @()
foreach ($pattern in $WheelPatterns) {
  $matches = @(Get-ChildItem -LiteralPath $LinuxWheelhouse -File -Filter $pattern)
  if ($matches.Count -ne 1) { throw "wheel identity is not unique for $pattern ($($matches.Count))" }
  $Wheels += $matches[0]
  [System.IO.Compression.ZipFile]::ExtractToDirectory($matches[0].FullName, $VendorPy)
}

Get-ChildItem -LiteralPath (Join-Path $Bundle 'payload') -Directory -Recurse -Filter '__pycache__' |
  Sort-Object FullName -Descending | Remove-Item -Recurse -Force

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$TextExtensions = @('.py', '.sh', '.slurm', '.md', '.txt', '.csv', '.json')
Get-ChildItem -LiteralPath $Bundle -Recurse -File | Where-Object { $TextExtensions -contains $_.Extension.ToLowerInvariant() } | ForEach-Object {
  $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
  if ($bytes -contains 0) { throw "NUL byte in text payload: $($_.FullName)" }
  $text = [System.Text.Encoding]::UTF8.GetString($bytes).Replace("`r`n", "`n").Replace("`r", "`n")
  [System.IO.File]::WriteAllText($_.FullName, $text, $Utf8NoBom)
}

$BundledContract = Join-Path $Bundle 'payload\runs\mainline_docs\ckda_d0_representation_compatibility_audit_preregistered_20260811.md'
if ((Get-FileHash -LiteralPath $BundledContract -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5') {
  throw 'FROZEN contract SHA drift after LF normalization'
}

[System.IO.File]::WriteAllText((Join-Path $Bundle 'bundle_commit.txt'), $Commit + "`n", $Utf8NoBom)
$Identity = [ordered]@{
  bundle_name = $BundleName
  commit_sha = $Commit
  contract_sha256 = 'ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5'
  netfound_repo_commit = 'b3ab5a3aa72640cc725ef207fb0145b039a57d35'
  netfound_model_commit = 'b812e625999165376ddb47a39d0d5579d4edce89'
  netfound_checkpoint_bytes = 698780900
  netfound_checkpoint_sha256 = 'e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105'
  linux_wheels = @($Wheels | ForEach-Object { [ordered]@{ name = $_.Name; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() } })
  final_included = $false
  seed37_47_included = $false
}
[System.IO.File]::WriteAllText((Join-Path $Bundle 'bundle_identity.json'), ($Identity | ConvertTo-Json -Depth 5) + "`n", $Utf8NoBom)

$Files = Get-ChildItem -LiteralPath $Bundle -Recurse -File | Where-Object { $_.Name -ne 'SHA256SUMS' } | Sort-Object FullName
$SumLines = foreach ($file in $Files) {
  $relative = $file.FullName.Substring($Bundle.Length + 1).Replace('\', '/')
  $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
}
[System.IO.File]::WriteAllText((Join-Path $Bundle 'SHA256SUMS'), ($SumLines -join "`n") + "`n", $Utf8NoBom)

foreach ($file in Get-ChildItem -LiteralPath $Bundle -Recurse -File) {
  if ($TextExtensions -contains $file.Extension.ToLowerInvariant() -or $file.Name -eq 'SHA256SUMS') {
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
    if ($bytes -contains 13) { throw "CR byte remains in text payload: $($file.FullName)" }
  }
}

tar -czf $Archive -C $TransferRoot $BundleName
if ($LASTEXITCODE -ne 0) { throw "tar build failed: exit $LASTEXITCODE" }
$ArchiveHash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText($ArchiveSidecar, "$ArchiveHash  $([IO.Path]::GetFileName($Archive))`n", $Utf8NoBom)

$VerifyRoot = Join-Path $TransferRoot ($BundleName + '_clean_verify')
if (Test-Path -LiteralPath $VerifyRoot) { Remove-Item -LiteralPath $VerifyRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $VerifyRoot | Out-Null
tar -xzf $Archive -C $VerifyRoot
if ($LASTEXITCODE -ne 0) { throw "clean extraction failed: exit $LASTEXITCODE" }
$Extracted = Join-Path $VerifyRoot $BundleName
foreach ($line in Get-Content -LiteralPath (Join-Path $Extracted 'SHA256SUMS')) {
  if (-not $line.Trim()) { continue }
  $parts = $line -split '  ', 2
  $actual = (Get-FileHash -LiteralPath (Join-Path $Extracted $parts[1].Replace('/', '\')) -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $parts[0]) { throw "clean-extraction SHA mismatch: $($parts[1])" }
}
Remove-Item -LiteralPath $VerifyRoot -Recurse -Force

[ordered]@{
  status = 'CKDA_D0_BUNDLE_BUILD_PASS'
  bundle = $Bundle
  archive = $Archive
  archive_bytes = (Get-Item -LiteralPath $Archive).Length
  archive_sha256 = $ArchiveHash
  payload_files = $Files.Count
  commit_sha = $Commit
  netfound_checkpoint_bytes = 698780900
  netfound_checkpoint_sha256 = 'e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105'
  clean_extract_sha_check = 'PASS'
  lf_only = 'PASS'
} | ConvertTo-Json -Depth 3
