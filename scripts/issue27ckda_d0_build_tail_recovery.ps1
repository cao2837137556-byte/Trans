param(
  [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
)

$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$GitRoot = (git -C $Repo rev-parse --show-toplevel).Trim()
if ([IO.Path]::GetFullPath($GitRoot).TrimEnd([char[]]'\/') -ne [IO.Path]::GetFullPath($Repo).TrimEnd([char[]]'\/')) {
  throw "unexpected Git root: $GitRoot"
}
$Commit = (git -C $Repo rev-parse HEAD).Trim()
$Name = 'issue27ckda_d0_tail_recovery_158210_20260811'
$Bundle = Join-Path $TransferRoot $Name
$Archive = Join-Path $TransferRoot ($Name + '_upload_bundle.tar.gz')
$Sidecar = $Archive + '.sha256'

foreach ($target in @($Bundle, $Archive, $Sidecar)) {
  if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}

function Copy-ScopedFile([string]$Relative) {
  $source = Join-Path $Repo $Relative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "missing repo input: $Relative" }
  $destination = Join-Path $Bundle ('payload\' + $Relative)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
  Copy-Item -LiteralPath $source -Destination $destination -Force
}

Copy-ScopedFile 'repo\ood\issue27ckda_d0_validate_and_pack_v1.py'
Copy-ScopedFile 'scripts\issue27ckda_d0_tail_recover_158210.sh'

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
Get-ChildItem -LiteralPath $Bundle -Recurse -File | ForEach-Object {
  $text = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($_.FullName)).Replace("`r`n", "`n").Replace("`r", "`n")
  [IO.File]::WriteAllText($_.FullName, $text, $Utf8NoBom)
}
[IO.File]::WriteAllText((Join-Path $Bundle 'recovery_commit.txt'), $Commit + "`n", $Utf8NoBom)
$identity = [ordered]@{
  bundle_name = $Name
  commit_sha = $Commit
  original_job_id = 158210
  original_job_state_required = 'FAILED'
  recovery_class = 'POST_RESULT_VALIDATION_PACKAGING'
  scientific_recomputation = $false
  slurm_submission = $false
  final_included = $false
  seed37_47_included = $false
}
[IO.File]::WriteAllText(
  (Join-Path $Bundle 'recovery_identity.json'),
  (($identity | ConvertTo-Json -Depth 4).Replace("`r`n", "`n").Replace("`r", "`n") + "`n"),
  $Utf8NoBom
)

$files = Get-ChildItem -LiteralPath $Bundle -Recurse -File | Sort-Object FullName
$lines = foreach ($file in $files) {
  $relative = $file.FullName.Substring($Bundle.Length + 1).Replace('\', '/')
  $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
}
[IO.File]::WriteAllText((Join-Path $Bundle 'SHA256SUMS'), ($lines -join "`n") + "`n", $Utf8NoBom)

foreach ($file in Get-ChildItem -LiteralPath $Bundle -Recurse -File) {
  if ([IO.File]::ReadAllBytes($file.FullName) -contains 13) { throw "CR byte in recovery payload: $($file.FullName)" }
}

tar -czf $Archive -C $TransferRoot $Name
if ($LASTEXITCODE -ne 0) { throw "tail-recovery tar build failed: exit $LASTEXITCODE" }
tar -tzf $Archive | Out-Null
if ($LASTEXITCODE -ne 0) { throw "tail-recovery tar readback failed: exit $LASTEXITCODE" }
$hash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($Sidecar, "$hash  $([IO.Path]::GetFileName($Archive))`n", $Utf8NoBom)

Write-Output "CKDA_D0_TAIL_RECOVERY_BUILD_PASS"
Write-Output "bundle=$Bundle"
Write-Output "archive=$Archive"
Write-Output "bytes=$((Get-Item -LiteralPath $Archive).Length)"
Write-Output "sha256=$hash"
