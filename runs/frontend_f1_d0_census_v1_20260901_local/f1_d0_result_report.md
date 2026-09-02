# Frontend-F1 D0 count-only census result

- status: `F1_D0_IDENTITY_OR_SCOPE_FAILURE`
- reason: `AUTHORIZED_COUNT_ONLY_TEACHER_BENIGN_VERDICT_NOT_MATERIALIZED`
- targets: `25,467`; A/B: `13,827` / `11,640`
- legal fit: `18,266` rows / `12,889` contexts
- cross-phase exclusion: `19` contexts, `132` fit rows, `32` select rows
- mechanically selected candidate: `torch.nn.GRU`
- synthetic resource cap: `113.994` hours; gate `True`
- blocking evidence: exact legal-fit benign P2 hard/normal counts were not persisted in an authorized count-only artifact.
- fail-closed action: D0 did not open score/probe/representation arrays and did not authorize D1 training.
