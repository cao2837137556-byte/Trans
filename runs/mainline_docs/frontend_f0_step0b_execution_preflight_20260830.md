# Frontend-F0 Step-0b real-execution preflight

- Date: 2026-08-30
- Branch: `codex/exp-mainline`
- Reviewed implementation commit: `d65f705`
- Independent implementation review: `727bbda` (`IMPLEMENTATION REVIEW: PASS`)
- User authorization: explicit real R1-R4 causal re-decode authorization received on 2026-08-30
- Frozen protocol SHA-256: `ace6a37fa1ad84fb1660426d4e6c6876fdd3bc407577e3b0709908465b910794`
- Reviewed R0 attachment SHA-256: `5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c`

## Resource gate

The reviewed 30-row packet identity attachment was used mechanically.  For
each member, the inclusive maximum target event position plus one is the
required packet-prefix length.

| Quantity | Pre-execution value |
|---|---:|
| Reviewed packet members | 30 |
| Frozen target rows | 25,467 |
| Estimated prefix packets per pass | 14,444,396 |
| Estimated packet visits for two passes | 28,888,792 |
| D: free bytes | 83,392,393,216 |
| D: free space | 77.67 GiB |
| Existing Step-0b output bytes | 15,224 |
| Conservative temporary-output reserve | 1,073,741,824 bytes (1 GiB) |
| Free-space / reserve ratio | 77.67x |

**Resource verdict: PASS.**  The run is CPU/local-disk bound, internet
independent, and member-atomic.  A disconnect or shutdown cannot change the
scientific result; rerunning the same command may reuse only exact completed
member checkpoints.

## Authorization and claim boundary

This preflight authorizes only the already user-approved Step-0b R1-R4 causal
re-decode over the reviewed fit/select packet prefixes.  It does not authorize
training, embedding generation, checkpoint inference, network retrieval,
report access, FINAL access, HPC submission, or a performance claim.

