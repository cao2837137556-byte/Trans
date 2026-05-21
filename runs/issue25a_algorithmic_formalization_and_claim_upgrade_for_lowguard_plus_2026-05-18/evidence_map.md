# Evidence Map

| issue | result type | role in paper | recommended section |
|---|---|---|---|
| issue09 | positive and boundary | source_rich has signal but can exceed OOD budget without guard | Appendix / motivation |
| issue10 | positive | fixed OOD guard can convert high detection into feasible low-alert behavior | Main experiment |
| issue11 | positive ablation | fixed guard with OOD weight fixed confirms independent guard value | Main ablation |
| issue12 | boundary | Transformer hidden integration feasible but not stable main gain | Appendix / boundary |
| issue13 | system framing | base detector remains cold-start/background; GDA/LOW-GUARD is deployment-stage adapter | Method motivation |
| issue14/14b | boundary | arbitration needs row-level score alignment; GDA-only high channel strong but review burden separate | Appendix / deployment discussion |
| issue15 | boundary | review queue is safety net, not confirmed attack pool | Discussion |
| issue16 | feasibility | harder holdout and second environment inventory | Appendix |
| issue16b | mixed/negative | fixed guard controls OOD but attack-side generalization can fail | Motivation for representation repair |
| issue16c | diagnostic | failure is representation/score bottleneck more than guard over-conservatism | Appendix / diagnosis |
| issue17 | partial repair | kcenter support helps but is not enough | Method support coreset motivation |
| issue18 | diagnostic | threshold tightness is not the main bottleneck | Appendix |
| issue19 | positive pilot | selected_source_rich top32/top64 opens strong repair path | Method development |
| issue19b | mixed | V2 top32 cannot replace V1 globally; motivates top64 non-regression check | Appendix |
| issue20 | negative | routing gate with weak proxy fails and degenerates to V1 | Discussion limitation |
| issue20b | negative | no clean automatic promotion proxy | Discussion limitation |
| issue21 | negative | active review assets do not cleanly repair promotion | Discussion limitation |
| issue22 | strong pilot | top64 strongly improves hard-shift detection while keeping OOD feasible | Main experiment |
| issue22b | strong non-regression | top64 repairs top32 primary OOD over-budget and improves primary detection | Main experiment |
| issue23 | moderate locked validation | locked bins support top64 but not as universal dominance | Main experiment, phrased moderately |
| issue24 | negative ablation | complex adapters do not replace LR | Main ablation / Appendix |
| issue24b | diagnostic | LR not clear bottleneck; fusion potential exists but risky | Appendix |
| issue24c | weak optional signal | fusion does not replace V2_top64 LR; stop adapter upgrade | Appendix / boundary |

Routing/promotion failures must not be promoted to main contribution. Adapter upgrade negative results should be written as evidence that the main gain comes from representation selection and guarded adaptation, not as failed work.
