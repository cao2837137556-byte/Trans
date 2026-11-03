param([Parameter(Mandatory=$true)][string]$OutputDirectory,[switch]$Watch)
$ErrorActionPreference='Stop'
$referenceRun=(Resolve-Path -LiteralPath $OutputDirectory).Path
do {
    $referenceStatus=Get-Content -LiteralPath (Join-Path $referenceRun 'status.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Output ('{0}: {1} {2}/{3}; retries={4}' -f $referenceStatus.status,$referenceStatus.stage,$referenceStatus.done,$referenceStatus.total,$referenceStatus.retries)
    if ($referenceStatus.worker.capture) { Write-Output ('capture={0}; packets={1}/{2}' -f $referenceStatus.worker.capture,$referenceStatus.worker.packets,$referenceStatus.worker.capture_packets) }
    if ($referenceStatus.peak_job_bytes) { Write-Output ('Peak job memory {0:N2} GiB; outputs {1:N2} GiB' -f ($referenceStatus.peak_job_bytes/1GB),($referenceStatus.output_bytes/1GB)) }
    if ($referenceStatus.error) { Write-Output $referenceStatus.error }
    if ($referenceStatus.status -in @('COMPLETE','STOPPED_NO_RETRY')) {
        Write-Output ('Saved result/failure: '+$referenceRun)
        break
    }
    $referenceSupervisor=Get-Process -Id $referenceStatus.supervisor_pid -ErrorAction SilentlyContinue
    $referenceLastUpdate = [DateTimeOffset]::FromUnixTimeMilliseconds([long]($referenceStatus.updated_epoch * 1000))
    if (-not $referenceSupervisor -or $referenceSupervisor.StartTime.ToUniversalTime() -gt $referenceLastUpdate.UtcDateTime) {
        Write-Output 'Supervisor is absent. Persisted RUNNING is stale: interrupted, not complete. No automatic restart.'
        break
    }
    if (-not $Watch) { break }
    Start-Sleep -Seconds 10
} while ($true)

