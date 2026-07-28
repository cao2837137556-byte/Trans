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
5. The upload bundle contains and hashes the complete local Python dependency
   closure used by the four primary scripts. The builder runs Python compile
   and all four contract suites from a clean extraction with only the bundled
   module directory on `PYTHONPATH`; remote worktree code cannot silently
   satisfy a missing payload dependency.
6. That dependency closure includes the exact mature AfterImage frontend and
   the frozen MiniRocket and TabM vendor sources at their repository-relative
   paths, including license/provenance files.
7. The builder creates only a temporary candidate archive before clean-extract
   verification. It publishes the final archive and hash only after checksum,
   LF, import, compile, all four contract-suite, and forbidden-artifact checks
   pass. A failed local build therefore cannot be mistaken for an uploadable
   bundle.

The correction changes only audit CSV serialization and reuse routing. It does
not change rows, features, labels, target alignment, fit/select/report roles,
model, score, gate, threshold, seed, or metric. Gotham preprocessing and the
formal model still require compute.

## 9. CKBV log-only watchdog observability failure

Observed on 2026-07-26:

- AMD job `154606` and Intel job `154607` independently reached
  `gotham_member_checkpoints`.
- Both reused all 31 auxiliary caches and all four legal ToN file checkpoints,
  and each committed six valid Gotham member checkpoints.
- Both failed after about 44 minutes on the same two large archive members with
  `member progress stale for 900s`.
- At failure, MaxRSS was about 12.6 GiB on AMD and 11.0 GiB on Intel, below the
  16 GiB request. Neither job reached formal training or produced scientific
  metrics.

Classification: `RUNTIME_FAILURE`, specifically
`WATCHDOG_UNOBSERVABLE_STATE`, with a secondary
`CONCURRENCY_PRESSURE_RISK`. The parent treated any unchanged log size as
proof of no work. The retained evidence cannot distinguish a live decoder,
Python GC/I/O delay, checkpoint finalization, and a genuinely stalled child.
Therefore it would be unjustified to label the event either a proven deadlock
or a proven false positive. The deterministic cross-partition signature
invalidates the old 900-second rule; it is not a scientific no-go.

Valid artifacts: the six member checkpoints from each run, all 31 auxiliary
caches, and all four ToN file checkpoints. Reuse remains conditional on the
existing member/source identity, schema, raw-label, plan-hash, NPZ shape, and
payload-hash validators. AMD `154606` is the first donor and Intel `154607` is
an independent fallback donor.

Permanent gate:

1. Every member child atomically publishes a typed progress state containing
   member identity, process ID, phase, decoded-event count, emit count,
   heartbeat sequence, and progress revision.
2. Parent supervision separates three limits: five minutes without a child
   heartbeat, one hour without decoded-count or phase progress, and four hours
   total member time. Log size is not a liveness signal.
3. Phase transitions such as target loading, scanning, alignment validation,
   atomic checkpoint writing, and completion count as real bounded progress;
   repeating heartbeats alone do not reset the one-hour progress limit.
4. Unit tests prove that a live quiet worker is retained, a missing heartbeat
   is rejected, a live but non-progressing worker is rejected, real progress
   resets the timer, and foreign progress-state files are rejected.
5. Gotham extraction defaults to two workers. This is based on the observed
   10.9--12.6 GiB four-worker MaxRSS and reduces memory/I/O contention while
   remaining within the measured 8-CPU, 16-GiB allocation.
6. The next run resumes validated checkpoints and does not repeat completed
   auxiliary, ToN, or Gotham member work.

The correction changes only execution supervision, concurrency, and reuse
routing. It does not change the 51D schema, target rows, labels, fit/select/
report roles, model, score, gate, threshold, seed, metrics, or review policy.

## 10. CKBV data-driven Gotham member decode stall

Observed on 2026-07-26:

- AMD job `154620` and Intel job `154621` (bundle r8, commit `5bc53b8`)
  resumed all donated caches, entered `gotham_member_checkpoints`, and both
  failed with the new watchdog reason `real_progress_stale`.
