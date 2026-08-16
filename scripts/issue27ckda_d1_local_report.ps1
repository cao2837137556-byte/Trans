[CmdletBinding()]
param(
    [switch]$AuthorizeReportOpen
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PaperRoot = 'D:\study\paper\anomaly_detection\paper04'
$TransferRoot = Join-Path $PaperRoot 'supercompute_transfer'
$RuntimeRoot = Join-Path $TransferRoot 'ckda_d1_local_runtime_20260814'
$D1Payload = Join-Path $TransferRoot 'issue27ckda_d1_representation_probe_20260812\payload'
$D0Payload = Join-Path $TransferRoot 'issue27ckda_d0_representation_compatibility_20260811_r2\payload'
$CacheRoot = Join-Path $TransferRoot 'ckda_d0_local_lineage_inputs_20260811\ckcz_rehearsal_inputs_20260810'
$Python = Join-Path $RuntimeRoot '.venv\Scripts\python.exe'
$TShark = 'C:\Program Files\Wireshark\tshark.exe'

$Contract = Join-Path $D1Payload 'runs\mainline_docs\ckda_d1_frozen_representation_probe_preregistered_20260812.md'
$OOD = Join-Path $D1Payload 'repo\ood'
$D0OOD = Join-Path $D0Payload 'repo\ood'
$RolePlan = Join-Path $OOD 'issue27ckda_d1_role_plan_v1.py'
$TargetMetadata = Join-Path $OOD 'issue27ckda_d1_target_metadata_v1.py'
$Probe = Join-Path $OOD 'issue27ckda_d1_probe_runner_v1.py'
$Metrics = Join-Path $OOD 'issue27ckda_d1_metrics_v1.py'
$Validator = Join-Path $OOD 'issue27ckda_d1_validate_and_pack_v1.py'
$CKBU = Join-Path $OOD 'issue27ckbu_unified_tshark_causal_frontend_v1.py'
$D0Pilot = Join-Path $D0OOD 'issue27ckda_d0_resource_pilot_v1.py'
$NetFoundSource = Join-Path $D0Payload 'vendor\netFound'
$NetFoundModel = Join-Path $D0Payload 'vendor\netFound-base'
$LocalEmbed = Join-Path $RepoRoot 'repo\ood\issue27ckda_d1_e3_embed_local_twopass_v1.py'

$Snapshot = Join-Path $TransferRoot 'ckby_157930_extract\issue27ckby_drocc_feature_dump_v1_2026-08-07_seed27_amd_157930\ckby_drocc_feature_snapshot_seed27.npz'
$Predictions = Join-Path $TransferRoot 'ckbw_157624_extract\issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624\ckbw_record_predictions.csv.gz'
$GothamManifest = Join-Path $CacheRoot 'ckbu_gotham_unified_causal_manifest.csv'
$AuxiliaryManifest = Join-Path $CacheRoot 'ckbu_auxiliary_unified_causal_manifest.csv'
$GothamAllowlist = Join-Path $D1Payload 'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv'
$AuxiliaryAllowlist = Join-Path $D1Payload 'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv'
$GothamZip = Join-Path $PaperRoot 'datasets\gotham2025\raw\GothamDataset2025.zip'
$TonRoot = Join-Path $PaperRoot 'datasets\external\ton_iot_raw_network\raw_pcap_pilot_v1'

$RunName = 'issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu'
$StageRoot = Join-Path $RepoRoot "runs\.$RunName.stage"
$L1ControlRoot = Join-Path $RepoRoot "runs\${RunName}_control"
$ControlRoot = Join-Path $RepoRoot "runs\${RunName}_l2_control"
$CheckpointRoot = Join-Path $RepoRoot 'runs\issue27ckda_d1_checkpoint_v1_localwin_ecb429926507d2c4'
$LogRoot = Join-Path $ControlRoot 'logs'
$IdentityPath = Join-Path $ControlRoot 'local_l2_identity.json'
$PhasePath = Join-Path $ControlRoot 'current_phase.txt'
$FailurePath = Join-Path $ControlRoot 'engineering_failure.json'
$L1Gate = Join-Path $RepoRoot 'runs\mainline_docs\ckda_d1_local_l1_codex_review_gate_20260816.json'
$ReportOpenMarker = Join-Path $ControlRoot 'local_report_opened.txt'
$Pullback = Join-Path $RepoRoot "runs\${RunName}_pullback.tar.gz"

function Get-Sha256([string]$Path) {
    $Stream = [IO.File]::OpenRead($Path)
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($Hasher.ComputeHash($Stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $Hasher.Dispose()
        $Stream.Dispose()
    }
}

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing file: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -le 0) { throw "Empty file: $Path" }
}

