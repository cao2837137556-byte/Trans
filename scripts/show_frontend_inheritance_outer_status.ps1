param([switch]$Once)
$ErrorActionPreference = 'Stop'
$outerRoot = Split-Path -Parent $PSScriptRoot
$outerPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$outerController = Join-Path $outerRoot 'repo/ood/issue27frontend_inheritance_outer_control_v1.py'
do {
    $outerText = & $outerPython -B $outerController status
    if ($LASTEXITCODE -ne 0) { throw 'Status could not be verified. Do not restart the attempt.' }
    $outerState = $outerText | ConvertFrom-Json
    Write-Output ('[' + (Get-Date -Format 'HH:mm:ss') + '] ' + $outerState.status)
    if ($null -ne $outerState.packets) { Write-Output ('Packets: ' + $outerState.packets + '/' + $outerState.packet_total) }
    if ($null -ne $outerState.targets_complete) { Write-Output ('Targets: ' + $outerState.targets_complete + '/' + $outerState.targets_total) }
    if ($outerState.final) {
        Write-Output 'Supervisor seal verified. The attempt is finished.'
        $outerState.verdict | Format-List
        break
    }
    if ($Once -or $outerState.status -eq 'NOT_STARTED' -or $outerState.status -like '*DO_NOT_RESTART*') { break }
    Start-Sleep -Seconds 2
} while ($true)
