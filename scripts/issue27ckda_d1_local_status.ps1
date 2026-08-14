[CmdletBinding()]
param()

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RunName = 'issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu'
$ControlRoot = Join-Path $RepoRoot "runs\${RunName}_control"
$CheckpointRoot = Join-Path $RepoRoot 'runs\issue27ckda_d1_checkpoint_v1_localwin_ecb429926507d2c4'

Write-Output '===== CKDA D1 LOCAL PROCESS ====='
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*-File*issue27ckda_d1_local_contingency.ps1*' } |
    Select-Object ProcessId, CreationDate, CommandLine
Write-Output '===== PHASE ====='
if (Test-Path -LiteralPath (Join-Path $ControlRoot 'current_phase.txt')) {
    Get-Content -LiteralPath (Join-Path $ControlRoot 'current_phase.txt')
} else { Write-Output 'not started' }
Write-Output '===== CHECKPOINTS ====='
$Files = @(Get-ChildItem -LiteralPath $CheckpointRoot -Recurse -File -ErrorAction SilentlyContinue)
Write-Output ("count={0} bytes={1}" -f $Files.Count, (($Files | Measure-Object Length -Sum).Sum))
Write-Output '===== ACTIVE LOG TAIL ====='
$Log = Get-ChildItem -LiteralPath (Join-Path $ControlRoot 'logs') -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -ne $Log) {
    Write-Output ("log={0} bytes={1} updated={2}" -f $Log.FullName, $Log.Length, $Log.LastWriteTime)
    Get-Content -LiteralPath $Log.FullName -Tail 30
}
Write-Output '===== TERMINAL MARKERS ====='
Get-ChildItem -LiteralPath $ControlRoot -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @('local_precompute_success.txt','local_phase_a_success.txt','engineering_failure.json') } |
    ForEach-Object { Write-Output $_.Name; Get-Content -LiteralPath $_.FullName }
