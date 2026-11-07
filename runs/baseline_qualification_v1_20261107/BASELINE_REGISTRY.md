# 强基线候选登记（2026-11-07）

当前登记12项，其中8项为2024–2026论文；目标最终保留8–10个任务适配、充分训练的外部方法。首批3项进入工程预检，其余仍待资格/适配。旧锚点只作领域坐标，不构成主体；不把内部消融凑成外部方法数量。

|候选|发表及论文强度证据（作者原文主张，不是本项目结果）|本轮状态与适配限制|
|---|---|---|
|TabM|[ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/c1ba41c694834aeef91ae161711d4939-Abstract-Conference.html)：广泛表格基准优于既有深度方法|首批预检；[官方代码](https://github.com/yandex-research/tabm)，Apache2，固定commit；现有旧实验不可直接复用成绩|
|ModernNCA|[ICLR2025](https://arxiv.org/abs/2407.03257)：300数据集，作者报告与CatBoost相当并优于深度方法|首批预检；[官方TALENT](https://github.com/LAMDA-Tabular/TALENT)，MIT；全源域检索扩展性待检查|
|Disent-AD|[AAAI2025](https://arxiv.org/abs/2411.07574)：20表格数据集，作者报告AUC-PR/AUC-ROC改善|首批预检；[作者代码](https://github.com/yjnanan/Disent-AD)，Apache2；正常训练；源域选择替代测试集选轮次|
|TabR|[ICLR2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/4ef594af0d9a519db8fb292452c461fa-Abstract-Conference.html)：作者报告平均优于深度表格模型，并在GBDT友好任务上有竞争力|[官方代码](https://github.com/yandex-research/tabular-dl-tabr)适配待做；源域标签、检索候选与内存须锁定|
|MCM|[ICLR2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/13ec20547d2b1ff3a3a7a7c68a28e742-Abstract-Conference.html)：学习mask的一类异常检测，论文报告SOTA|[作者代码](https://github.com/JXYin24/MCM)commit已定位，但当前树未见LICENSE；许可澄清前不将代码纳入运行包|
|SketchVision|[NSDI2026](https://www.usenix.org/conference/nsdi26/presentation/mirnajafizadeh)：19种slow-and-low攻击，作者报告平均AUC0.982、F1 0.913|[作者代码](https://github.com/NIDS-LAB/SketchVision)已定位；eBPF sketch/扩散输入、GPU与输出时间粒度资格待检，不能强行作为790维头|
|Fixed-Noise Denoiser|[ICML2026/PMLR306](https://proceedings.mlr.press/v306/hirth26a.html)：ADBench上作者报告相对既有生成式方法的平均ROC/PR优势|论文核实；官方可复现代码/超参来源待取得，不自行假造实现或称已运行|
|TabPFNv2|[Nature2025](https://www.nature.com/articles/s41586-024-08328-6)：小规模表格基础模型，论文报告强性能|论文覆盖≤10000样本/500特征，本任务617908/790超出原口径；先查版本、许可与扩展资格，不能任意截到弱配置来凑对比|
|SLAD|[ICML2023](https://proceedings.mlr.press/v202/xu23p.html)：尺度学习自监督异常检测，作者报告跨数据集优势|正常训练方向；正式代码版本、资源资格待核，不标成2025新方法|
|DIF|[Deep Isolation Forest作者论文](https://arxiv.org/abs/2206.06602)：深随机表示与隔离机制|2022预印本，正式发表信息需进一步核对；版本/代码资格待查，不虚标年份|
|KitNET/Kitsune|[作者官方实现](https://github.com/ymirsky/Kitsune-py)，NDSS2018，领域经典网络异常检测|必要领域锚点；原生包级特征/训练窗口/查询粒度适配待检，不算近期方法|
|CatBoost|[NeurIPS2018论文](https://proceedings.neurips.cc/paper/2018/hash/14491b756b3a51daac41c24863285549-Abstract.html)，强树模型参照|经典强表格锚点；待固定正式版本与源域调参，不能只用默认参数代表最佳水平|

补充候选：[CARAVAN/OSDI2024](https://www.usenix.org/conference/osdi24/presentation/zhang-qizheng)属于在线标签代理与数据面协同系统，额外标签/硬件权限不等价，暂不计入上述12项。若后续建立匹配信息权限的在线任务，再独立比较。Horus、NetMasquerade等不能仅凭会议年份或名字加入不同任务的检测器排名。

正式方法数以“作者来源核实＋输入/信息权限适配＋真实预检＋充分调参训练＋完整结果”全部完成为准。资源失败与缺失代码单列，不算我们战胜对手。
