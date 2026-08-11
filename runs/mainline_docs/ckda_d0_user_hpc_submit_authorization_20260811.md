# CKDA D0 formal HPC submission authorization

Date: 2026-08-11

User authorization text: `授权正式提交 CKDA D0`

## Authorized object

- experiment: CKDA D0 representation compatibility audit;
- bundle:
  `issue27ckda_d0_representation_compatibility_20260811_upload_bundle.tar.gz`;
- bundle bytes: `665814425`;
- bundle SHA-256:
  `c979638ecf430946cdd9e2614b082c42bc5f78f6cadd4bf545ff88afd70aade9`;
- implementation commit:
  `7178dccfd8d74d5b791846686e8015877099addd`;
- Kimi bundle review: `BUNDLE PASS`, commit `5f7bd2c`.

## Authorization scope

This authorization permits exactly one formal AMD seed-27 CKDA D0
result-producing submission through the bundled installer with
`CKDA_D0_SUBMIT_AUTHORIZATION=YES`.

It does not authorize:

- D1 execution or training;
- a second scientific seed;
- seed 37/47;
- opening cooler-motor or any FINAL data;
- changing the FROZEN D0 contract, candidate ranking, I1 gate or evidence;
- duplicate AMD/Intel submissions.

The submitted job must retain the bundle's immutable-input gates, named
real-input phases, checkpointing, strict terminal validator and pullback hash.
Scheduler acceptance alone is not a scientific or runtime PASS.
