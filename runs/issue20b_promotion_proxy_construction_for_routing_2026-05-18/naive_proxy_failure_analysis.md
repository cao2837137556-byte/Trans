# Naive Proxy Failure Analysis

Issue20 used a conservative proxy: V2 could be promoted only when V2 OOD validation alarm was within 1% and attack validation detection exceeded V1 by at least 0.05. This failed for two reasons:

- holdout_bin_2 did not have a usable attack validation proxy in the routing table, so the rule defaulted to V1 even though V2 was the feasible final champion.
- chrono_late had an attack validation proxy, but it favored V1 while final report-only metrics showed V2 was feasible and stronger.
- OOD validation alarm alone is insufficient. Primary low-OOD already shows the danger: V2 validation OOD can appear acceptable while final OOD exceeds the 1% budget.

Therefore the next trigger must include attack-side validation/support evidence and a stronger OOD/review safety check. This is a proxy design problem, not a V2 repair problem.