- Both partitions froze on the same member
  `raw/malicious/mirai-dos/iotsim-building-monitor-1_0-0_to_OpenvSwitch-28_1-0.pcap`
  (member index 0006, member log `0006_a44258a2b0e386d0ac15`, the first member
  after the six donated checkpoints) at the identical progress boundary
  `decoded_events=2375000` with a live heartbeat (ages 0.0 s and 5.0 s) and
  `real_progress_age` just over 3600 s.
- Member elapsed minus stale age places the stop about 185 s into the member
  after a sustained rate of roughly 12.8k packets/s. The stop is abrupt, not a
  gradual slowdown.

Local forensic evidence (full record walk of the member inside the frozen
local ZIP, 2026-07-26):

- The member holds 5,354,325 packets (2.207 GB expanded); no truncated tail,
  no malformed record, zero IP fragments; snaplen 65535, linktype EN10MB.
- Packet composition changes exactly at the 2,375,000 boundary: before it a
  single-pair UDP flood (67-byte packets, 192.168.17.10 to 192.168.18.10,
  about 89k packets/s of capture time); the transition bucket contains a
  54.4 s capture-time gap; after it a single-pair TCP flood with an RST storm
  (3k--7k RST per 25k packets) continues to the end of the member (about 3.0M
  packets). Roughly 1.5M GRE (protocol 47) packets appear earlier in the
  member.
- The four largest files in the entire frozen ZIP are the four mirai-dos
  members (3.54/2.60/2.25/2.21 GB). The section 9 failure on "the same two
  large archive members" is consistent with the same wall on two of them.

Classification: `RUNTIME_FAILURE`, specifically `DATA_DRIVEN_DECODE_STALL`.
The watchdog decision was correct: the typed progress state now proves a live
child without real progress, which is exactly the evidence section 9 lacked.
Four independent jobs across two rounds and two partitions stopped at the
same packet boundary, so the stall is a deterministic property of the member
content interacting with the decode path. The prime suspect is TShark
stateful TCP tracking (the frozen field set requires `tcp.stream` and
`tcp.analysis.*`, which force per-stream sequence analysis) applied to
single-pair flood traffic. The Python target matcher is excluded because
candidate lookup is a microsecond-exact dictionary probe and the UDP flood
phase sustained full throughput under identical single-flow pressure. Raising
watchdog limits again cannot fix this: the remaining ~3.0M flood packets at
under 7 packets/s would take days for this member alone.

Valid artifacts: unchanged donors from sections 7--9 plus any additional
member checkpoints committed by `154620`/`154621` before failure (inventory
pending pull-back). No formal model or scientific metric was produced.

Permanent gate:

1. Do not resubmit until bounded probes on the stalling member (control
   range, stall range, stateless field set, candidate mitigation) identify
   the stalling layer and demonstrate a mitigation that passes the stall
   window at production throughput.
2. Any decode-path change must preserve the frozen 51D contract: bit-exact
   target-row equivalence against the current path on unaffected ranges, and
   a preregistered documented equivalence argument for affected ranges,
   before any formal run consumes it.
3. Full-dispatch throughput projection must include a measured
   post-mitigation rate for the mirai-dos members specifically, not only the
   generic small/medium/large member classes.

This section records a diagnosis and a gate only; no science-facing row,
feature, label, role, model, threshold, seed, or metric changed.

### Update 2026-07-26: probe result and confirmed root cause

The bounded compute-node probe (commit `1532332`, AMD job `154681`, node186,
19m35s, exit 0) ran the full twelve-probe matrix. Every probe COMPLETED:

- The formal Python ZIP-producer path (`A_producer_P4`) decoded 2,450,000
  packets in 76 s; the stdin-pipe and pre-extracted-file paths matched.
- The full member (5,354,325 packets) decoded end to end in 176-182 s across
  the field-group and preference variants.
- Verdict: `no_stall_reproduced`; `first_stalling_field_group=null`.

This falsifies the prime suspect recorded above. TShark 4.6.6 and the
producer pipeline decode this member, with the full production field set,
in under three minutes. The stall is not in decoding.

The probe isolates the stall to the only layer it did not exercise: the
Python causal state machine that runs after row iteration
(`event_from_tshark` -> `matcher_candidates` -> `emit`/`prune_before_update`
-> `update`). A local reproduction on the real member (frozen ZIP, frozen
`CausalFeatureBuilder`) confirms the mechanism:

