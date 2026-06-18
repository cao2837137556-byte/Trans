# issue27cj Summary

primary_verdict: `initial_region_registry_not_qualified_115d_geometry_confounded`

issue27cj completed: yes
model_training: no
formal_benchmark: no
controller_tuning: no
support_reselection: no
sealed_final_access: no

## What Was Tested

The frozen issue27cf support bank was instantiated under the preregistered issue27cj protocol:

- `385` support-train rows formed one medoid candidate per exact attack label;
- `127` support-val rows audited coverage and label consistency;
- `24,000` OOD-benign-val rows audited overlap before registry freeze;
- `230,000` OOD-benign-stress rows were used read-only after freeze;
- `503,824` certified complete-only dev-query rows were used read-only after freeze.

Primary geometry:

`ID-benign robust-scaled Kitsune115D + Euclidean medoids`.

Challenger:

`same scaling + Ledoit-Wolf shrinkage Mahalanobis`.

## Main Result

Ten exact-label candidate regions were instantiated:

- `0` active strong regions;
- `1` active conflict-sensitive region;
- `9` ambiguous regions.

The conflict-sensitive region is not operationally trustworthy: its OOD-val direct core intrusion is approximately `99.996%`.

## Failure Evidence

- Support-val nearest-region exact-label consistency:
  - primary: `31.50%`;
  - challenger: `35.43%`.
- OOD-benign-val nearest attack-core rate:
  - primary medium shell: `85.07%`;
  - challenger medium shell: `81.58%`.
- OOD-benign-stress nearest attack-core rate:
  - primary: `95.67%`;
  - challenger: `95.93%`.
- Tight-shell OOD-benign-val core rate remains `63.87%`.
- Supported-label dev-future-query nearest-label consistency:
  - primary: `2.25%`;
  - challenger: `3.97%`.
- Same-file time-forward query nearest-label consistency:
  - primary: `3.77%`;
  - challenger: `4.79%`.
- Six labels satisfy the diagnostic two-medoid split signal, but no split was executed.
- For most candidate regions, a single feature contributes roughly `73%` to `99.9%` of the median squared distance; the top five dimensions contribute almost all distance.

Dominant features include `HH_5_covariance_0_1` and short-window `HH_jit` dimensions.

## Interpretation

The current raw Kitsune115D global metric space does not support a reliable attack-region registry.

The result does not show that the 512 support rows are useless. It shows that treating all 115 features as one global Euclidean/Mahalanobis geometry produces:

- extreme feature dominance;
- strong cross-label confusion;
- massive benign-OOD overlap;
- unstable support-query interpretation.

Changing shell width does not repair the failure. The preregistered challenger also fails, so this is not only an IQR-scaling artifact.

## Close-out

```text
solved: Instantiated and audited the initial region registry under preregistered primary/challenger geometries and established that raw global Kitsune115D regions are not qualified.
changed_mainline: yes
active_blocker: attack-region evidence space is confounded by feature dominance, label overlap, benign-OOD overlap, and support-query shift.
frozen: issue27cf support rows, issue27ch certified dev query, issue27cj preregistered protocol, medoid/shell audit outputs, failure verdict.
superseded: proceeding directly from the 512 support rows to active raw-115D attack regions, radius tuning, region splitting, model replay, or controller integration.
next_action: issue27ck_kitsune115_region_geometry_failure_anatomy_and_evidence_space_repair.
```
