# Frontend-F4 implementation handoff for Sol High

Date: 2026-09-05

Design finalized: 2026-09-06; filename retained for the original design lineage.

State: design complete; implementation and the no-model audit authorized by the
user, training not authorized.

## Read first

1. `frontend_f3_full_fit_l1_result_closure_20260905.md` and its JSON receipt.
2. `frontend_f4_fieldwise_input_feasibility_draft_20260905.md` in full.
3. The current top section of `mainline_handoff.md`.

All three live under `runs/mainline_docs` in
`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`.
Branch: `codex/exp-mainline`. Preserve unrelated dirty files. This is a narrow
successor within the existing frontend experiment thread, not a new worktree
or a new user task.

## Problem and design commitments

F3's L1 field strings eliminate the observed exact mixed-label conflicts, but
whole-string lookup maps unseen combinations to UNK. The selected F4 map
separates all 19 existing fields into exactly 131 float32 coordinates. Numeric
lengths use exact two-limb UInt32 representation plus a fixed log-magnitude
coordinate; categorical/optional information uses fixed one-hots and bits.
Its inverse must recover every original signature exactly. Do not add packet
fields, enlarge a vocabulary, silently clip values, fit a scaler, or choose a
different map. No new decoding is needed.

There is no D1 model to implement yet. In particular, no GRU, head, normalizer,
teacher score, random-weight canary, loss, or optimizer belongs in this change.
The current inherited validation A attack evidence is only one context / three
rows. Input feasibility must not be reported as attack capability.

Do not lose the 26 A benign-but-teacher-hard rows when reproducing the four
protected category summaries. Section 3 defines a fifth audit category and
full target conservation. Future label-aware teaching must not lock these
known benign mistakes in; no teaching happens in the present audit.

## Ordered implementation task

1. Check git status and the pinned F3 package. Do not rerun F3.
2. Mechanically create the F4 FROZEN document from the completed draft with only
   title/status/provenance changes. Generate a SHA-256 sidecar. Existing user
   authorization covers this implementation prerequisite; do not add a new
   approval loop for the same scope.
3. Add `repo/ood/issue27frontend_f4_fieldwise_input_v1.py` and
   `repo/ood/issue27frontend_f4_fieldwise_input_contract_tests_v1.py`.
   Keep them stdlib/NumPy-only and separate from model runners. Publish the
   schema from literal constants before any real feature computation.
4. Implement all 28 synthetic requirements. Tests must include distinct
   UInt32 values above 2^24, NONE/zero distinctions, unseen combinations,
   future-prefix invariance, metadata exclusion, and blocked IO sentinels.
5. Review exact feature offsets and state classification; run the tests. Once
   they pass and there is no unresolved contract issue, execute the offline
   audit from the F3 L1 corpus and its five-row checkpoint under the user's
   existing no-model authorization.
6. Independently verify the output hash package, round trips, target membership,
   role counts, and the two binary feature files through their saved offsets.
   Write the result report, update the current handoff, and commit/push only
   this task's files. No training follows a PASS automatically.

Suggested runner command to implement:

```powershell
python repo/ood/issue27frontend_f4_fieldwise_input_v1.py --output-dir runs/frontend_f4_fieldwise_input_feasibility_v1_20260905 --authorization-token I_AUTHORIZE_FRONTEND_F4_NO_MODEL_FIELDWISE_AUDIT
```

The token is an audit record of already granted user scope, not a request for
another permission. The runner must pin the F4 frozen SHA in its source and
report its own implementation/test/schema/runtime identities. Do not invent
future checkpoint hashes or claim execution before it happens.

## Required stop behavior

- F3's original package/verdict and its scope correction stay intact.
- Syntax/identity/code failures get an engineering receipt and no scientific
  verdict. Correct implementation bugs within the same frozen design.
- Valid values outside the declared domain, resource-cap violations, or a
  genuine feasibility failure produce the exact named terminal state; do not
  change the range, map, source split, or gate to make the same run pass.
- Keep existing train/internal-val assignments. All F3 diagnostics are exposed
  development evidence; the five older attacks are kill-only.
- No select/report/FINAL, scores/models/embeddings, PCAP/network, training,
  external dataset discovery, HPC, or changes to old deployment.

## Delivery to the user

Explain whether the observed fields survive the model input without UNK or
numeric collapse, give the scoped target/context counts, and distinguish this
from a trained capability result. If PASS, prepare a concise next-design brief
for the user to review with the higher-reasoning model. The one-shot training
contract remains a separate decision, with no training authorized yet.
