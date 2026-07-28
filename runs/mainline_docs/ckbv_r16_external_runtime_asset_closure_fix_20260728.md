# CKBV r16 external runtime-asset closure repair

## Scope

The r15 bundle was blocked during independent pre-submission review and was
not submitted to Slurm. The review found that r15 closed the small,
bundle-local frozen dependency set but still relied on Python parser defaults
for six large runtime inputs. Because the formal program executes from the
versioned bundle payload, those defaults resolve below `payload/runs`, while
the intentionally unbundled large immutable assets live below the remote
worktree `runs` directory.

This repair changes launch-path closure and its regression tests only. It does
not change any frozen manifest, cache content, target row, 51D feature,
raw51 eligibility mask, fit/select/report role, label, threshold, candidate,
seed, decision rule, or evaluation denominator. No PCAP or validated
checkpoint is recomputed.

## Explicit remote-worktree assets

The installer owns the exact versioned path definitions below
`/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/runs`:

1. CKBE T0 root, including `tgn_source_event_plan_frozen.csv`,
   `t0_cache_audit.csv`, and `tgn_event_cache/`.
2. CKBI report-only T0 extension, including its frozen manifest, manifest
   hash, ready record, fit/select exclusion audit, recorded targets, and
   `tgn_event_cache/`.
3. CKAT C1 load plan, target index, and `hpc_canonical_c1_cache/`.
4. CKBJ C1 report-only extension, including its ready record, manifest,
   manifest hash, load plan, target index, and `c1_report_cache/`.

The installer exports all six values to Slurm under required `CKBV_*`
environment names. The compute-node script rejects a missing export before
opening scientific output and passes all six parser arguments explicitly:

- `--t0-root`
- `--report-t0-extension`
- `--c1-plan`
- `--c1-targets`
- `--c1-cache`
- `--c1-report-extension`

The formal parser assigns `None`, rather than bundle-local paths, to these six
options. Formal execution and the local runtime-asset contract mode both
reject any omitted option with the stable signature
`formal mode requires explicit remote runtime assets`. The formal program
therefore cannot silently fall back to bundle-local defaults for assets that
the bundle deliberately excludes.

## Permanent gates

1. Installer validation fails before scheduler dry validation or submission
   if any required external file or directory is absent.
2. The compute-node script repeats the same checks before creating scientific
   output or invoking the model.
3. Clean-extract bundle validation requires the installer path definitions,
   six installer exports, six required Slurm imports, immutable-asset checks,
   all six CLI wiring edges, and six default-free formal arguments.
4. Clean-extract negative tests deliberately remove one CLI edge and one
   installer asset check; both altered launch contracts must be rejected.
5. A subprocess invokes the clean-extracted formal program with five of six
   explicit assets. It must exit non-zero and name
   `--c1-report-extension`; restoring the sixth argument must emit
   `CKBU_FORMAL_RUNTIME_ASSET_CONTRACT_PASS`.
6. Large caches, PCAPs, environments, and prior run outputs remain outside the
   upload bundle and are never overwritten.

## Retry boundary

Only a new partition/job-isolated r16 run may be submitted after independent
review. It may reuse checkpoints accepted by the existing identity, schema,
coverage, and hash validators. r15 is retired before submission and provides
no runtime or scientific evidence.
