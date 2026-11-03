param([switch]$Watch)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskRun = Join-Path $taskRoot 'runs/legacy_reference_sample_preparation_v1_20260917'
do {
    $taskStatus = Get-Content -LiteralPath (Join-Path $taskRun 'status.json') -Raw | ConvertFrom-Json
    Write-Output ('{0}  {1}/{2} captures; training={3}; scoring={4}; retries={5}' -f $taskStatus.status,$taskStatus.completed,$taskStatus.total,$taskStatus.training,$taskStatus.scoring,$taskStatus.retries)
    Get-ChildItem -LiteralPath (Join-Path $taskRun 'captures') -Filter '*_progress.json' | ForEach-Object {
        $taskWorker = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
        if ($taskWorker.status -in @('INDEXING','HASH')) {
            Write-Output ('  {0}: {1}, packets {2}/{3}' -f $taskWorker.capture,$taskWorker.status,$taskWorker.packets,$taskWorker.total)
        }
    }
    if ($taskStatus.error) { Write-Output $taskStatus.error }
    if (-not $Watch -or $taskStatus.status -in @('COMPLETE_SEALED','STOPPED_NO_RETRY')) { break }
    Start-Sleep -Seconds 10
} while ($true)
