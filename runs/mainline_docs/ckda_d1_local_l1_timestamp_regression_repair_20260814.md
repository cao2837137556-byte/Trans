# CKDA D1 local L1 timestamp-regression repair (2026-08-14)

## Scope and authorization

This is an engineering repair for the authorized local L1 contingency run. The
user explicitly waived an additional Kimi repair review and authorized direct
resume after local validation. It does not authorize L2, opening the sealed
report, touching FINAL, or making a formal HPC claim.

## Observed failure

The previous tail-reentry repair run reused and validated 26 member
checkpoints, then failed closed on member 27:

`raw/malicious/merlin/iotsim-ip-camera-museum-1_0-0_to_OpenvSwitch-29_1-0.pcap`

The failure was `session timestamp regressed; frozen causal order is not
representable`. No report or FINAL file was opened and no scientific verdict
was emitted.

A read-only scan decoded all 678,452 packets and all 134 frozen targets. Exactly
one endpoint-pair session had 22 capture-order timestamp regressions. The first
regression was at event position 200,147, immediately after position 200,146,
with a negative delta of approximately 23.13 microseconds. Thirty-two frozen
targets in that session occur at or after the first regression.

## Repair semantics

The repair preserves capture order and does not clamp timestamps, sort future
packets, drop targets, or change thresholds. On the first negative-IAT event,
only that endpoint-pair session becomes permanently unencodable. Its current
and later frozen targets receive the preregistered unified missing state.
Targets before the observed regression and all other sessions remain causal
and unchanged.

Both the formal single-pass embedder and the local exact two-pass adapter use
the same helper. A dedicated regression test proves that poisoning is causal,
clears retained state, and cannot be silently re-entered.

## Validation evidence

- CKDA D1 contract suite: 48/48 PASS under the frozen Python 3.9 runtime.
- Real member-27 end-to-end embedding: 134/134 rows, 69 missing, 65 embedded,
  and zero non-finite non-missing representations.
- Missing-set decomposition: 37 pre-existing discovery-unencodable targets plus
  32 targets at/after the timestamp regression; the expected union equals the
  emitted missing positions exactly, with zero overlap and zero unexplained
  rows.
- Real 32-target formal-vs-local equivalence: checkpoint hashes identical,
  maximum absolute representation delta 0.0.
- The 26 previously validated member checkpoints are retained and are the only
  checkpoints eligible for reuse.

## Claim boundary

This repair is local contingency evidence only. Formal paper claims still
require the frozen HPC replay after the cluster is restored. The same repair
must be included in that formal bundle and pass its independent launch gates.
