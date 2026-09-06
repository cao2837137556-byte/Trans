# Frontend-F5 Stage I: implementation and synthetic verification

Date: 2026-09-06

Status: `F5_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS`

## Outcome and authorization boundary

The authorized implementation is complete: numerical core, P/T/K controller,
synthetic suites, pinned-runtime verification, background launcher and read-only
monitor. The current Astra implementation setting was used; no Sol switch is
required. This supersedes the earlier I1 runner-pending checkpoint.

**47/47 synthetic tests PASS (22 numerical + 25 integration), two PowerShell
scripts parse successfully, and the single synthetic resource pilot passed.**
This is implementation acceptance, not independent third-party review and not a
scientific F5 result. Real teacher/feature opens and real optimizer steps are 0.
The real F5 output directory has not been created. P, T and K each remain
unauthorized until the user explicitly grants that scope.

Frozen contract SHA:
`b8069e6556d6719eef3e689b1ab9a8676c24a00a82e8b5f810a401c9c42786b6`.
No loss, architecture, threshold, split, denominator or scientific gate changed.

## What was built

| Component | Role |
|---|---|
| `repo/ood/issue27frontend_f5_unified_student_v1.py` | Shared 131D/GRU/student-head numerical core; losses, teacher math, causal batching, checkpoint primitives |
| `repo/ood/issue27frontend_f5_unified_student_runner_v1.py` | Separately authorized real P/T/K; pins, census, teacher whitelist, one trajectory, stage order, final accounting |
| `repo/ood/issue27frontend_f5_unified_student_contract_tests_v1.py` | 22 numerical/serialization regression tests |
| `repo/ood/issue27frontend_f5_unified_student_integration_tests_v1.py` | 25 synthetic controller and access-boundary tests |
| `repo/ood/issue27frontend_f5_verify_implementation_v1.py` | Runs both suites, verifies measured pilot compatibility, seals code/runtime receipt |
| `scripts/start_frontend_f5_local.ps1` | Explicit stage token, absolute local paths, hidden independent Python process |
| `scripts/watch_frontend_f5_local.ps1` | Read-only status, last completed epoch, terminal states and stale-lock warning |

Student deployment remains shadow-only and unchanged incumbent deployment is
not overwritten. Both A and B use the same new student computation; old P2 is
a nested-train teacher, not the new inference head or a learned router.

## Important behavioral checks

1. F4 context/UID/source joins and all frozen category denominators precede
   feature opens. Production preflight verifies 19 byte pins. Synthetic source
   crossing, offset drift, hash drift and invalid denominators stop early.
2. A synthetic 25,467-row NPZ contains finite representations only for the
   6,870 authorized teacher rows and NaNs elsewhere. The production selective
   reader/materializer succeeds while numerically opening exactly 6,870 rows,
   not all rows. It produces exactly 24 null strengths for teacher-wrong benign.
3. The canonical teacher uses float64 normalization, float32 network/sigmoid,
   then float64 threshold comparison. Raw logits remain available under
   saturated probabilities. Wrong benign has no teacher loss; B has no teacher.
4. Packed/individual prefixes agree within 1e-6 and synthetic hard decisions
   agree. Changing future events cannot change earlier prefix outputs; contexts
   reset state. Metadata and endpoints are not injected into model features.
5. The hand-calculated zero-logit loss is 2.6. Context averaging, global eligible
   denominators, empty batch groups, partial batches, tied-max gradients and
   singleton auxiliary exclusions have explicit tests.
6. Train and validation are evaluated separately without validation gradients.
   Every epoch logs individual protected-gate counts/worst margins, all failing
   UIDs and same-checkpoint full-training loss diagnostics. The latter's maximum
   is labelled whole-corpus, distinct from the training batch-max term.
7. Synthetic interrupted/resumed training reproduces tensors, optimizer/RNG,
   order/cursor and ledgers. Physical recomputation does not erase consumed time.
   Checkpoints explicitly store the order and early-stop state. A crash after
   the early-stop checkpoint cannot add another epoch on recovery.
8. No eligible checkpoint produces a named stop and never opens K. A sealed
   checkpoint is immutable before utility/kill-only evaluation. B utility must
   satisfy each literal key/target/context denominator; the target minima sum
   to 373, not 372. Failing utility never calls the kill loader.
