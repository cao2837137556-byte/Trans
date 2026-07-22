# CKBT ToN-IoT auxiliary process-support gate

Date: 2026-07-22

Status: local data gate PASS; static process expert not yet trained.

## Outcome

CKBT reuses the dataset-provided Bro/Zeek 21-field `conn.log` representation
and the existing CKAN loader policy. It does not modify the frozen Gotham
support bank. The active Gotham counts remain 385 train and 127 validation
rows (58 fit-side, 69 select-side).

A separate cross-dataset process-supervision candidate bank is now frozen:

| mechanism | role | conn-log/GroundTruth file pair | exact joined | frozen rows |
| --- | --- | --- | ---: | ---: |
| reconnaissance scan | fit | `normal_scanning_1` + GroundTruth 1 | 9,511 | 2,000 |
| reconnaissance scan | select | `normal_scanning2` + GroundTruth 2 | 7,946 | 500 |
| credential brute force | fit | `password_normal_1` + GroundTruth 14 | 5,561 | 2,000 |
| credential brute force | select | `password_normal4` + GroundTruth 15 | 8,064 | 500 |

Every frozen row has a unique direct match on:

```text
floor(conn.ts), src_ip, src_port, dst_ip, dst_port, proto
```

The independent validator rescanned all four complete conn logs and all four
million-row GroundTruth files, reproduced each selected raw line and feature,
confirmed one-to-one key/label matches, and regenerated source-local anonymous
node IDs. All checks passed.

Primary hashes:

- auxiliary candidate manifest:
  `c637e1e50d86252a590c216c286f53411b83facb60f44be3989afbab1b032fcb`;
- contract:
  `9ec01f6df760cdf9bc35836dc049e03e359780bf16278daf7a2466b4904f8940`.

## Data roles

- Fit and select use different ToN conn-log/GroundTruth file pairs. This is
  source-file separation, not a claim that the campaigns or hosts are fully
  independent.
- Seven additional scan/password conn files have zero use and remain internal
  reserve sources. Because the ToN route has already been inspected during
  development, they are not described as an untouched final test.
- ToN labels map only to generic mechanisms (`reconnaissance_scan` and
  `credential_bruteforce`). They are not claimed to equal Gotham `TCP Scan`
  or `Telnet Brute Force` labels.
- ToN rows cannot enter Gotham C1 fit/calibration, Gotham normalization,
  threshold selection, or any report/sealed role.
- Stream, hydraulic, ip-camera-street, predictive-maintenance, and all Gotham
  report/sealed rows have zero use.

## Causality limitation

The provided ToN `conn.log` records contain mature completed-connection fields
such as duration, byte/packet counters, state, and history, but do not contain
an explicit log-emission availability timestamp. CKBT therefore allows them
only for static completed-connection supervision. They are forbidden for
temporal replay, past-only memory claims, or event-order self-supervision.

For Gotham report-time use, a real Zeek run must record log-emission time and
make a record available only after emission. If no existing Zeek executable or
module is available, this route stops instead of replacing Zeek with a new
approximate parser.

## Next result experiment

The next implementation may train one small static connection-process expert
on the 4,000 auxiliary fit rows and choose its operating gate on the 1,000
auxiliary select rows plus legal Gotham support-val only. It must be evaluated
inside the asymmetric decision rule:

```text
ProcessAttack OR PolicyAttack OR (C1Hard AND NOT StrongNormality)
```

The first result job remains seed 27, review 0, paired AMD/Intel with isolated
outputs. It must report the unchanged C1 baseline, the process-only ablation,
attack preservation, all four development-held OOD hard rates, per-family
attack recall, worst-family recall, and exact zero use of report data in every
fit/select stage. No seeds 37/47 are allowed without a genuine seed-27 go
signal.

```text
solved: legal mature cross-dataset scan/password process supervision is available as a separate 4000/1000 fit/select bank.
changed_mainline: yes; Gotham support remains 385/127 and the quarantined Gotham 160 are never activated.
active_blocker: Gotham causal Zeek extraction and a result-producing asymmetric seed-27 experiment are not implemented yet.
frozen: exact raw joins, source-disjoint ToN roles, seven zero-use reserve sources, no temporal replay, and all Gotham report/sealed exclusions.
next_action: verify existing Zeek availability, then implement the static process expert plus causal Gotham emission-time adapter and one formal result chain.
```
