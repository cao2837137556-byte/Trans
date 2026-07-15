# CKBO job 151772 failure and corrected scope contract

Date: 2026-07-15

## Failed execution is not a scientific result

AMD job `151772` ended `FAILED 1:0` after `00:02:13`; the batch step reported
about `2,900,520 KiB` MaxRSS.  The validated environment and dependency checks
passed.  The job stopped while constructing the first C1 training matrix:

```text
Canonical source cache lacks 1137 requested rows for
processed/iotsim-combined-cycle-tls-3.csv; first=51
```

No C1 model, AfterImage/TabM verifier, threshold, attack metric, OOD metric, or
go/no-go decision was produced.  The sealed cooler-motor holdout was not
opened.  The already materialized predictive-maintenance AfterImage arrays are
label-free cache data only and may be reused after contract validation.

## Root cause

CKBO permanently removed stream-consumer, hydraulic-system, and cooler-motor
from fit/select, then re-applied a deterministic linspace cap.  Removing rows
changed the role length and therefore changed the sampled row identities.  The
immutable CKAT C1 cache contains the exact target union from the frozen five
leave-family folds, not the newly shifted identities.  A real local replay
found 3,431 missing C1 target identities in the shifted `id_calib/fit` cohort.

The same replay found a second protocol fact: after all three permanent
families are removed, the original strict 1M roles contain zero legal benign
select rows.  Repairing only the first missing-cache exception would therefore
have failed next during C1 threshold selection.  Missing features must not be
zero-filled and report canaries must not be reused as select.

## Corrected immutable scope

The corrected code first intersects every fit/select role with both the frozen
CKAT C1 target cohort and the frozen CKBE/CKBI T0 target cohort, then applies
held-family filtering and capping.  The formal job reads exact NPZ target
positions.  The local pullback omits the large NPZ arrays, so its audit uses the
frozen CKBE manifest hash and 26-source/34,622-target completion audit as a
proxy; formal execution rechecks exact arrays.

Real local 1M audit:

- `support_train/fit`: 385 rows;
- legal `support_val/select`: 69 rows;
- original non-canary benign fit: 3,413 rows;
- original non-canary benign select: 0 rows;
- permanent report-family fit/select use: 0;
- auxiliary source overlap with every frozen 1M role: 0;
- missing-feature zero fill: 0;
- newly materialized raw C1/T0 rows: 0.

Because no legal original benign select survives, the C1 candidate threshold
is frozen immediately below the minimum legal support-val attack score.  This
creates a conservative recall-first C1 candidate anchor using zero benign or
report rows.  The verifier gate still uses legal support-val attacks plus an
independent benign select extension.

## Corrected auxiliary roles

The failed run also exposed that the original non-canary held-family set would
have collapsed to one family.  Before any metric was opened, the auxiliary
roles were strengthened:

- 11 fit sources and 5 source-disjoint select sources from previously unused
  combined-cycle, combined-cycle-TLS, domotic-monitor, and building-monitor
  benign PCAPs;
- all 15 previously unused predictive-maintenance sources are excluded from
  fit/select and form a second unseen development-held family;
- every source has a fresh AfterImage state, 500 warmup packets, and 600
  model-ready events;
- resulting counts: 6,600 fit, 3,000 select, and 9,000 held-report events;
- no CSV or raw label column is read; source/device identity is audit metadata
  only.

Full local real-PCAP materialization passed for all 31 sources.  The two
non-canary development-held families are now `iotsim-ip-camera-street` and
`iotsim-predictive-maintenance`; go/no-go requires each to reach at most 90%
hard alarms and improve by at least five percentage points, with their macro
also improving by five points. Stream and hydraulic remain used
development canaries.  Cooler-motor remains sealed and is not scored.

Final static review also closed three downstream failures before resubmission:

- the formal launcher now freezes `600` model-ready rows per auxiliary source,
  matching the 6,600/3,000/9,000 result validator instead of retaining the old
  2,000-row argument;
- no-aux ablations select an attack-only gate because zero legal original
  benign-select rows exist; they never fall into the mature auxiliary gate
  routine that requires benign select data;
- global attack preservation reads attack reports only, so it cannot traverse
  `sealed_final_ood`; every protocol emits a measured cooler-motor score/use
  count that must remain zero.

## Next execution boundary

Only a corrected seed-27 result-producing AMD/Intel pair may run.  It must
reuse `scripts/00_env_issue27ckc.sh`, preserve partition/job-isolated paths,
and validate the complete attack, strict OOD, scope, support, selection, and
review=0 artifacts before packaging.  No environment-only, preflight-only,
audit-only, or smoke-only Slurm job is authorized.
