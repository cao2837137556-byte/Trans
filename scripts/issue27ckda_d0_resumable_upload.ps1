param(
  [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer',
  [string]$HostAlias = 'school-hpc',
  [string]$RemoteWork = '/public/home/jiangxinwei.zr/work',
  [string]$IdentityFile = "$env:USERPROFILE\.ssh\id_ed25519_school_hpc_ckda",
  [string]$WslDistro = 'Ubuntu-24.04',
  [string]$RemoteUser = 'jiangxinwei.zr',
  [string]$RemoteHost = '172.24.3.168',
  [int]$AuthMaxAttempts = 12,
  [int]$AuthRetrySeconds = 15,
  [int]$MaxAttempts = 100,
  [int]$RetrySeconds = 15
)

$ErrorActionPreference = 'Stop'

function ConvertTo-WslPath([string]$WindowsPath) {
  $FullPath = [IO.Path]::GetFullPath($WindowsPath)
  if ($FullPath -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "unsupported Windows path for WSL transfer: $FullPath"
  }
  $Drive = $Matches[1].ToLowerInvariant()
  $Tail = $Matches[2].Replace('\', '/')
  return "/mnt/$Drive/$Tail"
}

$ArchiveName = 'issue27ckda_d0_representation_compatibility_20260811_upload_bundle.tar.gz'
$ExpectedSha256 = 'c979638ecf430946cdd9e2614b082c42bc5f78f6cadd4bf545ff88afd70aade9'
$ExpectedBytes = 665814425
$Archive = Join-Path $TransferRoot $ArchiveName
$Sidecar = "$Archive.sha256"
$Target = "$RemoteUser@$RemoteHost"
$WslHome = (& wsl.exe -d $WslDistro -- bash -lc 'printf %s "$HOME"').Trim()
$WslArchive = ConvertTo-WslPath $Archive
$WslSidecar = ConvertTo-WslPath $Sidecar
$WslIdentityFile = "$WslHome/.ssh/id_ed25519_school_hpc_ckda"

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
if (-not $WslHome -or -not $WslArchive -or -not $WslSidecar) {
  throw 'failed to resolve CKDA upload paths inside WSL'
}
& wsl.exe -d $WslDistro -- test -f $WslIdentityFile
if ($LASTEXITCODE -ne 0) {
  throw 'CKDA WSL transfer key is unavailable; run issue27ckda_d0_install_transfer_key.ps1 first'
}

$PreviousErrorActionPreference = $ErrorActionPreference
$KeyTestExit = 255
for ($authAttempt = 1; $authAttempt -le $AuthMaxAttempts; $authAttempt++) {
  $ErrorActionPreference = 'Continue'
  & wsl.exe -d $WslDistro -- ssh `
    -o BatchMode=yes `
    -o ConnectTimeout=15 `
    -o ConnectionAttempts=1 `
    -o IdentitiesOnly=yes `
    -i $WslIdentityFile $Target 'command -v rsync >/dev/null' 2>$null
  $KeyTestExit = $LASTEXITCODE
  $ErrorActionPreference = $PreviousErrorActionPreference
  if ($KeyTestExit -eq 0) {
    "CKDA_D0_TRANSFER_AUTH_PASS attempt=$authAttempt"
    break
  }
  "CKDA_D0_TRANSFER_AUTH_RETRY attempt=$authAttempt max=$AuthMaxAttempts ssh_exit=$KeyTestExit"
  if ($authAttempt -lt $AuthMaxAttempts) {
    Start-Sleep -Seconds $AuthRetrySeconds
  }
}
if ($KeyTestExit -ne 0) {
  throw 'CKDA transfer key authentication is unavailable; run issue27ckda_d0_install_transfer_key.ps1 first'
}

$RsyncShell = "ssh -i $WslIdentityFile -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=20"
$RemoteArchive = "${Target}:$RemoteWork/$ArchiveName"
$RemoteSidecar = "${Target}:$RemoteWork/$ArchiveName.sha256"

for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
  "CKDA_D0_RSYNC_ATTEMPT attempt=$attempt max=$MaxAttempts utc=$([DateTime]::UtcNow.ToString('o'))"
  $ErrorActionPreference = 'Continue'
  & wsl.exe -d $WslDistro -- rsync `
    --partial `
    --append-verify `
    --human-readable `
    --info=progress2 `
    --timeout=120 `
    -e $RsyncShell `
    $WslArchive $RemoteArchive
  $TransferExit = $LASTEXITCODE
  $ErrorActionPreference = $PreviousErrorActionPreference
  if ($TransferExit -eq 0) {
    $ErrorActionPreference = 'Continue'
    & wsl.exe -d $WslDistro -- rsync `
      --partial `
      --human-readable `
      --timeout=120 `
      -e $RsyncShell `
      $WslSidecar $RemoteSidecar
    $SidecarExit = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    if ($SidecarExit -eq 0) {
      $VerifyCommand = "cd '$RemoteWork' && test `$(stat -c %s '$ArchiveName') = '$ExpectedBytes' && test `$(sha256sum '$ArchiveName' | awk '{print `$1}') = '$ExpectedSha256' && sha256sum -c '$ArchiveName.sha256'"
      $ErrorActionPreference = 'Continue'
      & wsl.exe -d $WslDistro -- ssh `
        -o BatchMode=yes `
        -o ConnectTimeout=30 `
        -o IdentitiesOnly=yes `
        -i $WslIdentityFile $Target $VerifyCommand
      $VerifyExit = $LASTEXITCODE
      $ErrorActionPreference = $PreviousErrorActionPreference
      if ($VerifyExit -eq 0) {
        "CKDA_D0_RESUMABLE_UPLOAD_PASS transport=rsync attempts=$attempt bytes=$ExpectedBytes sha256=$ExpectedSha256"
        return
      }
      "CKDA_D0_REMOTE_VERIFY_RETRY attempt=$attempt ssh_exit=$VerifyExit"
    } else {
      "CKDA_D0_SIDECAR_RETRY attempt=$attempt rsync_exit=$SidecarExit"
    }
  } else {
    "CKDA_D0_TRANSPORT_RETRY attempt=$attempt rsync_exit=$TransferExit"
  }
  if ($attempt -lt $MaxAttempts) {
    Start-Sleep -Seconds $RetrySeconds
  }
}
throw "CKDA resumable upload exhausted $MaxAttempts attempts"
