param(
  [string]$HostAlias = 'school-hpc',
  [string]$IdentityFile = "$env:USERPROFILE\.ssh\id_ed25519_school_hpc_ckda"
)

$ErrorActionPreference = 'Stop'
$PublicKey = "$IdentityFile.pub"
foreach ($path in @($IdentityFile, $PublicKey)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "missing purpose-specific CKDA transfer key: $path"
  }
}

'CKDA_D0_TRANSFER_KEY_PASSWORD_PROMPT_ONCE'
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
Get-Content -LiteralPath $PublicKey -Raw |
  & ssh.exe $HostAlias 'umask 077; mkdir -p .ssh; cat >> .ssh/authorized_keys; chmod 700 .ssh; chmod 600 .ssh/authorized_keys'
$InstallExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($InstallExit -ne 0) {
  throw "CKDA transfer public-key installation failed: exit $InstallExit"
}

$ErrorActionPreference = 'Continue'
& ssh.exe -o BatchMode=yes -o ConnectTimeout=30 -i $IdentityFile $HostAlias 'echo CKDA_D0_TRANSFER_KEY_AUTH_PASS'
$TestExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
if ($TestExit -ne 0) {
  throw "CKDA transfer key authentication still unavailable: exit $TestExit"
}
