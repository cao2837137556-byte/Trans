param(
    [string]$RepoRoot = 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline',
    [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer',
    [string]$BundleName = 'issue27ckbv_checkpointed_process_seed27_dual_20260728_r16'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$bundleRoot = Join-Path $TransferRoot $BundleName
$stageRoot = Join-Path $bundleRoot $BundleName
$archive = Join-Path $TransferRoot "${BundleName}_upload_bundle.tar.gz"
$archiveCandidate = "$archive.candidate"
$archiveHash = "$archive.sha256"

foreach ($path in @($bundleRoot, $archive, $archiveCandidate, $archiveHash)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing bundle artifact: $path"
    }
}

$payloadFiles = @(
    'repo/ood/issue27ab_gotham_kitsune115_frontend_feasibility.py',
    'repo/ood/issue27ac_gotham_kitsune115_attack_onset_alignment.py',
    'repo/ood/issue27ad_gotham_kitsune115_split_aware_smoke_expansion.py',
    'repo/ood/issue27af_gotham_kitsune115_larger_materialization_plan.py',
    'repo/ood/issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium.py',
    'repo/ood/issue27as_old_protocol_bounded_calibration_and_coverage_repair.py',
    'repo/ood/issue27au_coverage_aware_active_labeling_viability_diagnostic.py',
    'repo/ood/issue27ay_region_aware_attack_bank_and_score_gate_diagnostic.py',
    'repo/ood/issue27az_region_aware_ood_safe_gate_repair.py',
    'repo/ood/issue27ba_disjoint_ood_stress_pool_before_mixed_stream.py',
    'repo/ood/issue27bo_attack_future_shift_validation_without_new_support.py',
    'repo/ood/issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation.py',
    'repo/ood/issue27ckai_external_flow_feature_probe_v1.py',
    'repo/ood/issue27ckao_c1_strict_leave_device_family_canary_v1.py',
    'repo/ood/issue27ckat_canonical_time_c1_canary_v1.py',
    'repo/ood/issue27ckaw_canonical_interaction_episode_frontend_v1.py',
    'repo/ood/issue27ckbe_tgn_fullsupport_event_cache_v1.py',
    'repo/ood/issue27ckbf_tgn_m1_preflight_v1.py',
    'repo/ood/issue27ckbi_tgn_report_only_cache_extension_v1.py',
    'repo/ood/issue27ckbj_c1_report_only_cache_extension_v1.py',
    'repo/ood/issue27ckbj_tgn_m1_strict_formal_v2.py',
    'repo/ood/issue27ckbl_frontend_observability_audit_v1.py',
    'repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py',
    'repo/ood/issue27ckbo_mature_afterimage_transfer_v1.py',
    'repo/ood/issue27ckbp_source_local_normal_calibration_v1.py',
    'repo/ood/issue27ckbq_causal_minirocket_consensus_v1.py',
    'repo/ood/issue27ckbu_parallel_cache_resume_v1.py',
    'repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py',
    'repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py',
    'repo/ood/issue27ckbv_checkpointed_sparse_process_frontend_v1.py',
    'repo/ood/issue27ckc_frozen_medium_mainline_replay_on_certified_1m.py',
    'repo/ood/issue27ckf_hard_ood_calibrated_worst_group_veto.py',
    'repo/ood/issue27ckg_basic_capability_diagnostic.py',
    'repo/ood/issue27ckh_direct_multihead_detector.py',
    'repo/ood/issue27cki_c4_full_data_multiclass_replay.py',
    'repo/ood/issue27cko_mechanism_frontend_v1.py',
    'repo/ood/issue27ckq_flow_temporal_evidence_frontend_v1.py',
    'repo/kitsune_frontend_original/AfterImage.py',
    'repo/kitsune_frontend_original/FeatureExtractor.py',
    'repo/kitsune_frontend_original/LICENSE.original',
    'repo/kitsune_frontend_original/netStat.py',
    'repo/kitsune_frontend_original/SOURCE.md',
    'repo/ood/vendor/sktime_minirocket_v0_24_1/LICENSE',
    'repo/ood/vendor/sktime_minirocket_v0_24_1/minirocket_torch.py',
    'repo/ood/vendor/sktime_minirocket_v0_24_1/UPSTREAM_PROVENANCE.md',
    'repo/ood/vendor/tabm_v0_0_3/LICENSE',
    'repo/ood/vendor/tabm_v0_0_3/rtdl_num_embeddings.py',
    'repo/ood/vendor/tabm_v0_0_3/tabm.py',
    'repo/ood/vendor/tabm_v0_0_3/UPSTREAM_PROVENANCE.md',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/aux_process_support_candidate_manifest.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/contract.json',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/independent_validation.json',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/input_file_hashes.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/manifest.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/pair_exact_join_audit.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/reserved_toniot_conn_sources.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/summary.md',
    'runs/issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16/support_bank_sidecar.csv',
    'runs/issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17/certified_chunk_manifest.csv',
    'runs/issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17/certified_attack_subset_v1.json',
    'runs/issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10/unified_two_head_selection_audit.csv',
    'runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv',
    'runs/mainline_docs/ckbv_checkpointed_sparse_recovery_preregistered_20260725.md',
    'runs/mainline_docs/ckbv_r13_finalization_boundary_fix_20260727.md',
    'runs/mainline_docs/ckbv_r14_formal_handoff_contract_fix_20260727.md',
    'runs/mainline_docs/ckbv_r15_formal_dependency_closure_fix_20260728.md',
    'runs/mainline_docs/ckbv_r16_external_runtime_asset_closure_fix_20260728.md',
    'runs/mainline_docs/hpc_failure_ledger_and_launch_gate_20260725.md',
    'scripts/issue27ckbv_checkpointed_process_formal.slurm',
    'scripts/issue27ckbv_install_and_submit_dual.sh',
    'scripts/issue27ckbv_status_dual.sh',
    'scripts/issue27ckbv_validate_and_pack_seed27.sh',
    'runs/raw51_observable_v1/raw51_observable_v1_mask.csv',
    'runs/raw51_observable_v1/raw51_observable_v1_contract.json',
    'runs/raw51_observable_v1/README.md'
)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$textExtensions = @('', '.py', '.sh', '.slurm', '.md', '.txt', '.csv', '.json', '.original')
New-Item -ItemType Directory -Path $stageRoot | Out-Null

foreach ($relative in $payloadFiles) {
    $source = Join-Path $RepoRoot ($relative -replace '/', '\')
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing payload source: $source"
    }
    $target = Join-Path $stageRoot ("payload\" + ($relative -replace '/', '\'))
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    if ($textExtensions -contains [System.IO.Path]::GetExtension($source).ToLowerInvariant()) {
        $content = [System.IO.File]::ReadAllText($source)
        $content = $content.Replace("`r`n", "`n").Replace("`r", "`n")
        [System.IO.File]::WriteAllText($target, $content, $utf8NoBom)
    }
    else {
        [System.IO.File]::WriteAllBytes(
            $target,
            [System.IO.File]::ReadAllBytes($source)
        )
    }
}

$commit = (& git -C $RepoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-f]{40}$') {
    throw 'Cannot resolve repository commit'
}
[System.IO.File]::WriteAllText(
    (Join-Path $stageRoot 'bundle_commit.txt'),
    "$commit`n",
    $utf8NoBom
)

$readme = @'
# CKBV checkpointed process seed-27 HPC bundle

This is one result-producing AMD/Intel submission chain. It resumes validated
CKBU caches, checkpoints Gotham per PCAP member and ToN per file, applies a
measured completion projection and stall timeouts, then runs the unchanged
CKBU seed-27 formal model and result validator.

All text transfer copies are canonicalized to UTF-8/LF. Scientific table
records are unchanged and every transferred byte is bound by SHA256SUMS.
The complete frozen formal-input closure is included and checked by canonical
LF SHA-256 locally, after clean extraction, before submission, and again on
the compute node.

Run `payload/scripts/issue27ckbv_install_and_submit_dual.sh` from this extracted
directory in the already logged-in VS Code HPC terminal. The exact versioned
payload is executed in place; no existing remote worktree file is overwritten.
The installer is safe after a partial dual submission: a recorded job is not
submitted twice, while a missing second partition can still be submitted.
'@
[System.IO.File]::WriteAllText(
    (Join-Path $stageRoot 'README_run_on_hpc.md'),
    ($readme -replace "`r`n", "`n") + "`n",
    $utf8NoBom
)

$checksumFiles = @(
    'bundle_commit.txt',
    'README_run_on_hpc.md'
) + ($payloadFiles | ForEach-Object { "payload/$_" })

foreach ($relative in $checksumFiles) {
    $path = Join-Path $stageRoot ($relative -replace '/', '\')
    if ([System.IO.File]::ReadAllBytes($path) -contains 13) {
        throw "Text payload is not LF-only: $relative"
    }
}

$checksumLines = foreach ($relative in ($checksumFiles | Sort-Object)) {
    $path = Join-Path $stageRoot ($relative -replace '/', '\')
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $relative"
}
[System.IO.File]::WriteAllText(
    (Join-Path $stageRoot 'SHA256SUMS'),
    ($checksumLines -join "`n") + "`n",
    $utf8NoBom
)

Push-Location $bundleRoot
try {
    & tar -czf $archiveCandidate $BundleName
    if ($LASTEXITCODE -ne 0) {
        throw 'tar archive creation failed'
    }
}
finally {
    Pop-Location
}

$verifyRoot = Join-Path $bundleRoot '_verify_extract'
New-Item -ItemType Directory -Path $verifyRoot | Out-Null
& tar -xzf $archiveCandidate -C $verifyRoot
if ($LASTEXITCODE -ne 0) {
    throw 'tar archive verification extraction failed'
}

$verifiedStage = Join-Path $verifyRoot $BundleName
foreach ($relative in $checksumFiles) {
    $expectedLine = $checksumLines |
        Where-Object { $_ -like "*  $relative" } |
        Select-Object -First 1
    $expected = ($expectedLine -split '\s+')[0]
    $path = Join-Path $verifiedStage ($relative -replace '/', '\')
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Post-extraction hash mismatch: $relative"
    }
    if ([System.IO.File]::ReadAllBytes($path) -contains 13) {
        throw "Post-extraction CR byte found: $relative"
    }
}

$payloadOod = Join-Path $verifiedStage 'payload\repo\ood'
$verifiedCheckpoint = Join-Path $payloadOod 'issue27ckbv_checkpointed_sparse_process_frontend_v1.py'
$verifiedFormal = Join-Path $payloadOod 'issue27ckbu_unified_process_rescue_formal_v1.py'
$verifiedSlurm = Join-Path $verifiedStage 'payload\scripts\issue27ckbv_checkpointed_process_formal.slurm'
$verifiedInstaller = Join-Path $verifiedStage 'payload\scripts\issue27ckbv_install_and_submit_dual.sh'
$verifiedValidator = Join-Path $verifiedStage 'payload\scripts\issue27ckbv_validate_and_pack_seed27.sh'
$checkpointText = [System.IO.File]::ReadAllText($verifiedCheckpoint)
$formalText = [System.IO.File]::ReadAllText($verifiedFormal)
$slurmText = [System.IO.File]::ReadAllText($verifiedSlurm)
$installerText = [System.IO.File]::ReadAllText($verifiedInstaller)
$validatorText = [System.IO.File]::ReadAllText($verifiedValidator)

function Get-CkbvExternalRuntimeAssetClosureErrors {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FormalText,
        [Parameter(Mandatory = $true)]
        [string]$SlurmText,
        [Parameter(Mandatory = $true)]
        [string]$InstallerText
    )

    $errors = [System.Collections.Generic.List[string]]::new()
    $installerPathDefinitions = @(
        'T0_ROOT="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"',
        'REPORT_T0_EXTENSION="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"',
        'C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"',
        'C1_PLAN="$C1_ROOT/canonical_source_load_plan.csv"',
        'C1_TARGETS="$C1_ROOT/canonical_source_target_index.csv"',
        'C1_CACHE="$C1_ROOT/hpc_canonical_c1_cache"',
        'C1_REPORT_EXTENSION="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"'
    )
    foreach ($required in $installerPathDefinitions) {
        if (-not $InstallerText.Contains($required)) {
            $errors.Add("installer path definition missing: $required")
        }
    }

    $slurmExportImports = @(
        'T0_ROOT=${CKBV_T0_ROOT:?missing CKBV_T0_ROOT}',
        'REPORT_T0_EXTENSION=${CKBV_REPORT_T0_EXTENSION:?missing CKBV_REPORT_T0_EXTENSION}',
        'C1_PLAN=${CKBV_C1_PLAN:?missing CKBV_C1_PLAN}',
        'C1_TARGETS=${CKBV_C1_TARGETS:?missing CKBV_C1_TARGETS}',
        'C1_CACHE=${CKBV_C1_CACHE:?missing CKBV_C1_CACHE}',
        'C1_REPORT_EXTENSION=${CKBV_C1_REPORT_EXTENSION:?missing CKBV_C1_REPORT_EXTENSION}'
    )
    foreach ($required in $slurmExportImports) {
        if (-not $SlurmText.Contains($required)) {
            $errors.Add("slurm required export import missing: $required")
        }
    }

    $installerExports = @(
        'CKBV_T0_ROOT=$T0_ROOT',
        'CKBV_REPORT_T0_EXTENSION=$REPORT_T0_EXTENSION',
        'CKBV_C1_PLAN=$C1_PLAN',
        'CKBV_C1_TARGETS=$C1_TARGETS',
        'CKBV_C1_CACHE=$C1_CACHE',
        'CKBV_C1_REPORT_EXTENSION=$C1_REPORT_EXTENSION'
    )
    foreach ($required in $installerExports) {
        if (-not $InstallerText.Contains($required)) {
            $errors.Add("installer Slurm export missing: $required")
        }
    }

    $formalCliWiring = @(
        '--t0-root "$T0_ROOT"',
        '--report-t0-extension "$REPORT_T0_EXTENSION"',
        '--c1-plan "$C1_PLAN"',
        '--c1-targets "$C1_TARGETS"',
        '--c1-cache "$C1_CACHE"',
        '--c1-report-extension "$C1_REPORT_EXTENSION"'
    )
    foreach ($required in $formalCliWiring) {
        if (-not $SlurmText.Contains($required)) {
            $errors.Add("slurm formal CLI wiring missing: $required")
        }
    }

    $formalRequiredAssets = @(
        'parser.add_argument("--t0-root", type=Path, default=None)',
        'parser.add_argument("--report-t0-extension", type=Path, default=None)',
        'parser.add_argument("--c1-plan", type=Path, default=None)',
        'parser.add_argument("--c1-targets", type=Path, default=None)',
        'parser.add_argument("--c1-cache", type=Path, default=None)',
        'parser.add_argument("--c1-report-extension", type=Path, default=None)',
        'if args.mode in {"formal", "runtime-asset-contract"}:',
        '"formal mode requires explicit remote runtime assets; "',
        '"status": "CKBU_FORMAL_RUNTIME_ASSET_CONTRACT_PASS"'
    )
    foreach ($required in $formalRequiredAssets) {
        if (-not $FormalText.Contains($required)) {
            $errors.Add("formal explicit runtime-asset gate missing: $required")
        }
    }

    $requiredAssetChecks = @(
        '"$T0_ROOT/tgn_source_event_plan_frozen.csv"',
        '"$T0_ROOT/t0_cache_audit.csv"',
        '"$REPORT_T0_EXTENSION/report_only_extension_manifest_frozen.csv"',
        '"$REPORT_T0_EXTENSION/report_only_extension_manifest_sha256.txt"',
        '"$REPORT_T0_EXTENSION/extension_ready.json"',
        '"$REPORT_T0_EXTENSION/report_only_fit_select_exclusion_audit.csv"',
        '"$C1_PLAN"',
        '"$C1_TARGETS"',
        '"$C1_REPORT_EXTENSION/c1_report_extension_ready.json"',
        '"$C1_REPORT_EXTENSION/c1_report_only_extension_manifest.csv"',
        '"$C1_REPORT_EXTENSION/c1_report_only_extension_manifest_sha256.txt"',
        '"$C1_REPORT_EXTENSION/canonical_source_load_plan.csv"',
        '"$C1_REPORT_EXTENSION/canonical_source_target_index.csv"',
        '"$T0_ROOT/tgn_event_cache"',
        '"$REPORT_T0_EXTENSION/tgn_event_cache"',
        '"$C1_CACHE"',
        '"$C1_REPORT_EXTENSION/c1_report_cache"'
    )
    foreach ($required in $requiredAssetChecks) {
        if (-not $SlurmText.Contains($required)) {
            $errors.Add("slurm immutable asset check missing: $required")
        }
        if (-not $InstallerText.Contains($required)) {
            $errors.Add("installer immutable asset check missing: $required")
        }
    }
    return $errors
}

$externalRuntimeClosureErrors = @(
    Get-CkbvExternalRuntimeAssetClosureErrors `
        -FormalText $formalText `
        -SlurmText $slurmText `
        -InstallerText $installerText
)
if ($externalRuntimeClosureErrors.Count -ne 0) {
    throw (
        "Clean-extract external runtime asset closure failed: " +
        ($externalRuntimeClosureErrors -join '; ')
    )
}

# Negative wiring regressions: deleting either a formal CLI edge or an
# installer-side immutable-input check must be detected before publication.
$negativeSlurmText = $slurmText.Replace('--t0-root "$T0_ROOT"', '')
$negativeSlurmErrors = @(
    Get-CkbvExternalRuntimeAssetClosureErrors `
        -FormalText $formalText `
        -SlurmText $negativeSlurmText `
        -InstallerText $installerText
)
if (
    $negativeSlurmErrors.Count -eq 0 -or
    -not ($negativeSlurmErrors -contains 'slurm formal CLI wiring missing: --t0-root "$T0_ROOT"')
) {
    throw 'Clean-extract negative formal CLI wiring regression did not fail closed'
}

$negativeInstallerText = $installerText.Replace(
    '"$T0_ROOT/tgn_source_event_plan_frozen.csv"',
    ''
)
$negativeInstallerErrors = @(
    Get-CkbvExternalRuntimeAssetClosureErrors `
        -FormalText $formalText `
        -SlurmText $slurmText `
        -InstallerText $negativeInstallerText
)
if (
    $negativeInstallerErrors.Count -eq 0 -or
    -not (
        $negativeInstallerErrors -contains (
            'installer immutable asset check missing: ' +
            '"$T0_ROOT/tgn_source_event_plan_frozen.csv"'
        )
    )
) {
    throw 'Clean-extract negative installer asset-check regression did not fail closed'
}

foreach ($required in @(
    'def select_c1_audit_decisions(',
    'not record.uid.startswith("ton:")',
    '"c1_threshold_only_ton_rows"',
    '"c1_ton_policy": "conservative_all_hard_no_frozen_ckbq"',
    'missing non-ToN frozen coverage was not rejected',
    'CKBV_FORMAL_HANDOFF_DIRECTORIES = frozenset(',
    'CKBV_FORMAL_HANDOFF_FILES = frozenset(',
    'def validate_formal_handoff_dir(',
    '"member_logs"',
    '"ckbv_gotham_checkpoint_ready.json"',
    '"ckbv_source_aggregation_audit.csv"',
    '"ton_file_cache"',
    '"ckbv_throughput_projection.json"',
    'unexpected staged output was not rejected',
    'wrong-type staged output was not rejected',
    'FROZEN_FORMAL_DEPENDENCIES = (',
    'def validate_frozen_formal_dependency_closure(',
    'frozen formal dependency closure failed',
    '1db1e0e090398218f1d107e8468e17ac457c9e837c389722036b27b74e4962dd',
    'ea222d777ea9911264e906418749868936810a8bf8c4f185078fb190ca7ed851',
    '940842193c5e56db679270135d3c9d9fbbf1db0b14bfa01048435bfb6fae3d0c',
    '3fa394628211df286dd71d66da077201c9b6fd85367d9a7f2c9d7593d6a4f189'
)) {
    if (-not $formalText.Contains($required)) {
        throw "Clean-extract mixed C1 audit regression gate missing: $required"
    }
}
foreach ($required in @(
    'EXPECTED_PROTOCOLS = {',
    'per-source sensitivity reconciliation failed',
    'select C1 provenance boundary drift',
    'environment raw51 provenance drift',
    'run_spec raw51 provenance drift'
)) {
    if (-not $validatorText.Contains($required)) {
        throw "Clean-extract result-finalization gate missing: $required"
    }
}
foreach ($required in @(
    'MEMBER_PROGRESS_STATUS = "CKBV_MEMBER_PROGRESS_STATE_V1"',
    'worker_watchdog_reason(',
    '--progress-state',
    '--heartbeat-seconds'
)) {
    if (-not $checkpointText.Contains($required)) {
        throw "Clean-extract worker-watchdog contract missing: $required"
    }
}
$memberWatchdogStart = $checkpointText.IndexOf('def run_member_subprocess(')
$memberWatchdogEnd = $checkpointText.IndexOf(
    'def run_batch(',
    $memberWatchdogStart
)
if ($memberWatchdogStart -lt 0 -or $memberWatchdogEnd -le $memberWatchdogStart) {
    throw 'Cannot isolate clean-extract Gotham member watchdog implementation'
}
$memberWatchdogText = $checkpointText.Substring(
    $memberWatchdogStart,
    $memberWatchdogEnd - $memberWatchdogStart
)
if ($memberWatchdogText.Contains('if size != last_size:')) {
    throw 'Retired log-size-only Gotham watchdog returned in clean extraction'
}
foreach ($required in @(
    'GOTHAM_WORKERS=${CKBV_GOTHAM_WORKERS:-2}',
    '--member-timeout-seconds 14400 --stale-seconds 3600',
    '--liveness-seconds 300 --heartbeat-seconds 60'
)) {
    if (-not $slurmText.Contains($required)) {
        throw "Clean-extract Slurm runtime guard missing: $required"
    }
}
foreach ($required in @(
    'seed27_amd_154761',
    'seed27_amd_154620',
    'seed27_intel_154621',
    'seed27_amd_154606',
    'seed27_intel_154607'
)) {
    if (-not $installerText.Contains($required)) {
        throw "Clean-extract validated checkpoint donor missing: $required"
    }
}
foreach ($required in @('seed27_amd_154761', 'seed27_amd_154620', 'seed27_intel_154621')) {
    if (-not $slurmText.Contains($required)) {
        throw "Slurm donor list drifted from installer: $required"
    }
}
$raw51Expected = 'b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df'
$raw51Path = Join-Path $verifiedStage 'payload\runs\raw51_observable_v1\raw51_observable_v1_mask.csv'
if (-not (Test-Path -LiteralPath $raw51Path)) {
    throw "Clean-extract raw51 mask missing from payload"
}
$raw51Actual = (Get-FileHash -LiteralPath $raw51Path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($raw51Actual -ne $raw51Expected) {
    throw "Clean-extract raw51 mask sha256 mismatch: $raw51Actual"
}
foreach ($required in @($raw51Expected, 'CKBV_RAW51_MASK')) {
    if (-not $installerText.Contains($required)) {
        throw "Installer missing raw51 wiring token: $required"
    }
}
if (-not $slurmText.Contains('--raw51-mask')) {
    throw "Slurm missing raw51 CLI wiring: --raw51-mask"
}
$unexpectedPaths = Get-ChildItem -LiteralPath $verifiedStage -Recurse -Force |
    Where-Object {
        $_.FullName -match '([\\/])(\.git|__pycache__|datasets|wheelhouse|env)([\\/]|$)' -or
        $_.Extension -in @('.pcap', '.pcapng', '.npz', '.pt', '.pth', '.whl')
    }
if ($unexpectedPaths) {
    $listed = ($unexpectedPaths.FullName -join '; ')
    throw "Clean-extract payload contains forbidden runtime/data artifacts: $listed"
}

$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $payloadOod
    $primaryModules = @(
        'issue27ckbu_unified_tshark_causal_frontend_v1.py',
        'issue27ckbu_unified_process_rescue_formal_v1.py',
        'issue27ckbu_parallel_cache_resume_v1.py',
        'issue27ckbv_checkpointed_sparse_process_frontend_v1.py'
    ) | ForEach-Object { Join-Path $payloadOod $_ }
    & python -m py_compile @primaryModules
    if ($LASTEXITCODE -ne 0) {
        throw 'Clean-extract Python compile/import verification failed'
    }
    $contractTests = @(
        [pscustomobject]@{
            Script = 'issue27ckbu_unified_tshark_causal_frontend_v1.py'
            Mode = 'unit'
        },
        [pscustomobject]@{
            Script = 'issue27ckbu_unified_process_rescue_formal_v1.py'
            Mode = 'contract-unit'
        },
        [pscustomobject]@{
            Script = 'issue27ckbu_parallel_cache_resume_v1.py'
            Mode = 'unit'
        },
        [pscustomobject]@{
            Script = 'issue27ckbv_checkpointed_sparse_process_frontend_v1.py'
            Mode = 'unit'
        }
    )
    foreach ($test in $contractTests) {
        $script = Join-Path $payloadOod $test.Script
        & python $script --mode $test.Mode
        if ($LASTEXITCODE -ne 0) {
            throw "Clean-extract contract test failed: $($test.Script)"
        }
    }

    # Exercise the formal parser itself, not only static text inspection.
    # Omitting one of the six remote-worktree assets must fail immediately
    # with a stable signature; restoring all six must pass without touching
    # data, checkpoints, or the scientific model.
    $runtimeAssetArgs = @(
        '--mode', 'runtime-asset-contract',
        '--t0-root', '/explicit/t0',
        '--report-t0-extension', '/explicit/report-t0',
        '--c1-plan', '/explicit/c1-plan.csv',
        '--c1-targets', '/explicit/c1-targets.csv',
        '--c1-cache', '/explicit/c1-cache'
    )
    $runtimeAssetNegativeStdout = Join-Path $verifyRoot 'formal_runtime_asset_negative.stdout.txt'
    $runtimeAssetNegativeStderr = Join-Path $verifyRoot 'formal_runtime_asset_negative.stderr.txt'
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
    $runtimeAssetNegativeProcess = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList (@($verifiedFormal) + $runtimeAssetArgs) `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $runtimeAssetNegativeStdout `
        -RedirectStandardError $runtimeAssetNegativeStderr
    if ($runtimeAssetNegativeProcess.ExitCode -eq 0) {
        throw 'Clean-extract missing explicit runtime asset did not fail closed'
    }
    $runtimeAssetNegativeEvidence = [System.IO.File]::ReadAllText(
        $runtimeAssetNegativeStderr
    )
    $runtimeAssetNegativeSignature = (
        'formal mode requires explicit remote runtime assets; ' +
        'missing: --c1-report-extension'
    )
    if (-not $runtimeAssetNegativeEvidence.Contains($runtimeAssetNegativeSignature)) {
        throw 'Clean-extract missing explicit runtime asset failed for the wrong reason'
    }
    Write-Output (
        'CKBV_NEGATIVE_RUNTIME_ASSET_GATE_PASS=' +
        $runtimeAssetNegativeSignature
    )

    & python $verifiedFormal @runtimeAssetArgs `
        --c1-report-extension /explicit/c1-report
    if ($LASTEXITCODE -ne 0) {
        throw 'Clean-extract restored explicit runtime assets did not pass'
    }

    # Negative packaging regression: reproduce the r14 omission in the clean
    # extraction.  The formal contract must fail before any scientific work,
    # then pass again after the exact file is restored.
    $omissionTarget = Join-Path $verifiedStage (
        'payload\runs\issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_' +
        '2026-06-16\support_bank_sidecar.csv'
    )
    $omissionBackup = "$omissionTarget.omitted"
    $omissionStdout = Join-Path $verifyRoot 'formal_dependency_omission.stdout.txt'
    $omissionStderr = Join-Path $verifyRoot 'formal_dependency_omission.stderr.txt'
    Move-Item -LiteralPath $omissionTarget -Destination $omissionBackup
    $omissionExit = $null
    try {
        $pythonExe = (Get-Command python -ErrorAction Stop).Source
        $omissionProcess = Start-Process `
            -FilePath $pythonExe `
            -ArgumentList @($verifiedFormal, '--mode', 'contract-unit') `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $omissionStdout `
            -RedirectStandardError $omissionStderr
        $omissionExit = $omissionProcess.ExitCode
    }
    finally {
        Move-Item -LiteralPath $omissionBackup -Destination $omissionTarget
    }
    if ($omissionExit -eq 0) {
        throw 'Clean-extract negative omission regression did not fail closed'
    }
    $omissionEvidence = [System.IO.File]::ReadAllText($omissionStderr)
    if (-not $omissionEvidence.Contains('frozen formal dependency closure failed')) {
        throw 'Clean-extract negative omission regression failed for the wrong reason'
    }
    & python $verifiedFormal --mode contract-unit
    if ($LASTEXITCODE -ne 0) {
        throw 'Clean-extract formal dependency restoration regression failed'
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}

Move-Item -LiteralPath $archiveCandidate -Destination $archive
$archiveSha = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    $archiveHash,
    "$archiveSha  $(Split-Path -Leaf $archive)`n",
    $utf8NoBom
)

Write-Output "CKBV_BUNDLE=$archive"
Write-Output "CKBV_BUNDLE_SHA256=$archiveSha"
Write-Output "CKBV_BUNDLE_BYTES=$((Get-Item -LiteralPath $archive).Length)"
Write-Output "CKBV_BUNDLE_COMMIT=$commit"
Write-Output 'CKBV_CLEAN_EXTRACT_FULL_CONTRACT_PASS'
