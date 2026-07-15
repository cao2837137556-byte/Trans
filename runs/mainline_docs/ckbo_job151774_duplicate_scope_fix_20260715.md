# CKBO job 151774 duplicate-scope failure

Date: 2026-07-15

AMD job `151774` ended `FAILED 1:0` after `00:11:53`; the batch step reported
`4,774,988 KiB` MaxRSS. The environment, dependency hashes, and 31 auxiliary
cache sources passed. No scientific decision, readout, or validated pullback
archive was produced.

The failure occurred in the predictive-maintenance strict protocol. Its
9,000 `aux_report` records were already present in `core_records`, then the
candidate assembler appended the same report list again. The existing
`unique_records` contract rejected the first duplicate UID. This was an
in-memory scope-construction defect, not a data, environment, resource, or
model-performance result.

The corrected candidate scope starts from the protocol core exactly once. It
adds only held-filtered auxiliary fit and select records for auxiliary-enabled
candidates. Report rows are never appended independently. The contract unit
now exercises the exact predictive-report arrangement and requires unique
record identities.

A wider audit found that blindly iterating the historical `HELD` tuple would
also run combined-cycle and domotic-monitor strict protocols while their
families existed in the new auxiliary fit/select extension. The formal list is
therefore frozen to the five protocols required by the amended CKBO design:

- global attack preservation;
- `iotsim-ip-camera-street`;
- `iotsim-predictive-maintenance`;
- `iotsim-stream-consumer`;
- `iotsim-hydraulic-system`.

Independently, every protocol filters auxiliary fit/select by its held family,
and result validation rejects any nonzero held-family auxiliary use. The
original strict 1M split, 385/69 support roles, C1/T0 manifests, report
canaries, sealed cooler-motor, seed 27, and go/no-go gates remain unchanged.

Only a new result-producing dual-partition rerun is authorized. The completed
31-source label-free auxiliary cache may be copied into the new isolated run
roots; no Stage A, environment job, or standalone preflight is needed.
