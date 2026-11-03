param([switch]$Watch)
$completionRoot = Join-Path $PSScriptRoot '../runs/legacy_normal_supplement_completion_v2_20260917'
do {
    $state = Get-Content (Join-Path $completionRoot 'status.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $auditPath = Join-Path $completionRoot 'audit_status.json'
    $audit = if (Test-Path $auditPath) { Get-Content $auditPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $finalPath = Join-Path $completionRoot 'final_status.json'
    $final = if (Test-Path $finalPath) { Get-Content $finalPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    [pscustomobject]@{
        Status = $state.status
        CompleteFiles = $state.completed_files
        PlannedFiles = 7
        PriorAuditsReused = 5
        NewAuditsComplete = $state.new_audits_completed
        CumulativeBudgetGiB = [math]::Round($state.budget_charged_bytes / 1GB,3)
        CapGiB = 8
        CurrentFile = $state.file
        AuditStatus = $audit.status
        AuditStage = $audit.stage
        AuditPackets = $audit.packets
        StopReason = $state.reason
        FinalStatus = $final.status
    } | Format-List
    if ($final -or $state.status -eq 'STOPPED_NO_AUTOMATIC_RETRY') { break }
    if ($Watch) { Start-Sleep -Seconds 10 }
} while ($Watch)
