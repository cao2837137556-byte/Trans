# CKBO mature AfterImage transfer preregistration

Date: 2026-07-15
First seed: 27 only

## Execution amendment after failed job 151772

AMD job `151772` stopped before C1 fitting completed and before any model or
report metric was produced.  The permanent three-family exclusion changed the
length of each role before the deterministic linspace cap, so it requested
rows outside the immutable CKAT C1 cache.  The same audit also established
that the original 1M split has no legal benign-select rows after all permanent
canaries are removed.  The failed run therefore contains no scientific result
and does not open the sealed cooler-motor holdout.

The corrected execution keeps the method candidates, seed, features, support,
and named development canaries unchanged. Because no model/report metric was
opened, it also repairs the impossible auxiliary role contract before rerun:
source-disjoint known-family PCAPs provide fit/select, while all
predictive-maintenance sources remain a second unseen development-held family.
It freezes two previously implicit protocol details:

- every fit/select row must belong to the intersection of the immutable CKAT
  C1 target manifest and CKBE/CKBI T0 target manifests before held-family
  filtering or capping; missing features are never zero-filled or generated
  from new raw rows;
- the C1 candidate threshold is the floating-point value immediately below
  the minimum legal `support_val` attack score, giving a recall-first anchor
  with zero benign/report rows used for that threshold.  The verifier gate is
  still selected from legal `support_val` attacks and the five source-disjoint
  auxiliary benign-select sources.

The corrected launcher is eligible only after a real local 1M scope audit
confirms all 385 support-train rows, the 69 legal support-val lineage, zero
permanent-canary fit/select use, and complete immutable-cache coverage.

## Scientific question

CKBO tests whether the persistent unseen-normal-family failure is jointly due
to (a) insufficiently transferable process representation and (b) insufficient
legal benign process diversity. It does not tune a stream-specific rule.

The frozen C1 flow HistGB remains the high-recall attack candidate anchor. A
verifier may only suppress a C1 candidate when its independently trained
process evidence supports normality. Review is fixed to zero.

## Mature components and narrow adaptation

- Frontend: vendored `ymirsky/Kitsune-py` AfterImage at imported commit
  `28a654b5813936380d264c0934136efda672174a`, with the existing audited
  `RestoredNetStat115` wrapper. The wrapper restores the Host-BW block from the
  upstream source's commented logic; this is disclosed and is not described as
  byte-for-byte unmodified upstream code.
- Backend: vendored official TabM v0.0.3 at upstream commit
  `a507095893d784c5702059d737ddfbd1299c41dd`.
- Small adaptation: one deterministic 115D multiscale view. For each of the 23
  AfterImage statistics, it retains the slow `lambda=0.01` anchor and computes
  adjacent signed `asinh` contrasts for `5-3`, `3-1`, `1-0.1`, and
  `0.1-0.01`. It uses no learned report normalization and no identity fields.

Upstream references:

- Kitsune/AfterImage: https://github.com/ymirsky/Kitsune-py
- TabM: https://github.com/yandex-research/tabm

## Frozen original data contract

The strict 1M split, raw115 matrices, role sidecars, CKBE 26-source T0 manifest,
and CKBI/CKBJ report-only extensions remain read-only. CKBO never rewrites or
merges them.

The following families are permanently excluded from every fit/select scope,
even when another family is nominally held:

- `iotsim-stream-consumer`
- `iotsim-hydraulic-system`
- `iotsim-cooler-motor`

They contribute zero rows to C1 fitting/calibration, verifier fitting,
preprocessing, gate selection, hard-pair construction, or model choice.
Stream and hydraulic are development report canaries. Cooler-motor remains the
sealed final holdout and is not scored by CKBO seed 27.

## Separate benign-diversity and unseen-family extension

CKBO reads 31 previously unused benign PCAP members directly from
`GothamDataset2025.zip`. Sixteen source-disjoint captures from
combined-cycle, combined-cycle-TLS, domotic-monitor, and building-monitor are
split into 11 fit sources and 5 select sources. All 15
predictive-maintenance sources remain outside fit/select and form an
additional completely unseen development-held family. Each source gets a
fresh AfterImage state, 500 warmup packets, and 600 model-ready rows.

AfterImage's standard `update_get_stats` output is current-packet-inclusive.
This is disclosed rather than mislabeled as a score-before-update TGN memory
view: the current packet is the sample being scored, no future packet or label
is used, and TabM itself has no mutable report-time state.

