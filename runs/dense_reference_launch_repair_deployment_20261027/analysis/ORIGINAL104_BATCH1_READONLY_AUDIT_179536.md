# 179536 原104批次只读核查

失配8条恰好等于全部8个B1 shape组；其他96条（包括B2/B3/B4/B12尾批）逐字节相同。历史104条全部出自真实B16批次，分布于98批。这个精确对应支持优先检查B1数值路径，但本报告未做前向，不能证明因果。

按UID只读对比104个原spool与新包snapshot：flow、provenance均104/104相等；完整body均不相等，因为new增加source_sha256，且77条state不同。冻结E3 tokenizer只读flow，verify_tokenized检查flow/provenance；state不进入E3。不可把这项证据说成完整body或历史tensor receipt逐条一致。

旧104直接来自原cache/features/SOURCE_REFS.npy前768维，10/22 reference_forward仅算检测头logits，E3前向为0。旧cache和保留metadata环境均为Python3.9.24、torch2.5.1+cpu、MKL2024.2、EPYC7T83；本次为Python3.11.11、同号Torch的CUDA11.8构建、MKL2023.1、EPYC7742。96条跨环境仍exact，故构建差异只是次级候选，不是已证根因。

| 设备 | UID前12位 | shape | 原batch ID | 旧批位置 |
| --- | --- | --- | ---: | ---: |
| ArloQ Camera | 08435fcba19c | [6, 25, 10] | 9716 | 8 |
| Atomi Coffee Maker | 2d2dc8b2e3e0 | [17, 7, 4] | 53442 | 8 |
| SimCam | 34f33f8a5d4e | [6, 25, 8] | 9449 | 1 |
| Philips Hue Bridge | 5b77d9a64d81 | [17, 7, 1] | 50805 | 1 |
| SimCam | 75e945f27c50 | [6, 25, 3] | 7470 | 1 |
| SimCam | 894693b2d47d | [6, 13, 7] | 6078 | 3 |
| Amcrest Camera | 8efedb594ef1 | [6, 13, 1] | 1501 | 3 |
| Atomi Coffee Maker | dd358ae30223 | [6, 49, 7] | 21218 | 6 |

真实8旧批共128行，角色为{"LEARN": 80, "SOURCE_REFS": 8, "UNSW_DEV": 15, "CIC_DEV": 25}，含40行A/B查询。它不是source-only批次；本报告只记8个source anchor的旧batch ID、位置及角色计数，不导出128行队列或目标内容。

下一步拟做source-only8anchor B1/B16克隆隔离诊断：共136个模型位置，4CPU/16GiB/10分钟，无前向授权由本报告产生。每次B1及16克隆的输入tensor_hash须先等于179536对应hash；8个B1输出须先精确复现失败HPC hash，否则停止且不做B16。B16先验证16克隆输出彼此一致，再对旧expected feature hash做零容差判定。无任意变体、无入库、无CAL、无头训练或目标评价。

该克隆探针只能检验batch-size路径；不能称恢复真实历史队列，不能直接接着补21660，也不能据此宣布数值迁移成功。原始104字节门不放宽。历史导入前缀逐行tensor receipt缺口继续保留。

输入小件与本报告均登记SHA；4GB spool此次仅按mode=ro&immutable=1索引读取，未重新全文件hash，使用冻结回执中的登记SHA。没有模型加载、分词、远程操作或生产文件修改。
