param([switch]$Once)
$ErrorActionPreference = 'Stop'
$n1Root = Split-Path -Parent $PSScriptRoot
$n1Output = Join-Path $n1Root 'runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908'
do {
    if (-not $Once) { Clear-Host }
    Write-Output 'Paper04 N1 status'
    $n1Found = $false
    foreach ($n1Name in @('supervisor_terminal.json', 'worker_terminal.json', 'live_status.json', 'attempt.json')) {
        $n1Path = Join-Path $n1Output $n1Name
        if (Test-Path -LiteralPath $n1Path) {
            try { $n1State = Get-Content -LiteralPath $n1Path -Raw -Encoding UTF8 | ConvertFrom-Json }
            catch { Write-Output 'Status receipt unreadable. Do not restart.'; $n1Found = $true; break }
            Write-Output ('Source: ' + $n1Name)
            if ($n1Name -ne 'supervisor_terminal.json' -or -not (Test-Path -LiteralPath (Join-Path $n1Output 'SHA256SUMS'))) {
                Write-Output 'Provisional status; final supervisor seal is pending.'
            }
            $n1State | ConvertTo-Json -Depth 8 | Write-Output
            $n1Found = $true
            if ($n1Name -eq 'live_status.json') {
                $n1Active = Get-Process -Id $n1State.pid -ErrorAction SilentlyContinue
                if (-not $n1Active) { Write-Output 'Worker is absent. Await supervisor receipt; do not restart.' }
            }
            break
        }
    }
    if (-not $n1Found) { Write-Output 'NOT_STARTED (or startup has not produced a receipt).' }
    if (-not $Once) { Start-Sleep -Seconds 2 }
} while (-not $Once)
