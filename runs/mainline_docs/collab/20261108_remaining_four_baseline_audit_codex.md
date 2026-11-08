# 七基线范围固定与剩余四方法审查

结果：按用户最新决定，最终范围固定TabM、TabR、Disent-AD、ModernNCA、SLAD、DTE-C、CatBoost七个，不再为8–10数量扩充。四方法本地构造/前后向审查完成，本轮未提交新作业。
影响：本地小张量检查不等于Linux全量资源资格；不改主模型、既有训练包或参数搜索规则。发现ModernNCA更强内存下界及Disent-AD报告/选模差异，已记录具体边界。
下一步：TabM落实源组隔离早停和正式硬件整轮；TabR补历史参数绑定证据及原生检索资源；Disent-AD固定适配训练预算并测整轮；ModernNCA先按实际展开形状确认可用硬件，不能在8/12/20GiB上盲跑原默认。

## 本次实际检查

- TabM：官方make无embedding适配，4×32×2输出、逐成员CE反传有限，参数1117952。AdamW .002/3e-4、batch256、裁剪1、patience16来自封存官方示例。停止依据为源验证accuracy，不取目标分数；不能仅凭默认网络就删除早停验证。仍须覆盖与隔离检查；不开展超参数搜索。
- TabR：官方存档CA/adult默认模型d_main265，优化器和dropout一致。当前接口名context_dropout，档案为mixer_dropout。本次按候选映射实际构造并在小池穷举oracle上反传通过；历史提交查询未找到参数改名证据（证据文件为空），故不把语义等价标为通过。当前context_size16仅32候选的局部检查，正式96不变。此处不是原生FAISS全池资格。
- Disent-AD：已封存patch1/dim128共享790适配小批前后向和评分有限。作者train.py保存最低平均训练loss模型，但控制台best_ap取测试集历轮最大值。正式采用保存模型规则，禁止照搬控制台最佳测试成绩。batch512的单个双头attention张量即2.381GiB，未含softmax、中间激活和反传；整轮内存时间仍须测。作者按数据集配置轮数与batch，没有针对790的唯一推荐，不能称任意适配为作者最优。
- ModernNCA：保持官方sample_rate=.5、PLR77频率/34输出、lr.01/wd.0002。在真实作者模块上挂hook观察30×790×154周期输出，小池反传通过。按完整FIT617908、查询batch512计算候选308698：float32正弦/余弦拼接单张量139.908GiB，最终embedding单张量30.889GiB。此前30.89只是后段单张量，不是所需总显存。float64翻倍，总峰值还包含其他张量/反传；不能用这些下界宣称某个大内存资源必定足够。不缩候选池、不改默认以凑运行。

证据：[可重复审查脚本](../../baseline_remaining_four_audit_v1_20261108/audit.py)、[机器回执](../../baseline_remaining_four_audit_v1_20261108/AUDIT.json)。源码沿用baseline_author_defaults_v1_20261108/vendor封存版本。官方[TabR仓库](https://github.com/yandex-research/tabular-dl-tabr)为来源；未下载作者数据集、未按目标成绩选择基线。
