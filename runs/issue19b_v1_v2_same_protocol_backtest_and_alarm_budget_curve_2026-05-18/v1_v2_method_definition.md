# V1/V2 Method Definition

- V1 / LOW-GUARD-minimal: `original100 + kcenter32 + fixed guard LR`.
- V2 / LOW-GUARD+: `selected_source_rich_top32 + kcenter32 + fixed guard LR`.

V2 is intentionally narrow: no original100 fusion, no margin-hardneg, no topK search, no MLP/prototype/full neural GDA. The selected source_rich top32 rule is the fixed rule inherited from issue19 and applied using allowed development data only.
