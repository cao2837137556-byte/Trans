param(
  [string]$HostAlias = 'school-hpc',
  [string]$IdentityFile = "$env:USERPROFILE\.ssh\id_ed25519_school_hpc_ckda",
  [string]$WslDistro = 'Ubuntu-24.04',
  [string]$RemoteUser = 'jiangxinwei.zr',
  [string]$RemoteHost = '172.24.3.168'
)

$ErrorActionPreference = 'Stop'
$WslKeyName = 'id_ed25519_school_hpc_ckda'
$PublicKey = "$IdentityFile.pub"

function ConvertTo-WslPath([string]$WindowsPath) {
  $FullPath = [IO.Path]::GetFullPath($WindowsPath)
  if ($FullPath -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "unsupported Windows path for WSL transfer: $FullPath"
  }
  $Drive = $Matches[1].ToLowerInvariant()
  $Tail = $Matches[2].Replace('\', '/')
  return "/mnt/$Drive/$Tail"
}

foreach ($path in @($IdentityFile, $PublicKey)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "missing purpose-specific CKDA transfer key: $path"
  }
}

$WslHome = (& wsl.exe -d $WslDistro -- bash -lc 'printf %s "$HOME"').Trim()
$WslIdentitySource = ConvertTo-WslPath $IdentityFile
$WslPublicKeySource = ConvertTo-WslPath $PublicKey
if (-not $WslHome -or -not $WslIdentitySource -or -not $WslPublicKeySource) {
  throw 'failed to resolve CKDA transfer-key paths inside WSL'
}
$WslIdentityFile = "$WslHome/.ssh/$WslKeyName"
$WslPublicKey = "$WslIdentityFile.pub"
$Target = "$RemoteUser@$RemoteHost"

# The Windows key lives on a DrvFS mount, whose permissive mode makes OpenSSH
# reject it. Copy it into the WSL home with strict local-only permissions.
& wsl.exe -d $WslDistro -- install -d -m 700 "$WslHome/.ssh"
if ($LASTEXITCODE -ne 0) {
  throw 'failed to create the WSL SSH directory'
}
& wsl.exe -d $WslDistro -- install -m 600 $WslIdentitySource $WslIdentityFile
if ($LASTEXITCODE -ne 0) {
  throw 'failed to stage the CKDA private key inside WSL'
}
& wsl.exe -d $WslDistro -- install -m 644 $WslPublicKeySource $WslPublicKey
if ($LASTEXITCODE -ne 0) {
  throw 'failed to stage the CKDA public key inside WSL'
}

'CKDA_D0_TRANSFER_KEY_PASSWORD_PROMPT_ONCE'
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& wsl.exe -d $WslDistro -- ssh-copy-id `
  -o StrictHostKeyChecking=accept-new `
  -o ConnectTimeout=30 `
  -i $WslPublicKey $Target
$InstallExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($InstallExit -ne 0) {
  throw "CKDA transfer public-key installation failed: exit $InstallExit"
}

$ErrorActionPreference = 'Continue'
& wsl.exe -d $WslDistro -- ssh `
  -o BatchMode=yes `
  -o ConnectTimeout=30 `
  -o IdentitiesOnly=yes `
  -i $WslIdentityFile $Target 'echo CKDA_D0_TRANSFER_KEY_AUTH_PASS'
$WslTestExit = $LASTEXITCODE
& ssh.exe -o BatchMode=yes -o ConnectTimeout=30 -o IdentitiesOnly=yes `
  -i $IdentityFile $HostAlias 'echo CKDA_D0_WINDOWS_KEY_AUTH_PASS'
$WindowsTestExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($WslTestExit -ne 0 -or $WindowsTestExit -ne 0) {
  throw "CKDA transfer key authentication still unavailable: wsl_exit=$WslTestExit windows_exit=$WindowsTestExit"
}

'CKDA_D0_TRANSFER_KEY_INSTALL_PASS'
