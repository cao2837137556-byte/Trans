# Full Mirai Problem Support Feasibility

Stage verdict: `full_mirai_not_sufficient_for_ood_benign_problem`.

Full Mirai currently has enough rows for an engineering split, but not enough semantic evidence for the paper problem.

What is technically possible:

- ID/OOD/support/eval row ranges can be assigned.
- attack support and attack eval can be row-disjoint.
- final eval can remain report-only.

What is not claim-safe:

- OOD benign is not a validated deploy-time benign drift; it is a row-order slice from a benign prefix.
- attack rows are a contiguous suffix, so attack-vs-benign separation can reflect row segment, source, capture, or scale artifacts.
- no timestamp/capture/session/source metadata exists for the full 764k asset.
- no paired raw packets exist to test whether feature values reflect online traffic behavior rather than downstream feature-table construction.

Role if not main benchmark:

- feature/debug diagnostic
- interface stress test
- attack-only auxiliary after provenance warning
- historical exploratory baseline

It should not be the main low-OOD-alert benchmark in current anonymous_clean115 form.