- Single `emit()` cost scales linearly with retained state:
  0.92 s at 2,379,429 endpoint records, 0.38 s at 904,726, 0.31 s at 549,228.
- The cost is the per-call full scans inside `emit()`:
  `source_rates` sums over the entire `source_times` deque once per window,
  and `unique_peers`/`unique_ports` rebuild a list and set over the entire
  `endpoint.recent` deque once per window (`WINDOWS_SECONDS = (1, 10, 60)`).
- The flood after packet 2,375,000 is a random-source-port TCP/ACK flood
  (measured: 42,548 distinct 4-tuples and 62,428 distinct source ports per
  50k packets, zero SYN) at about 83k packets/s, so the 60 s window retains
  several million records and every `emit()` becomes an O(N) scan of that
  state. `prune_before_update` on non-candidate packets stays amortized O(1),
  which is why the UDP single-flow prefix and the probe (no builder) are fast.
- The frozen targets for this member fall inside the flood window, so
  candidate hits are dense there; each hit triggers one O(N) `emit()` of a
  few seconds, and a single 25,000-packet progress bucket accumulates enough
  of them to exceed the 3,600 s real-progress watchdog. `sparse_feature_emits`
  freezing at 12,167 with `decoded_events` frozen at 2,375,000 is consistent
  with the process being inside `emit()` calls after the last published
  bucket.

Classification refinement: the section 10 class `DATA_DRIVEN_DECODE_STALL`
is superseded by `DATA_DRIVEN_FEATURE_SCAN_STALL`. The watchdog decision
remains correct. The fix is an execution-performance change to `emit()` /
state maintenance (incremental sliding-window statistics reducing per-emit
cost from O(N) to amortized O(1)) that must be proven bit-exact against the
current path on all frozen target rows before any formal run consumes it; it
does not change the 51D schema, target rows, labels, roles, model, threshold,
seed, or metric. The permanent gate items from section 10 stand; gate item 1
is now discharged (the stalling layer is identified) and gate item 2
(bit-exact equivalence) governs the fix.

### Correction record (2026-07-26, same day): bit-exact fast path landed

Correction (execution-only, commit 69cdc42): `FastCausalState` in the CKBV
script maintains numpy ring mirrors of exactly the entries the frozen deques
hold and evaluates the same window predicates in the same operand order; the
frozen frontend module stays byte-identical
(`eca60311b0fe6a0eeea06abc83ef386a398e8519444b378624a1ed46928c38c9`). Only
the Gotham member scanning loop switches to the fast path; ToN paths and the
frozen reference helper are unchanged.

Evidence:

1. Unit suite: adversarial bit-exact streams (single-pair UDP flood, 54.4 s
   capture gap, random-port ACK/RST flood, timestamp inversions, port 0, the
   FIFO-prune quirk where a young head shields an expired deeper entry) plus
   mirror-synchronization invariants against the frozen deques.
2. Real-member parallel validation (frozen local ZIP, first 2,450,000
   packets, frozen and fast instances fed identically): 27 sampled emit
   positions including deep flood state, zero mismatches; frozen emit
   0.31-0.66 s versus fast emit 15-31 ms at identical positions.

Gate discharge for section 10: item 1 discharged by the probe matrix plus
local reproduction; item 2 discharged because the fast path is an exact
reimplementation of the frozen semantics enforced by the tests above; item 3
discharged because the size-range calibration already measures the largest
member (a mirai-dos capture) with the fast path in effect and the unchanged
300/3600/14400 member watchdog remains the backstop.

The r9 default resume donor order becomes `154620`, `154621`, `154606`,
`154607`, `154478`, `154440`, `154081` in both the installer and the
Slurm script, and the bundle clean-extract gate now asserts the r8 donors in
both files so the lists cannot drift apart again. Details:
`runs/mainline_docs/ckbv_r9_fast_emit_recovery_20260726.md`. No row,
feature, label, target, role, model, threshold, seed, or metric changed.

## 11. CKBV first aggregation-stage target-coverage failure (data structure)

Observed on 2026-07-26 (r9, AMD job `154695`, commit `94f3c73`):

