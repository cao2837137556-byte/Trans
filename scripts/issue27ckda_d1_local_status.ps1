[CmdletBinding()]
param()

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RunName = 'issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu'
$ControlRoot = Join-Path $RepoRoot "runs\${RunName}_control"
$CheckpointRoot = Join-Path $RepoRoot 'runs\issue27ckda_d1_checkpoint_v1_localwin_ecb429926507d2c4'

Write-Output '===== CKDA D1 LOCAL PROCESS ====='
$Processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*-File*issue27ckda_d1_local_contingency.ps1*' } |
    Select-Object ProcessId, CreationDate, CommandLine)
if ($Processes.Count -eq 0) {
    Write-Output 'no active CKDA D1 launcher'
} else {
    $Processes
}
Write-Output '===== PHASE ====='
if (Test-Path -LiteralPath (Join-Path $ControlRoot 'current_phase.txt')) {
    Get-Content -LiteralPath (Join-Path $ControlRoot 'current_phase.txt')
} else { Write-Output 'not started' }
Write-Output '===== CHECKPOINTS ====='
$Files = @(Get-ChildItem -LiteralPath $CheckpointRoot -Recurse -File -ErrorAction SilentlyContinue)
Write-Output ("count={0} bytes={1}" -f $Files.Count, (($Files | Measure-Object Length -Sum).Sum))
if ($Files.Count -gt 0) {
    $Files | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name, Length, LastWriteTime
}
Write-Output '===== STDOUT PROGRESS TAIL ====='
$Stdout = Get-ChildItem -LiteralPath $ControlRoot -File -Filter 'launcher*.stdout.log' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -ne $Stdout) {
    Write-Output ("stdout={0} bytes={1} updated={2}" -f $Stdout.FullName, $Stdout.Length, $Stdout.LastWriteTime)
    Get-Content -LiteralPath $Stdout.FullName -Tail 35
}
Write-Output '===== STDERR TAIL ====='
$Stderr = Get-ChildItem -LiteralPath $ControlRoot -File -Filter 'launcher*.stderr.log' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -ne $Stderr) {
    Write-Output ("stderr={0} bytes={1} updated={2}" -f $Stderr.FullName, $Stderr.Length, $Stderr.LastWriteTime)
    if ($Stderr.Length -gt 0) {
        Get-Content -LiteralPath $Stderr.FullName -Tail 25
    } else {
        Write-Output 'empty'
    }
}
Write-Output '===== TERMINAL MARKERS ====='
Get-ChildItem -LiteralPath $ControlRoot -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @('local_precompute_success.txt','local_embedding_attempt.txt','local_phase_a_success.txt','engineering_failure.json') } |
    ForEach-Object { Write-Output $_.Name; Get-Content -LiteralPath $_.FullName }
