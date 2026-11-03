param([switch]$Watch)
$supplementRoot = Join-Path $PSScriptRoot '../runs/legacy_normal_supplement_acquisition_v1_20260917'
do {
    $downloadPath = Join-Path $supplementRoot 'download_status.json'
    $auditPath = Join-Path $supplementRoot 'audit_status.json'
    $finalPath = Join-Path $supplementRoot 'final_status.json'
    $downloadState = if (Test-Path -LiteralPath $downloadPath) { Get-Content -LiteralPath $downloadPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $auditState = if (Test-Path -LiteralPath $auditPath) { Get-Content -LiteralPath $auditPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $finalState = if (Test-Path -LiteralPath $finalPath) { Get-Content -LiteralPath $finalPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $checkedCount = @(Get-ChildItem -LiteralPath $supplementRoot -Filter '??_summary.json' -File -ErrorAction SilentlyContinue).Count
    [pscustomobject]@{
        Download = $downloadState.status
        ReceivedGiB = [math]::Round($downloadState.total_received_bytes / 1GB, 3)
        BudgetGiB = 8
        DownloadedFiles = $downloadState.completed_files
        CheckedFiles = $checkedCount
        TotalFiles = 7
        CurrentDownload = $downloadState.current_file
        CurrentAudit = $auditState.file
        AuditStatus = $auditState.status
        AuditStage = $auditState.stage
        AuditPackets = $auditState.packets
        DownloadStopReason = $downloadState.reason
        AuditStopReason = $auditState.reason
        FinalStatus = $finalState.status
        MaterialDecision = $finalState.material_decision
    } | Format-List
    if ($finalState -or $downloadState.status -eq 'STOPPED_NO_RETRY' -or $auditState.status -eq 'STOPPED_NO_RETRY') { break }
    if ($Watch) { Start-Sleep -Seconds 10 }
} while ($Watch)
