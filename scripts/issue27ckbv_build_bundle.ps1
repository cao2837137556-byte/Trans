param(
    [string]$RepoRoot = 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline',
    [string]$TransferRoot = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer',
    [string]$BundleName = 'issue27ckbv_checkpointed_process_seed27_dual_20260726_r5'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$bundleRoot = Join-Path $TransferRoot $BundleName
$stageRoot = Join-Path $bundleRoot $BundleName
$archive = Join-Path $TransferRoot "${BundleName}_upload_bundle.tar.gz"
$archiveHash = "$archive.sha256"

foreach ($path in @($bundleRoot, $archive, $archiveHash)) {
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
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/aux_process_support_candidate_manifest.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/contract.json',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/independent_validation.json',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/input_file_hashes.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/manifest.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/pair_exact_join_audit.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/reserved_toniot_conn_sources.csv',
    'runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/summary.md',
    'runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv',
    'runs/mainline_docs/ckbv_checkpointed_sparse_recovery_preregistered_20260725.md',
    'runs/mainline_docs/hpc_failure_ledger_and_launch_gate_20260725.md',
    'scripts/issue27ckbv_checkpointed_process_formal.slurm',
    'scripts/issue27ckbv_install_and_submit_dual.sh',
    'scripts/issue27ckbv_status_dual.sh',
    'scripts/issue27ckbv_validate_and_pack_seed27.sh'
)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$textExtensions = @('.py', '.sh', '.slurm', '.md', '.txt', '.csv', '.json')
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
    & tar -czf $archive $BundleName
    if ($LASTEXITCODE -ne 0) {
        throw 'tar archive creation failed'
    }
}
finally {
    Pop-Location
}

$verifyRoot = Join-Path $bundleRoot '_verify_extract'
New-Item -ItemType Directory -Path $verifyRoot | Out-Null
& tar -xzf $archive -C $verifyRoot
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
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}

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
