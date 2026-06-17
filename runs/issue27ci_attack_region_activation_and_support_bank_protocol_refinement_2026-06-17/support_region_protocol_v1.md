# Support Region Protocol v1

issue: `issue27ci_attack_region_activation_and_support_bank_protocol_refinement`

This issue freezes protocol semantics only. It does not instantiate regions, compute radii, train models, tune thresholds, run replay, or change controller policy.

## Current State

The current initial support bank has:

- `69,492` eligible exact-label support candidate rows.
- `512` selected support rows.
- `385` `support_train` rows.
- `127` `support_val` rows.
- `10` exact attack labels.
- `16` provenance seeds in issue27cf `region_manifest.csv`.

The `region_id` currently present in issue27cf sidecars is a provenance seed derived from source group, exact label, PCAP, and phase. It is not yet an active geometric attack region.

## Layer Definitions

| Layer | Meaning | Current status |
|---|---|---|
| exact_attack_label | Dataset attack name such as `TCP Scan` or `Mirai TCP Flooding`. | known |
| semantic_attack_group | Coarse family such as `merlin`, `mirai`, or `tooling`. | known |
| provenance_seed | Source/label/PCAP/phase seed used for audit and initial grouping. | known, 16 seeds |
| candidate_geometric_region | A proposed cluster or prototype set in a declared evidence space. | not instantiated |
| active_evidence_region | A candidate region that passes activation audits and can emit attack-region evidence. | not instantiated |

Do not treat labels, semantic groups, or provenance seeds as active regions.

## Scientific Design Basis

The protocol follows five conservative principles:

1. Prototype evidence is useful in low-sample regimes, but it must live in a declared metric/evidence space.
2. Open-set handling is required: out-of-region means `support_bank_cannot_explain`, not benign.
3. Support-query shift is expected; support-side radii must not be over-tightened from support_train alone.
4. Compact support regions are useful, but overlap with benign/OOD development data must downgrade reliability.
5. Initial support memory and later online updates must be versioned separately.

## Allowed Initial Evidence Space

issue27cj may instantiate candidate regions in:

```text
primary_space = standardized_kitsune115_development_space
```

where the standardization rule must be declared and fitted only on development-allowed data. Learned attack embeddings, controller scores, and final/report-only outcomes are forbidden in issue27cj unless a later issue explicitly authorizes them.

## Candidate Region Formation

Candidate regions may be proposed from `support_train` only.

A candidate region must record:

- source provenance seed IDs;
- exact labels represented;
- semantic groups represented;
- support_train row IDs;
- proposed prototype IDs;
- declared distance metric;
- whether it is single-prototype or multi-prototype;
- whether it is single-label or mixed-label;
- source/file/device/phase diversity.

`support_val` may validate compactness and shell behavior, but it may not create new candidate regions.

## Prototype Rules

A region may have one or more prototypes.

Allowed prototype types for issue27cj:

- `mean_prototype`: mean of support_train rows in the declared space.
- `medoid_prototype`: real support_train row nearest to the local center.
- `local_multi_prototype`: multiple local prototypes when within-label structure is not compact.

Prototype count is not fixed in issue27ci.

## Shell Semantics

issue27ci freezes shell names, not numeric radii:

| Shell | Meaning |
|---|---|
| core | Strong known-attack-region evidence. |
| near | Plausible known attack drift around a region. |
| uncertain | Weak/boundary attack evidence needing OOD-risk, temporal evidence, or review context later. |
| out_of_region | Current support bank cannot explain this sample. This is not benign and not suppress. |

issue27cj may estimate shell boundaries only with development-allowed data and must report sensitivity.

## Activation States

| State | Meaning |
|---|---|
| candidate_region | Proposed from support_train; not active. |
| active_strong | Passes support count, compactness, label/source audit, and low OOD-overlap audit. |
| active_conflict_sensitive | Attack-like but overlaps development benign/OOD or has label/source ambiguity; emits weaker evidence. |
| ambiguous_region | Insufficient count, unstable geometry, weak validation, or unclear label/source structure. |
| quarantined_region | Provenance, label, timestamp, role, or numerical failure. |
| retired_region | Future lifecycle state, not active but retained for audit. |

## Evidence Output Contract

The region system emits evidence, not final decisions. It must not output final `attack`, `benign`, `hard_alarm`, or `suppress`.

Required evidence fields are defined in `evidence_output_schema.json`.

## Initial vs Online State

`initial_support_bank_v1` remains immutable after issue27cf.

Future online updates must create a separate versioned registry:

```text
online_region_registry_v2
parent_registry = initial_region_registry_v1
```

Online insertion, merge, split, retire, and quarantine require explicit future issues and cannot rewrite the initial bank.

## Forbidden in issue27ci

- model training;
- formal benchmark;
- threshold tuning;
- controller policy;
- numeric final radius values;
- sealed final attack/OOD access for selection, calibration, activation, or tuning;
- using dev query as support;
- using old partial issue27cd emissions from excluded chunks.
