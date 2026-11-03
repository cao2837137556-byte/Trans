# Codex：历史正常参考 C1 已实现，工程验证完成，尚未运行

日期：2026-10-31。状态：`IMPLEMENTED_SYNTHETIC_VERIFIED_NOT_RUN`。

按用户“开始实现”完成了 r2 + 最终 Codex 复核绑定的代码与工程验证，已经结束方案往返阶段。新包在 `runs/history_normal_reference_v1_20261031/`。原 r2 SHA `dc566523f91256de7616391634bcfc348d1434e3a4227b0f8414122984a9dbf0`、复核 SHA `f73c0bdd2dd6aa3a114a58ef3b4f56f9bd99e30ca53c4a7ffd1d5f3351f9b803` 均核验一致，原稿未改。

**结果：56 项生成数据/模拟编排测试全部通过，本机只读资产验收 READY；没有真实包解码、特征生成、补库、新评分/距离/support、A/B 新评价、训练或远端操作。现在是实现完成，不是新实验完成，也没有2%新成绩。**

已实现的具体链路如下。

- **整成员连续历史适配**：三台原始成员按已核稳定时间索引复制为逐块原样保留的 PCAPNG，实际派生对象 SHA 绑定逻辑流；帧从1到N连续，保留原成员SHA/原包序号，重复字节不同原包仍保留。冻结 Contexts 看见每条未过滤 decoder 行；缺头污染、真实idle重置和当前包读出保持原合同。原始非空UTC日期80/20分割，REF/DEV边界不重置。
- **磁盘候选、确定性有界选点**：第一遍完整解码只枚举全部合法端点身份，SQLite复合索引避免逐组件反复全表扫描；REF优先无旧锚点组件且每设备/协议≤4096，DEV每设备总计≤4096。完整选择独立回放；第二遍完整解码只为已选UID保存快照。SQLite排序临时存储受内存守卫覆盖。A11行直接复用，不解码/重编号。
- **新历史编码入口**：REFERENCE 与 QUERY 分别调用冻结 descriptor，再核q14、帧/头/token连接、形状分组和张量身份，绝不伪装旧B2回执。复用冻结 E3 权重及已验收 singleton→16物理副本修复，输出逐字节相等后只保留一个UID。独立记账逻辑向量和实际物理位置，单encoder进程跨三成员复用。
- **双截止与门顺序**：DEV只看有真实历史截止的HIST-REF；新旧合库沿用原A/B B2截止并保留各capture帧界，DEV不再入库。DEV正常查询使用冻结QUERY_TAIL三头评分；任一DEV门失败，在A/B查询加载前停止。DEV保存逐UID来源、logits、support、四头决策及SHA审计。
- **一次A/B终评**：复用旧raw logits/E3/q14，仅重算四台own support，其余复用179700支持及原决策并校验一致；所有原设备保留。四头累计保护、RAW低召回零TP撤回、主视图PASS/IMPROVED与full并列报告已落地；全局尝试标记阻止换输出目录重跑，无重校准/选档/自动回退。
- **资源和右侧进度**：CPU4、16GiB、20GiB、整次8h，实际距离对预扣≤579,614,444、唯一新增E3≤36,864。逐包复制、完整性读盘与两次解码都受实际资源守卫，不承诺ETA。复制/解码包数、REF/DEV选中、快照、编码批次、DEV及A/B阶段都有记录；工作和服务心跳分开，超90秒无工作更新显示未知。Codex右侧只读页面及Slurm模板已准备。

56项测试包含完整生成包字段→census→选点→双角色descriptor→token/tensor→伪E3适配链、2017年真实量级整数微秒往返、跨4.800584秒角色边界保留上下文、缺头污染不可预删、相同字节不同原位置不去重、caps/溢出/并列时间/确定回放、双截止、单encoder三成员复用、DEV失败绝不读A/B、完整合成A/B/未补设备复用、四头保护、资源中止、进度陈旧与封印篡改。

复核中发现并已修复一个实际部署漏洞：配置比较不能把名为normalizer的整个字典略掉。现在仅允许路径字符串迁移，normalizer及全部科学输入SHA仍冻结；另有独立回归测试证明SHA替换被拒绝。代码封印覆盖1361个实际实现/外部科学Python和配置等文件；编码器源文件与权重另有完整文件清单，权重SHA核对原冻结值 `e6237f49…f5105`。

验收材料：

- [实现入口与接口说明](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_v1_20261031/README.md)
- [执行卡](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_v1_20261031/EXECUTION_CARD.md)
- [机器实现回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_v1_20261031/validation/IMPLEMENTATION_RECEIPT.json)
- [56项测试报告](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_v1_20261031/validation/TEST_REPORT.json)
- [本机只读资产验收](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_v1_20261031/validation/READ_ONLY_ACCEPTANCE.json)
- [代码封印](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_v1_20261031/CODE_MANIFEST.json)，SHA256 `31ab70c41014427a49c5ce134dba269e2bbade54e911ca5e1d674ab3ad95b84e`。

本机生成数据测试使用Python3.10 / NumPy2.2.6 / Torch2.8.0+cpu。它们验证工程逻辑；正式HPC数值合同仍是实验9的Python3.11.11 / Torch2.5.1 / NumPy2.0.1私有overlay，本轮未在该环境运行。只读验收核了现有索引SHA、时间序、文件路径/大小及冻结输入登记；未提前加载A/B查询载荷，原包完整SHA在真正prepare入口再次核验。READY仅说明本机材料齐备。

下一执行阶段须先映射和核验超算路径、保持科学SHA并封存交付身份，再做远端环境验收和一次提交；拟定16GiB/8h仍不是旧8GiB授权的延伸。本轮实现授权没有被解释为真实科学执行授权。没有job ID，不恢复旧失败路线，不继续写原则确认稿。

这次方案已解除“没有合法新材料/不能补第二组件”的工程阻碍，但历史几何能否覆盖A/B残留误报，以及是否会撤回攻击，仍须本轮固定DEV门和一次A/B验证；没有依据保证2%。