9. A synthetic kill failure is evaluated once, is not positive evidence and
   cannot select a replacement epoch. An unclean stop after its opening marker
   requires engineering review instead of automatic reopening.
10. Time, RAM and output resource checks, completion refusal, corrupt checkpoint
    refusal, separate authorization tokens and conservative claim flags are
    tested. No capability, OOD, commissioning or CE PASS is emitted by I.

The controller success-path test mocks evaluation to isolate state-machine
behavior; it does not pretend a synthetic model demonstrated real efficacy.
Other trajectory tests actually optimize a small synthetic model. All synthetic
arrays/checkpoints are temporary fixtures, not scientific data.

## Runtime and resource screen

Python 3.9.13 / NumPy 2.0.2 / torch 2.8.0+cpu; 4 intra-op and 1 inter-op threads.
No install/upgrade was performed. The frozen 94,748-parameter model is unchanged.

The single pilot measured source commit `117e43f`: projected 9,320.99668 s;
threefold 27,962.99004 s; cap 47,494.34391 s. This is approximately 2.59 / 7.77 /
13.19 hours respectively, not a promise of wall-clock completion. Full controller
accounting includes actual evaluation, diagnostics, serialization and active
between-batch work. Exceeding the unchanged cap is a resource stop, not a PASS
from an incomplete best checkpoint.

The pilot was **not rerun** to get a better time. Later core changes only added
an evaluation resource callback and earlier failure-access accounting. The
verification script compares the AST identities of the entire measured
model/loss/batching/pilot path and its constants against the pinned measured
source. That path is unchanged. Initial tensor SHA is also rechecked.

The first 47-test acceptance receipt is preserved as
`stage_i_acceptance_initial_47tests.json`. Before any real execution, controller
durability was tightened to persist the actual order and charge active gaps;
the complete 47 tests were rerun and `stage_i_acceptance.json` resealed. No
scientific result or real input informed this engineering revision.

## Operator handoff — do not launch before authorization

Current gate: **wait for real P authorization**. P reads only the authorized
teacher scope after identities/census pass, then seals the teacher cache.
T is a separate one-trajectory authorization; K is a separate final evaluation
authorization. The launcher cannot silently advance from one stage to another.

After the corresponding user authorization, the stage commands are:

```powershell
# P only: identities, parent inputs, 6,870-row teacher materialization; no optimizer.
& 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\scripts\start_frontend_f5_local.ps1' -Stage preflight -Authorization I_AUTHORIZE_F5_REAL_P_TEACHER_ONLY

# T only, after P PASS and a separate training authorization.
& 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\scripts\start_frontend_f5_local.ps1' -Stage train -Authorization I_AUTHORIZE_F5_REAL_T_ONE_TRAJECTORY

# K only, after a completed selected checkpoint and separate evaluation authority.
& 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\scripts\start_frontend_f5_local.ps1' -Stage evaluate -Authorization I_AUTHORIZE_F5_REAL_K_ONCE
```

Read-only monitor (does not start anything):

```powershell
& 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\scripts\watch_frontend_f5_local.ps1'
```

Ctrl+C stops only this monitor. Network loss is irrelevant to local Python.
Keep Windows awake. A killed process/unclean shutdown is different from network
loss: verify the old PID is gone, inspect its lock/time/checkpoint receipts, then
resume the same trajectory; never delete checkpoints or initialize a new run.
Stale locks are deliberately not auto-deleted. An unclosed batch charges the
uncertain UTC downtime conservatively and may exhaust the resource budget.

Control stdout/stderr logs live in the separate `_local_control` directory,
because process stdout closes after the sealed scientific result manifest.
The scientific output directory is `runs/frontend_f5_unified_student_v1_20260906_local`.
No background process has been launched in this implementation turn.

## Evidence

`runs/frontend_f5_implementation_v1_20260906/stage_i_acceptance.json` pins all
seven implementation/test/operator files, the runtime, protocol, numeric pilot
path, test transcripts and original pilot. `SHA256SUMS` seals the implementation
evidence directory. Earlier I1 files remain historical, not the current status.

Next scientific question is still open: can this one student retain permitted
A decisions while gaining useful B normal decisions? Passing implementation
tests does not answer that question. Broader untouched confirmation and new
device commissioning remain later, separately scoped work.
