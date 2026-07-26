# CKBV Bounded Compute-Node Stall Probe (Design)

Date: 2026-07-26
Scope: diagnostic execution of failure-ledger section 10. This probe writes no
science artifact, cache, checkpoint, model, threshold, or metric. It exists to
discharge permanent gate item 1 of ledger section 10 before any r9
resubmission.

## Why a compute-node job

Login-node scanning of multi-GB PCAPs is not permitted, and the probe must use
the exact formal runtime: `scripts/00_env_issue27ckc.sh`, `module load
apps/tshark/4.6.6`, the shared `libpcap.so.1` at the validated
`LD_LIBRARY_PATH`, the frozen Gotham ZIP, and the byte-identical frozen
frontend module from the installed r8 payload (`CKBV_FROZEN_CODE_ROOT`).
No pip/conda/container/new environment is used.

## Files

- `repo/ood/issue27ckbv_stall_probe_driver_v1.py` — probe driver. Modes:
  `selftest` (asserts P0 subset P1 subset P2 subset P3 = P4 = production
  `TSHARK_FIELDS`), `fieldargs` (single source of truth for probe field
  lists), `producer` (drives the formal `iter_tshark_rows` ZIP-producer ->
  TShark stdin path with an in-loop deadline; exits 124 via `os._exit` on
  stall so a blocked `process.wait()` cannot deadlock the probe), and
  `summarize` (aggregates `probe_matrix.csv` into `probe_verdict.json`).
- `scripts/issue27ckbv_stall_probe.slurm` — the bounded matrix job.
- `scripts/issue27ckbv_stall_probe_submit_dual.sh` — dual AMD/Intel
  submission with login-node static checks, duplicate-submission guard, and
  `sbatch --test-only` validation first.

## Diagnostic matrix

Member: `raw/malicious/mirai-dos/iotsim-building-monitor-1_0-0_to_OpenvSwitch-28_1-0.pcap`
(5,354,325 packets; observed wall at decoded 2,375,000). Stall limit
2,450,000 crosses the wall by three progress buckets.

| Probe | Input path | Fields | Limit | Timeout |
| --- | --- | --- | --- | --- |
| A_producer_P4 | formal Python ZIP producer -> stdin | P4 | 2.45M | 1500 s |
| B_stdinpipe_P4 | unzip -p (or cat) -> stdin | P4 | 2.45M | 1500 s |
| C_file_P4 | pre-extracted file | P4 | 2.45M | 1500 s |
| C_file_P0 | file | frame/IP/ports/flags | 2.45M | 900 s |
| C_file_P1 | file | P0 + tcp/udp stream + tcp timing | 2.45M | 900 s |
| C_file_P2 | file | P1 + tcp.connection.syn | 2.45M | 900 s |
| C_file_P4_no_&lt;pref&gt; | file | P4 + `-o <pref>:FALSE` | 2.45M | 900 s |
| DEPTH_FULL_P0 | file | P0 | full member | 1500 s |
| DEPTH_3M_no_&lt;pref&gt; | file | P4 + pref off | 3.0M | 1500 s |
| DEPTH_FULL_no_&lt;pref&gt; | file | P4 + pref off | full member | 3600 s |

Preference variants are generated only for names that actually exist in this
TShark build, discovered at runtime via `tshark -G defaultprefs` filtered on
`^#?tcp\.(analyze|desegment|track|relative)`; nothing is hardcoded from
memory. Candidates checked: `tcp.analyze_sequence_numbers`,
`tcp.desegment_tcp_streams`, `tcp.track_bytes_in_flight`. Note
`tcp.desegment_tcp_streams:FALSE` disables only upper-layer reassembly, not
sequence analysis, so it can never be the sole basis for attribution.

P3 (P2 + `tcp.analysis.retransmission`/`tcp.analysis.lost_segment`) is
set-identical to the full production list P4; `selftest` asserts this, so the
matrix runs P4 once instead of twice.

## Interpretation rules

- A stalls, B and C complete: producer-pipeline defect (Python feed thread /
  stdin path).
- A, B, C all stall: TShark-internal stall; the field-group escalation then
  localizes the triggering field group, and the preference variants identify
  a mitigation candidate.
- All complete: stall not reproduced under probe conditions; escalate to a
  review of scheduler/storage interaction before any resubmission.
- Upstream `141` (SIGPIPE) with `-c` is the designed early-stop consequence
  and is recorded, never treated as failure.
- Every probe records rows, elapsed, exit codes, and MaxRSS
  (`/usr/bin/time -v`); depth probes must clear at least 3.0M packets and one
  passing configuration must clear the full member to give the real
  post-mitigation throughput for the ledger gate item 3 projection.

The probe job itself succeeds when the matrix completes; observed stalls are
data. Worst-case matrix time is under 4.5 h against a 6 h wall limit; typical
completion is far faster because passing probes finish in minutes.

## Isolation

Run root `runs/issue27ckbv_stall_probe_<partition>_<jobid>` refuses to reuse
an existing directory, never touches formal run roots, donors, or caches, and
the 2.2 GB extracted `member.pcap` lives inside the probe run root only. Both
partitions read the frozen ZIP concurrently read-only. Leftover TShark
processes are reaped between probes inside the job's own node allocation.

## Recorded observation for the r9 fix round

The r8 runs `154620` (AMD) and `154621` (Intel) each committed additional
Gotham member checkpoints (46 NPZ files per run root) before the stall; the
r9 resume donor list (`CKBV_REUSE_RUN_ROOTS`) must be extended to include
them ahead of the older donors so completed member work is not repeated.
