# CKBB E/R/H attention local smoke — 2026-07-11

## Question

Can a minimal mechanism-aware architecture improve the strict Level-2 held OOD
failure without sacrificing packet-level attack support?

The candidates were deliberately narrow:

```text
D0: E only, HistGB control
D1: E only, MLP control
D2: E + R (source-relative residual), packet MLP
D3: E + H (attention-pooled episode), joint packet/bag loss
D4: E + R + H, joint packet/bag loss
```

`E` is the immutable CKAW 48D label-free interaction representation. `R` is
new: rolling 5-second source snapshots, robust median/MAD residuals, and no
truth-cleaning. `H` is a label-free 60-second source episode. Attention is
auxiliary: all fit packet/support rows still receive a packet loss, unlike
CKAY's pure bag-level pooling.

## Contract checks

`issue27ckbc_erh_contract_audit_v1.py` passed:

- mutating raw truth labels does not change R;
- mutating a timestamp-later packet does not change the target R vector;
- mutating a timestamp-earlier packet does change it;
- the target is scored before it enters online state.

The smoke also keeps fit/select/report bags role-isolated, has `review=0`, and
excludes the held family from both fit and select.

## Result

This is **not a positive Level-2 solution**.

| candidate | stream OOD hard | hydraulic OOD hard | domotic attack hard | combined attack hard |
|---|---:|---:|---:|---:|
| D0 E HistGB | 99.87% | 12.87% | 93.72% | 0.78% |
| D1 E MLP | 99.63% | 12.67% | 98.66% | 0.00% |
| D2 E+R MLP | 99.60% | 22.90% | 97.43% | 0.16% |
| D3 E+H attention | 99.60% | 7.50% | 99.38% | 0.00% |
| D4 E+R+H attention | 99.67% | 10.63% | 98.77% | 0.00% |

The same local-150k cache contains only `58` legal support packets for most
holds and `25` after holding `combined-cycle`. Therefore the combined-cycle
column is a support-coverage warning, not a formal comparison with the 385
support full-HPC results.

The reliable directional observations are:

1. R did not reduce stream; it worsened hydraulic here. A generic short
   source-relative residual is insufficient.
2. Attention continues to carry a small hydraulic-side signal (12.87% to
   7.50%) but leaves stream at ~100%.
3. No review was introduced, so the negative conclusion is not hidden by a
   reject option.

## Decision

Do not promote the current R construction or run a full-HPC attention sweep
yet. The next efficient work is a **process-evidence observability diagnostic**
on legal pseudo-held groups: audit connection completion/response-chain, edge
churn, target/port expansion persistence, and multi-window burst lifetime
before adding another neural module. Stream/hydraulic remain development
canaries only; a family/time/dataset held out after method freeze is required
for a final generalization claim.
