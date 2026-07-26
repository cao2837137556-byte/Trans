# Paper04 HPC Failure Ledger and Launch Gate

Date: 2026-07-25

Scope: `codex/exp-mainline` paper04 experiments, including paired AMD/Intel
submissions. This document is a permanent engineering contract. It does not
change any scientific split, model, threshold, cache manifest, or result.

## 1. Required outcome classification

Every HPC attempt must be assigned exactly one execution class before any
scientific interpretation:

1. `PACKAGE_OR_TRANSFER_FAILURE`
   - Bundle bytes, line endings, checksum, upload, extraction, or transfer are
     invalid.
2. `INSTALL_OR_SUBMIT_FAILURE`
   - Remote paths, immutable-file policy, installed-file hashes, submission
     metadata, or `sbatch` invocation fail before allocation.
3. `COMPUTE_STARTUP_FAILURE`
   - The allocated job exits during startup because a command, shared library,
     environment, input path, or launcher is unavailable on the compute node.
4. `RUNTIME_FAILURE`
   - The scientific program started but failed, timed out, exhausted resources,
     deadlocked, or made no bounded progress.
5. `POST_RESULT_FAILURE`
   - Scores/results were produced, but validation, metadata finalization,
     packaging, or pullback failed.
6. `SCIENTIFIC_NO_GO`
   - Execution and validation completed successfully, but preregistered
     scientific criteria were not met.
7. `SCIENTIFIC_GO`
   - Execution and validation completed successfully and preregistered
     scientific criteria were met.

`POST_RESULT_FAILURE` and `SCIENTIFIC_NO_GO` must never be reported as generic
"the experiment crashed." A recovery must state whether models were retrained
and whether scores, gates, thresholds, or manifests changed.

## 2. Mandatory failure record

Every new failure must add a ledger entry containing:

- date, bundle commit, job ID, partition, and exact error signature;
- execution class from Section 1;
- root cause, not only the final exception;
- which scientific artifacts are valid and which are not;
- minimal correction;
- an automated regression test or launch gate that prevents recurrence;
- whether rerunning compute is necessary;
- evidence that the correction does not change the scientific protocol.

If a known signature recurs, the launch chain is considered defective. Do not
ask the user to retry until the missing permanent gate is added and exercised.

## 3. Permanent gates learned from prior failures

The following checks are mandatory for all future paper04 bundles:

### Bundle and transfer

- Generate text payloads as LF-only and byte-audit the extracted archive.
- Build `SHA256SUMS` from the exact archive payload and verify it after a clean
  re-extraction.
- Publish one unambiguous bundle directory, archive path, byte size, and
  SHA-256.
- Use resumable transfer for large data and verify source/destination hashes.
- Never mix PowerShell syntax, interactive `sftp` commands, and Bash heredocs.

### Installation and immutable inputs

- Do not assume the remote experiment tree is a Git checkout or that `.git` is
  a directory.
- Check every required immutable input path before `sbatch`.
- Distinguish an absent target, an identical target, and a differing target.
  Do not overwrite a differing frozen target.
- Use versioned new filenames when implementation bytes legitimately change;
  do not make remote installation depend on replacing historical files.
- Make installation idempotent and make duplicate-submission detection
  explicit.

### Compute-node runtime

- Reuse only `scripts/00_env_issue27ckc.sh`; do not run pip, create Conda
  environments, pull containers, or use old r1/r2/r3 environment scripts.
- A login-node command check is insufficient. Required binaries and shared
  libraries must be probed in the actual Slurm runtime context.
- Do not assume `/usr/bin/time` exists.
- For module-provided programs such as TShark, verify compute-node shared
  library resolution, including `libpcap`.
- Run Python compile/import tests and Bash syntax checks before submission.

### Scientific contract and validation

- Preserve fit/select/report isolation and frozen manifest hashes.
- Report-only sources must have zero fit/select/training use.
- Current events must be scored before state update; report is label-free,
  no-gradient, past-only, and source-reset.
- Validator constants must be derived from or matched to the frozen producer
  contract; stale hard-coded warm-up/schema values are forbidden.
- Duplicate record IDs across scopes must be rejected before expensive work.
- Recovery after result production must not silently retrain models or alter
  scores, gates, thresholds, or manifests.
- Validation must check the actual producer schema and output directory, not an
  obsolete directory name.

### Slurm execution and observability

