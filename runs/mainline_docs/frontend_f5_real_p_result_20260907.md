# Frontend-F5 real P result

Date: 2026-09-07. Status: `F5_PREFLIGHT_PASS`.

The user authorized the next stage, P only. Executed the existing frozen
`scripts/start_frontend_f5_local.ps1 -Stage preflight` with its matching P token.
Base branch: `codex/exp-mainline`; base HEAD:
`4b28747b09480471e2bac1beb3a9badf27280efb`. Existing unrelated modifications
and untracked files were preserved. No implementation or protocol was changed.

## Verified result

- Frozen protocol SHA: `b8069e6556d6719eef3e689b1ab9a8676c24a00a82e8b5f810a401c9c42786b6`.
- Runner checks passed for 19 input byte pins, Stage I code identities,
  runtime, canonical teacher decisions and initial student tensor identity.
- Parent census: train 8,660 targets / 4,984 contexts / 13 sources;
  internal validation 5,206 targets / 4,323 contexts / 4 sources.
- Teacher cache: 6,870 unique UIDs; 2,179 attack-hard, 4,667 benign-normal,
  24 benign-hard. Exactly 24 null strengths, as frozen.
- Teacher CSV SHA: `d1d67dd2af32898dd84d41ffc587ddb5284ab2e69c1646f1e3d0f2d36c5c7048`.
- Independent read-only verification: output manifest 9/9 hashes PASS;
  teacher unique-row count, category counts, null count and split census agree.
- P budget receipt: 1.328 seconds charged, against 1,800-second cap.
  This is P accounting, not a training duration estimate.
- Launcher stdout contains `F5_PREFLIGHT_PASS`; stderr is empty;
  no remaining run lock, engineering/resource stop, training or evaluation directory.

Artifacts: `runs/frontend_f5_unified_student_v1_20260906_local/`, with
`preflight/complete.json`, `preflight/identities.json`, `preflight/census.json`,
`preflight/teacher.csv`, `preflight/uid_scope.csv`, `preflight/time.json`,
`role_open_audit.json`, authorization receipt and `SHA256SUMS`.
Launcher logs are in the separate sibling `_local_control` directory.

## Access and next gate

Saved access audit records 205,470 parent feature events numerically read,
6,870 teacher representation rows and six permitted teacher state arrays.
Teacher validation/B rows, optimizer steps, student train/validation evaluations,
kill-only numeric targets, select/report/FINAL, PCAP and network counts are zero.
Opaque representation container bytes read are separately recorded, not counted
as numeric access to unauthorized rows.

T and K remain unauthorized and unstarted. P establishes input/teacher readiness
only. T can first show the prescribed development inheritance gates; K can then
establish or reject the fixed candidate's development utility and kill-only gates.
Even a full PASS is development-only: A validation attack evidence remains one
context / three targets. Broad inheritance and new-device commissioning require
later separately scoped evidence. No incumbent deployment change occurred.
