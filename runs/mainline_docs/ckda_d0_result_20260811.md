# CKDA D0 representation compatibility audit — formal result

Date: 2026-08-11

Original Slurm job: `158210` (`FAILED`, preserved as engineering history)

Result mode: `CKDA_D0_POST_RESULT_TAIL_RECOVERY`

Overall assessment: **PASS / ready for independent review**

## 1. Formal verdict

```text
status  = CKDA_D0_PRIMARY_AND_OPTIONAL_BACKUP_FROZEN
primary = I1  (domain-internal self-supervised session encoder)
backup  = E3  (netFound)
```

This verdict closes D0 and authorizes only a separately frozen D1 information
probe.  It does not claim anomaly-detection improvement, attack recall, OOD
false-positive reduction, or paper-level detector performance.

## 2. Pullback identity and integrity

- archive: `issue27ckda_d0_representation_compatibility_audit_v1_2026-08-11_amd_158210_pullback.tar.gz`
- bytes: `14,045`
- SHA-256: `6bb7c1ec92e5954c30d8d89c5033ebd1edeec7d12a459d360543f950e72ca1bb`
- extracted top-level files: `17`
- scientific `SHA256SUMS` members independently rehashed: `8/8` PASS
- recovery `TAIL_RECOVERY_SHA256SUMS` members independently rehashed: `16/16` PASS
- candidate-audit SHA-256:
  `3522319bae1c82c1883759cc8bdcacddaf628b11092caec758d47b2e1e7a785a`
- frozen contract SHA-256:
  `ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`

The original failed stage remains unchanged.  Recovery copied the preserved
outputs, reran only the corrected validator, and packaged the result.  The
lineage records `scientific_recomputation=false` and
`final_or_labels_reopened=false`.  Job 158210 must continue to be reported as
FAILED at the Slurm level; the recovered artifact is independently marked PASS.

## 3. Data census and boundary audit

| Check | Result |
|---|---:|
| fit sources | 25 |
| fit-prefix rows | 27 |
| unique fit-visible packets | 13,261,939 |
| I1 fit sessions | 4,764,022 |
| I1 fit tokens | 11,705,453 |
| frozen minimum sessions | 500,000 |
| frozen minimum tokens | 10,000,000 |
| I1 data gate | PASS |
| FINAL files opened | 0 |
| raw label columns read | 0 |
| performance embeddings persisted | 0 |

I1 exceeds the session minimum by `9.53x` and the token minimum by `1.17x`.
The token margin is adequate under the frozen gate but is not large enough to
justify claims about scaling behavior before D1.

The 27 fit-prefix rows comprise 24 Gotham archive members and three direct
PCAPs, with 25 unique source IDs and 27 unique `(source_id, pcap_member)` pairs.
The two repeated source IDs correspond to distinct PCAP members, not duplicate
manifest rows.  All 100 pilot sessions have unique selection orders and unique
session hashes.

## 4. Candidate gates and mechanical ranking

| Candidate | Hard gate | Main reason/status | Fit-encodable | Overlap | D0 projected non-FINAL wall |
|---|---|---|---:|---|---:|
| E1 / ET-BERT | FAIL | complete checkpoint SHA unavailable | 88.26% | no known overlap | n/a |
| E2 / YaTC | FAIL | research-use license not granted; checkpoint SHA unavailable | 88.08% | no known overlap | n/a |
| E3 / netFound | PASS | official checkpoint and pilot valid | 75.09% | no known overlap | 89,571.29 s |
| I1 / domain-internal | PASS | data gate and pilot valid | 88.26% | known disjoint | 35.92 s |

Only E3 and I1 enter the frozen lexicographic ranking.  I1 wins first on the
predeclared overlap key (`KNOWN_DISJOINT < NO_KNOWN_OVERLAP`) and also has the
higher fit-encodable fraction.  E3 satisfies every hard gate and is therefore
frozen as the optional backup/control.

The wall-time values are D0 pilot projections for the specific non-FINAL
compatibility path.  I1 is still untrained at D0.  These numbers must not be
described as full encoder-training time, end-to-end detector latency, or a
performance speedup over netFound.

E1 and E2 were excluded by reproducibility/license gates.  D0 provides no
evidence that their learned representations would perform worse scientifically.

## 5. Resource-pilot evidence

Both eligible candidates completed one warmup plus three measured runs on 100
nonempty sessions, produced finite forward outputs, and persisted no embedding
values.

| Candidate | Raw packets | Candidate tokens | Peak RSS | Median raw packets/s | Runs |
|---|---:|---:|---:|---:|---:|
| E3 | 273 | 1,946 | 942,321,664 B | 111.18 | 3 |
| I1 | 331 | 331 | 430,395,392 B | 325,865.98 | 3 |

The pilot establishes executability and resource order only.  It is not a
detector benchmark and contains no labels or persisted performance embeddings.

## 6. Independent validation assessment

### Overall: ready to share within the project

No blocking integrity, completeness, denominator, ranking, or boundary defect
was found.  Independent checks confirmed:

- outer pullback SHA and both internal manifests;
- exact 50-column, four-row candidate schema;
- candidate IDs `E1,E2,E3,I1` and hard-gate outcomes;
- candidate-audit hash linkage into the verdict;
- census thresholds and conjunctive I1 gate;
- exact pilot candidate set and three-run evidence;
- verdict and validation agreement on ranking `[I1,E3]`;
- zero FINAL, label, and embedding counters across census, pilot, exclusion,
  verdict, validation, and recovery lineage;
- original failure classified and retained as post-result packaging only.

The corrected validator was also rerun locally against the extracted pullback.
It returned PASS, changed none of the 17 file hashes, and both internal manifests
still verified (`CKDA_D0_LOCAL_REVALIDATION_PASS`).

Required caveat: D0 is a compatibility/selection result, not a detector result.
Publication claims about effectiveness remain blocked until D1 demonstrates
new label-blind representation information and later frozen evaluation meets
the preregistered detection gates.

## 7. Next authorized design step

Start CKDA D1 protocol design with:

- `I1` as primary representation route;
- `E3` as backup/control;
- no FINAL access and no performance-driven encoder selection;
- nonparametric geometry, linear probe, and small-MLP probe gates frozen before
  any D1 embedding is opened;
- causal/no-lookahead tests as executable contracts;
- D1 verdict limited to information availability, not paper-level promotion.

No D1 implementation or HPC submission is authorized by this result document.
