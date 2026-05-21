# Issue24c Candidate Ranking

| candidate | evidence_strength | recommendation | reason |
|---|---|---|---|
| shallow nonlinear | moderate | not first choice | Some feature-space signals exist, but issue24 did not run a clean shallow-tree result and broad nonlinear sweeps risk overfitting. |
| DevNet-like | weak | not recommended now | No clear evidence that deviation objective is the bottleneck; would add neural complexity without diagnosis support. |
| DeepSAD-like | weak | not recommended now | No strong benign-center evidence; center-distance may be too blunt for attack-bin complementarity. |
| pairwise low-FPR ranking | weak | secondary | There is some low-FPR ranking room, but V2_top64 already has strong guarded performance. |
| V1+V2 residual/fusion | strong | recommended if continuing adapter work | V1 and V2 show bin-specific rescue patterns: V1 helps bin6/7 and V2 helps bin8. |
| stop adapter upgrade | moderate | recommended if paper schedule prioritizes rigor | LR is not beaten by lightweight upgrades; next clean route is strong baselines and second environment. |
