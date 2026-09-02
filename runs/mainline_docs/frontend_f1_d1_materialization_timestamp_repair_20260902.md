# Frontend-F1 D1 materialization timestamp repair (2026-09-02)

## 1. Failure classification

The first authorized fit-corpus materialization completed fresh two-pass replay
for all 24 packet members and all 18,266 legal-fit targets. It then stopped
before corpus finalization while joining the timestamp used by the inherited
fit-only geometry instrument.

```text
failure class = F1_ENGINEERING_OR_PROTOCOL_FAILURE
scientific verdict = null
training started = 0
select/viewed/report/FINAL opened = 0
```

The target plan's `feature_available_time_epoch` is legitimately the literal
string `nan` for 12,000 ToN rows. Treating that plan field as a universally
finite timestamp was an implementation error.

## 2. Narrow repair

The repair does not alter semantic contexts, labels, the split, vocabulary,
model, losses, or any scientific gate.

The inherited Lane-G geometry instrument already pins the exact embedding
metadata file:

```text
runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/
  ckda_d1_fit_select_embeddings.npz.metadata.csv.gz
SHA-256 = 120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd
rows = 25,467
unique UID = 25,467
finite timestamp_epoch = 25,467
```

Post-replay timestamp ordering now uses this pinned, UID-exact metadata source.
The target plan remains unchanged and is still used for target identity and
packet location.

## 3. Checkpoint compatibility

All 24 member checkpoints were produced by the same semantic replay code whose
source SHA-256 was:

```text
f5b38023244485415570a6235be8160706b8ace0aad449d30481e7a9b3efc7e9
```

That digest is now a literal replay identity. The repair occurs strictly after
all replay and does not change any checkpointed field. Reusing those 24 exact
member-boundary checkpoints therefore avoids a scientifically redundant
re-decode without weakening identity checks. The final manifest records both
the current implementation SHA and the replay implementation SHA.

## 4. Regression evidence

```text
Python 3.9 compile = PASS
F1_D1_CONTRACT_TESTS passed=72 failures=0 errors=0
```

New tests independently verify the old replay source digest, the target-plan
12,000-row `nan` fact, the inherited metadata SHA, finite timestamp coverage,
UID uniqueness, and 25,467/25,467 exact join.

The prior engineering-failure directory is preserved under a distinct failed
namespace. The resumed run may reuse only checkpoints whose full marker
identity and checkpoint-content SHA still match.
