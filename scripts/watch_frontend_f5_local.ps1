[CmdletBinding()]
param([switch]$Once)
$ErrorActionPreference = 'Stop'
$f5Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$f5Output = Join-Path $f5Root 'runs\frontend_f5_unified_student_v1_20260906_local'
do {
    if (-not $Once) { Clear-Host }
    Write-Output "F5 read-only monitor | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    if (-not (Test-Path -LiteralPath $f5Output)) {
        Write-Output 'No real F5 run directory: training has not been started.'
    } else {
        foreach ($f5Name in @('heartbeat.json','preflight\complete.json','training\terminal.json','verdict.json','resource_stop.json','engineering_failure.json')) {
            $f5Path = Join-Path $f5Output $f5Name
            if (Test-Path -LiteralPath $f5Path) {
                Write-Output "--- $f5Name ---"
                Get-Content -LiteralPath $f5Path
            }
        }
        $f5Ledger = Join-Path $f5Output 'training\epoch_ledger.json'
        if (Test-Path -LiteralPath $f5Ledger) {
            try {
                $f5Epochs = @(Get-Content -LiteralPath $f5Ledger -Raw | ConvertFrom-Json)
                Write-Output '--- last completed epoch ---'
                $f5Epochs | Select-Object -Last 1 | ConvertTo-Json -Depth 8
            } catch { Write-Output 'Ledger is not readable yet; retry at next refresh.' }
        }
        $f5Lock = Join-Path $f5Output 'run.lock'
        if (Test-Path -LiteralPath $f5Lock) {
            try {
                $f5LockInfo = Get-Content -LiteralPath $f5Lock -Raw | ConvertFrom-Json
                $f5Live = Get-Process -Id $f5LockInfo.pid -ErrorAction SilentlyContinue
                if ($null -eq $f5Live) { Write-Output 'WARNING: lock PID absent. Inspect crash receipts before recovery; do not start over.' }
                else { Write-Output "Lock PID exists: $($f5LockInfo.pid). Presence alone is not proof of progress." }
            } catch { Write-Output 'Lock status temporarily unreadable.' }
        }
    }
    if (-not $Once) {
        Write-Output 'Refresh: 30 seconds. Ctrl+C stops this monitor, not the experiment.'
        Start-Sleep -Seconds 30
    }
} while (-not $Once)
