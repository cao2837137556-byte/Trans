# issue27ckf Preregistered Data Feasibility Protocol

## Objective

Determine whether the local Gotham archive contains a legally untouched,
two-sided evaluation pair capable of certifying the current initial attack
regions:

- attack traffic relevant to at least one of the ten frozen support labels;
- benign OOD traffic from a declared matched device/environment;
- neither side previously used for fitting, selection, query diagnostics,
  stress diagnostics, or report-only evaluation.

This issue is a metadata, provenance, and interval audit only. It does not
materialize Kitsune115 features, train a model, evaluate a region, or open
sealed outcome metrics.

## Evidence Levels

1. `feature_materialized_dev`: source features were used in development roles.
2. `reserved_report_only`: source belongs to a sealed final role.
3. `metadata_scanned_only`: source name or pairing candidacy was inspected, but
   no feature rows were materialized.
4. `archive_only`: source was not present in current role or pairing manifests.

Only levels 3 and 4 may be considered for a fresh materialization candidate.
Level 2 is not available for repair or model selection.

## Fresh Pair Requirements

A candidate pair must satisfy all of the following:

- malicious PCAP has never been feature-materialized;
- malicious scenario has exact-label rows in the paired processed CSV;
- at least one matching label belongs to the current ten-label initial bank;
- matched benign PCAP has never been feature-materialized or reserved final;
- attack and benign members share the same device key;
- pairing ambiguity is declared before materialization;
- feature extraction and hashes are frozen before any region comparison.

## Same-Capture Residual Rows

Exact-label rows not selected by prior targeted plans are counted separately.
They remain from an already used source/capture and therefore may be used only
as development diagnostics. They cannot be presented as a fresh independent
holdout.

## Stop Rule

If no pair meets all fresh-pair requirements:

- do not submit a new HPC materialization job from the existing archive;
- do not consume sealed final assets as a repair loop;
- stop further support tuning against reused Gotham roles;
- define a new capture or second-environment acquisition contract.
