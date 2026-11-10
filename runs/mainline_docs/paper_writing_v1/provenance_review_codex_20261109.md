# 编码器、数据与正常参考谱系核对（Codex，2026-11-09）

结果：已将可由现有代码、清单与回执确认的内容写入正文2.2、3.1、3.5和附录B，新增四张复现表及五项官方来源。编码器为官方冻结netFound-base，之前“编码器曾在源内验证数据上训练”的表述不准确，已同步纠正正文、实验设置底稿和流程图。

影响：论文的数据访问边界现在能区分第三方预训练、源归一化、分类头训练、正常校准与现场参考。UNSW全部72,553条攻击查询满足SYN且无ACK的保护条件，告警保持不能独立归因于上下文几何；上下文的直接保全证据仍是Edge同库同尺度消融。Edge未参与开发的角色不变，原有结果与冻结方法不变。

下一步：用户可按2.2 → 3.1 → 3.5 → 附录B阅读新增内容，之后继续逐段润色和随已核对结果扩充比较。以下为本轮证据及核验范围，不把已完成内容重新列为待办。

## 1. 核验方式与边界

仅静态阅读代码、读取已保存元数据与14维描述数组、计算身份摘要/数量并修改写作文件；未启动编码、模型推理、训练、评价或超算作业。`provenance_audit_codex_20261109.json`记录1,094,929条源/开发查询的分组数量、协议保护计数、采集身份、时间范围及文件摘要，并记录三个正常参考库的来源构成。六份查询元数据/描述数组的实际摘要均与当前训练`ASSET_PLAN.json`相符。

审查原始运行证据不等于重新执行实验。本轮没有重新计算分数、阈值、几何支持或性能指标；正文现有结果表仍依前轮核对的冻结结果。

## 2. 编码器与源训练谱系

|要点|直接依据|正文处理|
|---|---|---|
|官方模型与发布版本|`runs/mainline_docs/ckda_d0_official_candidate_evidence_20260811.json`的E3条目；`runs/history_normal_reference_keyrepair_v1_20261031/config/ENCODER_RUNTIME_FILES.json`|netFound-base官方权重、代码commit、权重revision、大小和SHA写入B.4|
|现场编码沿用同一固定实现|`runs/edge_formal_execution_v4_20261104/streaming.py:FrozenBackend` → `runs/history_normal_reference_keyrepair_v1_20261031/hnr/encoding.py:new_encoder` → `repo/ood/legacy_unsw_archival_runtime_v1.py:e3_runtime` → `repo/ood/issue27ckda_d1_e3_embed_v1.py:build_e3_runtime`|项目内冻结；不随源检测头或现场建库更新|
|输出层与推理模式|`repo/ood/issue27ckda_d1_representation_probe_v1.py:e3_forward_batches`，`model.eval()`、`torch.inference_mode()`、`base_transformer.last_hidden_state`和masked mean|768维末层掩码均值，排除预训练预测头|
|缓存构建没有参数更新|`runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/cache_binding.json`中的optimizer updates为0|纠正旧稿“编码器见过源内验证输入”的训练含义|
|源归一化|`repo/ood/continuous_model_v3.py:fit_normalizer`及当前上下文训练实现|完整源训练集拟合统计量；源校准不参与拟合；分类头内验证复用完整训练集归一化|
|查询前缀与字段|`repo/ood/continuous_input_v3.py:RecentState.snapshot, headers`|方向内10ms突发、最近12突发×6包、60s输入边界、相对TCP锚点、无载荷/地址/端口token|

`tokenizer.pretraining=True`是现有输入适配接口的配置，不表示进行了预训练；模型配置明确`pretraining=False`，调用的是基础Transformer。不能根据单个配置字段或目录名推断训练行为。

权重身份由官方获取证据及后续运行清单绑定；本轮未重新下载或遍历完整权重。第三方官方说明给出了预训练来源，但本地没有逐流语料清单，因此没有写入“第三方预训练语料与全部评价流量经验证完全不相交”。这与Edge未参与本项目开发是不同问题。

## 3. 数据与查询选择

|范围|已核实事实|直接依据|
|---|---|---|
|CIC源训练/校准|六设备；训练617,908、正常134,493；校准148,819、正常33,147；组件和会话交集均为0|已保存`LEARN.jsonl.gz`；`repo/ood/legacy_qref_data_v1.py:split`；本轮audit分组统计|
|CIC开发|HeimVision与Eufy；997/99,833正常，65,549/13,507攻击；会话内至多32个等秩查询|`repo/ood/legacy_reference_sample_prepare_v1.py:even_indices,label,scan_capture`；既有file_index及`CIC_DEV.jsonl.gz`|
|UNSW开发|2018-05-28正常、2018-06-01攻击混合文件；五设备；指定时段/源/目标服务、入站SYN且无ACK|`runs/legacy_commissioning_unsw_evaluation_preparation_v1_20260926/`中的recipe、roster、label contract；`repo/ood/legacy_unsw_archival_data_v1.py`；当前`UNSW_DEV.jsonl.gz`与`UNSW_DEV_q.npy`|
|UNSW历史|Dryad 2025年发布，但所用记录采于2016—2017年；不是2018攻击采集的无标注扩充|`runs/same_bank_context_v6_20261106/HISTORY_INPUTS.json`及其引用元数据；官方Dryad说明[12]|
|Edge外部|温湿度正常、HTTP与UDP泛洪三个PCAP；单一Raspberry Pi目标；五段正常上下文|`runs/edge_iiotset_raw_qualification_v1_20261102/APPROVED_CARD.json`；`runs/device_context_evaluation_v1_20261105/EDGE_CARD.json`|
|Edge查询选择|每角色20,000；正常组件覆盖、HTTP状态分层、UDP哈希；候选总体与各层配额|`runs/edge_query_selection_v1_20261103/seal20k/QUERY_SELECTION_SEAL.json`、`selection_core.py`及既有选择验证；最终采用规模仍以正式结果回执为依据|

