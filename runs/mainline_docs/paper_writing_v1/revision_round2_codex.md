# 第二轮正文重构与证据核对（Codex，2026-11-08）

对象：`manuscript_maintext_v1_codex.md`，前版为Commit `b302d35`。本轮依据Antigravity的第二轮审查及相关工作清单，重写引言、方法和实验设置，并补充已有结果的系统与机制分析。未改模型、阈值、冻结结果或评价程序，未启动实验。Antigravity文件及旧技术底稿保留。

## 1. 已落实的写作调整

- 引言以源正常加权1%预算与现场高误报的矛盾开篇，随后呈现TabM的排序/工作点差异、正常参考的覆盖/安全矛盾和方法贡献。
- 将参考覆盖、扣分幅度、上下文交集分为三个机制；第4.3节分别使用覆盖对照和2×2消融，避免把降误报全部归于上下文。
- 正文去掉内部方法代号、工程验收和版本封存措辞；数据来源、信息访问和重要参数保留为学术定义。RAW仅在命题中明确定义为未修正基础检测器，2D/3D定义为两个/三个空间。
- 第2.5节精确定义基准尺度和等效系数；第2.6节给出Proposition 1、基于次序统计量保序性的证明，以及误报/检出率推论。
- 将8条HTTP额外撤警放入第4.4节的单调性边界分析，并区分34条基础漏检、8条后处理额外漏检和42条总漏检。
- 正文表1给TabM成对排序/工作点指标；表2给同前端系统比较；表3给几何×尺度消融。六方法总成绩不提前填入。

## 2. 正文名称与原始证据映射

|正文名称|原始身份或字段|说明|
|---|---|---|
|CIC视频监控设备测试床|CIC_DEV / 旧Pool A|开发评价；以来源命名，不从缩写猜具体数据集版本|
|UNSW智能设备测试床|UNSW_DEV / 旧Pool B|开发评价|
|独立外部工业物联网测试床|EDGE / Edge-IIoTset|未参与开发；基于采集流量的重放评价|
|基础融合分类器|FUSION790，RAW|训练及阈值不变|
|未受上下文约束的基准几何参考系统|T1 C5_FROZEN；T2 C5_2D_FUSION|二维，使用当前头尺度σ；不能与二维b尺度臂混称|
|二维基准尺度修正|C5_2D_OLD|同尺度命题与2,296条恢复计数的直接比较臂|
|完整系统|C5_3D_OLD|三空间，使用b尺度|
|离线基准对数几率离散度b|METHOD_FREEZE.correction中的旧源尺度|来自不含入站上下文的基准头源FIT分布；不是新的现场拟合|
|当前头离散度σ|METHOD_FREEZE.heads各scale|同为加权q90−q10，不是标准差|

## 3. 对审查范例的必要纠正

采用第6节的问题、直觉和叙事顺序，但以下内容按原始指标/代码纠正。

1. **TabM AUROC的适用集合。** 集成完整视图CIC为0.9999951264653146，UNSW为0.994498427488047，Edge为0.9989907025000001。不能将CIC的“>0.999”与另两池误报拼为同一实验事实。正文同时报告Edge的0.998991和78.8350%；UNSW建档后26.3822%，全时段26.1025%，二者分开。
2. **强结论的证据范围。** TabM反例支持“高排名不保证固定阈值可靠”，不证明所有分类器存在不可逾越的架构极限，亦不证明几何后处理唯一或不可替代。正文保留TabM在CIC建档后14条误报优于完整系统18条的结果。
3. **离散度来源。** `repo/ood/constrained_onboarding_core_v3.py:fit_scales`使用包含正常与攻击的源FIT、training_weights和q90−q10。审查示例中的“正常分布”“标准差”不符合代码。b约为118.9563/121.3747/122.3612，σ约为91.6874/95.9807/87.3069；λeff依种子顺序为0.3243527709/0.3161435517/0.3503765175。
4. **几何概念。** 1−cos不是满足三角不等式的一般度量；正文写归一化邻域交集，不写凸流形或凸度量球交集。双组件是不同组件，并非统计独立；不虚构功能聚类。
5. **查询描述。** `constrained_onboarding_reference_v2.py:_snapshot_descriptor`包含协议指示、九个TCP标志、三个连续变换分量及方向，共14维；不是全二值向量。编码器表述为冻结编码表示，不臆断它仅编码包载荷。
6. **保全性质。** 命题在同库、同尺度、同基础分数、同保护规则、同阈值下成立。FPR_3D≤FPR_RAW，Recall_3D≥Recall_2D，同时FPR_3D≥FPR_2D且Recall_3D≤Recall_RAW。不能写“杜绝所有误撤警”“全部恢复查询支持归零”或“完全对冲风险”。额外8/20,000为0.040个百分点；总漏检42/20,000为0.21%，并非千分之二以内。
7. **结果范围。** HTTP99.79%不适用于UDP，后者98.66%。正常0.12%/0.282%是指定评价视图的普通率，不推广为所有设备、种子、时段或权重口径的上界。第4.4节保留全时段与种子127差异。
8. **场景名称。** 不把离线前缀重放改写为我们在真实工业系统完成在线部署，也不据范例添加设备硬件规格、六设备数量、载荷伪装或对抗者能力等未经本轮证据支持的描述。
9. **基线设置。** TabM/TabR选轮指标为源验证准确率，随后完整源FIT重训；TabR推理检索全部对应源训练候选，不能把选轮阶段472,627行固定写成最终候选库。DTE-C当前formal.py为400轮，非范例20轮；正文未扩写未经逐项核验的超参。