function Assert-FileSha([string]$Path, [string]$Expected) {
    Assert-File $Path
    $Actual = Get-Sha256 $Path
    if ($Actual -ne $Expected) { throw "SHA256 mismatch: $Path actual=$Actual expected=$Expected" }
}

function Set-Phase([string]$Name) {
    $Now = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    [IO.File]::WriteAllText($PhasePath, "phase=$Name`nupdated_utc=$Now`n", [Text.UTF8Encoding]::new($false))
}

function Complete-Phase([string]$Name) {
    $Marker = Join-Path $ControlRoot ("phase_" + $Name + '.complete')
    [IO.File]::WriteAllText($Marker, ([DateTime]::UtcNow.ToString('o') + "`n"), [Text.UTF8Encoding]::new($false))
}

function Test-Phase([string]$Name) {
    return Test-Path -LiteralPath (Join-Path $ControlRoot ("phase_" + $Name + '.complete')) -PathType Leaf
}

function Invoke-PythonPhase([string]$Name, [string[]]$Arguments, [string[]]$RequiredOutputs) {
    if (Test-Phase $Name) {
        foreach ($Output in $RequiredOutputs) { Assert-File $Output }
        Set-Phase ("reuse_" + $Name)
        return
    }
    Set-Phase $Name
    $Log = Join-Path $LogRoot ($Name + '.log')
    $ErrorLog = Join-Path $LogRoot ($Name + '.stderr.log')
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Python @Arguments 1> $Log 2> $ErrorLog
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousPreference
    if ($ExitCode -ne 0) {
        Get-Content -LiteralPath $Log -Tail 100 -ErrorAction SilentlyContinue
        Get-Content -LiteralPath $ErrorLog -Tail 100 -ErrorAction SilentlyContinue
        throw "Phase failed: $Name exit=$ExitCode log=$Log stderr=$ErrorLog"
    }
    foreach ($Output in $RequiredOutputs) { Assert-File $Output }
    Complete-Phase $Name
}

New-Item -ItemType Directory -Force -Path $ControlRoot, $LogRoot, (Join-Path $CheckpointRoot 'e3_report') | Out-Null
if (Test-Path -LiteralPath $FailurePath -PathType Leaf) {
    $PreviousFailure = Join-Path $ControlRoot ("engineering_failure_previous_" + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '.json')
    Move-Item -LiteralPath $FailurePath -Destination $PreviousFailure
}
Set-Phase 'l2_startup'

