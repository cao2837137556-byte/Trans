# issue27cj Preregistered Protocol

This protocol was frozen before inspecting region, OOD-overlap, or dev-query results.

## Scope

Instantiate and audit an initial attack-region registry from the frozen issue27cf support bank.

This is not model training, formal benchmarking, detector threshold tuning, controller tuning, support reselection, or online updating.

## Role Order

1. `id_benign_train`: fit feature scaling and challenger covariance only.
2. `support_train`: form one initial medoid candidate per exact attack label.
3. `support_val`: audit candidate coverage and calibrate preregistered shell candidates.
4. `ood_benign_val`: development-side overlap audit and region status assignment.
5. Freeze the primary registry.
6. `ood_benign_stress`: read-only frozen-registry stress.
7. Certified complete-only dev query: read-only coverage/unknown stress.

No later role may modify an earlier artifact.

## Primary Geometry

Space:

`ID-benign robust-scaled Kitsune115D`

Scaler fit role:

`id_benign_train` only.

For each feature:

- center = ID-train median;
- scale = ID-train IQR;
- if IQR is effectively zero, fall back to ID-train standard deviation;
- if both are effectively zero, use scale 1 and mark the feature constant.

Distance:

`Euclidean distance in the robust-scaled 115D space`.

Prototype:

One medoid per exact attack label, selected from `support_train`.

## Challenger Geometry

Use the same robust-scaled features and fit Ledoit-Wolf shrinkage covariance on `id_benign_train` only.

Distance:

`full shrinkage Mahalanobis distance`.

The challenger is a stability audit. It cannot replace the primary after seeing query or OOD results.

## Shell Candidates

All quantiles are computed per exact-label region.

| Scheme | Core | Near | Uncertain |
|---|---:|---:|---:|
| tight | support_train q50 | pooled support_train/support_val q75 | pooled q90 |
| medium | support_train q75 | pooled q90 | pooled q97.5 |
| wide | support_train q90 | pooled q97.5 | pooled q99.5 |

`medium` is the preregistered primary shell scheme.

Tight and wide are sensitivity outputs only.

## Region Status Rules

The primary medium scheme determines the provisional status.

Minimum evidence:

- at least 12 `support_train` rows;
- at least 3 `support_val` rows;
- support-val true-region uncertain-shell coverage at least 0.80;
- support-val nearest-region exact-label consistency at least 0.80.

`active_strong` additionally requires:

- at least two provenance source groups;
- OOD-val core intrusion assigned to the region no greater than 0.001 of all OOD-val rows;
- OOD-val core+near intrusion assigned to the region no greater than 0.01.

Candidates passing minimum evidence but failing source diversity or OOD-overlap requirements become `active_conflict_sensitive`.

Candidates failing minimum evidence become `ambiguous_region`.

Quarantine is reserved for data-contract, numerical, role, or provenance failures.

## Split Policy

No region is formally split in issue27cj.

A two-medoid diagnostic may mark `split_candidate` only when:

- support_train count is at least 24;
- each proposed train subcluster has at least 8 rows;
- each proposed support-val subcluster has at least 2 rows;
- two-medoid within-distance improves by at least 35 percent;
- the split is not explained solely by a source/file shortcut.

Any split requires a later explicit issue.

## Read-only Stress Rule

`ood_benign_stress` and certified dev query cannot:

- change medoids;
- change scaler or covariance;
- change shell radii;
- change region activation status;
- add support;
- trigger split or merge.

They may only produce diagnostic reports.
