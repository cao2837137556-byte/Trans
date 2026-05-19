# Protocol

This run is proxy construction and diagnosis, not final routing validation.

- V1 is fixed as original100 + kcenter32 + fixed guard LR.
- V2 is fixed as selected_source_rich_top32 + kcenter32 + fixed guard LR.
- Support-holdout is built only from local attack train pool after removing selected supports.
- OOD tail and disagreement proxies use only OOD validation.
- Representation-shift proxy uses support-holdout and OOD validation features.
- Final OOD eval and final attack eval are used only for report-only diagnostics.
- No V2 repair, V3, source_rich topK reselection, margin-hardneg, or threshold change is performed.
