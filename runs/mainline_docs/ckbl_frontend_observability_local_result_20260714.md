# CKBL local real-data observability result

## Registered status

`TRUNCATED_LOCAL_NO_SIGNAL`

Canonical local artifact directory:
`runs/issue27ckbl_frontend_observability_audit_v1_2026-07-14_local_real_300k_v2`.
The first and final invocations have byte-identical `aggregate_metrics.csv`,
`fold_metrics.csv`, and `feature_value_audit.csv`; the final invocation exited
0 from end to end.

This is implementation and early observability evidence, not a formal held
report result. It uses label-free canonical prefix replay with an explicit
`recorded_index <= 300000` target cap. The full-source protocol remains the
only chronology-complete scientific run.

Post-run protocol review found that this bounded implementation allowed every
label-free earlier raw event into passive state, including rows later
identified by metadata as non-selected targets. No raw label was read, but the
formal protocol is stricter: the pre-formal addendum blocks every known
non-selected target from fit state. Therefore the bounded numbers remain route
motivation only and are not a substitute for the hardened full-source result.

## Scope and contracts

- 8,344 legal fit rows: 8,286 benign and 58 attack;
- 7 sources: 5 benign and 2 attack;
- 3 attack labels: File Download, Ingress Tool Transfer, Mirai UDP Flooding;
- stream-consumer use: 0;
- hydraulic-system use: 0;
- sealed cooler-motor final-holdout use: 0;
- raw label column read by frontend: false;
- target alignment: 8,344 / 8,344;
- identity fields used as model features: false;
- outer test labels used for fitting or threshold selection: 0.

The bounded run excludes the museum attack source because its legal support
targets extend to raw recorded index 10,042,290. Therefore it has neither all
385 support rows nor enough remaining attack sources for complete inner
leave-source threshold selection. Threshold metrics are intentionally reported
as unavailable rather than silently using outer labels.

## Result

| protocol | bundle | macro AUROC | worst-fold AUROC |
|---|---|---:|---:|
| unseen source pair | exact TGN 9D | 0.5678 | 0.4754 |
| unseen source pair | current 20D | 0.5686 | 0.4709 |
| unseen source pair | compact process 69D | 0.6244 | 0.6110 |
| unseen source pair | compact 69D history-permuted control | 0.6244 | 0.6110 |
| unseen source pair | C1 207D upper bound | 0.7737 | 0.5718 |
| unseen attack family + origin source | exact TGN 9D | 0.5962 | 0.5200 |
| unseen attack family + origin source | current 20D | 0.5976 | 0.5200 |
| unseen attack family + origin source | compact process 69D | 0.6279 | 0.5770 |
| unseen attack family + origin source | compact 69D history-permuted control | 0.6279 | 0.5770 |
| unseen attack family + origin source | C1 207D upper bound | 0.8367 | 0.5767 |

The history-permuted matrix is not accidentally identical to the ordered
matrix. Across sources, 55%--69% of historical cells changed and 96%--99.9% of
rows changed. The identical predictive metrics therefore mean that this HistGB
probe did not use transferable event-order information from the registered
69D adapter. It mainly used current or source-marginal distributions.

## Interpretation

The early result supports three narrow statements:

1. Exact 9D is too weak as the sole evidence space in this strict transfer
   probe.
2. Merely appending the registered pair/biflow summaries does not yet create a
   credible temporal-order signal.
3. The C1 207D upper bound contains substantially more transferable signal on
   the bounded cohort, so the next step should identify which mature C1-style
   process blocks carry that signal and express them causally/portably before
   another large neural backend run.

The result does not establish that C1 207D solves open-world IDS: its worst
fold remains only about 0.57 and the cohort contains only three attack labels.
It also does not justify tuning on stream or hydraulic.

## Engineering close-out

All 13 outer folds and metrics completed. The first invocation then failed
only while rendering Markdown because pandas `to_markdown` depends on the
uninstalled optional `tabulate` package. No dependency was installed and no
models were rerun. The renderer was replaced with a dependency-free writer,
and the summary was reconstructed from the already-written CSV/JSON metrics.

## Next action

Run the same frozen CKBL protocol with full-source chronology and all 385
support rows. Do not add a new backend yet. The complete result decides whether
to retain the compact process adapter, expand it toward the informative C1
blocks, or conclude that the present raw fields/data contract are insufficient.

```text
solved: strict fit-only observability code and bounded real-data evidence
changed_mainline: yes, backend promotion is now blocked by the full CKBL feature-information gate
active_blocker: full-source 385-support observability result is not yet available
frozen: canary/final exclusions, two outer protocols, feature bundles, controls, and interpretation thresholds
superseded: treating a larger TGN/GraphMixer alone as the immediate next fix
next_action: full-source CKBL result-producing run, then choose the mature sequence backend only if the order-sensitive feature gate passes
```
