# C1–C3只读核查：计算前口径说明

2026-10-25。按用户授权执行Claude主方案第3节第一步。本文记录实际资产与方案文字的差异，不修改主方案或改变研究方向；后续分支由Claude判读。本轮使用本地已封存的QUERY_TAIL三seed集成＋V3＋B2资产，不训练、不新增E3、不改原结果。

1. **A的BANK_NOT_YET_AVAILABLE不全是两小时观察期。** B2 receipt中A的观察窗口为t0=1635851700.06933至cutoff=1635858900.06933，但DEV包含更早日期的查询。因此C1分别统计timestamp<t0的历史、[t0,cutoff]内、cutoff后，不能将所有timestamp<=cutoff都写成“窗口内”。密参考代理仅按原窗口/source/capture筛选已编码位置，标签只用于后验污染分账。B窗口为1527465601.09039至1527472801.09039。
2. **实际V3支持公式使用源半径与第二真实组件。** 几何距离为joint=max(dz/rho_z,dq/rho_q)，各component先取最小值，再取两个不同component的次小值，support=clip(1-second_joint,0,1)。原稿max(dz/2,dq)可作描述性距离，不能替换原支持公式；最近单点更近不等于原V3支持恢复。C3将同时报告描述性最近点及原公式的支持关键参考，dz/dq拆分按对应代表计算，不能把trace中独立计算的second_dz/second_dq误认成同一joint代表。
3. **两池原权重层级不同。** A实际采用device→activity→capture→session→row；B正常采用device→component→row，攻击采用device→annotation→component→row。C1主表将按各池原实际层级，在观察期后保留的非空分支重新归一；另列原权重裁剪结果以暴露评价总体变化，不为B臆造A的层级。
4. **诊断代理保留原标签，不伪造正常身份。** 原ReferenceBank构造器要求reference label=0；C3不通过篡改DEV标签绕过它，而在独立诊断结构中复用纯数学。窗口候选的选择不看label／score，窗口是否含攻击单独审计；诊断结果不能直接宣布为可信参考部署收益。

完整结果另回传collab。本说明只冻结计算口径，不授权第二步或更改主评价指标。