Sources are ranked by `SHA256("ckbo|27|" + raw_member_path)` within family.
The select counts are frozen as 2 combined-cycle, 1 combined-cycle-TLS,
1 domotic-monitor, and 1 building-monitor source. Predictive-maintenance is
always `aux_report`. No CSV is opened and no raw label column is read. The
source path supplies only the preregistered benign role. Source/device identity
is audit metadata, never a model input.

The extension has its own manifest, schema hash, source-code hashes, PCAP ZIP
CRC/size, cache hashes, and manifest SHA-256. It does not modify the 1M split.

## Candidates

1. `M0-C1`: unchanged legal C1 anchor.
2. `M1-AfterImage115-NoAux`: mature raw115 verifier without added benign data.
3. `M2-AfterImage115-Aux`: mature raw115 verifier plus the separate extension.
4. `M3-AfterImageContrast-Aux`: preregistered primary; multiscale view plus the
   extension.
5. `A1-AfterImageContrast-NoAux`: representation-only ablation.

Every TabM epoch covers every legal fit row at least once. All 385 legal
`support_train` attacks participate in the global protocol, with attack-family
balanced sampling. The 69 legal `support_val` rows are gate-only. Fit-only
QuantileTransformer parameters are frozen before select/report.

Auxiliary select and held-report rows have no C1 cache. Gate/report evaluation
conservatively treats all of them as C1 candidates, so verifier false positives
are counted rather than hidden by an unavailable C1 score. This worst-case
convention is reported separately from C1-scored strict 1M families.

## Selection and report protocol

The exact gate frontier is defined only by legal support_val attack scores. It
first enforces attack preservation, then minimizes legal select benign hard
rate. The two no-aux ablations have no legal original benign-select rows, so
their gates use the maximum support-val-only threshold satisfying the same
attack constraints; they use zero benign/report scores and are never eligible
to replace the auxiliary primary. Stream, hydraulic, cooler, future, query,
and sealed labels never select a feature, model, normalization statistic, C1
threshold, or verifier gate. The global attack-preservation pass reads attack
reports only; cooler-motor is absent from every CKBO scoring protocol.

Before report canaries are opened, CKBO performs strict evaluation of the
existing `iotsim-ip-camera-street` held family and the separate, entirely
unseen `iotsim-predictive-maintenance` family. Each held family is excluded
from C1 fitting, verifier fitting, preprocessing, and gate selection. Legal
select comes from source-disjoint non-held auxiliary benign sources. The
go/no-go rule requires each held family to reach at most 90% hard alarms and
improve by at least five points, with the macro also improving by five points.
This prevents one named canary from carrying the result.

Report scoring uses frozen matrices and frozen model state. There are zero
gradients, zero threshold updates, zero normalization updates, and review=0.
Confidence intervals use source or episode clusters, not packet independence.

## Seed-27 go/no-go

`M3-AfterImageContrast-Aux` is a `GO_SIGNAL` only if all hold:

- overall attack hard recall decreases by no more than 0.5 percentage point;
- every attack family with at least 15 report rows decreases by no more than
  2 percentage points;
- stream hard false alarm is at most 90% and improves over C1 by at least
  10 percentage points;
- hydraulic does not worsen over C1 by more than 2 percentage points;
- both legal benign held families reach at most 90% hard alarms and improve
  over the conservative C1 baseline by at least 5 percentage points; their
  macro also improves by at least 5 points;
- all target alignments are complete, all 385 global support rows are used,
  every permanent report-only use count is zero, the selected gate satisfies
  its attack constraint, and review is zero.

This single seed is only a route signal. Seeds 37/47 and a genuinely untouched
final family/source are deferred until the signal is real.

## Resources and execution

AMD and Intel each receive one independent result-producing job with
partition/job-specific run and log paths. Each requests 8 CPU, 32 GiB RAM, and
8 hours. The request is based on the approximately 19 GiB peak of the recent
full-source diagnostic plus headroom for 18,600 auxiliary 115D rows and TabM;
it is not copied from the older 128 GiB job.

The job writes the complete attack table, strict Level-2 table, per-family
metrics, source/episode confidence intervals, candidate frontier, support use,
loss curves, data/feature manifests, environment and runtime evidence, and a
single-seed decision. It automatically validates and packs a pullback archive.