旧UNSW准备文件中的历史角色名称不用于推翻当前开发/外部分工；这里只从这些文件提取数据身份和标签生产规则。Edge的早期选择封存文件本身也不作为模型执行完成证据。

本轮新增的关键归因检查是直接读取保存的UNSW q14列：攻击标签行72,553条，全部满足TCP、SYN、非ACK。因为后处理对这些行保留原始分数，所以该池正常误报的改进仍然有效，但攻击保持不构成几何约束的独立实验证据。已在3.1、4.2和覆盖分析中明确。

## 4. 正常参考构建与身份

|库|组成|选取与时间资格依据|
|---|---|---|
|CIC 8,863|两小时建档8,574＋三份较早HeimVision正常交互记录289（11既有＋278补充）|`repo/ood/onboarding_dense_reference_v1.py:plan_dense_positions`；`runs/same_bank_context_v6_20261106/HISTORY_INPUTS.json`；原始选中参考元数据|
|UNSW 66,082|两小时建档13,247＋历史52,835；历史初选三个设备，物理位置补选四个设备；WEMO Motion无历史扩容|`runs/history_normal_reference_v1_20261031/hnr/history.py:role_binding`及组件选择代码；`runs/history_sample_coverage_c4_batch_resume_v1_20261102/topup_selector.py`；各阶段参考元数据|
|Edge 4,124|TCP 4,096条/4,096组件；UDP 28条/12组件；无额外历史|`runs/edge_external_test1_engineering_v1_20261103/adapter/population_v1/REFERENCE_ROWS.jsonl.gz`及`DENSE_REFERENCE_PLAN.json`；选择封存中的同文件SHA|

两小时库的4,096上限作用于设备×协议；保留锚点后，已编码候选优先于未编码候选，层内按组件名额和时间覆盖分配。历史参考的第一阶段按组件覆盖，后一阶段按物理包身份哈希选至多4,096个新位置，并保留旧参考，不能统称为一个均匀或组件均衡抽样器。

`runs/same_bank_context_v6_20261106/history_context.py:union`将历史参考原截止时间保存在`historical_reference_end`，实际`reference_end`采用当前两小时建档截止时间。正文据此说明完整联合库的开放时点，未将历史日期误写为评价访问的生效时间。

本地从参考元数据按生产者顺序重建CIC和UNSW联合UID序列，摘要分别为`c4e7e3fdae684bd4260becf6a551649bb4a3f2ccb08af5986ad4644a9990eaf2`和`e5998e097854ab2fae253719ffd29fe510c15dd9360f5ae22e2d128d79a361a6`，均与`METHOD_FREEZE.json`一致。

Edge核实到原参考元数据文件SHA与选择封存一致，并据该文件统计组成。当前评价实现`runs/device_context_evaluation_v1_20261105/inputs.py:edge`按编码批次清单装配参考顺序，而本地未持有该完整批次清单；因此原元数据顺序摘要不能与冻结运行顺序摘要直接比较。本轮未声称重新验证Edge最终数组顺序；该范围明确写入audit JSON，未把序列顺序差异推断为参考库发生变化。

## 5. 本轮写作收束

- 正文2.2补齐编码器来源、输出池化、输入前缀与字段；3.1补数据角色、具体设备和查询边界；3.5完整描述正常参考构建。
- 附录B1–B4分别提供源设备计数、查询资格/抽样、参考行数/组件数、参数来源与编码器版本；新增参考文献[9]–[13]链接官方代码、数据发布页和原论文。
- 同步纠正实验设置技术底稿及架构图；较早审查记录保留，但顶部标明本轮已经解决的内容，避免将历史待办反复带入下一轮。
- 本轮没有把第三方预训练逐流交集、缺失的Edge最终批次顺序或未知的原始组件端点写成“已完全验证”。这些局部证据边界不阻碍现有方法与设置章节成稿。

核验记录：源/开发查询合计与分角色计数、UNSW全部攻击的协议保护计数、三个参考库总数、12份参考元数据文件SHA、六份当前训练输入身份、13项参考文献编号、13张表编号与数学括号配对均通过检查。更新后的流程图已查看PNG确认文字与布局。