## 4. 参考文献核对

以下为本轮直接查阅的作者/出版方来源；正文采用原论文标题和简式引用，作者、卷页等投稿格式后续统一。

|方法|核对结果|一手来源|
|---|---|---|
|DTE-C|论文为On Diffusion Modeling for Anomaly Detection，ICLR 2024；DTE指Diffusion Time Estimation，不是Deep Tabular Embeddings|https://github.com/vicliv/DTE ；https://openreview.net/forum?id=lR3rk7ysXz|
|SLAD|论文为Fascinating Supervisory Signals and Where to Find Them: Deep Anomaly Detection with Scale Learning，ICML 2023；为尺度学习，不是范例中的正交重构方法|https://proceedings.mlr.press/v202/xu23p.html|
|Disent-AD|论文为Disentangling Tabular Data Towards Better One-Class Anomaly Detection，AAAI 2025|https://github.com/yjnanan/Disent-AD ；https://doi.org/10.1609/aaai.v39i12.33425|
|TabM|题名与ICLR 2025相符；作者为Yury Gorishniy、Akim Kotelnikov、Artem Babenko，范例Ivan Rubachev不在该论文作者列表中|https://github.com/yandex-research/tabm ；https://arxiv.org/abs/2410.24210|
|TabR|会议正式题名为TabR: Tabular Deep Learning Meets Nearest Neighbors；不沿用旧预印本题名或范例混合题名|https://proceedings.iclr.cc/paper_files/paper/2024/hash/4ef594af0d9a519db8fb292452c461fa-Abstract-Conference.html|
|CatBoost|题名CatBoost: unbiased boosting with categorical features，NeurIPS 2018|https://proceedings.neurips.cc/paper_files/paper/2018/hash/14491b756b3a51daac41c24863285549-Abstract.html|

未覆盖或改动Antigravity证据清单；以上纠正用于本轮正文，不把对方的“已严格核验”声明当成证据。

## 5. 本轮核验范围

- 读取冻结METHOD_FREEZE、ALL_METRICS、T2、T4、S1、S2，核对主结果的视图、种子、分母、整数计数与加权口径；未重跑模型或重新评价原始分数。
- TabM读取本地COMPLETE、EVALUATE、METRICS、EVALUATION_INPUTS、RETRIEVAL。四个结果/输入文件SHA与取回清单一致；METRICS SHA同时匹配EVALUATE（865a64d75a038d12b878f8e8f5d45c8c508d77efd2a2827feec51339f40caf70）。四池查询UID摘要在评价与输入回执间一致。该检查是本地回执一致性核对，不等于重算远端分数或全部六基线最终审计。
- 手工检查命题保序证明；算术核对λeff、2,296恢复、7条正常增量及8条额外撤警；主结果来自既有冻结统计。
- 正文内部术语扫描、公式括号配对、式(1)–(8)唯一编号及git diff空白检查通过。
- 本轮未证明统计显著性、实时吞吐、最优性、对抗鲁棒性或全球SOTA，正文不作这些主张。

## 6. 后续写作衔接

当前引言、方法、设置和已完成结果可继续逐段精修。下一步补齐编码器训练谱系、通信组件与数据集正式版本的复现附表，以及逐池评价权重层级；汇总六基线最终成绩后扩充统一比较表；再完成针对正常参考和上下文约束的相关工作、图示与摘要。技术细节缺口沿用既有待办，不阻塞当前章节写作，不新增实验。
