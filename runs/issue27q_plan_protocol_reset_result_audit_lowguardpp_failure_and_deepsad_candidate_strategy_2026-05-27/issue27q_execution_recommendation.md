# issue27q Execution Recommendation

Recommended execution order:

1. P0: DeepSADStyle_Lite sanity controls and threshold replay.
2. P1: DeepSADStyle_Lite seed expansion to 42-51 plus row-block/cluster stratification.
3. P2: LOW-GUARD++ failure diagnosis for seed-44 detection collapse and seed-42 OOD over-budget.
4. P3: paired protocol universality matrix across LR, HistGB, DeepSAD-style, DevNet-style, and one traditional anomaly detector.
5. P4: expensive baselines, optional KitNET AE, and second-dataset preparation.

Do not make a mainline method claim before P0/P1 pass. Do not abandon LOW-GUARD++ before P2 explains whether its failure is support, threshold, config, feature, or objective mismatch.
