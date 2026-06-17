# Literature Alignment

This issue uses literature as design grounding, not as an executable model choice.

## Sources Checked

| Source | Signal used for this protocol |
|---|---|
| Snell et al., Prototypical Networks for Few-shot Learning, arXiv:1703.05175, https://arxiv.org/abs/1703.05175 | Supports prototype/distance evidence in low-sample settings; motivates explicit metric space declaration. |
| Bendale and Boult, Towards Open Set Deep Networks, arXiv:1511.06233, https://arxiv.org/abs/1511.06233 | Supports explicit unknown/open-set handling; motivates `out_of_region != benign`. |
| Ruff et al., Deep One-Class Classification, ICML 2018, https://proceedings.mlr.press/v80/ruff18a.html | Supports compact region/hypersphere-style evidence, while keeping objective/training out of this issue. |
| Rebuffi et al., iCaRL, arXiv:1611.07725, https://arxiv.org/abs/1611.07725 | Supports versioned exemplar memory and separation between initial memory and later incremental updates. |
| Bennequin et al., Bridging Few-Shot Learning and Adaptation, arXiv:2105.11804, https://arxiv.org/abs/2105.11804 | Shows standard few-shot assumptions can break under support-query shift; motivates support_val and dev-query stress as separate roles. |
| Jiang et al., Dual Adversarial Alignment for Realistic Support-Query Shift Few-shot Learning, arXiv:2309.02088, https://arxiv.org/abs/2309.02088 | Reinforces that realistic support-query shifts are varied and unknown; motivates conservative shell semantics and no over-tight radius in issue27ci. |
| Jeong et al., Few-shot Open-set Recognition by Transformation Consistency, arXiv:2103.01537, https://arxiv.org/abs/2103.01537 | Reinforces few-shot open-set rejection around prototype behavior; motivates unknown/evidence output rather than closed-set forced classification. |

## Design Consequences

1. Region evidence must be tied to a declared representation space.
2. One exact label may split into multiple candidate regions.
3. Multiple labels may overlap or later merge if geometry and evidence justify it.
4. Candidate regions can have multiple prototypes.
5. Out-of-region is an unknown/explanation failure state, not a benign label.
6. Region activation must audit source, file, phase, compactness, label consensus, and OOD overlap.
7. Initial support memory is immutable; future online updates require versioned registries.
