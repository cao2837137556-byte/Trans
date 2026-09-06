# Frontend-F5: compact Sol implementation handoff

Date: 2026-09-06

Status: `DESIGN_HANDOFF_IMPLEMENTATION_AND_REAL_RUN_NOT_YET_AUTHORIZED`

## Read budget and source of truth

Worktree:
`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`.

First read the top current section of `runs/mainline_docs/mainline_handoff.md`,
then these two documents fully:

1. `frontend_f5_unified_student_one_shot_training_draft_20260906.md` and its
   later accepted FROZEN successor, if present;
2. this handoff.

Only when needed, read the exact F4 schema or teacher numeric erratum pinned
in the protocol. Do not reload the full months-long handoff, all Kimi/GPT
reviews, or rejected routes. Do not repeat F4's real audit: it already passed
at `9023e39`. Verify inputs against its hashes instead.

The draft plus its SHA is not execution permission. Check the user's latest
authorization. Existing F4 implementation/no-model permission does not extend
to real F5 teacher/score/model work. Once F5 implementation is authorized, do
not ask again for individual code files, synthetic tests, or mechanical fixes
within the accepted design. Real P/T/K requires its separate bounded run
authorization. Do not manufacture an independent-review approval.

## What to build when authorized

One shared model for A and B:

```text
fixed F4 131D events
 -> Linear(131,64) + GELU
 -> causal one-layer GRU(64,128)
 -> Linear(128,64) + GELU + Linear(64,1)
 -> raw logit >= 0 means hard
```

Old P2 is a training-only A teacher. Do not attach the frozen old P2 to the
student or add a 768D adapter. Owner, source, label, device and context IDs
cannot enter the forward signature. Student inference is the same for A/B.

Use `issue27frontend_f5_unified_student_v1.py`, its contract-test companion,
and a minimal Windows launcher/monitor. Functions should separate identity,
selective teacher IO, forward/losses, eligibility, checkpoint lifecycle, and
final rejection testing. Never import old runner modules with data side effects.

The normative draft contains all numeric choices. Most error-prone details:

- Parent 13,866 targets = 8,660 nested train + 5,206 nested validation;
  contexts 9,307 = 4,984 + 4,323; inherited source split is immutable.
- Teacher materialization is only 6,870 nested-train A rows, not 8,353 parent
  A rows, not all 25,467 NPZ rows. Validate UID/missing metadata, stream other
  representation rows opaquely. Canonical float64 normalizer -> float32 P2.
- Signed teacher strength `clip((2*y-1)*(z_old-z0_old),0,6)`; wrong-benign A
  teacher value is null. Student uses zero threshold; old threshold is only
  a teacher identity. Do not confuse raw logit and sigmoid output.
- Losses: four-group context-balanced BCE, two-group one-sided teacher Huber,
  attack mean plus batch-worst Huber, 0.1 causal next-attribute auxiliary.
  The protocol specifies global context-denominator minibatch weights.
- Auxiliary predicts protocol-group/direction/length-bin/delta-bin, never a
  vocabulary or a future target's classification label.
- Per-epoch eligibility requires zero A attack flips, zero B attack misses,
  and zero new A protected-benign hard decisions on both train and validation.
  Save each gate's counts; an eligible boolean alone is insufficient.
- Select by validation supervised loss only; no kill-only-based epoch choice.
  Tiny validation attack counts remain an explicit claim limitation.
- B validation utility: all three inherited device-family keys meet both
  target and whole-B-benign-context 10% thresholds. These are not CE's 4,812/482
  gate, and the keys are not asserted to be independent physical devices.
- Five exposed attack inputs open only once after selected checkpoint hashing
  and B utility PASS. A flip cannot cause another training/checkpoint attempt.
- Exactly 94,748 training parameters; seed 2705; 100-epoch maximum; no search.
- Resume exact model/optimizer/RNG/cursor, keeping cumulative resources and
  complete interruption receipts. Never reset a spent scientific attempt.

## Delivery phases

After implementation authorization: mechanically freeze the accepted text if
the user's authorization includes freezing; add only status/provenance and
its SHA. Implement, run the 22 synthetic contract categories, and run the
bounded synthetic resource pilot in a separate process. Record exact runtime,
code/test identities and initial tensor hash; do not touch real arrays/models.
Return a short implementation review and one copy-paste real-run command.

After real-run authorization: identity checks -> narrow teacher materialization
-> one local trajectory -> seal best checkpoint -> utility -> five-row reject
gate -> package. One process-chain authorization covers these conditional
stages. Stage failure prevents downstream opens.

To return to the design task, supply only: implementation/result report path,
verdict path, checksum path, relevant commit, and any unresolved semantic
question. Do not paste every log or the entire prior conversation.

## Escalation and stop discipline

Routine serialization/path/Windows errors may be fixed without changing the
science. Preserve failed-attempt receipts and unrelated dirty files. A true
protocol ambiguity, changed input identity, unavailable pinned runtime,
resource excess, or scientific failure is not license to change constants.
Prepare the smallest concrete issue for the design task.

Do not broaden to commissioning, fresh data, full report/FINAL, deployment,
source split repair, an extra model, or a new training seed. The operating
incumbent is preserved, but that fact is not a student-inheritance result.