- **The emit fix succeeded.** All mirai-dos giant members decoded to
  completion: `iotsim-building-monitor-1...` decoded 5,354,325 in 429 s
  (36,358 sparse emits); `city-power` and `domotic-monitor` also
  `CKBV_MEMBER_SCAN_COMPLETE`. The 2,375,000 wall that killed rounds 1-4 is
  broken. This is the first run ever to finish Gotham member checkpointing
  and enter source aggregation.
- The job then failed in `aggregate_one_source`
  (`issue27ckbv_checkpointed_sparse_process_frontend_v1.py:937`) with
  `incomplete member target coverage for processed/iotsim-hydraulic-system-1.csv:
  missing=[50, 52, 55, 58, 61, 64, 66, 69] extra=[]`.
  `sacct` State=FAILED, ExitCode 1:0, Elapsed 01:25:16.

Classification: `RUNTIME_FAILURE`, subclass
`FROZEN_TARGET_MEMBER_PAIRING_INCONSISTENCY`. Not caused by the emit fix:
target matching uses only timestamp (+/-2 us), frame length, and 5-tuple from
the raw packet, all independent of the emitted feature vector. This is a
latent inconsistency in the frozen data plan, exposed for the first time
because no prior round reached aggregation, and because CKBQ used a different
(MiniRocket) frontend that does not use this per-member raw-pcap alignment.

Verified root cause (local forensic against the frozen ZIP, 2026-07-26):

- The source pairs with exactly one raw pcap member,
  `raw/benign/iotsim-hydraulic-system-1_0-0_to_OpenvSwitch-15_1-0.pcap`
  (pairing rule "exact_complete_source_stem...", one candidate member).
- The missing targets reference host `192.168.20.44 -> 192.168.0.4:8883`
  (MQTT). That host, and the whole `.40-.44` cluster, has **zero packets** in
  the paired pcap, which instead contains `192.168.20.10-30`, `192.168.4.x`,
  `192.168.0.2-3`.
- Quantified: of 17,432 IP-bearing rows in the processed CSV, **14,926
  (85.6%)** reference an IP absent from the paired pcap. The Gotham processed
  CSV aggregates a multi-device vantage point (`192.168.20.10-44` to the
  broker), while each raw pcap captures a single switch link. The certified
  target selection (1353 targets) drew from the processed CSV; most targets
  are on-link and matchable, but a minority reference off-link hosts and are
  unmatchable in the single paired member.

Scientific-decision required (do NOT patch unilaterally; this changes the
metric denominator / frozen target set):

- Option A (re-pair): materialize each source against every raw pcap whose
  hosts its targets reference. The off-link traffic is scattered across other
  devices' pcaps and the processed vantage point maps to no single raw file,
  so this is a non-trivial plan redesign.
- Option B (preregistered exclusion): exclude targets unmatchable in their
  paired member, with a full per-source audit and count, documented as a
  known alignment limitation. Requires the total unmatchable count across all
  30 sources first, to confirm it does not bias metrics.
- Option C (re-select targets): restrict the certified target set to
  on-link-matchable targets. Cleanest scientifically, largest change.

Required before any decision: a local full-scope sweep counting unmatchable
targets across all 30 Gotham sources (feasible offline from the frozen ZIP
without HPC). Coordinate with the original pipeline author (Codex) because
the target set and pairing rule are frozen artifacts.

Permanent gate:

1. Do not resubmit the formal run until the target/member coverage
   inconsistency is resolved by a preregistered rule (A, B, or C) with an
   audit, so aggregation cannot fail mid-run on frozen-data structure.
2. Any target-set change is preregistered with per-source unmatchable counts
   and an argument that metrics are not biased.
3. Add a pre-materialization validator that, for each source, checks target
   fingerprints against the paired member's host set and reports the
   unmatchable count up front, instead of failing only at aggregation after
   hours of compute.

### Section 11 full-scope sweep (2026-07-26, same day)

Local sweep over all 26 base-T0 sources (34,622 targets from
`canonical_source_target_index.csv`), counting targets whose processed-CSV
`ip.src`/`ip.dst` is absent from the union of the source's paired raw pcap
members' host sets:

