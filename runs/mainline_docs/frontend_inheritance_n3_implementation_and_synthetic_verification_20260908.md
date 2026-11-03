# N3 implementation and synthetic verification

Date: 2026-09-08.
Status: N3_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS.
Authority: the user's current "authorize implementation" message covers this
implementation and generated synthetic acceptance only. It does not authorize
real input decoding, model loading, fitting, K or deployment.

## Result

70/70 generated tests passed, zero failures and zero errors. Both PowerShell
scripts passed parser checks. Formal tests took 4.030 seconds in the inherited
Python 3.9.13 / NumPy 2.0.2 / torch 2.8.0+cpu / SciPy 1.13.1 runtime.
A preliminary 64-test development run passed before additional failure-path and
split-accounting coverage was added; it was not a real experiment or resource pilot.

The acceptance includes 11 code pins (seven new N3 files and four reused
definitions/helpers), seven runtime file pins and all three N3 protocol/evidence
identities. Readiness revalidated the inherited 57-name input pin chain and 16
historically attested code files. Historical acceptance metadata was read for
identity verification; historical numerical payloads were not read by this stage,
and historical suites/workers were not run.

Acceptance:
runs/frontend_inheritance_n3_implementation_v1_20260908/synthetic_acceptance.json
SHA256: 647b8f02e22b5197a7f301f093b560ef84f4e176e45366fe2a52ea5c7515639f

Implementation manifest:
runs/frontend_inheritance_n3_implementation_v1_20260908/SHA256SUMS
SHA256: 08535bb118463b8d70e708e5b21614c9aa7d9d59fb2aff9575ebb528c32175df

Detailed individual test receipts:
runs/frontend_inheritance_n3_implementation_v1_20260908/synthetic_tests.json
SHA256: 2d58de319f39eb34d79e5af9db298f364f548d38a047e41df6ca5244ea8f70f7

## Implementation

New support, runner, controller, verifier and test modules live under
repo/ood/issue27frontend_inheritance_n3_*_v1.py. The start/status scripts are
scripts/start_frontend_inheritance_n3_local.ps1 and
scripts/show_frontend_inheritance_n3_status.ps1.

The new reader projects both original splits without accessing l1_prefix_sha256
or old_all_unk. It joins F4/P identities and saved N1/N2 predictions, freezes the
three fitting roles before feature decoding, and preserves the exposed residual
role separately. The generated population test verifies 12,711 constraints,
2,253 positive labels and 1,155 exposed report-only rows.

The restricted checkpoint projection does not index any epoch_ledger value.
It uses one weights-only load, excludes ambient safe globals and restores them
afterward, and records incidental container materialization without using it.
Head and cache containers are counted as numerical inputs. The cache decoder
checks original protected membership rather than replacing it with N3 fitting
membership.

The canonical read-only hook captures complete per-context pre-head matrices
using the unchanged F5 Student and original batch order, no_grad and split
boundaries. Baseline development logits must reproduce every N2 float32 bit.
Training cache and development vectors have separate identity comparisons.
There is no baseline training replay in the real worker.

The runner uses the pure sealed N1 math functions for one fixed LP and one
candidate cast, exact signs and one rational alternative check. A candidate is
installed into a separate model copy. Both candidate splits finish when a
scientific gate fails; integrity failures stop. Reports include residual rows,
source/family/category summaries, six development attacks, normal_1 groups and
changes against the complete historical references. B retention checks old
target/context membership by inclusion and independently checks original floors.
Additional normal releases are permitted and reported.

The controller requires separate explicit real authorization and an absent real
namespace. Its Windows Job enforces one worker and committed-memory limits,
with external time/output/peak-memory monitoring and terminal sealing. Global
and phase-specific counters distinguish baseline development, candidate train,
candidate development, one-time decoding and repeated forward events.
The viewer distinguishes NOT_STARTED, provisional status and a hash-verified
final supervisor receipt. An existing real attempt cannot restart.

## Synthetic evidence and limits

Generated checks cover input pin overlaps, selective CSV access, duplicate and
reference joins, original versus fitting protection, outcome-informed B roles,
retention membership/context unions, additional releases, cache/prefix hashes
and one-time decoding, checkpoint projection and restricted safe globals,
float32 signed-zero and scalar-bit comparisons, full-context ordering and
batch boundaries, immutable representation and candidate assembly.

Numerical checks cover a complete generated Student/LP/exact/replay workflow,
separable and nonseparable fixtures, tiny positive margins, fixed-fixture
repeatability, attack-zero versus benign-zero, actual Linear rounding versus
exact arithmetic, timeout candidates and no-candidate branches, impossible
solver statuses, one-solve limits, rational certificate corruption/rank/support/
time/bit limits and verdict precedence. A generated scientific failure still
completes both candidate passes and the residual report; a baseline mismatch
prevents the solver, and residual labels do not enter the LP.

Controller checks include startup, abnormal exit, missing/corrupt receipts,
provisional/final seals, no restart, external wall/output monitoring, cooperative
memory limits and an injected external peak-memory violation. The memory
monitor contract test injects an over-limit reading; it is not a real 8 GiB
allocation benchmark. Generated subprocess checks are contract tests, not
resource pilots.

The suite enforced a filesystem audit guard denying repository runs/ opens.
Its one intentional denied-open test passed. All numerical/model/checkpoint
fixtures were generated. No real scientific success, true-scale numerical
feasibility, full-scale run time, or broader inheritance result follows from
these tests. Synthetic pass is implementation evidence only.

## Current state and next gate

Read-only controller readiness:
READY_FOR_SEPARATELY_AUTHORIZED_REAL_N3, real_numeric_access=0.

Read-only real status:
NOT_STARTED.

The real namespace
runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908/
remains absent. No real checkpoint load, cache/feature decode, forward, LP,
optimizer/backward step, teacher call, historical rerun, resource pilot, download,
HPC run or K was performed.

Next is separate authorization for ONE real N3 conservative fitting attempt
under the frozen protocol. Its ceiling is 1,800 seconds including input checks
and sealing; this is a stop bound, not a promise of success or inheritance.
Even a verified witness establishes only the stated finite-set repair:
broader_inheritance=NOT_PROVED, F5_eligible=false, deployment=false,
K=NOT_AUTHORIZED, new_device=NOT_EVALUATED.

Branch remains codex/exp-mainline; HEAD remains
4b28747b09480471e2bac1beb3a9badf27280efb.
The eight existing unrelated tracked modifications were preserved; hashes of
all 17 top-level files in their issue27by directory match the initial read-only
snapshot. Existing F5/N1/N2 attested source and all three N3 frozen documents
remain unchanged. No worktree/branch change, reset, commit or push occurred.

