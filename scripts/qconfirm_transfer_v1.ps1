param([Parameter(Mandatory=$true)][ValidateSet('Upload','Pull')][string]$Mode)
$ErrorActionPreference = 'Stop'
$delivery = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../runs/legacy_qref_device_confirmation_delivery_v1_20260923'))
$server = 'jiangxinwei.zr@172.24.3.168'
$remoteWork = '/public/home/jiangxinwei.zr/work'
$remoteRoot = "$remoteWork/legacy_qref_device_confirmation_v1_20260923"
function WslPath([string]$Path) {
    $converted = & wsl -d Ubuntu-24.04 -- wslpath -a -u ($Path.Replace('\','/'))
    if ($LASTEXITCODE -ne 0) { throw 'wslpath failed' }
    return $converted.Trim()
}
function VerifyArchive([string]$Path) {
    $fields = (Get-Content -LiteralPath "$Path.sha256" -Raw).Trim() -split '\s+'
    if ($fields.Count -ne 2 -or $fields[1] -ne [IO.Path]::GetFileName($Path)) { throw 'Invalid checksum sidecar' }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $fields[0]) { throw "Checksum mismatch: $Path" }
}
if ($Mode -eq 'Upload') {
    $auth = Join-Path $delivery 'confirmation_authorization_v1_20260923.json'
    $scope = Get-Content -LiteralPath $auth -Raw | ConvertFrom-Json
    if ($scope.execution_authorized -ne $true -or $scope.package_inputs -ne $true) { throw 'Real confirmation is not authorized' }
    $archives = @('qref_confirmation_code_v1_20260923.tar.gz','qref_confirmation_inputs_v1_20260923.tar.gz')
    $sources = @()
    foreach ($name in $archives) {
        $path = Join-Path $delivery $name
        VerifyArchive $path
        $sources += (WslPath $path)
        $sources += (WslPath "$path.sha256")
    }
    $sources += (WslPath $auth)
    $sources += (WslPath (Join-Path $PSScriptRoot 'qconfirm_install_v1.py'))
    & wsl -d Ubuntu-24.04 -- rsync -t --append-verify --info=progress2 --human-readable @sources "${server}:$remoteWork/"
    if ($LASTEXITCODE -ne 0) { throw 'Transfer interrupted; rerun the same transfer command to resume; do not submit' }
    Write-Host 'Upload complete. Installation and once-only submission are separate user actions.'
} else {
    $dest = Join-Path $delivery 'pullback'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $wslDest = (WslPath $dest) + '/'
    & wsl -d Ubuntu-24.04 -- rsync -t --append-verify --info=progress2 --human-readable "${server}:$remoteRoot/confirmation_pullback.tar.gz" "${server}:$remoteRoot/confirmation_pullback.tar.gz.sha256" $wslDest
    if ($LASTEXITCODE -ne 0) { throw 'Pull interrupted; rerun to resume' }
    VerifyArchive (Join-Path $dest 'confirmation_pullback.tar.gz')
    Write-Host 'Pullback SHA256 verified. Ready for local result verification; no automatic re-execution.'
}
