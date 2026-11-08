# 实现与适配审计

本轮不复现作者论文数据集成绩。复现准确性指：固定官方源码/版本与SHA，核对输入、目标、损失、评分、随机性和检查点，明确本任务的适配边界。

## 新增方法

**DTE-C（ICLR2024）**：[官方仓库](https://github.com/vicliv/DTE)，MIT，commit见DTE_PROVENANCE.json。直接加载原diffusion/dte.py，不改网络、加噪、损失或评分。作者实现为无漂移方差加噪；分类网络已softmax而compute_loss再次调用CrossEntropyLoss，此处保留作者真实实现并独立核对，不擅自“纠正”造成不同方法。分数为时间桶的期望编号。每次显式设NumPy/PyTorch种子；标准化仅拟合当次合法正常训练子集。正常训练，与监督方法分组报告。400轮是作者默认上限，不是本轮1轮资源探针的成绩资格。

**CatBoost 1.2.8**：[官方仓库](https://github.com/catboost/catboost)，Apache2；固定PyPI Linux cp311官方wheel SHA，隔离解包，不重建环境。正类是攻击，评分RawFormulaVal，与predict_proba正类概率关系及原生cbm回读一致性测试。全量8树仅测资源；正式调参保留深度/学习率/L2/随机强度空间。2018经典强锚点，不虚称新方法。

## 新查到的阻塞

**DIF**：author-maintained DeepOD commit 351db62cb39d99a6e4e1e74fb96617bcd7dc4247（BSD2）中decision_function对测试批重新fit StandardScaler，测试批组成会改变分数。不能以此实现直接宣称因果在线检测。保存原文件作审计证据；本轮不执行DIF。若改为训练期scaler须登记inductive变体并做额外一致性检查，不静默改作者算法。

**FND2026**：PMLR原文称代码在OpenReview补充zip，当前尚未取得并审核可执行源码；不能自行凭摘要实现后称官方复现。MCM许可、SketchVision输入/硬件、TabPFN样本/维度资格继续待办。

## 既有方法

TabM采用两类CE、32成员概率平均，废弃首批平均logit口径。TabR原Model AST不改，仅启用作者原生memory_efficient与candidate_encoding_batch_size；验证原生FAISS及小池数值，真实全池反传单独测。ModernNCA原采样率和PLR嵌入保留；不采用未验证的分块反传。SLAD保留原loss与变换过程，epoch_steps=15按作者循环实际16步。Disent-AD保留patch_size=1/overlap=0/normalization=none的共享790适配。

截至本轮准备时既有5方法取得工程证据，新2方法仍须真实通过。最终8–10方法是目标而非已完成事实；DTE属于新增近期方法，CatBoost属于强经典锚点。最终不得按是否弱于本系统筛选方法。
