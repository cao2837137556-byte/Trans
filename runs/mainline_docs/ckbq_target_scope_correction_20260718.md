# CKBQ target-scope correction after jobs 152413/152414

## Failure classification

The first paired CKBQ seed-27 jobs produced no scientific result:

- AMD `152413`: `FAILED 1:0`, elapsed `00:04:28`, MaxRSS `3,620,584K`;
- Intel `152414`: `FAILED 1:0`, elapsed `00:04:51`, MaxRSS `3,797,232K`.

Both failed deterministically in the pre-training causal audit.  This was not
an environment, memory, scheduler, or dual-output collision.  The audit
incorrectly assumed that every source in the immutable 1M row-role split must
form a contiguous chronological `fit -> select -> report` block.

## Frozen-data fact

Local reconstruction from the unchanged canonical target index and raw Gotham
archive reproduced the three sources reported by both jobs:

| source | fit targets | select targets | report targets | phase interleavings |
|---|---:|---:|---:|---:|
| `processed/iotsim-city-power-1.csv` | 137 | 23 | 0 | 136 |
| `processed/iotsim-combined-cycle-10.csv` | 33 | 6 | 3,129 | 39 |
| `processed/iotsim-ip-camera-museum-1.csv` | 215 | 40 | 0 | 212 |

Totals remain the frozen `385` support-train and `69` support-val rows.  The
interleaving is a property of the existing row-role split; deleting the later
fit rows would violate the full-support contract and silently change the
experiment.

## Corrected executable contract

The source-block assertion is replaced by target-level causal isolation:

1. fit windows allow untargeted past raw events and frozen fit targets only;
2. select windows allow untargeted past raw events plus frozen fit/select
   targets only;
3. report windows are label-free, current-event-inclusive, past-only, and use
   a frozen model and thresholds;
4. any later-phase frozen target inside an earlier-phase 32-event window is
   skipped and counted;
5. cross-phase duplicate target positions, missing target alignments, future
   reads, or exclusion of the current target remain fatal.

The original 26-source CKBE manifest/hash, four-source report extension,
strict 1M role tables, C1 inputs, 385/69 support lineage, and model/gate design
are unchanged.

## Real target-position regression

Three temporary local cache copies were rebuilt from the original archive only
to test the corrected window policy.  They are not part of Git or the formal
cache contract.  Results:

- reconstructed frozen targets: `3,583` (`385 fit`, `69 select`, `3,129 report`);
- target positions found: `3,583/3,583`;
- later-phase target-event occurrences skipped from earlier-phase windows: `283`;
- forbidden target events used: `0`;
- future events used: `0`;
- current targets missing from their own windows: `0`;
- raw label column read: `false`.

The full local frozen-scope audit also passed with `385` support-train fit,
`69` support-val select, `3,413` original benign fit, zero original benign
select, zero permanent-canary fit/select rows, zero report-extension retention,
zero raw rematerialization, and zero missing-feature fill.

This correction is made before any CKBQ performance metric exists.  It fixes a
protocol implementation error and does not use report labels, report scores,
or outcome-dependent tuning.
