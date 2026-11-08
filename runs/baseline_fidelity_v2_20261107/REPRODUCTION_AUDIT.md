# 逐项复现审计 v2

结果：发现并纠正首批TabM适配与作者分类示例的差异；保留首批工程回执，不将其升级为准确论文复现。
影响：只更新独立基线适配，不修改FUSION790、C5、阈值、参考或已冻结主结果。旧基线小切片从未用于正式胜负比较。
下一步：完成作者数值语义/真实输入/资源门；作者公开任务指标复现仍单独待办，不用本轮PASS替代。

## 分级准入

L1 来源、许可、commit、原始源码SHA可追溯；L2 架构/损失/采样/评分/预处理逐项一致或明确记录适配；L3 同运行时真实数据工程预检及资源；L4 作者公开任务复现（公开划分、论文配置、种子、指标/容差预先锁定）；L5 本任务充分源域调参、训练与公平全量评价。

只有L1–L3通过可以称“工程适配通过”；不得称“论文性能已复现”。目前所有候选L4/L5仍待完成。没有原任务数据、算力或容差依据时写明缺项；不先跑目标成绩再倒推准入规则。

|方法|源码核对与具体变化|本轮证据/剩余项|
|---|---|---|
|TabM|原v1单输出BCE、平均logit；作者[示例](https://github.com/yandex-research/tabm/blob/b53fd7cf2d9be2d66b918ca6cf66e0365e4ce11c/example.ipynb)使用分类CE、逐成员训练，在概率空间平均。v2改为2输出CE、32成员概率平均；底层库仍固定v0.0.3。|构造排序反转反例证明平均logit不是等价替换；逐成员CE与展平CE核对。v1为旧工程变体，禁止用于TabM正式排名。原任务复现/含数值嵌入强变体调参尚待做。|
|ModernNCA|官方PLR、编码器、候选采样与原训练保持。新增仅eval使用的分块预编码/稳定softmax全候选归约，保留原`log(prob+1e-7)`；不替换训练梯度。|合成多块大小对原forward；真实CAL8对相同1024候选池及原切点判决一致；617908完整源FIT池只验资源，不与原1024池成绩混比。全量训练内存仍待检查。|
|Disent-AD|原DatasetBuilder的patch1、overlap0、normnone，与本项目unsqueeze严格一致。原重构+双注意力相似性损失保留。|输入一致性核对；既有真实工程PASS保留。作者测试AP选择与本项目源域选择区别明示；原任务/归一化/patch搜索待正式方案。|
|TabR|[官方源码](https://github.com/yandex-research/tabular-dl-tabr/tree/17baa9082506f8e7a0f8d11bb1e08212926a1507)Model类和get_d_out函数AST原样加载，只去CLI及无关训练框架导入。无类别列/无数值嵌入分支；标签embedding、距离差值、残差、self排除全保留。|Linux用真实FAISS IndexFlatL2，和独立穷举距离oracle比较。delu0.0.15同作者；FAISS1.9.0.post1适配现有NumPy2，区别于原GPU1.7.2，须门验证，不能声称环境完全相同。完整模型、原任务和源域调参待做。|
|SLAD|[作者原始实现](https://github.com/xuhongzuo/scale-learning/tree/41c7a1147700239342ea8f6be9483ab0d642ec62)全部训练及评分直接调用；默认20组/10分布/128统一维度/hidden100保留。作者损失中对softmax概率再log_softmax的实际运算原样保留，不能私自改为教科书JSD后仍称原算法。|独立展开KL项比对；epoch_steps=15在作者`cnt > epoch_steps`循环实际16次更新，仅工程检查。正常训练、完整随机投影状态保存/回读。原任务100epochs等正式配置另行复现。|

TabR预检具体配置在作者空间内选固定工程点：d_main128、encoder0、predictor1、context96、dropout0/context_dropout0.1、dropout1=0、LayerNorm/ReLU、AdamW lr1e-4/weight_decay0。不是作者“最佳配置”，不用于正式排名；全0权重衰减避免预检阶段忽略作者参数分组语义。正式搜索必须保留其规则。

## 剩余候选与数量

本轮新增TabR（ICLR2024）、SLAD（ICML2023），后二者不是重复计算TabM修订版。DIF作者仓库当前未见许可证，不将代码打入交付；MCM同样保留许可/来源待办。SketchVision原生sketch/扩散输入和时序适配、Fixed-Noise Denoiser2026官方代码、TabPFNv2容量与信息权限仍待核实。不得用旧锚点填满数量后宣称“多数近期强模型已完成”。

每个正式方法需补：作者任务/数据SHA、对应论文表格、预处理/划分、训练选择规则、种子、预先约定误差或统计区间、实测差异解释。迁移到共享790维只能说明受控表示下的性能，不能替代原生系统比较。