- **Total unmatchable: 1,353 of 34,622 (3.91%).**
- **Concentrated entirely in one source, `iotsim-hydraulic-system-1`, which
  is 100% unmatchable (1,353/1,353).** All other 25 base sources are exactly
  0% unmatchable, including multi-member sources (city-power 5 members,
  combined-cycle 6, domotic 5, ip-camera-museum 5) and the other seven
  hydraulic-system sources (`-2,-10,-11,-12,-13,-14,-15`), which are clean.

This reclassifies the problem from a systemic granularity mismatch to a
single mispaired source. `hydraulic-system-1` is paired with
`..._to_OpenvSwitch-15_1-0.pcap`, whose hosts are `192.168.20.10-30`, while
its processed CSV targets live on `192.168.20.40-44 -> 192.168.0.4:8883`.
The held-OOD hydraulic-system family evaluation uses other hydraulic sources
and is unaffected.

Caveat: the 290,445 report-extension targets (4 sources) were not in this
sweep because `report_extension_recorded_targets.csv` was not at the expected
local path; those must be swept on HPC or after the path is restored. The
base-T0 result is nonetheless decisive for `hydraulic-system-1`.

Given the isolation, the choice narrows to:

- Option B (preregistered exclusion): drop the single mispaired source
  `hydraulic-system-1` (3.91% of base targets, no held/eval source involved),
  with the per-source audit above. Cleanest and fastest to a rerun.
- Option A (re-pair): fix only this one source by pairing it with the pcap(s)
  actually carrying `192.168.20.40-44`, preserving all 1,353 targets. Small,
  localized, no global plan redesign.

Either way the pre-materialization coverage validator (permanent gate item 3)
should be added so a mispaired source fails fast up front, not after hours.

### Section 11 full TShark-rule audit and a critical self-correction (2026-07-26)

Per Codex's mandate, a read-only full-scope audit reproduced the frozen
matching rule (`TargetMatcher.compatible` + time key in [t-2, t+2] us) over
all 325,067 frozen targets against all 110 pcap members in a single hashed
pass. Artifacts under
`runs/raw51_target_pcap_alignment_audit_2026-07-26_local/`:
`alignment_target_audit.csv`, `alignment_source_summary.csv`,
`alignment_role_family_summary.csv`, `alignment_member_summary.csv`,
`alignment_decision_inputs.json`, `alignment_scan.py`.

Raw classification (reconciled to 325,067):
`exact_member_unique=295,209`, `non_exact_member_unique=1,353`,
`absent_from_all_pcaps=28,505`, ambiguous/multiple/malformed=0.

**These raw counts are NOT decision-grade. The local audit parses pcap bytes
directly instead of via TShark, and a confirmed systematic bias inflates the
absent count for attack-role targets:**

- Sampled absent building-monitor-1 targets have fingerprints like
  `proto=1 (ICMP), tcp.srcport=43432 -> tcp.dstport=23, frame_len=82`. ICMP
  has no ports; TShark fills these from the ORIGINAL packet header embedded
  in the ICMP error message (`-E occurrence=f` still yields the embedded L4
  ports). The local byte parser does not extract L4 ports from ICMP payloads,
  so the 5-tuple mismatches and the target is misfiled as absent.
- Confirmed empirically: the referenced len=82 ICMP packets between
  `192.168.16.12` and `192.168.17.10` at the target's second exist (9 of
  them, all len=82) in the paired mirai-infection pcap. The packets ARE
  present; only the local parser cannot reproduce TShark's embedded-port
  extraction. GRE-tunneled attack traffic (this dataset carries ~1.5M GRE
  packets in mirai-dos captures) is a second likely inflator.
- Consequence: the alarming role-level absent counts (support_train 66,
  support_val 10, sealed_final_attack 15,340, future_query 13,040) are
  substantially local-parser artifacts and must NOT trigger a data-contract
  rebuild. The real TShark-based absent count is unknown and likely far
  smaller.

What the local audit DOES establish reliably:

1. The pipeline and parser match 295,209 clean TCP/UDP targets exactly, so
   the method works for the common case.
2. `hydraulic-system-1` (1,353 targets, clean TCP MQTT to `192.168.0.4:8883`)
   is a GENUINE benign source->pcap mispairing, not an artifact: its targets
   are `non_exact_member_unique`, found in sibling pcaps
   `iotsim-hydraulic-system-15_..._OpenvSwitch-16_5-0.pcap` (867) and
   `iotsim-hydraulic-system-10_..._OpenvSwitch-15_10-0.pcap` (486). Benign
   TCP, no ICMP/GRE extraction involved, so this conclusion stands.

