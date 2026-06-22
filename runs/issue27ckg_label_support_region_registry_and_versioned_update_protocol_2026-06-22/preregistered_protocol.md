# issue27ckg Preregistered Protocol

## Decision

The system has one formal region abstraction:

`label_support_region`

Each region is bound to one human-confirmed exact attack label. It manages
labelled memory and versioned training views. It does not classify unknown
traffic by geometric proximity.

S3 geometry, prototypes, shells, and strong/weak statuses remain optional
diagnostic metadata. They cannot block a human-confirmed sample from entering
the correct label archive and cannot authorize automatic unknown-traffic
routing.

## Frozen Initial State

- `initial_support_bank_v1`: 512 immutable rows;
- `support_train_view_v1`: 385 rows used as attack-positive training data;
- `support_val_view_v1`: 127 rows, immutable validation role;
- ten exact attack labels;
- no support-train/support-val overlap;
- final/report-only data forbidden from archive promotion or training views.

## Update Layers

1. `online_label_archive`: append-only record of every human-confirmed event.
2. `region_candidate_pool`: legal, deduplicated archive records awaiting
   promotion.
3. `support_train_view_vN`: versioned attack-positive training manifest.
4. `model_release_vN`: model, training-view hash, configuration, evaluation,
   and rollback pointer.

## Archive And Candidate Gates

An archive event requires:

- exact label;
- human confirmation identity and timestamp;
- source PCAP/CSV and packet/row/timestamp provenance;
- source role and role restrictions;
- feature asset reference and hash;
- append-only event ID and parent ingest batch ID.

A candidate is eligible only when:

- exact label exists in the registry;
- human confirmation is present;
- source is selection-allowed;
- source is not report-only, sealed-final, or fit-forbidden;
- provenance and feature reference are complete;
- provenance hash is not already present in the frozen bank, archive, current
  candidate pool, or current support view.

## Promotion

Promotion is deterministic within a frozen budget profile and prioritizes:

1. new provenance source;
2. new time/session coverage;
3. lower duplication risk;
4. stable event ID tie-break.

The policy supports global and per-region extension caps, but production
promotion is disabled until a budget profile is empirically certified in a
separate model-update experiment. A simulation-only profile may test the
workflow and invariants without authorizing deployment.

## Model Release

A candidate support view does not automatically replace the current model.
Release requires:

- frozen positive/ID/OOD sampling and weighting contract;
- no support-val role migration;
- low-FPR attack and benign-OOD evaluation;
- per-label non-regression and forgetting audit;
- version hashes and rollback target;
- explicit release decision.

## Explicit Non-Actions

- no model training or controller change;
- no production support promotion;
- no reuse of E64/E128 as an approved update;
- no automatic unknown-traffic classification by label region;
- no sealed-final access;
- no change to the initial 512 rows.
