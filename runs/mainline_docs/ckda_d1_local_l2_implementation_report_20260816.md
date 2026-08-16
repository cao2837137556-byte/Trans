# CKDA D1 local L2 implementation report (2026-08-16)

## Outcome

The local report-only continuation is implemented as a separate script rather
than extending or reopening the completed L1 chain. It is authorized by the
user after the Codex L1 review PASS.

## Fixed execution order

1. Revalidate all immutable inputs and the tracked Codex L1 review gate.
2. Verify the threshold marker, fit/select plan, embeddings, probe state, 30
   member checkpoints, FINAL=0, and sealed-report state.
3. Require the explicit `-AuthorizeReportOpen` switch.
4. Materialize the frozen 262,050-row report plan and target metadata.
5. Generate E3 report embeddings with identity-checked member checkpoints.
6. Score only the frozen G0/P1/P2 probes and thresholds.
7. Compute the frozen metrics and 2,000-replicate bootstrap evidence.
8. Validate the scientific verdict and create a SHA-pinned pullback package.

## Failure and resume behavior

- No-authorization dry run opens zero report outputs.
- The one-shot report-open marker is written before the first report plan is
  materialized.
- Every long phase has a completion marker and required-output checks.
- E3 report embedding resumes only from member checkpoints whose contract,
  plan, member, and UID identities validate.
- A code or immutable-input hash change blocks resume.
- Engineering failure writes a null scientific verdict and never changes a
  threshold, candidate, denominator, or family rule.

## Verification

- Both PowerShell scripts parse successfully.
- The no-authorization preflight completed with zero report artifacts before
  and after execution.
- The CKDA D1 Python contract suite passes 48/48.
- The L1 gate is tracked and pins the exact plan, embedding, probe-state, and
  threshold-marker SHA-256 values.

## Boundary

This implementation does not open cooler-motor, seed 37, seed 47, or any other
FINAL asset. Local results remain contingency evidence pending formal HPC
replay under the frozen contract.
