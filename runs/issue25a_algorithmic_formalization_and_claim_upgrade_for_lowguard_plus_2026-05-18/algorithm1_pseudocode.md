# Algorithm 1：增强型低告警守卫适配（Enhanced LOW-GUARD+）

## Input

- ID benign train set D_id_train。
- ID calibration set D_id_cal。
- OOD benign train set D_ood_train。
- OOD validation set D_ood_val。
- confirmed attack train/support pool D_attack_pool。
- source_rich feature matrix X_sr。
- OOD alarm budget B = 1%。
- support budget k = 32。
- feature budget m = 64。

## Output

- selected feature set S。
- guarded adapter f。
- deployment threshold tau。

## Pseudocode

1. Extract source_rich representation X_sr for ID, OOD, and attack-pool samples.
2. For each source_rich feature j, compute an empirical OOD-safe attack-separation score using attack supports, ID calibration, and OOD validation statistics.
3. Rank features by the attack-separation score and apply redundancy pruning.
4. Select the top m features as S.
5. Select k confirmed attack supports from D_attack_pool using kcenter coreset selection.
6. Fit scaler on ID benign train, OOD benign train, and selected attack supports using features S.
7. Train a fixed guarded few-shot adapter f with selected attack supports as positives and ID/OOD benign train as negatives.
8. Calibrate threshold tau using ID calibration and OOD validation under OOD alarm budget B.
9. Report scores and metrics on final OOD eval and attack eval without tuning.

## Provenance Rule

Steps 1-8 must not use final OOD eval or attack eval. Final eval is report-only.
