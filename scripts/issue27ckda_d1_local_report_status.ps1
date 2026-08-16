[CmdletBinding()]
param()

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RunName = 'issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu'
$ControlRoot = Join-Path $RepoRoot "runs\${RunName}_l2_control"
$CheckpointRoot = Join-Path $RepoRoot 'runs\issue27ckda_d1_checkpoint_v1_localwin_ecb429926507d2c4\e3_report'

Write-Output '===== CKDA D1 LOCAL L2 PROCESS ====='
$Processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq 'powershell.exe' -and $_.CommandLine -like '*-File*issue27ckda_d1_local_report.ps1*' } |
    Select-Object ProcessId, CreationDate, CommandLine)
if ($Processes.Count -eq 0) { Write-Output 'no active CKDA D1 L2 launcher' } else { $Processes }
Write-Output '===== PHASE ====='
$PhasePath = Join-Path $ControlRoot 'current_phase.txt'
if (Test-Path -LiteralPath $PhasePath) { Get-Content -LiteralPath $PhasePath } else { Write-Output 'not started' }
Write-Output '===== REPORT CHECKPOINTS ====='
$Files = @(Get-ChildItem -LiteralPath $CheckpointRoot -File -Filter '*.npz' -ErrorAction SilentlyContinue)
Write-Output ("count={0} bytes={1}" -f $Files.Count, (($Files | Measure-Object Length -Sum).Sum))
if ($Files.Count -gt 0) { $Files | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,Length,LastWriteTime }
Write-Output '===== ACTIVE PHASE STDOUT ====='
$LogRoot = Join-Path $ControlRoot 'logs'
$Stdout = Get-ChildItem -LiteralPath $LogRoot -File -Filter '*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike '*.stderr.log' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -ne $Stdout) {
    Write-Output ("stdout={0} bytes={1} updated={2}" -f $Stdout.FullName,$Stdout.Length,$Stdout.LastWriteTime)
    Get-Content -LiteralPath $Stdout.FullName -Tail 35
}
Write-Output '===== ACTIVE PHASE STDERR ====='
$Stderr = Get-ChildItem -LiteralPath $LogRoot -File -Filter '*.stderr.log' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -ne $Stderr) {
    Write-Output ("stderr={0} bytes={1} updated={2}" -f $Stderr.FullName,$Stderr.Length,$Stderr.LastWriteTime)
    if ($Stderr.Length -gt 0) { Get-Content -LiteralPath $Stderr.FullName -Tail 25 } else { Write-Output 'empty' }
}
Write-Output '===== TERMINAL MARKERS ====='
foreach ($Name in @('local_report_opened.txt','local_l2_success.txt','engineering_failure.json')) {
    $Path = Join-Path $ControlRoot $Name
    if (Test-Path -LiteralPath $Path) { Write-Output $Name; Get-Content -LiteralPath $Path }
}
