# Frontend-F1 D1 incumbent five-margin result

Date: 2026-09-04

Status: `F1_D1_INCUMBENT_FIVE_MARGIN_MATERIALIZED`

## Outcome

The five terminal Frontend-F1 attack flips were all strongly hard under the
frozen incumbent E3 + P2. This rejects the narrow explanation that the new
model merely lost five attacks sitting at the incumbent decision boundary.

| quantity | result |
|---|---:|
| frozen rows | 5 |
| incumbent hard | 5/5 |
| `STRONG_5PP` | 5/5 |
| minimum incumbent score | 0.9990673865 |
| median incumbent score | 0.9992767823 |
| maximum incumbent score | 0.9999999908 |
| frozen threshold | 0.0651598722 |
| minimum score margin | +0.9339075143 |

The corresponding terminal student probabilities were between approximately
`1.36e-34` and `0.03187`. Thus the observed failure is a large reversal of
strong incumbent evidence, not a threshold-ULP artifact.

## Interpretation

The one-shot run evaluated all 2,000 protected A-side fit/internal-validation
attack rows. It preserved 1,995 and flipped five. This materialization did not
replace that full protected denominator with a five-row test: it examined only
the five failed members to identify the failure mechanism.

The result supports the following bounded conclusion:

> The current unified GRU training recipe does not fully inherit strong
> incumbent attack evidence, even on ordinary H1 TCP/UDP A-side contexts.

It does not show that inheritance is impossible. It does show that relaxing
the zero-flip safety gate or slightly moving the threshold would be
scientifically unjustified. Any second training design would need a new,
pre-frozen mechanism that protects the incumbent decision function more
directly; it cannot be presented as a small numerical repair.

## Reproducibility and boundary audit

- Frozen protocol SHA-256:
  `2c35d80f63c9ea0337e33244192e5218b56e5a2287ff1d6dbbfc5bba2288a67a`
- Output package: `runs/frontend_f1_d1_incumbent_five_margin_v1_20260904`
- Output `SHA256SUMS`: independently recomputed, 3/3 files matched.
- Representation container rows streamed as opaque bytes: 25,467.
- Numeric representation rows decoded: 5.
- Non-allowlisted numeric rows: 0.
- Select/viewed/report/FINAL/PCAP opens: 0.
- Parameters fitted / optimizer steps / training starts: 0 / 0 / 0.

## Route consequence

Do not rerun the same GRU with a looser threshold or a different seed. The next
decision should compare two bounded options before any further training:

1. add an explicit incumbent-function preservation mechanism on A (for
   example a frozen-logit or feature distillation term whose scale is fixed
   from fit-only evidence); or
2. stop the unified-encoder branch and retain the existing system plus the
   fully documented coverage limitation.

No second training run is authorized by this result.
