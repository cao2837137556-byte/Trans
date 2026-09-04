# Frontend-F2 old-function preservation D0 result

Date: 2026-09-04

Status: `F2_D0_NO_IDENTIFIABLE_PROTECTED_INPUT_FUNCTION`

## Outcome

Frontend-F2 stopped before opening any incumbent representation or score. The
frozen H1-H4 semantic input is not rich enough to reproduce the protected old
P2 function exactly: two distinct token-prefix buckets contain both an A-side
old-hard attack and an A-side old-normal benign target.

| audit item | result |
|---|---:|
| parent training contexts audited | 9,307 |
| parent training targets audited | 13,866 |
| canonical-prefix mixed-label buckets | 2 |
| token-prefix mixed-label buckets | 2 |
| hard protected contradiction buckets | 2 |
| rows in the two contradiction buckets | 28 |
| representation rows decoded | 0 |
| old scores computed | 0 |
| optimizer steps | 0 |

Canonical-signature and integer-token results agree exactly, so this is not an
UNK-vocabulary collision.

## Contradiction 1

Two A targets share the same two-event H1 UDP causal prefix:

- one `normal_1.pcap` benign target, old P2 normal;
- one `password_normal1.pcap` ToN credential-bruteforce target, old P2 hard.

The current GRU receives the same two integer tokens for both rows and must
therefore emit the same representation and frozen-P2 logit.

## Contradiction 2

Twenty-six A targets share the same four-event H1 TCP causal prefix:

- 25 old-normal benign targets across building-monitor/domotic-monitor pools;
- one old-hard Mirai C&C target from the IP-camera pool.

Again, the complete causal signature sequence and token sequence are identical.
No loss weight or continuous teacher target can make a deterministic encoder
emit both required decisions from that same input.

## Fresh split side result

The pre-frozen nested source split itself is feasible: both sides contain A
correct attacks and A correct benign rows, while nested training retains B
benign and B attack rows. It is not the blocker. The input contradiction gate
correctly fires first.

## Interpretation

The proposed continuous old-P2 envelope was a real improvement over the weak
threshold-relative F1 teacher term, but it cannot restore information discarded
before the GRU. The current H1-H4 signatures retain protocol, direction,
coarse length/delta bins, and field-presence information; they do not retain
enough of the packet/session content that allowed old E3 + P2 to distinguish
these 28 rows.

Therefore the route

```text
current frozen coarse H1-H4 tokens -> new encoder -> frozen old P2
```

is scientifically closed before a second training run. This is not evidence
that all unified frontends are impossible. It says that inheritance requires
either a richer causal input contract or a different deployment interface.

## Boundary and next decision

- The full 25,467-row representation member was not opened numerically.
- Internal-validation, select, viewed, report, FINAL, and PCAP scores remained
  closed.
- No old continuous score beyond the previously authorized five-row audit was
  opened.
- No model or resume checkpoint was opened; no parameter was fitted.

The next inexpensive action is a targeted input-sufficiency audit on these two
conflict buckets, using only their 28 original training targets. It should test
a predeclared short list of causal, deployable fields that the coarse signature
discarded (for example service ports, TCP flags, exact rather than binned
length/delta, and endpoint-masked header values). If no such field separates
the protected labels, the project should stop trying to reuse frozen P2 behind
a unified new encoder and choose a structurally safe deployment route instead.

No new training is authorized by this result.
