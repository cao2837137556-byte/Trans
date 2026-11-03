# 密参考结果查看与 A/B 先行评价准备回传

2026-10-28。用户希望先看密参考效果。本轮核对现有结果，并把缺第三池情况下的下一步准备为可审阅候选；**未远端操作、未提交、未目标评价、未训练/编码/新CAL。**

## 当前真实结果

179602的新增21,660参考及真正密源CAL已完成并拉回。源CAL集成FPR：BASE 0.974305% → 原参考0.142897% → 密参考0.135608%，两参考臂召回100%。密参考额外改善0.007289个百分点。修正后源正常FPR由保存汇总派生，独立审计范围详见[完整结果回传](20261027_dense_reference_final_result_readout_codex.md)。

**仍无新A/B密参考正式FPR/召回。** 不能用源读数向用户宣称A/B已经降到0.136%。

## 第三池核查

完整三池仍被真实缺资产阻塞，独立只读再次核对：

- `runs/onboarding_new_lineage_v1_20261022/package_v3/frozen_onboarding/protocol.json`：第三池仍需new-input cache及separate replay。
- 同包 `onboarding_service.py`：完成scope为TWO_POOL，第三池NOT_RUN。
- `runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/banks_manifest.json`：只有A/B的B0/B1/B2。
- V4-EVAL1 parent inventory的956件中没有第三池科学产物；查询只有CIC_DEV/UNSW_DEV。
- 相邻旧regression目录为合成梯度测试，不能当真实第三池结果。

因此不能称“第三池资产齐全但无窗口”，不能造参考、换窗口或用源CAL替代。

## 可审阅的解决办法

新独立候选目录：`runs/dense_reference_ab_stage_candidate_v1_20261028`。详见[具体执行卡](../../dense_reference_ab_stage_candidate_v1_20261028/EXECUTION_CARD.md)。

建议明确修订为分阶段执行：**先完成原A/B三臂评价，第三池延期并一直显示未评价。** 原三池协议与完整性判定保留。新scope为 `AB_DENSE_STAGE_PENDING_THIRD_POOL`，旧授权无效；必须显式确认分阶段修订，并绑定新封包/manifest/源RESULT及本次资源。

已做：

1. 本地58件输入SHA与源seal核查；17件科学文件对齐原已验导出manifest，19件源seal alias精确核对，原产物不改。
2. 原窗口/供体/QUERY_TAIL头/阈值/尺度/λ网格/三臂/四ε/四suffix/两视图保持；只绑定已完成179602派生资产。
3. 独立候选runner与原指标及判决做合成对照；增加逐UID原始/修正分数保存，未做99%阈值选择。
4. 准备HPC manifest精确路径重定位与27静态/7既有派生件清单。运行距离预算912,302,797对，无模型前向、编码或训练。
5. 准备单次amd4CPU/16GiB、RSS8GiB、2小时/输出2GiB/空闲12GiB、零自动重试执行卡。代码单测及封包验收以候选validation和包外回执为准。

远端目标静态件存在性尚未核查；授权后按精确清单复用，必要时只传缺失件（静态上限1,264,976,065字节）。原179602派生件若缺失或SHA不同则停止，不重编码/CAL。

## 为什么还需要一次明确范围确认

原[冻结协议](../../dense_reference_matrix_v1_20261027/PROTOCOL.md)规定：“不得为绕过缺口自动执行A/B-only；第三池修复或明确科研范围修订必须另行记录并封包。” 本轮已把可审阅的分阶段候选做实；这是需要确认的科研范围变化，不是重复申请已完成179602的授权。

截至本回传，候选**尚未获明确分阶段/本次云端确认**，未生成真实授权，未提交新作业。没有新A/B指标。

## 最终封包验收

源目录19/19合成测试、Slurm语法与独立范围/身份审阅通过。独立解包后34件精确清单及逐文件SHA通过，同19/19合成测试再次通过；没有真实评价。

- [封包回执](../../dense_reference_ab_stage_distribution_20261028/r1/PACKAGE_RECEIPT.json)
- [独立解包验收](../../dense_reference_ab_stage_distribution_20261028/r1/VALIDATION.json)
- [候选独审](../../dense_reference_ab_stage_candidate_v1_20261028/validation/INDEPENDENT_REVIEW.json)
- 包清单SHA256：`6870ae7c60ecfb82e4e8c0bc8a18306cad6ee0cf62ed640a82ca254da1fa8f61`
- 归档SHA256：`b37e9213bf7546134205cfcc52192c54d493fb99d4f393a78383d51dbf417937`
- 归档650,274字节；不包含真实授权、不包含1.26GB静态大件。授权后按已封清单复用/补传，源已完成派生输出只读复用。

本候选不是已批准范围修订；不要自动生成真实授权或提交。后续用户明确同意本卡“A/B先行、第三池延期”及一次2小时具体运行后，可以按该授权继续部署、单次提交和普通隐藏进度同步，无需重复申请同一范围。
