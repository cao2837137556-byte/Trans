# CKBR/CKBS support-v2 and mature process-frontend gate

Date: 2026-07-22

Status: candidate exact materialization complete but temporally inadmissible and quarantined; detector training not started.

## Outcome

The frozen support v1 remains unchanged:

- `support_train_view_v1`: 385 rows, SHA-256
  `6440c9ba57412149008277c0c6ab2fb9d853a3be8d77b19812b20bed59c3ed99`;
- `support_val_view_v1`: 127 rows, SHA-256
  `e9ac02ff6d3393613e67c43b7612784d6088afa9dec4eca6ab297c0a1dc427d5`;
- the formal lineage still reproduces 58 fit-side and 69 select-side validation rows.

CKBR audited a separate candidate plan for two mechanisms missing from the
original support bank:

| label | mechanism | support train | support val fit | support val select |
| --- | --- | ---: | ---: | ---: |
| TCP Scan | reconnaissance / scan | 60 | 10 | 10 |
| Telnet Brute Force | credential brute force | 60 | 10 | 10 |

The apparent combined bank would be 505 support-train rows and 167
support-val rows. Those counts are hypothetical only and must not be activated:
the 160 candidates fail the temporal-admissibility gate described below.
Active support therefore remains 385 train and 127 validation rows, with the
unchanged 58/69 fit/select lineage.

CKBS reused the vendored mature Kitsune/AfterImage `RestoredNetStat115`
frontend and the frozen ID-train state. It sequentially scanned 122,463
packets from the exact timestamp-compatible PCAP and emitted 160/160 rows with
zero missing targets, zero timestamp ambiguity, zero packet parse errors, and
finite shape `(160, 115)`. The independent validator rechecked every raw CSV
label, PCAP packet index/time, per-vector hash, query embargo, v1 hash, and
role flag without importing the generator. It passed all feature and
provenance checks, then a separate chronology check quarantined every row.

Primary artifact hashes:

- CKBR plan:
  `2807447b5aad1fa7c86d7246e4759d77cc61f0f57c3cf0910fa642c2493bac10`;
- CKBS feature contract:
  `d352881c6bc86089ec07eb86dfb271547297d966b93c130b1c0bc23eaf15d586`;
- CKBS sidecar:
  `01adf4e97b8205974019cddef89b25c7f61ae47d7a3757b542ba408366b7a08f`.

## Two corrected provenance assumptions

### 1. The old 1M exact-label index audit is invalid

`recorded_index_within_file` in the 1M sidecar is a role-local emitted-record
ordinal, not the row index of `processed/*.csv`. Issue27cb used it as a CSV
row index. Its 90,000-row exact-label inventory must not drive support-v2.

CKBR replaces that operation with a unique timestamp join:

```text
sidecar packet_timestamp_epoch
<-> processed CSV frame.time
within 2 microseconds
```

Only 28,640 TCP/Telnet rows obtain a unique timestamp match; all of them are
already inside the frozen certified query intervals. Thus none can be reused
as a non-overlapping support extension.

### 2. The label-name PCAP candidate is only a heuristic

Issue27cc named the `network-scanning` PCAP as preferred for TCP Scan/Telnet.
Its timestamps do not overlap these city-power CSV rows. The formal issue27cd
pullback actually materialized chunks 35/36 from the `mirai-infection` PCAP,
where scanning and Telnet are labeled stages of the infection process. The
actual chunk metadata/sidecar hashes are frozen in
`issue27cd_actual_vs_planned_pcap_audit.csv`.

CKBR therefore chooses a PCAP only after checking the selected rows' exact
time range. The 160 new rows map uniquely to:

```text
raw/malicious/mirai-infection/
iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap
```

This corrects provenance; it does not relabel packets by scenario directory.

### 3. Row non-overlap is not temporal admissibility

The candidate rows are outside the query row-index intervals and satisfy the
500-row embargo, but they come from the same `mirai-infection` capture after
the already frozen future/query rows:

| label | frozen query end epoch | candidate start epoch | candidate starts later by |
| --- | ---: | ---: | ---: |
| TCP Scan | 1737236386.608933 | 1737236709.220403 | 322.611 s |
| Telnet Brute Force | 1737236524.121581 | 1737236714.273319 | 190.152 s |

