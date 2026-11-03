# A/B dependency closure repair — prepared, not authorized

Job 179680 stopped before producing A/B results because the original five-module
package omitted a function-local import of `causal_reference_overlap_v1`.
The original 19 synthetic tests had no overlapping query/reference UID. Real
historical replay correctly exercises that branch. No bad scientific result is
being reused and no identity rule is relaxed.

This independent overlay copies the exact six-module recursive import closure
from the original frozen encoder vendor. Existing five modules are unchanged;
the additional causal identity module depends only on standard-library `math`.
`DEPENDENCY_CLOSURE.json` records every import, including function-local imports,
and all frozen SHA256 values. The original candidate, archive, input matrix,
source seal, calibration result, scores and failed job remain unchanged.

`bootstrap/repair_runtime.py` uses a strict import finder so the old matrix's
explicit insertion of its vendor directory cannot override the repaired closure.
The matrix child loads the same finder through `sitecustomize.py`; bootstrap
failure terminates with exit 78 instead of silently continuing. Scientific
launcher and matrix are consumed directly from the unchanged original package.

`src/metadata_preflight.py` is a separate read-only engineering gate. It performs
input file identity, metadata, UID join, q14 range and historical overlap checks.
It never opens target score arrays, constructs reference supports/distances,
normalizes E3, evaluates a score, forwards a model, trains, encodes or calibrates.
Its output is evidence of input readiness, not an experimental result.

`tests/test_dependency_repair.py` reproduces the old missing import in a clean
`python -I -B` subprocess and verifies the fixed branch, corrupted identities,
roles, labels, times, frames, q14 and UID joins. It checks the recursive AST
closure, root-repo shadow resistance, actual child bootstrap and fail-closed
behavior. Inputs in those tests are synthetic only.

The new authorization template defaults to false. The repaired entry requires a
new user evidence field and the exact repair `PACKAGE_SHA256SUMS` SHA in addition
to all original approval gates. The old job's approval cannot run this package.
No script automatically submits, resumes, requeues or retries a scientific job.