try {
    foreach ($File in @(
        $Python, $TShark, $Contract, $RolePlan, $TargetMetadata, $Probe, $Metrics,
        $Validator, $CKBU, $D0Pilot, $LocalEmbed, $Snapshot, $Predictions,
        $GothamManifest, $AuxiliaryManifest, $GothamAllowlist, $AuxiliaryAllowlist,
        $GothamZip, (Join-Path $NetFoundModel 'config.json'),
        (Join-Path $NetFoundModel 'model.safetensors'), $L1Gate,
        (Join-Path $L1ControlRoot 'local_phase_a_success.txt')
    )) { Assert-File $File }
    foreach ($Directory in @($CacheRoot, $NetFoundSource, $TonRoot, $StageRoot)) {
        if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { throw "Missing directory: $Directory" }
    }

    Assert-FileSha $Contract 'ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9'
    Assert-FileSha $Predictions 'd1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85'
    Assert-FileSha $Snapshot 'b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c'
    Assert-FileSha (Join-Path $NetFoundModel 'model.safetensors') 'e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105'

    $L1Success = Get-Content -LiteralPath (Join-Path $L1ControlRoot 'local_phase_a_success.txt') -Raw
    if ($L1Success -notmatch 'status=PASS' -or $L1Success -notmatch 'report_opened=0') {
        throw 'L1 success marker is not sealed PASS'
    }
    if (Test-Path -LiteralPath (Join-Path $L1ControlRoot 'engineering_failure.json')) {
        throw 'Current L1 engineering failure marker exists'
    }
    $Gate = Get-Content -LiteralPath $L1Gate -Raw | ConvertFrom-Json
    if ($Gate.status -ne 'PASS' -or $Gate.reviewer -ne 'Codex' -or [int]$Gate.final_files_opened -ne 0 -or [int]$Gate.report_rows_opened -ne 0) {
        throw 'L1 Codex review gate invalid'
    }

    $FitPlan = Join-Path $StageRoot 'ckda_d1_fit_select_plan.csv'
    $FitEmbeddings = Join-Path $StageRoot 'ckda_d1_fit_select_embeddings.npz'
    $ProbeState = Join-Path $StageRoot 'ckda_d1_probe_state.npz'
    $ThresholdMarker = Join-Path $StageRoot 'ckda_d1_threshold_freeze_marker.json'
    Assert-FileSha $FitPlan ([string]$Gate.fit_select_plan_sha256)
    Assert-FileSha $FitEmbeddings ([string]$Gate.fit_select_embeddings_sha256)
    Assert-FileSha $ProbeState ([string]$Gate.probe_state_sha256)
    Assert-FileSha $ThresholdMarker ([string]$Gate.threshold_marker_sha256)
    $Marker = Get-Content -LiteralPath $ThresholdMarker -Raw | ConvertFrom-Json
    if ($Marker.status -ne 'CKDA_D1_THRESHOLDS_FROZEN' -or [int]$Marker.final_files_opened -ne 0 -or [int]$Marker.report_labels_opened -ne 0 -or [int]$Marker.report_rows_opened -ne 0) {
        throw 'Threshold marker is not sealed/frozen'
    }
    if ([string]$Marker.fit_select_plan_sha256 -ne (Get-Sha256 $FitPlan) -or [string]$Marker.fit_select_embeddings_sha256 -ne (Get-Sha256 $FitEmbeddings) -or [string]$Marker.probe_state_sha256 -ne (Get-Sha256 $ProbeState)) {
        throw 'Threshold marker lineage mismatch'
    }
    $FitCheckpoints = @(Get-ChildItem -LiteralPath (Join-Path $CheckpointRoot 'e3_fit_select') -File -Filter '*.npz')
    if ($FitCheckpoints.Count -ne 30) { throw "Expected 30 validated L1 checkpoints, got $($FitCheckpoints.Count)" }

    $env:PYTHONPATH = "$($RepoRoot)\repo\ood;$OOD;$D0OOD"
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:HF_HUB_OFFLINE = '1'
    $env:TOKENIZERS_PARALLELISM = 'false'
    $env:OMP_NUM_THREADS = '8'
    $env:OPENBLAS_NUM_THREADS = '8'
    $env:MKL_NUM_THREADS = '8'
    $PythonVersion = (& $Python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))").Trim()
    if (-not $PythonVersion.StartsWith('3.9.')) { throw "Frozen Python 3.9 gate failed: $PythonVersion" }
    $TSharkVersion = (& $TShark --version | Select-Object -First 1)
    if ($TSharkVersion -notmatch '4\.6\.6') { throw "Frozen TShark 4.6.6 gate failed: $TSharkVersion" }

    if (-not $AuthorizeReportOpen) {
        Set-Phase 'l2_report_pending_explicit_authorization'
        return
    }

    $ReportPlan = Join-Path $StageRoot 'ckda_d1_report_plan.csv'
    $ReportTargetMetadata = Join-Path $StageRoot 'ckda_d1_report_target_metadata.csv'
    $ReportEmbeddings = Join-Path $StageRoot 'ckda_d1_report_embeddings.npz'
    $ReportScores = Join-Path $StageRoot 'ckda_d1_report_scores.csv.gz'
    $Verdict = Join-Path $StageRoot 'ckda_d1_verdict.json'
    $Validation = Join-Path $StageRoot 'ckda_d1_validation_report.json'
    $ReportOutputs = @($ReportPlan, $ReportTargetMetadata, $ReportEmbeddings, $ReportScores, $Verdict)

    $FirstAuthorizedAttempt = -not (Test-Path -LiteralPath $IdentityPath -PathType Leaf)
    if ($FirstAuthorizedAttempt) {
        foreach ($Output in $ReportOutputs) {
            if (Test-Path -LiteralPath $Output) { throw "Pre-existing report output before first L2 authorization: $Output" }
        }
        $Identity = [ordered]@{
            status = 'CKDA_D1_LOCAL_L2_IDENTITY'
            contract_sha256 = Get-Sha256 $Contract
            snapshot_sha256 = Get-Sha256 $Snapshot
            predictions_sha256 = Get-Sha256 $Predictions
            l1_gate_sha256 = Get-Sha256 $L1Gate
            threshold_marker_sha256 = Get-Sha256 $ThresholdMarker
            probe_state_sha256 = Get-Sha256 $ProbeState
            fit_select_plan_sha256 = Get-Sha256 $FitPlan
            fit_select_embeddings_sha256 = Get-Sha256 $FitEmbeddings
            local_embedder_sha256 = Get-Sha256 $LocalEmbed
            local_report_runner_sha256 = Get-Sha256 $PSCommandPath
            python = $Python
            tshark = $TShark
            report_opened = $true
        }
        [IO.File]::WriteAllText($IdentityPath, (($Identity | ConvertTo-Json -Depth 4) + "`n"), [Text.UTF8Encoding]::new($false))
    } else {
        $Identity = Get-Content -LiteralPath $IdentityPath -Raw | ConvertFrom-Json
        $ExpectedIdentity = [ordered]@{
            contract_sha256 = Get-Sha256 $Contract
            snapshot_sha256 = Get-Sha256 $Snapshot
            predictions_sha256 = Get-Sha256 $Predictions
            l1_gate_sha256 = Get-Sha256 $L1Gate
            threshold_marker_sha256 = Get-Sha256 $ThresholdMarker
            probe_state_sha256 = Get-Sha256 $ProbeState
            fit_select_plan_sha256 = Get-Sha256 $FitPlan
            fit_select_embeddings_sha256 = Get-Sha256 $FitEmbeddings
            local_embedder_sha256 = Get-Sha256 $LocalEmbed
            local_report_runner_sha256 = Get-Sha256 $PSCommandPath
        }
        foreach ($Key in $ExpectedIdentity.Keys) {
            if ([string]$Identity.$Key -ne [string]$ExpectedIdentity[$Key]) { throw "L2 resume identity drift: $Key" }
        }
    }

    if (-not (Test-Path -LiteralPath $ReportOpenMarker -PathType Leaf)) {
        [IO.File]::WriteAllText($ReportOpenMarker, "status=AUTHORIZED_ONE_SHOT`nopened_utc=$([DateTime]::UtcNow.ToString('o'))`nfinal_opened=0`n", [Text.UTF8Encoding]::new($false))
    }

    $FitSha = Get-Sha256 $FitPlan
    $RolePlanPhase = 'l2_report_role_plan_after_freeze'
    $ReportRoleAudit = Join-Path $StageRoot 'ckda_d1_report_role_plan_audit.json'
    if (Test-Phase $RolePlanPhase) {
        Assert-File $ReportPlan
        Assert-File $ReportRoleAudit
        Set-Phase ("reuse_" + $RolePlanPhase)
    } else {
        Set-Phase $RolePlanPhase
        $RoleLog = Join-Path $LogRoot ($RolePlanPhase + '.log')
        $RoleErrorLog = Join-Path $LogRoot ($RolePlanPhase + '.stderr.log')
        $PreviousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $Python $RolePlan --scope report --contract $Contract --snapshot $Snapshot --predictions $Predictions --threshold-marker $ThresholdMarker --out $StageRoot 1> $RoleLog 2> $RoleErrorLog
        $ExitCode = $LASTEXITCODE
        $ErrorActionPreference = $PreviousPreference
        if ($ExitCode -ne 0) { throw "Phase failed: $RolePlanPhase exit=$ExitCode" }
        $GenericRoleAudit = Join-Path $StageRoot 'ckda_d1_role_plan_audit.json'
        Assert-File $ReportPlan
        Assert-File $GenericRoleAudit
        Move-Item -LiteralPath $GenericRoleAudit -Destination $ReportRoleAudit -Force
        Complete-Phase $RolePlanPhase
    }
    $ReportSha = Get-Sha256 $ReportPlan

    Invoke-PythonPhase 'l2_report_target_metadata_after_freeze' @(
        $TargetMetadata, '--scope', 'report', '--contract', $Contract, '--plan', $ReportPlan,
        '--threshold-marker', $ThresholdMarker, '--fit-select-plan-sha256', $FitSha,
        '--ckbv-root', $CacheRoot, '--gotham-manifest', $GothamManifest,
        '--auxiliary-manifest', $AuxiliaryManifest, '--gotham-allowlist', $GothamAllowlist,
        '--auxiliary-allowlist', $AuxiliaryAllowlist, '--ton-pcap-root', $TonRoot,
        '--gotham-zip', $GothamZip, '--out', $ReportTargetMetadata
    ) @($ReportTargetMetadata, ($ReportTargetMetadata + '.audit.json'))

    Invoke-PythonPhase 'l2_e3_one_shot_report_embeddings' @(
        $LocalEmbed, '--contract', $Contract, '--target-metadata', $ReportTargetMetadata,
        '--plan-sha256', $ReportSha, '--netfound-source', $NetFoundSource,
        '--netfound-checkpoint', $NetFoundModel, '--ckbu-decoder', $CKBU,
        '--d0-pilot', $D0Pilot, '--tshark', $TShark, '--device', 'cpu',
        '--batch-size', '16', '--checkpoint-dir', (Join-Path $CheckpointRoot 'e3_report'),
        '--out', $ReportEmbeddings
    ) @($ReportEmbeddings, ($ReportEmbeddings + '.audit.json'), ($ReportEmbeddings + '.metadata.csv.gz'))

    Invoke-PythonPhase 'l2_frozen_report_scoring' @(
        $Probe, '--scope', 'report', '--contract', $Contract, '--candidate', 'E3',
        '--plan', $ReportPlan, '--embeddings', $ReportEmbeddings, '--state', $ProbeState,
        '--marker', $ThresholdMarker, '--out', $StageRoot
    ) @($ReportScores, (Join-Path $StageRoot 'ckda_d1_report_score_audit.json'))

    Invoke-PythonPhase 'l2_metrics_bootstrap_and_state' @(
        $Metrics, '--contract', $Contract, '--candidate', 'E3', '--scores', $ReportScores,
        '--metadata', ($ReportEmbeddings + '.metadata.csv.gz'), '--out', $StageRoot
    ) @(
        (Join-Path $StageRoot 'ckda_d1_family_ood_and_baseline_metrics.csv'),
        (Join-Path $StageRoot 'ckda_d1_target_coverage_by_role_source.csv'),
        (Join-Path $StageRoot 'ckda_d1_bootstrap_intervals.csv'), $Verdict
    )

    Invoke-PythonPhase 'l2_validate_result' @(
        $Validator, '--result', $StageRoot, '--contract', $Contract
    ) @(
        $Validation, (Join-Path $StageRoot 'ckda_d1_result_report.md'),
        (Join-Path $StageRoot 'PULLBACK_ALLOWLIST.txt'), (Join-Path $StageRoot 'SHA256SUMS')
    )

    $PackagePhase = 'l2_package_pullback'
    if (Test-Phase $PackagePhase) {
        Assert-File $Pullback
        Assert-File ($Pullback + '.sha256')
    } else {
        Set-Phase $PackagePhase
        $PullbackTemp = $Pullback + '.tmp.' + $PID
        if (Test-Path -LiteralPath $PullbackTemp) { Remove-Item -LiteralPath $PullbackTemp -Force }
        & tar.exe -czf $PullbackTemp -C $StageRoot -T (Join-Path $StageRoot 'PULLBACK_ALLOWLIST.txt')
        if ($LASTEXITCODE -ne 0) { throw "Pullback packaging failed: exit=$LASTEXITCODE" }
        Move-Item -LiteralPath $PullbackTemp -Destination $Pullback -Force
        $PullbackSha = Get-Sha256 $Pullback
        [IO.File]::WriteAllText(($Pullback + '.sha256'), "$PullbackSha  $([IO.Path]::GetFileName($Pullback))`n", [Text.UTF8Encoding]::new($false))
        Complete-Phase $PackagePhase
    }

    $VerdictValue = Get-Content -LiteralPath $Verdict -Raw | ConvertFrom-Json
    $ValidationValue = Get-Content -LiteralPath $Validation -Raw | ConvertFrom-Json
    if ($VerdictValue.status -ne 'PASS' -or $ValidationValue.status -ne 'PASS') { throw 'Validated L2 terminal status is not PASS' }
    Set-Phase 'l2_complete'
    $Success = "status=PASS`nverdict=$($VerdictValue.verdict)`ngo_d2=$($VerdictValue.go_d2)`nfinal_files_opened=0`npullback=$Pullback`ncompleted_utc=$([DateTime]::UtcNow.ToString('o'))`n"
    [IO.File]::WriteAllText((Join-Path $ControlRoot 'local_l2_success.txt'), $Success, [Text.UTF8Encoding]::new($false))
} catch {
    $Failure = [ordered]@{
        status = 'CKDA_D1_LOCAL_L2_ENGINEERING_FAILURE'
        phase = if (Test-Path -LiteralPath $PhasePath) { (Get-Content -LiteralPath $PhasePath -Raw).Trim() } else { 'UNKNOWN' }
        message = $_.Exception.Message
        scientific_verdict = $null
        final_files_opened = 0
        failed_utc = [DateTime]::UtcNow.ToString('o')
    }
    [IO.File]::WriteAllText($FailurePath, (($Failure | ConvertTo-Json -Depth 4) + "`n"), [Text.UTF8Encoding]::new($false))
    throw
}
