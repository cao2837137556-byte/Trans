# Figure Plan

## Figure 1：Method overview

- 表达内容：Enhanced LOW-GUARD+ 从 source-rich 表示到 feature selection、kcenter supports、guarded adapter、threshold calibration 的流程。
- 数据来源：算法设计文档，不需要新实验。
- 论文位置：Method。

## Figure 2：Algorithm pipeline with provenance barriers

- 表达内容：哪些步骤可使用 train/cal/val，哪些步骤禁止使用 final eval。
- 数据来源：protocol 和 provenance 文件。
- 论文位置：Method / Experiment setup。

## Figure 3：Claim-evidence map

- 表达内容：claim、supporting issue、evidence strength、limitation。
- 数据来源：claim_evidence_risk_matrix.csv。
- 论文位置：Experiment overview 或 Appendix。

## Figure 4：Low-alert performance plot

- 表达内容：V1、V2_top32、V2_top64 在 primary、holdout_bin_2、chrono_late 上的 detection 与 OOD alarm。
- 数据来源：issue22、issue22b。
- 是否需要新实验：不需要。
- 论文位置：Main experiments。

## Figure 5：Locked bin result heatmap

- 表达内容：bins 5/6/7/8 上 V1、V2_top32、V2_top64 的 detection/OOD。
- 数据来源：issue23。
- 论文位置：Locked validation。

## Figure 6：Ablation figure

- 表达内容：top32 vs top64、LR vs weighted LR/SVM/fusion、kcenter support。
- 数据来源：issue22、issue24、issue24c。
- 论文位置：Ablation。

## Figure 7：Boundary figure optional

- 表达内容：routing/promotion 当前失败，不作为主贡献。
- 数据来源：issue20、issue20b、issue21。
- 论文位置：Discussion / Appendix。