- Run `sbatch --test-only` when supported.
- Size CPU, memory, and wall time from measured `TotalCPU`, `MaxRSS`, elapsed
  time, and I/O, with a stated safety margin.
- AMD and Intel copies must have partition/job-specific run directories, logs,
  checkpoints, temporary files, validation outputs, and pullback archives.
- Never auto-cancel the other partition; the user chooses. Both copies must
  remain correct if both finish, and duplicate hardware runs are not extra
  scientific seeds.
- Write a startup marker, periodic progress with completed/total units, and a
  `job_failure.txt` trap containing phase and exit code.
- A heartbeat alone is not proof of progress. Monitoring must expose CPU, I/O,
  completed units, active worker files, and stderr from the real output paths.
- Long preprocessing must checkpoint per source and resume completed sources.
- Parallelism must be bounded from measured CPU/I/O behavior; neither a serial
  bottleneck nor blind over-allocation is acceptable.

### User-facing command safety

- Commands intended for the already logged-in VS Code HPC terminal must be
  plain Bash only.
- Do not include passwords in commands or documentation.
- Submission helpers must run work in a child shell, keep the terminal open,
  and write a persistent `tee` log with an explicit exit code.
- Commands must be copy-paste complete and must not require the user to edit
  paths or placeholders.

## 4. Pre-handoff launch gate

Before giving the user upload or submission commands, the owner must record:

- branch, commit SHA, and scoped Git status;
- exact changed files;
- clean archive re-extraction and checksum result;
- LF audit result;
- Python compile/import and Bash syntax results;
- unit/contract test results;
- immutable input and installed-target simulation;
- compute-node dependency plan;
- `sbatch --test-only` result or documented cluster limitation;
- AMD/Intel resource rationale and isolated output paths;
- expected scientific CSV/JSON/Markdown outputs;
- persistent submit/status/pullback commands.

No standalone environment-only, preflight-only, audit-only, or synthetic-only
HPC job may be introduced when the requested next job is result-producing.
Necessary gates must execute locally or inside the same formal result chain.

## 5. Current CKBU monitoring lesson

The CKBU parallel-resume status display originally searched `gotham_worker`,
while the active worker output is under `parallel_source_logs`. This is an
observability defect, not by itself a scientific failure. Future status scripts
must be tested against a fixture using the exact producer directory layout.
For long PCAP extraction, cache-file count can remain unchanged while workers
are processing large sources; liveness therefore requires CPU/I/O deltas plus
per-worker progress, not cache count alone.

## 6. CKBU Gotham source-granularity failure

Observed on 2026-07-25:

- AMD job `154081` had run for approximately 17 hours with Gotham cache
  coverage still at `1/30`.
- Intel job `154082` showed the same `1/30` behavior before cancellation.
- The four active Gotham Python workers were each near 99 percent CPU, while
  their TShark children were mostly sleeping.
- No `CKBU_PARALLEL_SOURCE_COMPLETE` record or non-empty Gotham worker log had
  been produced.
- The ToN pilot was also consuming one full Python core concurrently.

Classification: `RUNTIME_FAILURE_RISK`, specifically a throughput and
checkpoint-granularity defect. It is not a compute-startup failure and it is
not scientific evidence.

Root cause:

- TShark streams packet rows correctly, but the Python causal builder consumes
  and transforms every packet sequentially.
- Four largest Gotham sources are scheduled first.
- A cache pair is committed only after an entire source and all of its PCAP
  members finish.
- There is no per-member checkpoint, packet/member progress counter, measured
  throughput estimate, or early wall-time feasibility gate.

Permanent rule: the current source-monolithic CKBU launcher must not be reused
unchanged. Any successor must, before a full formal run:

1. Measure packets/second and wall time on representative small and largest
   source members in the same compute-node runtime.
2. Refuse full dispatch when the conservative projected completion time exceeds
   70 percent of the requested wall-time.
3. Emit member start/complete and periodic decoded-packet counters.
4. Persist validated member-level checkpoints so cancellation or timeout does
   not discard completed member work.
5. Resume from validated member/source artifacts without recomputing them.
6. Separate preprocessing worker allocation from model-training allocation and
   avoid running two identical shared-filesystem decoders after one copy has
   begun productive work.
7. Compare the Python feature-builder throughput with a vectorized or compiled
   mature implementation before allocating more CPUs.

CPU consumption alone is no longer accepted as evidence that an HPC job is
making useful bounded progress.

### Enforced successor

CKBV implements the permanent rule rather than documenting it only:

