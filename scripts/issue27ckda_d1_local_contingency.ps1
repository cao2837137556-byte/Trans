[CmdletBinding()]
param(
    [switch]$AuthorizeReviewedEmbedding
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
$Census = Join-Path $OOD 'issue27ckda_d1_benign_census_v1.py'
$TargetMetadata = Join-Path $OOD 'issue27ckda_d1_target_metadata_v1.py'
$Probe = Join-Path $OOD 'issue27ckda_d1_probe_runner_v1.py'
$CKBU = Join-Path $OOD 'issue27ckbu_unified_tshark_causal_frontend_v1.py'
$D0Audit = Join-Path $D0OOD 'issue27ckda_d0_representation_compatibility_audit_v1.py'
$D0Pilot = Join-Path $D0OOD 'issue27ckda_d0_resource_pilot_v1.py'
$NetFoundSource = Join-Path $D0Payload 'vendor\netFound'
$NetFoundModel = Join-Path $D0Payload 'vendor\netFound-base'
$LocalEmbed = Join-Path $RepoRoot 'repo\ood\issue27ckda_d1_e3_embed_local_twopass_v1.py'
$LocalEquivalence = Join-Path $RepoRoot 'repo\ood\issue27ckda_d1_e3_embed_local_twopass_equivalence_v1.py'
$LocalProgression = Join-Path $RepoRoot 'repo\ood\issue27ckda_d1_local_progression_v1.py'

$Snapshot = Join-Path $TransferRoot 'ckby_157930_extract\issue27ckby_drocc_feature_dump_v1_2026-08-07_seed27_amd_157930\ckby_drocc_feature_snapshot_seed27.npz'
$Predictions = Join-Path $TransferRoot 'ckbw_157624_extract\issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624\ckbw_record_predictions.csv.gz'
$D0Manifest = Join-Path $TransferRoot 'ckda_d0_local_lineage_inputs_20260811\ckda_d0_fit_prefix_manifest.csv'
$GothamManifest = Join-Path $CacheRoot 'ckbu_gotham_unified_causal_manifest.csv'
$AuxiliaryManifest = Join-Path $CacheRoot 'ckbu_auxiliary_unified_causal_manifest.csv'
$GothamAllowlist = Join-Path $D1Payload 'runs\mainline_docs\ckcz_gotham_source_allowlist_20260809.csv'
$AuxiliaryAllowlist = Join-Path $D1Payload 'runs\mainline_docs\ckcz_auxiliary_source_allowlist_20260809.csv'
$GothamZip = Join-Path $PaperRoot 'datasets\gotham2025\raw\GothamDataset2025.zip'
$TonRoot = Join-Path $PaperRoot 'datasets\external\ton_iot_raw_network\raw_pcap_pilot_v1'

$RunName = 'issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu'
$StageRoot = Join-Path $RepoRoot "runs\.$RunName.stage"
$ControlRoot = Join-Path $RepoRoot "runs\${RunName}_control"
$CheckpointRoot = Join-Path $RepoRoot 'runs\issue27ckda_d1_checkpoint_v1_localwin_ecb429926507d2c4'
$LogRoot = Join-Path $ControlRoot 'logs'
$IdentityPath = Join-Path $ControlRoot 'local_identity.json'
$PhasePath = Join-Path $ControlRoot 'current_phase.txt'
$FailurePath = Join-Path $ControlRoot 'engineering_failure.json'
$EmbeddingGate = Join-Path $ControlRoot 'local_embedding_review_pass.txt'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-FileSha([string]$Path, [string]$Expected) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing immutable input: $Path"
    }
    $Actual = Get-Sha256 $Path
    if ($Actual -ne $Expected) {
        throw "SHA256 mismatch: $Path actual=$Actual expected=$Expected"
    }
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
        foreach ($Output in $RequiredOutputs) {
            if (-not (Test-Path -LiteralPath $Output -PathType Leaf)) {
                throw "Completed phase lacks output: phase=$Name output=$Output"
            }
        }
        Set-Phase ("reuse_" + $Name)
        return
    }
    Set-Phase $Name
    $Log = Join-Path $LogRoot ($Name + '.log')
    & $Python @Arguments *> $Log
    if ($LASTEXITCODE -ne 0) {
        Get-Content -LiteralPath $Log -Tail 100
        throw "Phase failed: $Name exit=$LASTEXITCODE log=$Log"
    }
    foreach ($Output in $RequiredOutputs) {
        if (-not (Test-Path -LiteralPath $Output -PathType Leaf)) {
            throw "Phase produced no output: phase=$Name output=$Output"
        }
    }
    Complete-Phase $Name
}

