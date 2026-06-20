# issue27ckb Offline Static Capability Snapshot

primary_verdict: `offline_static_attack_signal_present_but_benign_ood_nonseparable_score_saturated_and_seed_unstable`

issue27ckb completed: yes
full_hpc_jobs: 7
formal_benchmark: no
online_deployment_simulated: no
candidate_pool_reused: no
final_or_report_only_used_for_selection: no

## Question

Can a static classifier fitted on the frozen `385` attack support-train rows plus ID-benign training data show useful offline attack capability before the online protocol is complete?

## Models

- HistGradientBoosting, support weights `64` and `256`, seeds `42/43/44`.
- Balanced logistic regression.
- Kitsune115D input, frozen issue27cf support bank.
- No use of the unselected `69,492` candidate rows.

## Main Result

The models learn strong support/source-associated attack signal, but not an attack-specific boundary against benign OOD drift.

Threshold-free separation:

| Model group | Dev attack vs OOD-stress ROC-AUC | Sealed attack vs sealed OOD ROC-AUC |
|---|---:|---:|
| HistGB support64 | mean `0.204`, range `0.104-0.256` | mean `0.296`, range `0.173-0.372` |
| HistGB support256 | mean `0.206`, range `0.105-0.259` | mean `0.336`, range `0.194-0.471` |
| Logistic regression | `0.377` | `0.500` |

No model ranks attacks above benign OOD reliably. HistGB is also materially seed-sensitive.

## Why the Apparent Attack Rates Are Misleading

At the ID-only q99 threshold:

- support-val detection is `100%`;
- same-file query detection is roughly `97.6-99.0%`;
- dev-future attack detection is roughly `76.3-80.4%`;
- sealed attack detection is approximately `99.99%`.

But at the same threshold:

- OOD-stress false alarm is approximately `99.81%`;
- sealed-final OOD false alarm is approximately `99.90%`.

The classifier is largely detecting departure from ID benign, not attack identity.

The nominal OOD-guarded q99 threshold is additionally invalid as a 1% operating point because score ties/saturation make the q99 value equal to the maximum OOD-val score. Depending on model, `6.8-71.8%` of OOD-val rows equal that threshold.

## Support-Query Generalization

Under the recorded OOD-guarded threshold:

- HistGB development read-only micro detection:
  - support-seen labels: about `51-52%`;
  - support-unseen labels: about `9.8-9.9%`.
- Logistic regression:
  - support-seen labels: about `88.7%`;
  - support-unseen labels: about `46.6%`;
  - but OOD-stress and sealed-OOD false alarm remain about `99.8-99.9%`.

The apparent logistic generalization is therefore not operational attack discrimination.

## Interpretation Boundary

This result establishes a negative baseline for:

```text
raw Kitsune115D
+ static attack-vs-ID classifier
+ 385 frozen attack supports
```

It does not prove that:

- Kitsune115D contains no useful attack information;
- a family-aware evidence representation will fail;
- a future model trained with a newly authorized, disjoint OOD-negative training role will fail.

The current OOD-val role was calibration/selection only. Reusing it for gradient fitting would require a new split and explicit contract.

## Close-out

```text
solved: Ran and validated the seven-job offline static capability snapshot and separated apparent attack detection from benign-OOD discrimination.
changed_mainline: no
active_blocker: raw/global Kitsune115 evidence remains confounded; static attack-vs-ID heads saturate on benign OOD and do not provide an operational boundary.
frozen: issue27cf support rows, issue27ch complete-only query roles, downloaded HPC aggregates and frozen-config hashes.
superseded: treating high sealed attack detection from this run as evidence of deployable or attack-specific capability.
next_action: continue issue27ck family-aware non-gradient evidence-space repair; separately fix tie-aware calibration semantics before any repeat of this capability matrix.
```