Corrected decision status:

- Do NOT choose A/B/C or rebuild the data contract on the local absent
  numbers; they are biased.
- The authoritative coverage was ALREADY computed by r9 (`154695`) using
  TShark during member checkpointing for every base-T0 source; only the
  hydraulic-1 aggregation raised. The cheapest decision-grade audit is a
  read-only pass that reports per-source TShark coverage over the existing r9
  member checkpoints (no re-decode), or a TShark-based re-run of this audit
  script's matching. Recommended before any A/B/C choice.
- `hydraulic-system-1` re-pairing (option A for this one source) carries the
  state-semantics caveat Codex raised: sibling pcaps are different capture
  links, so which observation unit accumulates 51D causal state, and how
  multiple members merge/reset, is a frontend-contract question, not a plain
  member-list edit.

This section records diagnosis, artifacts, and a self-correction only; no
science-facing row, feature, label, role, model, threshold, seed, or metric
was changed.

### Section 11 authoritative TShark coverage (2026-07-26, late)

Read-only review of the r9 (`154695`) TShark member checkpoints
(`ckbv_tshark_coverage_review.csv` in the run root):

- **28 of 30 sources: 100% coverage.** Every target my local parser had
  misfiled as absent — including all ICMP-embedded-port and GRE attack
  targets (building-monitor-1 101,282/101,282; ip-camera-street-1
  110,104/110,104; museum-2 54,950/54,950) — was matched by the formal
  TShark path. The parser-artifact self-correction is confirmed against
  TShark ground truth.
