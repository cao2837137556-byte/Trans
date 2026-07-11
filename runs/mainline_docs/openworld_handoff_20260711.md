# Open-world IDS handoff — 2026-07-11

This document supersedes older region/controller-era summaries when selecting
the current detection-method route.  It is intentionally compact; detailed
evidence remains in the referenced issue run directories.

## Paper objective

Build an open-world IDS that jointly achieves:

1. low hard-attack false alarms on benign/OOD traffic;
2. high hard detection of known and future attack mechanisms;
3. no collapse on a device/source/family excluded from both fit and select;
4. bounded **episode** review, not a conversion of all failures to review.

## Frozen experimental contract

- `fit`, `select`, and `report` roles are disjoint by use.  Query/future/sealed
  rows do not choose features, fit a model, set a threshold, or select a route.
- For strict leave-device-family testing, the held family is absent from both
  fit and select.  It appears only in its report role.
- CKAW packet/episode features are constructed from timestamp-earlier raw
  packets in the same source file.  The raw `label` field is not read by the
  frontend; future-timestamp state is excluded.
- A separate executable audit verifies label invariance, future-packet
  invariance, and held-family role exclusion.  The live context policy is
  deliberately **label-free mixed history**; ground-truth label cleaning is
  prohibited because it is unavailable at deployment.

## Current evidence

### Strong Level-1 frontend candidate

`C1_cicflow_style_only_histgb` is the strongest aggregate/Level-1 frontend
candidate from CKAI.  It preserves attack detection while sharply reducing
aggregate sealed-OOD hard alarms.  It is not a Level-2 solution by itself.

### Strict Level-2 failure remains real

CKAO/CKAT show that C1 still hard-alarms the held stream-consumer family at
about 100 percent and the held hydraulic-system family at about 99–100 percent
under the strict protocol.  CKAV separately confirmed that the ten raw sources
used by those two held benign families are entirely benign; their failure is
not explained by hidden attack labels in those source files.

### CKAW/CKAX/CKAY full-support paired result

All runs use the same complete 26-source CKAW cache and the same strict held
family protocol.  Review is disabled (`review=0`) in this probe.

| candidate | stream OOD hard | hydraulic OOD hard | domotic attack hard | combined attack hard | ip-camera OOD hard |
|---|---:|---:|---:|---:|---:|
| CKAX packet HistGB | 99.80% | 12.40% | 99.93% | 97.73% | 1.87% |
| CKAX packet MLP | 99.70% | 16.90% | 98.90% | 77.23% | 2.03% |
| CKAY episode-pooling MLP | 75.00% | 6.74% | 97.40% | 68.44% | 9.09% |

Interpretation:

- event-level aggregation contains real OOD-side signal (especially hydraulic);
- it does **not** solve stream-consumer and reduces combined-cycle coverage;
- episode pooling compresses 385 packet support rows into roughly 42 positive
  training episodes, so it is not a free replacement for packet-level support;
- this is evidence for a two-state / multi-branch design, not evidence that a
  generic MLP or pooling layer alone solves open-world generalization.

## Current route

Do not repeat raw115/C1 score tuning, generic MLP, all-OOD prototype, or
review-only repairs.  The next route is a mechanism-aware dual-state system:

```text
current flow mechanism evidence (E)
+ clean normal reference state from legal ID-benign fit (R)
+ label-free, past-only live interaction history (H)
-> constrained fusion decision: hard attack / benign-OOD / episode-review
```

Before training that route, run a **context-label conflict audit** using raw
truth labels only after the fact: measure whether a target's past 10/60-second
history contains attack activity.  This audit must never feed labels back into
the frontend, model, threshold, or deployment state.

### CKBB E/R/H local smoke: contract passes, mechanism still insufficient

CKBB implemented the first minimal E/R/H attention version.  Its new R branch
uses only timestamp-earlier, unlabeled source history; CKBC proves label and
future-packet invariance.  It also preserves per-packet support loss while
using attention only as an auxiliary episode loss.

It did **not** reduce stream-consumer hard alarms (~100%).  Attention made a
small hydraulic improvement, while the short relative baseline did not help.
Because the local 150k cache has only 25 legal combined-cycle support packets
in that hold, this smoke is a contract/direction result—not a formal
full-support attack comparison.  Do not send this exact R+attention variant to
full HPC yet.  The next evidence gap is process observability: connection
completion/response chains, edge churn, and persistent expansion must be
tested before adding another neural loss.

## Evidence index

- `repo/ood/issue27ckao_c1_strict_leave_device_family_canary_v1.py`
- `repo/ood/issue27ckat_canonical_time_c1_canary_v1.py`
- `repo/ood/issue27ckau_c1_mechanism_observability_diagnostic_v1.py`
- `repo/ood/issue27ckav_held_ood_provenance_preflight_v1.py`
- `repo/ood/issue27ckaw_canonical_interaction_episode_frontend_v1.py`
- `repo/ood/issue27ckax_episode_head_strict_l2_smoke_v1.py`
- `repo/ood/issue27ckay_episode_pooling_strict_l2_smoke_v1.py`
- `repo/ood/issue27ckaz_context_causality_contract_audit_v1.py`
- `repo/ood/issue27ckbb_erh_attention_strict_l2_smoke_v1.py`
- `repo/ood/issue27ckbc_erh_contract_audit_v1.py`
- `runs/issue27ckax_episode_head_strict_l2_smoke_v1_2026-07-10_hpc_fullsupport_groupA/`
- `runs/issue27ckax_episode_head_strict_l2_smoke_v1_2026-07-10_hpc_fullsupport_groupB/`
- `runs/issue27ckay_episode_pooling_strict_l2_smoke_v1_2026-07-11_hpc_fullsupport_groupC/`
- `runs/mainline_docs/ckbb_erh_smoke_20260711.md`

## Claim boundary

Do not claim that unknown OOD or cross-device generalization is solved.  The
current defensible claim is that C1 is a strong Level-1 frontend and that
episode aggregation exposes a partial Level-2 signal, while the hardest held
OOD family remains unresolved.