New-Item -ItemType Directory -Force -Path $StageRoot, $ControlRoot, $CheckpointRoot, (Join-Path $CheckpointRoot 'e3_fit_select'), $LogRoot | Out-Null
Set-Phase 'startup'

try {
    $RequiredFiles = @(
        $Python, $TShark, $Contract, $RolePlan, $Census, $TargetMetadata, $Probe,
        $CKBU, $D0Audit, $D0Pilot, $LocalEmbed, $LocalEquivalence, $LocalProgression,
        $Snapshot, $Predictions, $D0Manifest, $GothamManifest, $AuxiliaryManifest,
        $GothamAllowlist, $AuxiliaryAllowlist, $GothamZip,
        (Join-Path $NetFoundModel 'config.json'), (Join-Path $NetFoundModel 'model.safetensors')
    )
    foreach ($File in $RequiredFiles) {
        if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { throw "Missing local D1 input: $File" }
    }
    foreach ($Directory in @($CacheRoot, $NetFoundSource, $TonRoot)) {
        if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { throw "Missing local D1 directory: $Directory" }
    }

    Assert-FileSha $Contract 'ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9'
    Assert-FileSha $Predictions 'd1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85'
    Assert-FileSha $Snapshot 'b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c'
    Assert-FileSha $D0Manifest '9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689'
    Assert-FileSha (Join-Path $NetFoundModel 'model.safetensors') 'e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105'

    $Identity = [ordered]@{
        status = 'CKDA_D1_LOCAL_CONTINGENCY_IDENTITY'
        contract_sha256 = Get-Sha256 $Contract
        snapshot_sha256 = Get-Sha256 $Snapshot
        predictions_sha256 = Get-Sha256 $Predictions
        d0_manifest_sha256 = Get-Sha256 $D0Manifest
        netfound_checkpoint_sha256 = Get-Sha256 (Join-Path $NetFoundModel 'model.safetensors')
        local_embedder_sha256 = Get-Sha256 $LocalEmbed
        local_equivalence_gate_sha256 = Get-Sha256 $LocalEquivalence
        python = $Python
        tshark = $TShark
        device = 'cpu'
        batch_size = 16
        report_opened = $false
    }
    $IdentityText = $Identity | ConvertTo-Json -Depth 4
    if (Test-Path -LiteralPath $IdentityPath -PathType Leaf) {
        $Existing = Get-Content -LiteralPath $IdentityPath -Raw | ConvertFrom-Json
        foreach ($Key in @('contract_sha256','snapshot_sha256','predictions_sha256','d0_manifest_sha256','netfound_checkpoint_sha256','local_embedder_sha256','local_equivalence_gate_sha256')) {
            if ([string]$Existing.$Key -ne [string]$Identity[$Key]) { throw "Local resume identity drift: $Key" }
        }
    } else {
        [IO.File]::WriteAllText($IdentityPath, ($IdentityText + "`n"), [Text.UTF8Encoding]::new($false))
    }

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

    $Preflight = Join-Path $RuntimeRoot 'preflight'
    Invoke-PythonPhase 'real_equivalence' @(
        $LocalEquivalence, '--contract', $Contract,
        '--fit-select-plan', (Join-Path $Preflight 'ckda_d1_fit_select_plan.csv'),
        '--target-metadata', (Join-Path $Preflight 'ckda_d1_fit_select_target_metadata.csv'),
        '--netfound-source', $NetFoundSource, '--netfound-checkpoint', $NetFoundModel,
        '--ckbu-decoder', $CKBU, '--d0-pilot', $D0Pilot, '--tshark', $TShark,
        '--device', 'cpu', '--batch-size', '16', '--targets', '32',
        '--out', (Join-Path $RuntimeRoot 'equivalence')
    ) @((Join-Path $RuntimeRoot 'equivalence\ckda_d1_local_twopass_equivalence.json'))

    Invoke-PythonPhase 'fit_select_role_plan' @(
        $RolePlan, '--scope', 'fit-select', '--contract', $Contract,
        '--snapshot', $Snapshot, '--out', $StageRoot
    ) @((Join-Path $StageRoot 'ckda_d1_fit_select_plan.csv'))
    $RoleAudit = Join-Path $StageRoot 'ckda_d1_role_plan_audit.json'
    $FitRoleAudit = Join-Path $StageRoot 'ckda_d1_fit_select_role_plan_audit.json'
    if (-not (Test-Path -LiteralPath $FitRoleAudit -PathType Leaf)) { Move-Item -LiteralPath $RoleAudit -Destination $FitRoleAudit }
    if (-not (Test-Path -LiteralPath $FitRoleAudit -PathType Leaf)) { throw "Fit/select role audit is absent" }

    Invoke-PythonPhase 'benign_only_i1_census' @(
        $Census, '--contract', $Contract, '--fit-prefix-manifest', $D0Manifest,
        '--d0-audit', $D0Audit, '--ckbu-decoder', $CKBU, '--tshark', $TShark,
        '--out', $StageRoot
    ) @((Join-Path $StageRoot 'ckda_d1_benign_census.json'))

    Invoke-PythonPhase 'candidate_progression' @(
        $LocalProgression, '--contract', $Contract,
        '--census', (Join-Path $StageRoot 'ckda_d1_benign_census.json'),
        '--out', (Join-Path $StageRoot 'ckda_d1_candidate_progression.json')
    ) @((Join-Path $StageRoot 'ckda_d1_candidate_progression.json'))

    Invoke-PythonPhase 'fit_select_target_metadata' @(
        $TargetMetadata, '--scope', 'fit-select', '--contract', $Contract,
        '--plan', (Join-Path $StageRoot 'ckda_d1_fit_select_plan.csv'),
        '--ckbv-root', $CacheRoot, '--gotham-manifest', $GothamManifest,
        '--auxiliary-manifest', $AuxiliaryManifest, '--gotham-allowlist', $GothamAllowlist,
        '--auxiliary-allowlist', $AuxiliaryAllowlist, '--ton-pcap-root', $TonRoot,
        '--gotham-zip', $GothamZip,
        '--out', (Join-Path $StageRoot 'ckda_d1_fit_select_target_metadata.csv')
    ) @((Join-Path $StageRoot 'ckda_d1_fit_select_target_metadata.csv'))

    if ($AuthorizeReviewedEmbedding) {
        $GateText = "status=PASS`nreview_scope=LOCAL_UNION_FRONTEND_AND_TWOPASS_ADAPTER`nlocal_embedder_sha256=$(Get-Sha256 $LocalEmbed)`nequivalence_gate_sha256=$(Get-Sha256 $LocalEquivalence)`n"
        [IO.File]::WriteAllText($EmbeddingGate, $GateText, [Text.UTF8Encoding]::new($false))
    }
    if (-not (Test-Path -LiteralPath $EmbeddingGate -PathType Leaf)) {
        Set-Phase 'precompute_complete_embedding_pending_kimi_review'
        [IO.File]::WriteAllText((Join-Path $ControlRoot 'local_precompute_success.txt'), "status=PASS`nreport_opened=0`nembeddings_started=0`n", [Text.UTF8Encoding]::new($false))
        return
    }

    $FitPlan = Join-Path $StageRoot 'ckda_d1_fit_select_plan.csv'
    $FitSha = Get-Sha256 $FitPlan
    Invoke-PythonPhase 'e3_fit_select_embeddings' @(
        $LocalEmbed, '--contract', $Contract,
        '--target-metadata', (Join-Path $StageRoot 'ckda_d1_fit_select_target_metadata.csv'),
        '--plan-sha256', $FitSha, '--netfound-source', $NetFoundSource,
        '--netfound-checkpoint', $NetFoundModel, '--ckbu-decoder', $CKBU,
        '--d0-pilot', $D0Pilot, '--tshark', $TShark, '--device', 'cpu',
        '--batch-size', '16', '--checkpoint-dir', (Join-Path $CheckpointRoot 'e3_fit_select'),
        '--out', (Join-Path $StageRoot 'ckda_d1_fit_select_embeddings.npz')
    ) @((Join-Path $StageRoot 'ckda_d1_fit_select_embeddings.npz'))

    Invoke-PythonPhase 'fit_probes_and_freeze_thresholds' @(
        $Probe, '--scope', 'fit-select', '--contract', $Contract, '--candidate', 'E3',
        '--plan', $FitPlan, '--embeddings', (Join-Path $StageRoot 'ckda_d1_fit_select_embeddings.npz'),
        '--out', $StageRoot
    ) @((Join-Path $StageRoot 'ckda_d1_threshold_freeze_marker.json'), (Join-Path $StageRoot 'ckda_d1_probe_state.npz'))

    Set-Phase 'thresholds_frozen_report_sealed_pending_kimi_review'
    [IO.File]::WriteAllText((Join-Path $ControlRoot 'local_phase_a_success.txt'), "status=PASS`nreport_opened=0`n", [Text.UTF8Encoding]::new($false))
} catch {
    $Failure = [ordered]@{
        status = 'CKDA_D1_LOCAL_ENGINEERING_FAILURE'
        phase = (Get-Content -LiteralPath $PhasePath -Raw).Trim()
        message = $_.Exception.Message
        scientific_verdict = $null
        failed_utc = [DateTime]::UtcNow.ToString('o')
    }
    [IO.File]::WriteAllText($FailurePath, (($Failure | ConvertTo-Json -Depth 4) + "`n"), [Text.UTF8Encoding]::new($false))
    throw
}