- `iotsim-air-quality-1` shows 24,109 "missing" **only because its four
  member checkpoints do not exist**: that source is served by the
  source-level cache donated by job `154081` (the long-standing "1/30
  Gotham source cache" donor), which the member-level review script did not
  read. Verification against `gotham_causal_cache` issued; expected 24,109
  rows.
- `iotsim-hydraulic-system-1`: 1,353 missing — the only genuine gap,
  consistent with the local audit's mispairing finding.

Role decomposition of the 1,353 (from the frozen canonical index, joined
after matching): **all 1,353 are `roles=ood_val`, `stages=fit`.** Zero
`support_train`, zero `support_val`, zero report/sealed/held rows. The
support bank (385/69) and every paper-metric denominator are untouched;
the loss is development-phase benign-OOD validation rows (8,682 -> 7,329).

Air-quality-1 confirmation (2026-07-26, executed on HPC): the donated
source-level cache `gotham_causal_cache/d739aac3260e66f35d25.npz` exists and
holds exactly **24,109 matched targets with features (24109, 51)** — full
coverage. The authoritative totals are therefore FINAL:
**1,353 / 325,067 = 0.4163% overall unmatchable** (within the pre-declared
0.5% overall gate), 29/30 sources at 100%, with 100% concentration in the
single mispaired benign source (per-source gate exceeded, fully explained;
packets exist in sibling captures).

Proposed handling (draft for the original author's ruling, see
`runs/mainline_docs/raw51_observable_v1_mask_prereg_draft_20260726.md`):
a derived `raw51_observable_v1` eligibility mask excluding exactly these
1,353 rows for all raw-51D consumers, all compared systems on the identical
intersection, both denominators reported; no frozen manifest overwritten.
Re-pairing (option A) is not recommended now: it would introduce a
multi-capture observation-unit contract (merge/dedup/reset semantics) for
the sake of 1,353 development-only rows.

## Section 12: CKBV formal-stage handoff rejection (2026-07-27)

Affected jobs: AMD `154761`, Intel `154762`.

Observed boundary:

- real CKBV member/checkpoint processing ran successfully;
- an earlier AMD `154761` live snapshot showed 58/62 Gotham member
  checkpoints, 25/30 Gotham source caches, 31/31 auxiliary caches, and 4/4
  ToN file caches; it subsequently entered `formal_seed27_model`, proving
  that the required pre-formal readiness and aggregation gates completed;
- entry to `formal_seed27_model` failed with
  `refusing mixed CKBU output directory`;
- the rejected names (`member_logs`,
  `ckbv_gotham_checkpoint_ready.json`,
  `ckbv_source_aggregation_audit.csv`, `ton_file_cache`,
  `ckbv_throughput_projection.json`) are legitimate products of the current
  CKBV launcher.

Classification: **stage-handoff/metadata contract failure**. It is not a
scientific NO_GO and not a raw-data, TShark, model, memory, or scheduler
failure.

Root cause: the formal program retained a stale CKBU-only output-directory
whitelist while CKBV intentionally runs validated preprocessing and formal
scoring in the same new partition/job-isolated root.

Permanent repair and regression gate:

1. Preserve a fail-closed, exact list of legal pre-formal files and
   directories, including expected path types.
2. Contract-unit materializes the complete legal staged run root and must
   accept it.
3. The same test adds an unknown partial-science CSV and a wrong-type
   checkpoint path; both must be rejected.
4. Clean-extract bundle validation requires those tests/tokens before an
   archive can be published.
5. AMD `154761` is the first reuse donor. New jobs make no blanket assumption
   that every donor file is valid: they reuse only source/member/file
   checkpoint pairs accepted by the existing schema, coverage, identity, and
   hash validators, and never write into the failed run root.

Accepted retry path: a new partition/job-isolated r14 run using `154761` as
the first donor, then earlier validated donors as fallbacks.

Rejected retry paths:

- rerunning formal in the failed `154761`/`154762` root;
- deleting the mixed-directory guard;
- allowing arbitrary existing files;
- re-decoding all raw PCAPs without first attempting validated checkpoint
  reuse;
- changing features, target rows, mask, roles, thresholds, model, seed, or
  decision rules to repair this operational failure.

## Section 13: CKBV r14 frozen formal dependency omission (2026-07-28)

Affected jobs: AMD `154875`, Intel `154876`.

Observed boundary:

- both jobs reused validated preprocessing and entered
  `phase=formal_seed27_model`;
- AMD failed after `00:01:49` and Intel after `00:02:04`, both with
  `ExitCode=1:0`;
- `issue27ckc.validate_inputs()` rejected four missing immutable inputs under
  the bundle-local `payload/runs/` root:
  `support_bank_sidecar.csv`, `certified_chunk_manifest.csv`,
  `certified_attack_subset_v1.json`, and
  `unified_two_head_selection_audit.csv`;
- no model result or scientific GO/NO_GO was produced.

Classification: **package/transfer dependency-closure failure**. This is not a
data-alignment, TShark, checkpoint, model, scheduler, memory, or scientific
failure. Reaching the formal phase in roughly two minutes also confirms that
the r13-to-r14 formal handoff repair and validated checkpoint reuse worked.

Root cause:

`issue27ckbv_build_bundle.ps1` staged the Python import chain but omitted four
frozen data artifacts reached through
`issue27ckbu -> issue27ckbq -> issue27cko -> issue27ckc`. The existing local
contract-unit tested formal logic and stage handoff but did not prove the full
runtime dependency closure of the clean extracted payload.

Permanent repair and regression gate:

1. Name the exact four paths in the bundle manifest, installer input check, and
   compute-node input check.
2. Bind their canonical UTF-8/LF SHA-256 values in the formal program. This
   matches the bundle builder's intentional CRLF-to-LF normalization and avoids
   treating platform line endings as scientific changes.
3. Invoke the same closure validator in local contract-unit, clean-extract
   contract-unit, installer regression checks, and the compute-node formal
   process before model setup.
4. In clean extraction, deliberately remove one dependency and require
   contract-unit to fail with the dependency-closure signature; restore it and
   require the same contract to pass again.
5. Keep all four artifacts read-only and covered by bundle `SHA256SUMS`.

Accepted retry path: a new r15 partition/job-isolated run using only validated
checkpoint donors. No PCAP re-decoding is required.

Rejected retry paths:

- ad hoc copying the four files into an already extracted r14 directory;
- weakening `issue27ckc.validate_inputs()` or changing any input hash;
- rerunning in either failed r14 output root;
- changing features, target rows, roles, masks, thresholds, model, seed, or
  decision rules;
- recomputing valid raw-PCAP checkpoints for a packaging-only failure.
