# 隔离依赖导入缓存修复回执

结果：独立v6作业182749已提交，1CPU/8GiB/2小时；86包材料、17实际远端依赖、31项包约束通过，最终资源检查待验收。
影响：182748于ENVIRONMENT约31.76秒停止，未进入真实数据链路和训练；主模型与训练协议设计未改。
下一步：ENVIRONMENT原生启动→FIDELITY→真实链路→新基线与全源训练资源→带资源门的协议封存；14阶段，进度页18806，普通程序更新。

根因已定位而非继续猜测缺包：远端faiss/sklearn/catboost的__init__.py全部存在。worker在runtime目录尚不存在时先加入sys.path，Python将该路径finder缓存为None；解包后未清缓存，故报No module named faiss。该现象已在本地临时目录完整复现，调用invalidate_caches及移除sys.path_importer_cache对应项后导入成功，加入长期回归。

v6只预注册已经存在的runtime，解包后刷新finder缓存，并检查三个关键模块文件真实存在。额外在既有超算登录会话的新进程只读导入全部关键依赖，输出CLEAN_IMPORT_GATE_PASS 2.0.1 1.5.2 1.2.8。该项属于实际二进制导入证据，不冒充计算节点训练资格；计算节点仍先跑ENVIRONMENT原生拟合检查。

此前182747总107秒中真实链路99.37秒有效、失败语义阶段6.90秒；182748启动失败31.76秒单列。v3提交前拦截0作业；各版本原始材料和回执均保留，不修改运行过的包。依赖文件在超算复用，大数据、模型、分数留超算。

本轮仍无需原论文数据集成绩复现；目前5方法既有工程资格，DTE/CatBoost新增后以真实通过为准。正式训练设计已写出，16次源域调参/方法、三种子、源CAL阈值、A/B/Edge全口径统一评价；资源外推、ModernNCA全反传和其他待办必须明确，封存不等于自动通过所有资源门。

另恢复交接与实验地图既有历史正文的原始换行字节，避免文档更新造成无关历史整文件变化。

[执行卡](../../baseline_training_readiness_v6_20261107/EXECUTION_CARD.md) · [新作业](../../baseline_training_readiness_v6_20261107/JOB.json) · [回归检查](../../baseline_training_readiness_v6_20261107/LOCAL_REGRESSION.json) · [修复记录](../../baseline_training_readiness_v6_20261107/REPAIR.json) · [正式协议设计](../../baseline_training_readiness_v6_20261107/TRAINING_PROTOCOL.json)
