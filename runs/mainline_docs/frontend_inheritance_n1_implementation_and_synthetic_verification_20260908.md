# N1 implementation and synthetic verification

Date: 2026-09-08.
Status: `N1_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS`.
Branch: `codex/exp-mainline`.
HEAD: `4b28747b09480471e2bac1beb3a9badf27280efb`.

## Authorized scope and current gate

The user switched to the implementation setting and authorized the next stage.
This stage implemented the sealed N1 protocol and tested generated synthetic
fixtures only. The real N1 parameter-fitting attempt is NOT authorized or started.
The frozen scientific protocol and input/runtime pin file remain byte-identical.
Existing unrelated modifications, old F5 artifacts and incumbent are preserved.
Files remain local; no commit or push is claimed.

Current acceptance package:
`runs/frontend_inheritance_n1_implementation_v2_20260908/`.
Its `synthetic_acceptance.json`, `synthetic_tests.json` and check receipt are
sealed by `SHA256SUMS`. Nine code/dependency identities and seven runtime file
identities are recorded. The controller checks this package before real access.

## Implemented behavior

- Restricted metadata projections, full-file opaque identity checks, immutable
  train UID/context joins and category counts, then sealed train prefix ranges.
  Numeric feature access uses seek/read on those ranges only.
- Restricted weights-only checkpoint loading with the four literal NumPy safe
  globals. The projected training reference discards incidental optimizer/RNG
  and historical validation contents without using them.
- Canonical F5 Student forward under torch.no_grad(), full-context head hooks,
  original batching and complete pre-head context hashes. The five-error
  terminal baseline must reproduce before any real solve.
- One fixed HiGHS dual-simplex LP, one candidate cast, independent exact signs
  and original float32 replay. One bounded exact certificate reconstruction,
  with the frozen positive/negative/unknown precedence and accompanying-row
  outcome accounting, including explicit absence when no candidate exists.
- One worker under a Windows job object with process-memory and active-process
  limits, kill-on-supervisor-exit and external wall/output monitoring. Payload
  hashing precedes the final supervisor verdict. Missing/corrupt terminal data,
  startup identity failures and abnormal exits produce engineering-stop records.
- Explicit authorization gate, refusal of existing real attempt directories,
  no restart, and a read-only viewer that prioritizes the final supervisor
  record and identifies provisional or unreadable status.

The implementation uses the existing F5 numerical core as an inert model
definition. No historical loading, optimization, teacher, resource-pilot or
evaluation launcher is invoked.

## Verification evidence

Final acceptance: **36/36 synthetic tests PASS**, plus **2/2 PowerShell parser
checks PASS**. The suite includes mixed-row access sentinels, generated metadata
with all five original category denominators, wrong identities/ranges/joins,
checkpoint allowlist rejection, full-context replay identity, exact threshold
ties, known separable/nonseparable fixtures, tiny positive margins, a real
float32 cancellation counterexample, solver statuses, certificate corruption,
rank/support/bit/time limits, result precedence and no-retry guards.

Synthetic subprocess checks confirmed wall-stop handling, Windows rejection of
an oversized allocation and second worker, output-stop handling, preflight
failure with zero spawned workers, corrupt terminal handling and abnormal exit
sealing. These are limit-enforcement tests, not a resource timing pilot.
The small fixed LP repeatability check passed in the pinned runtime.

A process audit guard rejected access paths to historical experiment artifacts;
the suite recorded zero such attempted opens and zero real numeric access.
Real model forwards, checkpoint tensor loads, LP calls and optimizer/backward
steps were all zero. No historical experiment, F4 audit, resource pilot, data
download or HPC job was run. No validation, select, viewed/report, FINAL or K
numeric data was opened. All tensors and numerical arrays used by tests were
generated fixtures, including the checkpoint's JSON-roundtripped identities.

The first implementation package (`...implementation_v1_20260908/`) retains its
32-test passing receipt as historical evidence. Final workflow review then
strengthened failure sealing and provisional status handling and added four
tests. V2 is the authoritative acceptance; V1 must not authorize current code.
The scientific protocol did not change between those packages.

The post-acceptance read-only readiness check returned
`READY_FOR_SEPARATELY_AUTHORIZED_REAL_N1`; the status viewer returned
`NOT_STARTED`. No real N1 output directory or worker was created.

## Next step and limits

The next stage requires explicit authorization for one real N1 fit, including
the disclosed restricted full-checkpoint container access. The real namespace
is `runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908/`.
The fixed ceilings remain 1,800 seconds total, 8 GiB process memory, 100 MiB new
output, one LP and at most two canonical forwards. No optimizer/backward step
occurs, but adjusting the last layer is still parameter fitting.

After authorization, launch with `scripts/start_frontend_inheritance_n1_local.ps1`
and its explicit `-AuthorizeRealN1` switch. Inspect progress with
`scripts/show_frontend_inheritance_n1_status.ps1` (or `-Once` for one snapshot).
The viewer is read-only and does not grant or trigger real execution.

Synthetic acceptance is engineering readiness only. Inheritance remains
unproved and F5 remains `NO_ELIGIBLE_CHECKPOINT`. A future N1 positive witness
would establish only the fixed finite-set joint decisions. Coverage, holdout
inheritance, B utility and new-device commissioning remain separate questions.
