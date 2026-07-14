# CKBJ M1 v2 Single-Seed Formal Result

Date: 2026-07-14

Formal job: AMD `151377`

Experiment commit: `f2c8a07526284b1feae4f5454c984f3c0d18622d`

Seed: `27`

Registered decision: `NO_GO`

## Execution and pullback integrity

- Slurm state was `COMPLETED 0:0`; elapsed time was `01:28:18`, total CPU was
  `08:28:28`, and batch MaxRSS was `16,156,416 K` (about 15.4 GiB).
- The pulled archive SHA-256 is
  `bf85bcb1ece48a277f4d7f74ebc6d90bcc99a9e0db7c0b8c4497bc4c83756261`
  and matches the remote sidecar.
- `pullback_validation.json` is `PASS`. It confirms seed 27, the bundle commit,
  `review=0`, complete target alignment, all support used, no ghost negative
  nodes, and no future node identities.
- The frozen 26-source T0 manifest remained
  `b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67`.
  The independent four-source report-only extension remained
  `862a9ae62622c001bdf1c1d9b2c524bc33c25351433599fdd8935fd6e5f2ffb1`.
  Extension rows used in fit/select were zero.

## Headline metrics

| Candidate | Overall attack hard recall | Delta vs C1 | Support-val recall | Global sealed OOD hard | Stream OOD hard | Hydraulic OOD hard | IP-camera OOD hard |
|---|---:|---:|---:|---:|---:|---:|---:|
| M0 C1 | 99.9795% | 0.0000 pp | 100.0000% | 2.8870% | 100.0000% | 100.0000% | 1.8667% |
| M1-Random | 99.7996% | -0.1799 pp | 92.7536% | 2.5902% | 99.3333% | 76.2000% | 1.7667% |
| M1-SSL | 98.0799% | -1.8996 pp | 84.0580% | 2.7610% | 100.0000% | 82.1000% | 1.7333% |
| TGN-only | 98.2045% | -1.7750 pp | 84.0580% | 95.1234% | 100.0000% | 79.5000% | 83.9667% |

M1-SSL suppressed 537 of 3,000 hydraulic false alarms but none of the 3,000
stream false alarms. Against 244,050 attack evaluation rows, it missed 4,636
attacks that C1 marked hard. The largest family losses included Mirai C&C
communication (-16.80 pp), Telnet brute force (-7.48 pp), C&C communication
(-5.59 pp), UDP scan (-5.31 pp), and ingress tool transfer (-5.20 pp).

The hydraulic reduction is not attributable to learned SSL because the random
control reduced hydraulic hard alarms even more. The learned representation
therefore supplied no defensible incremental signal in this run.

## Contract findings that passed

- Strict held-family exclusion, fit/select/report isolation, report-only cache
  exclusion, target alignment, source-local anonymous node IDs, fresh source
  resets, pre-event scoring, no-gradient report replay, and label-free memory
  updates all passed.
- All 385 legal support-train rows were used in every verifier epoch. Family
  balancing was applied and `review=0` throughout.
- Negative samples came only from the current source's past-seen legal nodes;
  ghost nodes and future node identities were both zero.
- Support-val lineage was 512 original support rows -> 385 immutable train and
  127 validation -> 58 temporal-fit validation rows excluded -> 69 legal
  select rows.

## Why this does not yet kill the entire TGN route

The registered result is a genuine no-go for the exact CKBJ v2 implementation,
but the run also exposes protocol defects that prevent treating it as a fair
test of a mature temporal verifier.

1. **Fit/report history-density mismatch.** `pretrain_ssl` and
   `embed_target_phase` update TGN only at sparse frozen target positions.
   `embed_report_records`, in contrast, replays every raw past event between
   report targets. Across the audit rows, fit has no memory-only history events,
   while report replay has about 25.9 million memory-only events per encoder
   candidate aggregation. The verifier is trained and selected under sparse
   histories but evaluated under dense histories.
2. **Different update granularity.** Fit/select update one event at a time;
   report-only history uses batches of 200. Repeated endpoint occurrences are
   extremely frequent on the small source-local graphs, so this is not the same
   recurrent process distribution used for training.
3. **Weak and highly imbalanced SSL targets.** In the global protocol, reverse
   response is about 71.7% positive, retry/survival about 97.6% positive, and
   ACK/RST completion is 46/47 positive with only 47 labeled examples among
   12,385 fit targets. Legal link negatives are available for only about 71.4%
   of positive events and the mean candidate pool is about 1.22 nodes. Link loss
   increased from 1.1279 to 1.2044 and completion loss from 0.4333 to 0.6053
   over the three SSL epochs; only reverse and retry losses improved.
4. **The gate search is incomplete.** It searches only benign verifier
   quantiles 0.50 through 0.995. No global M1 candidate met the attack
   preservation constraint, after which the code deliberately reported a
   constraint-violating fallback. Lower, less aggressive verifier thresholds
   were not evaluated. This cannot explain the stream result: the held-stream
   M1-SSL threshold did satisfy the attack gate and still left stream at 100%.
5. **Several audit CSVs omit the protocol/held identifier.** Loss, negative
   sampling, memory, support-usage, and future-label rows from six protocols are
   concatenated without a protocol key. Their order can be reconstructed from
   the run loop, but this is not reviewer-grade provenance.

## Decision

- Do not run seeds 37 and 47 for CKBJ v2.
- Do not claim that M1 solved open-world generalization.
- Do not claim that this one run disproves the whole mature-TGN route. It
  disproves the current sparse-train/dense-report, imbalanced-task realization.
- Before another formal seed, make fit/select/report use one consistent,
  label-free past-event replay contract; make SSL tasks non-degenerate and
  auditable; complete the attack-preserving gate search; and add protocol keys
  to every audit row. Any new design choice must be selected without consulting
  stream/hydraulic report labels.

The detailed artifacts are stored in
`runs/issue27ckbj_tgn_m1_strict_formal_v2_2026-07-13_hpc_seed27_151377/`.
