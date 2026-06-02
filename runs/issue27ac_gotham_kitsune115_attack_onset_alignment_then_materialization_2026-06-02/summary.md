# issue27ac Summary

1. issue27ac complete: yes.
2. primary_verdict: `attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion`.
3. Current blocker addressed: attack-side label/onset alignment, not benign split and not Kitsune115 frontend recovery.
4. Attack onset scan: processed CSV first-attack timestamps were used to choose causal malicious PCAP windows.
5. Attack support/eval onset-selected: `true`.
6. All attack contract files onset-aligned within scan budget: `false`.
7. Tiny Kitsune115 attack-onset probe executed: `true`.
8. 115D numeric stability in probe passed: `true`.
9. Benign prefix handling: prefix packets may warm the frontend state but are not labelled as attack support.
10. Attack eval handling: sidecar keeps packet timestamps and role labels; metric computation remains future work.
11. Model experiment allowed: no.
12. issue27ad recommendation: expand to a balanced onset-aligned Kitsune115 smoke dataset and deep-scan unresolved ip-camera attack files before any model interface smoke.
13. Slurm needed: not for this probe; likely useful for larger/full 115D extraction.
14. commit hash: pending.
