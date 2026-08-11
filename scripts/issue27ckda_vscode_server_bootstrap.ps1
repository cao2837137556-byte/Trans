param(
  [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer',
  [string]$HostAlias = 'school-hpc',
  [string]$IdentityFile = "$env:USERPROFILE\.ssh\id_ed25519_school_hpc_ckda",
  [int]$MaxAttempts = 100,
  [int]$RetrySeconds = 5
)

$ErrorActionPreference = 'Stop'
$Commit = 'df53daabb18cd157bdb08c7f01c34df936cf12f4'
$ArchiveName = "vscode-server-$Commit-linux-x64.tar.gz"
$Archive = Join-Path $TransferRoot $ArchiveName
$ExpectedBytes = 227503960
$ExpectedSha256 = 'adf5816366a9a8c430745f96fd783df70e7606a35311999aac53b70b257aebc0'
$RemoteTarget = "/public/home/jiangxinwei.zr/.vscode-server/bin/$Commit"
$RemoteArchive = "$RemoteTarget/vscode-server.tar.gz"

foreach ($path in @($Archive, $IdentityFile)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "missing VS Code bootstrap input: $path"
  }
}
if ((Get-Item -LiteralPath $Archive).Length -ne $ExpectedBytes) {
  throw 'VS Code server archive byte count mismatch'
}
if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedSha256) {
  throw 'VS Code server archive SHA-256 mismatch'
}

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& ssh.exe -o BatchMode=yes -o ConnectTimeout=15 -i $IdentityFile $HostAlias 'true' 2>$null
$KeyTestExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($KeyTestExit -ne 0) {
  throw 'CKDA transfer key authentication is unavailable; run issue27ckda_d0_install_transfer_key.ps1 first'
}

& ssh.exe -o BatchMode=yes -i $IdentityFile $HostAlias "mkdir -p '$RemoteTarget'"
if ($LASTEXITCODE -ne 0) {
  throw 'failed to prepare remote VS Code server directory'
}

$ArchiveSftp = $Archive.Replace('\', '/')
$BatchFile = [IO.Path]::GetTempFileName()
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Batch = "reput `"$ArchiveSftp`" `"$RemoteArchive`"`n"
[IO.File]::WriteAllText($BatchFile, $Batch, $Utf8NoBom)

try {
  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    "VSCODE_SERVER_TRANSFER_ATTEMPT attempt=$attempt max=$MaxAttempts utc=$([DateTime]::UtcNow.ToString('o'))"
    & sftp.exe -b $BatchFile -B 32768 -R 4 -l 6000 `
      -o BatchMode=yes -o ConnectTimeout=30 `
      -o ServerAliveInterval=15 -o ServerAliveCountMax=20 `
      -i $IdentityFile $HostAlias
    $TransferExit = $LASTEXITCODE
    if ($TransferExit -eq 0) {
      $VerifyCommand = "test `$(stat -c %s '$RemoteArchive') = '$ExpectedBytes' && test `$(sha256sum '$RemoteArchive' | awk '{print `$1}') = '$ExpectedSha256' && touch '$RemoteArchive.done'"
      & ssh.exe -o BatchMode=yes -o ConnectTimeout=30 `
        -o ServerAliveInterval=15 -o ServerAliveCountMax=20 `
        -i $IdentityFile $HostAlias $VerifyCommand
      if ($LASTEXITCODE -eq 0) {
        "VSCODE_SERVER_MANUAL_BOOTSTRAP_PASS commit=$Commit bytes=$ExpectedBytes sha256=$ExpectedSha256"
        return
      }
      "VSCODE_SERVER_REMOTE_VERIFY_RETRY attempt=$attempt"
    } else {
      "VSCODE_SERVER_TRANSPORT_RETRY attempt=$attempt sftp_exit=$TransferExit"
    }
    Start-Sleep -Seconds $RetrySeconds
  }
  throw "VS Code server bootstrap exhausted $MaxAttempts attempts"
}
finally {
  if (Test-Path -LiteralPath $BatchFile) {
    Remove-Item -LiteralPath $BatchFile -Force
  }
}