- the unit of durable progress is one Gotham ZIP PCAP member;
- every non-target packet still performs the same causal state maintenance and
  update, but the 51D vector is emitted only for frozen target candidates;
- selected-event vectors are bit-exact against the original dense path in the
  regression test;
- calibration spans the member-size range, including a largest member;
- a conservative measured projection must fit the remaining allocation;
- each member/file has both wall-time and no-progress termination;
- ToN is checkpointed per eligible PCAP;
- auxiliary, ToN, Gotham, aggregation, formal training, and validation are
  sequential named phases;
- bundle code executes from a content-verified versioned payload and never
  overwrites a differing remote worktree file;
- a partial AMD/Intel submission can be safely resumed without duplicating the
  already recorded job.

The old source-monolithic CKBU launcher remains superseded and must not be
submitted again.

## 7. CKBV upstream PCAP terminal-truncation failure

Observed on 2026-07-25:

- AMD job `154440` and Intel job `154441` both reached
  `ton_file_checkpoints`, completed three of four legal ToN checkpoints, and
  failed on the same file and error signature.
- `password_normal1.pcap` yielded about 2.35 million complete packets before
  TShark exit 14 reported one packet cut short at the terminal capture tail.
- The remote file size and SHA-256 match the frozen locally downloaded file.

Classification: `RUNTIME_FAILURE`, caused by a deterministic upstream capture
tail defect rather than environment, transfer, resource exhaustion, or model
code.

Valid artifacts: 31 auxiliary caches and the `normal_1`, `normal_2`, and
`normal_scanning1` ToN checkpoints. No formal model or scientific conclusion
was produced.

Permanent gate:

1. Generic decoder failures remain fatal.
2. The exact TShark exit-14 terminal-truncation signature is accepted only
   after every preregistered target aligns and the last complete packet is
   beyond every target stop time plus matching tolerance.
3. Safe and unsafe cases are regression-tested.
4. The capture audit records observation, acceptance, reason, last decoded
   timestamp, maximum target stop, and target closure.
5. The submit helper no longer equates `sbatch` acceptance with runtime
   success. It reports `CKBV_SUBMISSION_RECORDED`, then watches the real jobs
   and prints `CKBV_RUNTIME_GATE_PASS` only after they leave the ToN real-PCAP
   phase. Immediate terminal failures print their actual status and return
   non-zero while leaving the terminal open.

Rerunning compute is necessary only for the unfinished ToN file, Gotham member
checkpoints, and formal model. Validated completed checkpoints are reused.

## 8. CKBV heterogeneous audit serialization failure

Observed on 2026-07-25:

- AMD job `154478` and Intel job `154479` completed all four legal ToN file
  checkpoints and reused all 31 auxiliary caches.
- Both then failed while finalizing
  `ckbu_ton_raw_pcap_materialization_audit.csv`.
- The exact signature was `ValueError: dict contains fields not in
  fieldnames` for fields present on attack/normal capture audits but absent
  from the first reserved-source audit row.

Classification: `RUNTIME_FAILURE`, specifically post-preprocessing metadata
serialization before Gotham dispatch. No model, score, gate, threshold, or
scientific result was produced.

Root cause: the inherited CSV helper fixed its schema from the first row,
while the frozen ToN audit intentionally combines heterogeneous role-specific
dictionaries. The data rows were valid; the serializer contract was not.

Valid artifacts: all four legal ToN file checkpoints from AMD job `154478`,
all 31 auxiliary caches, and the previously validated Gotham/auxiliary donor
artifacts. These remain cache donors only and are reused only after their
existing identity, schema, shape, raw-label, and SHA-256 validation.

Permanent gate:

1. The ToN aggregate audit uses an atomic writer whose schema is the
   deterministic union of all row keys.
2. The unit suite writes and reads heterogeneous reserved and attack audit
   rows, asserts the exact union schema, and verifies that missing cells are
   empty without dropping or shifting role-specific values.
3. The shared historical CKBU writer is not changed; only this intentionally
   heterogeneous CKBV audit uses the union-schema contract.
4. The default retry donor order starts with AMD job `154478`, so all four
   validated ToN checkpoints are reused and no ToN PCAP is decoded again.

The correction changes only audit CSV serialization and reuse routing. It does
not change rows, features, labels, target alignment, fit/select/report roles,
model, score, gate, threshold, seed, or metric. Gotham preprocessing and the
formal model still require compute.
