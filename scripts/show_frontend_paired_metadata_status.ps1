param([switch]$Once)
$ErrorActionPreference = 'Stop'
$pairedRoot = Split-Path -Parent $PSScriptRoot
$pairedPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$pairedController = Join-Path $pairedRoot 'repo/ood/issue27frontend_paired_metadata_control_v1.py'
do {
    $pairedText = & $pairedPython -B $pairedController status
    if ($LASTEXITCODE -ne 0) { throw 'Status could not be verified. Do not restart.' }
    $pairedState = $pairedText | ConvertFrom-Json
    Write-Output ('[' + (Get-Date -Format 'HH:mm:ss') + '] ' + $pairedState.status)
    if ($null -ne $pairedState.packets) { Write-Output ('Packets: ' + $pairedState.packets + '/' + $pairedState.packet_total) }
    if ($null -ne $pairedState.targets_complete) { Write-Output ('B targets: ' + $pairedState.targets_complete + '/' + $pairedState.targets_total) }
    if ($null -ne $pairedState.members_complete) { Write-Output ('Members: ' + $pairedState.members_complete + '/' + $pairedState.members_total) }
    if ($null -ne $pairedState.elapsed_seconds) { Write-Output ('Elapsed seconds: ' + [math]::Round($pairedState.elapsed_seconds, 1)) }
    if ($pairedState.final) {
        Write-Output 'Supervisor seal verified. Metadata attempt finished; this is not a training result.'
        $pairedState.verdict | Format-List
        break
    }
    if ($Once -or $pairedState.status -eq 'NOT_STARTED' -or $pairedState.status -like '*DO_NOT_RESTART*') { break }
    Start-Sleep -Seconds 2
} while ($true)
