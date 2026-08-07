# CKBW seed-27 upload bundle builder.
# Stages the exact payload, LF-normalizes every text file, writes
# bundle_commit.txt (git HEAD), computes SHA256SUMS over the whole payload,
# then tars to supercompute_transfer.  Run from anywhere; paths are absolute.
$ErrorActionPreference = 'Stop'

$Worktree = 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline'
$OutDir   = 'D:\study\paper\anomaly_detection\paper04\supercompute_transfer'
$BundleName = 'issue27ckbw_tail_margin_dual_control_20260805'
$Archive = Join-Path $OutDir ($BundleName + '_upload_bundle.tar.gz')

$Modules = @(
  'issue27ab_gotham_kitsune115_frontend_feasibility',
  'issue27ac_gotham_kitsune115_attack_onset_alignment',
  'issue27ad_gotham_kitsune115_split_aware_smoke_expansion',
  'issue27af_gotham_kitsune115_larger_materialization_plan',
  'issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium',
  'issue27as_old_protocol_bounded_calibration_and_coverage_repair',
  'issue27au_coverage_aware_active_labeling_viability_diagnostic',
  'issue27ay_region_aware_attack_bank_and_score_gate_diagnostic',
  'issue27az_region_aware_ood_safe_gate_repair',
  'issue27ba_disjoint_ood_stress_pool_before_mixed_stream',
  'issue27bo_attack_future_shift_validation_without_new_support',
  'issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation',
  'issue27ckai_external_flow_feature_probe_v1',
  'issue27ckao_c1_strict_leave_device_family_canary_v1',
  'issue27ckat_canonical_time_c1_canary_v1',
  'issue27ckaw_canonical_interaction_episode_frontend_v1',
  'issue27ckbe_tgn_fullsupport_event_cache_v1',
  'issue27ckbf_tgn_m1_preflight_v1',
  'issue27ckbi_tgn_report_only_cache_extension_v1',
  'issue27ckbj_c1_report_only_cache_extension_v1',
  'issue27ckbj_tgn_m1_strict_formal_v2',
  'issue27ckbl_frontend_observability_audit_v1',
  'issue27ckbm_tabm_causal_source_calibration_v1',
  'issue27ckbo_mature_afterimage_transfer_v1',
  'issue27ckbp_source_local_normal_calibration_v1',
  'issue27ckbq_causal_minirocket_consensus_v1',
  'issue27ckbu_unified_process_rescue_formal_v1',
  'issue27ckbu_unified_tshark_causal_frontend_v1',
  'issue27ckbw_tail_margin_dual_control_v1',
  'issue27ckc_frozen_medium_mainline_replay_on_certified_1m',
  'issue27ckf_hard_ood_calibrated_worst_group_veto',
  'issue27ckg_basic_capability_diagnostic',
  'issue27ckh_direct_multihead_detector',
  'issue27cki_c4_full_data_multiclass_replay',
  'issue27cko_mechanism_frontend_v1',
  'issue27ckq_flow_temporal_evidence_frontend_v1'
)

