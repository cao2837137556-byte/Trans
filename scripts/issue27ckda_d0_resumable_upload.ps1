param(
  [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer',
  [string]$HostAlias = 'school-hpc',
  [string]$RemoteWork = '/public/home/jiangxinwei.zr/work',
  [string]$IdentityFile = "$env:USERPROFILE\.ssh\id_ed25519_school_hpc_ckda",
  [int]$MaxAttempts = 100,
  [int]$RetrySeconds = 5
)

$ErrorActionPreference = 'Stop'
$ArchiveName = 'issue27ckda_d0_representation_compatibility_20260811_upload_bundle.tar.gz'
$ExpectedSha256 = 'c979638ecf430946cdd9e2614b082c42bc5f78f6cadd4bf545ff88afd70aade9'
$ExpectedBytes = 665814425
$Archive = Join-Path $TransferRoot $ArchiveName
$Sidecar = "$Archive.sha256"

foreach ($path in @($Archive, $Sidecar, $IdentityFile)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "missing CKDA resumable-upload input: $path"
  }
}
if ((Get-Item -LiteralPath $Archive).Length -ne $ExpectedBytes) {
  throw 'CKDA archive byte count mismatch'
}
$ActualSha256 = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
$SidecarSha256 = ((Get-Content -LiteralPath $Sidecar -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
if ($ActualSha256 -ne $ExpectedSha256 -or $SidecarSha256 -ne $ExpectedSha256) {
  throw "CKDA archive identity mismatch: actual=$ActualSha256 sidecar=$SidecarSha256"
}

$ArchiveSftp = $Archive.Replace('\', '/')
$SidecarSftp = $Sidecar.Replace('\', '/')
$BatchFile = [IO.Path]::GetTempFileName()
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Batch = @(
  "reput `"$ArchiveSftp`" `"$RemoteWork/$ArchiveName`"",
  "put `"$SidecarSftp`" `"$RemoteWork/$ArchiveName.sha256`""
) -join "`n"
[IO.File]::WriteAllText($BatchFile, $Batch + "`n", $Utf8NoBom)

try {
  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    "CKDA_D0_TRANSFER_ATTEMPT attempt=$attempt max=$MaxAttempts utc=$([DateTime]::UtcNow.ToString('o'))"
    & sftp.exe -b $BatchFile -B 32768 -R 4 -l 6000 `
      -o BatchMode=yes `
      -o ConnectTimeout=30 `
      -o ServerAliveInterval=15 `
      -o ServerAliveCountMax=20 `
      -i $IdentityFile $HostAlias
    $TransferExit = $LASTEXITCODE
    if ($TransferExit -eq 0) {
      $VerifyCommand = "cd '$RemoteWork' && test `$(stat -c %s '$ArchiveName') = '$ExpectedBytes' && test `$(sha256sum '$ArchiveName' | awk '{print `$1}') = '$ExpectedSha256' && sha256sum -c '$ArchiveName.sha256'"
      & ssh.exe -o BatchMode=yes -o ConnectTimeout=30 `
        -o ServerAliveInterval=15 -o ServerAliveCountMax=20 `
        -i $IdentityFile $HostAlias $VerifyCommand
      if ($LASTEXITCODE -eq 0) {
        "CKDA_D0_RESUMABLE_UPLOAD_PASS attempts=$attempt bytes=$ExpectedBytes sha256=$ExpectedSha256"
        return
      }
      "CKDA_D0_REMOTE_VERIFY_RETRY attempt=$attempt"
    } else {
      "CKDA_D0_TRANSPORT_RETRY attempt=$attempt sftp_exit=$TransferExit"
    }
    Start-Sleep -Seconds $RetrySeconds
  }
  throw "CKDA resumable upload exhausted $MaxAttempts attempts"
}
finally {
  if (Test-Path -LiteralPath $BatchFile) {
    Remove-Item -LiteralPath $BatchFile -Force
  }
}
