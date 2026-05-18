# Reviewer Defense Notes

## Q1: Are you just stacking whichever model looks best?

No. The routing gate is constrained by a low-alert budget, validation evidence, review burden, and provenance checks. Issue20 must compare routed deployment against always-V1, always-V2, OR, AND, and review-heavy policies.

## Q2: Why not replace V1 with V2?

Because V2 is not uniformly safer. In primary low-OOD, V2 exceeds the 1% OOD budget, while V1 remains below it. V2 is a harder-shift repair module, not a universal replacement.

## Q3: What if V2 also fails later?

The system uses a bounded champion-challenger lifecycle. A candidate must pass a promotion gate before becoming active. Failed candidates remain in shadow or are rejected; they are not stacked indefinitely.

## Q4: Does low attack fraction in review weaken the contribution?

Review is a safety net, not a confirmed attack pool. The high-priority alert channel is controlled by the active champion. Review preserves base-only or challenger-conflict evidence for auditing and later model updates.

## Q5: Is this just MLOps rather than research?

The research point is the low-alert intrusion detection problem under benign-OOD drift: a high-recall adapter can be unsafe under OOD alarm constraints, so promotion must be budget-bound and evidence-driven. This is tied to measured V1/V2 conflicts, not generic engineering process.

## Q6: Did you select the model using final evaluation?

No. The proposed routing and promotion rules must use validation windows. Final OOD and attack evaluations are for reporting only. Issue19b alarm-budget slack is diagnostic and requires locked validation.

## Q7: Will V3/V4 cause catastrophic forgetting or model proliferation?

The lifecycle retains old champions as fallback and audit references, uses validation windows and rollback, and rejects candidates that fail the gate. It is not unconstrained continual learning.
