# CKBO mature AfterImage transfer preregistration

Date: 2026-07-15
First seed: 27 only

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

The following families are permanently report-only in every protocol, even
when another family is nominally held:

- `iotsim-stream-consumer`
- `iotsim-hydraulic-system`
- `iotsim-cooler-motor`

They contribute zero rows to C1 fitting/calibration, verifier fitting,
preprocessing, gate selection, hard-pair construction, or model choice.

## Separate benign-diversity extension

CKBO reads the 15 benign predictive-maintenance PCAP members directly from
`GothamDataset2025.zip`. The archive must contain no predictive-maintenance
member below `raw/malicious/`. Each source gets a fresh AfterImage state,
500 warmup packets, and 2,000 model-ready rows.

AfterImage's standard `update_get_stats` output is current-packet-inclusive.
This is disclosed rather than mislabeled as a score-before-update TGN memory
view: the current packet is the sample being scored, no future packet or label
is used, and TabM itself has no mutable report-time state.

Sources are ranked by `SHA256("ckbo|27|" + raw_member_path)`. The first 10 are
`aux_fit`; the final 5 are source-disjoint `aux_select`. No CSV is opened and no
raw label column is read. The source path supplies only the preregistered benign
role. Source/device identity is audit metadata, never a model input.

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

Auxiliary select rows have no C1 cache. Gate selection conservatively treats
all of them as C1 candidates, so their verifier false positives are counted
rather than hidden by an unavailable C1 score.

## Selection and report protocol

The exact gate frontier is defined only by legal support_val attack scores. It
first enforces attack preservation, then minimizes legal select benign hard
rate. Stream, hydraulic, cooler, future, query, and sealed labels never select
a feature, model, normalization statistic, C1 threshold, or verifier gate.

Before report canaries are opened, CKBO also performs strict rotations over
every non-canary benign device family that has both legal fit and select rows.
The held family is excluded from C1 fit/calibration, verifier fit,
preprocessing, and gate selection. This prevents success on one named canary
from being the only generalization evidence.

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
- the macro hard rate across all legal benign held rotations improves over C1
  by at least 5 percentage points;
- all target alignments are complete, all 385 global support rows are used,
  every permanent report-only use count is zero, the selected gate satisfies
  its attack constraint, and review is zero.

This single seed is only a route signal. Seeds 37/47 and a genuinely untouched
final family/source are deferred until the signal is real.

## Resources and execution

AMD and Intel each receive one independent result-producing job with
partition/job-specific run and log paths. Each requests 8 CPU, 32 GiB RAM, and
8 hours. The request is based on the approximately 19 GiB peak of the recent
full-source diagnostic plus headroom for 30,000 auxiliary 115D rows and TabM;
it is not copied from the older 128 GiB job.

The job writes the complete attack table, strict Level-2 table, per-family
metrics, source/episode confidence intervals, candidate frontier, support use,
loss curves, data/feature manifests, environment and runtime evidence, and a
single-seed decision. It automatically validates and packs a pullback archive.
