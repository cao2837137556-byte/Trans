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

& ssh.exe -o BatchMode=yes -o ConnectTimeout=15 -i $IdentityFile $HostAlias 'true' 2>$null
if ($LASTEXITCODE -eq 0) {
  'CKDA_D0_TRANSFER_KEY_ALREADY_ACTIVE'
  return
}

'CKDA_D0_TRANSFER_KEY_PASSWORD_PROMPT_ONCE'
Get-Content -LiteralPath $PublicKey -Raw |
  & ssh.exe $HostAlias 'umask 077; mkdir -p .ssh; cat >> .ssh/authorized_keys; chmod 700 .ssh; chmod 600 .ssh/authorized_keys'
if ($LASTEXITCODE -ne 0) {
  throw "CKDA transfer public-key installation failed: exit $LASTEXITCODE"
}

& ssh.exe -o BatchMode=yes -o ConnectTimeout=30 -i $IdentityFile $HostAlias 'echo CKDA_D0_TRANSFER_KEY_AUTH_PASS'
if ($LASTEXITCODE -ne 0) {
  throw "CKDA transfer key authentication still unavailable: exit $LASTEXITCODE"
}
