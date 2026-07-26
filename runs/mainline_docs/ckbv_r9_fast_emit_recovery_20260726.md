# CKBV r9 Fast-Emit Recovery (Execution-Only)

Date: 2026-07-26
Scope: result-producing resubmission of the frozen CKBV seed-27 program after
the section-10 root cause was fixed. This recovery changes execution only; it
does not change the 51D schema, target rows, labels, fit/select/report
roles, support usage, model, score, gate, threshold, seed 27, metrics, or
review policy. The frozen frontend module
`repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py` is byte-identical
to r8 (`eca60311b0fe6a0eeea06abc83ef386a398e8519444b378624a1ed46928c38c9`).

## What failed and why (ledger section 10 outcome)

Four jobs across two rounds froze deterministically at decoded 2,375,000 of
the mirai-dos member `iotsim-building-monitor-1_0-0_to_OpenvSwitch-28_1-0`.
The compute-node probe matrix (job `154681`) exonerated TShark and both
input pipelines; local reproduction on the frozen member showed the frozen
`emit` costs 0.92 s per call at 2.38M live history entries because it
rescans the full 60-second source/endpoint history per candidate. The
mirai-dos attack window is a single-pair random-source-port flood (~83k
packets/s of capture time), so the history holds millions of live entries
exactly where the frozen targets cluster.

## The fix

`FastCausalState` (in `repo/ood/issue27ckbv_checkpointed_sparse_process_frontend_v1.py`)
wraps the frozen `CausalFeatureBuilder` with numpy ring mirrors that hold
exactly the entries the frozen deques hold, popped and appended in lockstep
with the frozen pruning and update calls. Window statistics are evaluated
with vectorized passes using the same predicate and operand order as the
frozen scans (`event.timestamp - stamp <= window`); distinct peer/port
counts use exact bincount cardinality over interned ids; syn/rst rates use
integer running totals identical to the frozen boolean sums. Emitted 51D
vectors are therefore bit-identical, not approximately equal.

Only the Gotham member scanning loop switches to the fast path. The ToN
paths are unchanged (all four legal ToN file checkpoints are complete and
donated). The reference helper `sparse_selected_transform` keeps calling the
frozen `emit` so every bit-exactness test compares against the frozen
semantics.

## Evidence

1. Unit suite (`--mode unit`, runs inside the bundle clean-extract
   contract): new adversarial bit-exact streams covering a single-pair UDP
   flood, a 54.4 s capture gap, a random-port ACK/RST flood, timestamp
   inversions, port 0, and the FIFO-prune quirk where a young head shields
   an expired deeper entry; plus mirror-synchronization invariants
   (lengths and syn/rst totals against the frozen deques).
2. Real-member parallel validation (frozen local ZIP, first 2,450,000
   packets, frozen and fast instances fed identically): 27 sampled emit
   positions including deep flood state, zero mismatches; frozen emit
   0.31-0.66 s versus fast emit 15-31 ms at identical positions.
3. Throughput consequence: at the worst observed history size (~5M live
   entries) the fast emit stays under ~0.1 s, so a full mirai-dos member's
   candidate emits cost minutes, far inside the unchanged 4-hour member
   limit. The size-range calibration measures the largest member (a
   mirai-dos capture) with the fast path in effect before full dispatch.

## Reuse

The default resume donor order becomes `154620`, `154621`, `154606`,
`154607`, `154478`, `154440`, `154081`, so the member checkpoints committed
by the r8 pair are reused ahead of older donors. Checkpoint identity remains
bound to the member plan hash and content validators, which are unchanged;
no completed auxiliary, ToN, or Gotham member work is repeated.

## Unchanged contracts

Watchdog limits (300 s heartbeat / 3600 s real progress / 14400 s member),
two Gotham workers, AMD/Intel isolation, duplicate-submission guards, the
terminal-truncation safety contract, and all section 1-10 permanent gates
remain in force. Completion still requires the unchanged attack-preservation,
strict Level-2, support-use, review, predictions, and single-seed go/no-go
outputs of the preregistered CKBV program.
