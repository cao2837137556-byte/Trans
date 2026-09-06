# Frontend-F4 to F5: higher-reasoning design brief

Date: 2026-09-06

Status: `DESIGN_INPUT_ONLY_TRAINING_UNAUTHORIZED`

F4 has removed the mechanical input blocker: the same L1 information now
reaches a fixed 131D input with exact round trips and no UNK. The next design
question is no longer which packet field to add. It is whether one narrowly
specified learner can preserve the incumbent's correct A behavior while
learning useful B behavior.

The next protocol should preserve these commitments:

1. One mechanically chosen small sequence encoder; one seed, no hyperparameter
   sweep, no fallback model zoo, and one authorized training run only.
2. Use all legal A-fit teacher evidence through a label-aware continuous
   old-function constraint. Preserve high-confidence old attack evidence, but
   do not force the 26 known benign teacher errors to remain hard.
3. Do not require the new representation to occupy the old E3 coordinates or
   treat the frozen old P2 as the only possible deployment head. F1 already
   showed that equal output width does not imply functional compatibility.
   Compare a declared frozen-P2 compatibility arm only if it has a distinct,
   pre-frozen purpose; the primary unified interface may use a small student
   head trained under the old teacher constraint.
4. Separate three claims and gates: A functional inheritance, B blind-spot
   utility, and later OOD/commissioning behavior. A pass in one cannot fill an
   evidence gap in another.
5. The inherited internal validation has only one A attack context / three
   rows. Before optimizer access, define a defensible development/kill-only/
   untouched confirmation topology without moving sources after seeing
   outcomes. If no positive inheritance claim is identifiable, name that
   limitation before training rather than weakening the denominator.
6. Keep select/viewed/report/FINAL inaccessible for loss, checkpoint selection,
   thresholds, or retries. Previously exposed five attacks can only kill.
7. Predefine a hard stop: if the one mechanism-level training attempt cannot
   preserve A while obtaining nontrivial B benign utility, close the unified
   inheritance experiment. Do not tune weights after the result.

New-device benign observation remains the second system objective, after a
usable unified score exists. Commissioning should compare the absolute unified
score with deviation from a device's clean observed baseline, using session-
level units and untouched devices. It must not be used to rescue a failed
inheritance run or to claim industrial OOD generalization without paired
evidence.

This brief is not a numerical addendum and authorizes no score opening, teacher
materialization, model construction, or training. It is intended for the next
very-high-reasoning design/review turn.