$Copies = [System.Collections.Generic.List[object]]::new()
foreach ($m in $Modules) {
  $Copies.Add([pscustomobject]@{
    Src = "repo\ood\$m.py"; Dst = "payload\repo\ood\$m.py" })
}
foreach ($f in 'tabm.py','rtdl_num_embeddings.py','LICENSE','UPSTREAM_PROVENANCE.md') {
  $Copies.Add([pscustomobject]@{
    Src = "repo\ood\vendor\tabm_v0_0_3\$f"; Dst = "payload\repo\ood\vendor\tabm_v0_0_3\$f" })
}
foreach ($f in 'minirocket_torch.py','LICENSE','UPSTREAM_PROVENANCE.md') {
  $Copies.Add([pscustomobject]@{
    Src = "repo\ood\vendor\sktime_minirocket_v0_24_1\$f"; Dst = "payload\repo\ood\vendor\sktime_minirocket_v0_24_1\$f" })
}
foreach ($f in 'AfterImage.py','FeatureExtractor.py','netStat.py','LICENSE.original','SOURCE.md') {
  $Copies.Add([pscustomobject]@{
    Src = "repo\kitsune_frontend_original\$f"; Dst = "payload\repo\kitsune_frontend_original\$f" })
}
$Copies.Add([pscustomobject]@{ Src = 'runs\issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16\support_bank_sidecar.csv'; Dst = 'payload\runs\issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16\support_bank_sidecar.csv' })
$Copies.Add([pscustomobject]@{ Src = 'runs\issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17\certified_chunk_manifest.csv'; Dst = 'payload\runs\issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17\certified_chunk_manifest.csv' })
$Copies.Add([pscustomobject]@{ Src = 'runs\issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17\certified_attack_subset_v1.json'; Dst = 'payload\runs\issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17\certified_attack_subset_v1.json' })
$Copies.Add([pscustomobject]@{ Src = 'runs\issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10\unified_two_head_selection_audit.csv'; Dst = 'payload\runs\issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10\unified_two_head_selection_audit.csv' })
$Copies.Add([pscustomobject]@{ Src = 'runs\raw51_observable_v1\raw51_observable_v1_mask.csv'; Dst = 'payload\runs\raw51_observable_v1\raw51_observable_v1_mask.csv' })
$Copies.Add([pscustomobject]@{ Src = 'scripts\issue27ckbw_tail_margin_dual_control_formal.slurm'; Dst = 'payload\scripts\issue27ckbw_tail_margin_dual_control_formal.slurm' })
$Copies.Add([pscustomobject]@{ Src = 'scripts\issue27ckbw_install_and_submit.sh'; Dst = 'payload\scripts\issue27ckbw_install_and_submit.sh' })
foreach ($f in 'ckbw_tail_margin_dual_control_prereg_draft_20260730.md',
              'ckbw_tail_margin_dual_control_preregistered_20260803.md',
              'ckbw_tail_margin_dual_control_preregistered_20260803.md.sha256',
              'ckbw_implementation_handoff_20260805.md',
              'ckbw_implementation_self_review_20260805.md') {
  $Copies.Add([pscustomobject]@{ Src = "runs\mainline_docs\$f"; Dst = "payload\runs\mainline_docs\$f" })
}

$Staging = Join-Path $env:TEMP ($BundleName + '_staging')
$Root = Join-Path $Staging $BundleName
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force $Root | Out-Null

foreach ($c in $Copies) {
  $src = Join-Path $Worktree $c.Src
  if (-not (Test-Path $src)) { throw "missing source: $src" }
  $dst = Join-Path $Root $c.Dst
  New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  Copy-Item $src $dst
}

# LF-normalize every staged text file (payload is text-only).
Get-ChildItem -Recurse -File $Root | ForEach-Object {
  $bytes = [IO.File]::ReadAllBytes($_.FullName)
  $text = [Text.Encoding]::UTF8.GetString($bytes)
  $text = $text -replace "`r`n", "`n" -replace "`r", ''
  [IO.File]::WriteAllText($_.FullName, $text, (New-Object Text.UTF8Encoding($false)))
}

# raw51 mask must hash to the immutable identity after LF normalization.
$maskPath = Join-Path $Root 'payload\runs\raw51_observable_v1\raw51_observable_v1_mask.csv'
$maskSha = (Get-FileHash -LiteralPath $maskPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($maskSha -ne 'b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df') {
  throw "raw51 mask sha256 after LF normalization drifted: $maskSha"
}

$head = (git -C $Worktree rev-parse HEAD).Trim()
[IO.File]::WriteAllText((Join-Path $Root 'bundle_commit.txt'), "$head`n", (New-Object Text.UTF8Encoding($false)))

$sums = New-Object System.Collections.Generic.List[string]
Get-ChildItem -Recurse -File $Root | Sort-Object FullName | ForEach-Object {
  $rel = $_.FullName.Substring($Root.Length + 1) -replace '\\', '/'
  if ($rel -eq 'SHA256SUMS') { return }
  $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  $sums.Add("$hash  $rel")
}
[IO.File]::WriteAllText((Join-Path $Root 'SHA256SUMS'), ($sums -join "`n") + "`n", (New-Object Text.UTF8Encoding($false)))

New-Item -ItemType Directory -Force $OutDir | Out-Null
if (Test-Path $Archive) { Remove-Item -Force $Archive }
$TarExe = Join-Path $env:SystemRoot 'System32\tar.exe'
& $TarExe -C $Staging -czf $Archive $BundleName
if ($LASTEXITCODE -ne 0) { throw "tar failed with exit $LASTEXITCODE" }

$archiveSha = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText("$Archive.sha256", "$archiveSha`n", (New-Object Text.UTF8Encoding($false)))

Remove-Item -Recurse -Force $Staging
"CKBW_BUNDLE_BUILT $Archive"
"CKBW_BUNDLE_SHA256 $archiveSha"