Training on those candidates and evaluating the earlier frozen query would be
reverse chronology. All 160 materialized rows are therefore diagnostic only:
`selection_allowed=false`, and fit/threshold/model-selection are all
fail-closed. The independent validators verify both the exact feature vectors
and this quarantine. No current Gotham row has been added to legal support.

## Data boundary

- The original strict 1M split, 26-source CKBE T0 manifest, 385/127 support
  files, and certified query chunks are not modified.
- The 160 diagnostic rows come from exact-label segments outside every
  city-power TCP/Telnet query row interval, but their later same-capture time
  makes them ineligible for training or selection.
- The proposed train/validation segments are disjoint with a 32-row local
  embargo, but this does not override the failed chronology gate.
- The source is city-power, already a development support source for other
  attack mechanisms; no report family is converted into training data.
- Stream, hydraulic, ip-camera-street, predictive-maintenance, report, and
  sealed rows have zero use.
- The entire candidate set is always removed before standardization, fit,
  negative sampling, threshold selection, or model selection. This is stricter
  than a held-family-only exclusion.
- Raw labels are read only for offline support materialization. They are not a
  model feature or report-time memory input.

## Mature process frontend gate

The next process representation should use official Zeek connection
semantics, not a handwritten flow parser. Official Zeek `Conn::Info` exposes
protocol, service, duration, direction-specific bytes/packets, connection
state, and state history. Zeek documents `ts` as the first-packet time and
emits `Conn::log_conn` when the completed record is sent to logging.

That creates a mandatory causality rule: final connection fields are not
available at `ts`. A small adapter must record an explicit log-emission
availability time (for example `network_time()` inside the logging event), and
a target at time `t` may consume only records whose availability time is
strictly earlier than `t`. Source reset, label-free report replay, no gradient,
and no threshold update remain mandatory.

Official references:

- https://docs.zeek.org/en/current/scripts/base/protocols/conn/main.zeek.html
- https://docs.zeek.org/en/current/tutorial/logs.html
- https://github.com/zeek/zeek

The local Windows checkout has no `zeek` executable. No package, environment,
or container was installed. Before implementing the adapter, the HPC login
node must be checked without submitting a job:

```bash
command -v zeek || true
zeek --version 2>/dev/null || true
module spider zeek 2>&1 | head -n 80
module avail zeek 2>&1 | head -n 80
```

If Zeek is unavailable in the existing environment/module system, stop and
choose another mature already-installed flow component. Do not replace it
with a new approximate parser and do not create an environment-only Slurm job.

## Next result route

CKBT subsequently passed a legal independent-source gate using source-disjoint
ToN-IoT Bro/Zeek scan/password rows; see
`ckbt_toniot_aux_process_support_gate_20260722.md`. The current evidence now
supports testing this asymmetric decision structure:

```text
ProcessAttack
OR PolicyAttack
OR (C1Hard AND NOT StrongNormality)
```

- `ProcessAttack` uses generic mature connection/process evidence and only a
  legally ordered training bank. The current Gotham scan/brute-force
  candidates are not part of that bank.
- `PolicyAttack` is limited to generic, preregistered Zeek state-transition
  rules such as repeated failed connections or broad destination-port scans;
  it cannot encode report-family identity.
- `StrongNormality` remains one-sided, source-held-out, and fail-closed: weak,
  cold, or non-transferable normal evidence cannot suppress C1.

This route must still be tested by one seed-27 result job. CKBR/CKBS prove that
the current Gotham archive cannot legally supply the missing mechanisms under
the frozen chronology; they do not prove OOD or attack improvement.

```text
solved: exact TCP-Scan/Telnet candidate provenance and features are audited; all 160 rows are quarantined for same-capture reverse chronology.
changed_mainline: yes; legacy index labels, label-name PCAP pairing, and row-embargo-only admissibility are rejected.
active_blocker: no Gotham emission-time Zeek cache or trained asymmetric process result exists yet.
frozen: strict 1M/T0/query assets, v1 support hashes, report/sealed zero use, review=0, and seed27-first policy.
superseded: reusing issue27cb exact-label counts, forcing PCAP by directory name, or adding later same-capture rows to support.
next_action: use the CKBT legal auxiliary bank, verify existing Zeek availability, and implement one emission-time-aware seed-27 result chain; no standalone audit job.
```
