# SYN保护开关消融回执

## 本项结论（固定集成，完整视图与单头见下表）
- CIC_DEV / post_window_primary / NORMAL：开启保护额外保留 0 条告警（分母 96041 条查询），加权变化 0.000000 个百分点；反向变化 0 条。
- CIC_DEV / post_window_primary / ATTACK：开启保护额外保留 0 条告警（分母 79056 条查询），加权变化 0.000000 个百分点；反向变化 0 条。
- UNSW_DEV / post_window_primary / NORMAL：开启保护额外保留 28 条告警（分母 74444 条查询），加权变化 0.107511 个百分点；反向变化 0 条。
- UNSW_DEV / post_window_primary / ATTACK：开启保护额外保留 295 条告警（分母 72553 条查询），加权变化 3.294476 个百分点；反向变化 0 条。
- EDGE / full / NORMAL：开启保护额外保留 0 条告警（分母 20000 条查询），加权变化 0.000000 个百分点；反向变化 0 条。
- EDGE / full / ATTACK：开启保护额外保留 5 条告警（分母 40000 条查询），加权变化 0.010107 个百分点；反向变化 0 条。
- EDGE / full / HTTP：开启保护额外保留 5 条告警（分母 20000 条查询），加权变化 0.020215 个百分点；反向变化 0 条。
- EDGE / full / UDP：开启保护额外保留 0 条告警（分母 20000 条查询），加权变化 0.000000 个百分点；反向变化 0 条。

结果：基准复现及本项不变量检查通过；以下为全部配置的选中查询结果，不据结果替换冻结参数。
影响：NORMAL为误报，攻击为攻击关联查询检出；降低告警同时可能减少正常误报和攻击检出。普通/加权不可混用。

|池|视图|配置|组|告警/查询|普通率(%)|加权率(%)|HT率(%)|
|---|---|---|---|---|---|---|---|
|CIC_DEV|full|BASE|NORMAL|464/100830|0.460181|5.412342|--|
|CIC_DEV|full|BASE|ATTACK|79056/79056|100.000000|100.000000|--|
|CIC_DEV|post_window_primary|BASE|NORMAL|18/96041|0.018742|0.002235|--|
|CIC_DEV|post_window_primary|BASE|ATTACK|79056/79056|100.000000|100.000000|--|
|CIC_DEV|full|GUARD_OFF|NORMAL|464/100830|0.460181|5.412342|--|
|CIC_DEV|full|GUARD_OFF|ATTACK|79056/79056|100.000000|100.000000|--|
|CIC_DEV|post_window_primary|GUARD_OFF|NORMAL|18/96041|0.018742|0.002235|--|
|CIC_DEV|post_window_primary|GUARD_OFF|ATTACK|79056/79056|100.000000|100.000000|--|
|UNSW_DEV|full|BASE|NORMAL|833/75763|1.099481|0.695814|--|
|UNSW_DEV|full|BASE|ATTACK|72543/72553|99.986217|99.991298|--|
|UNSW_DEV|post_window_primary|BASE|NORMAL|210/74444|0.282091|0.286266|--|
|UNSW_DEV|post_window_primary|BASE|ATTACK|72543/72553|99.986217|99.991298|--|
|UNSW_DEV|full|GUARD_OFF|NORMAL|805/75763|1.062524|0.588512|--|
|UNSW_DEV|full|GUARD_OFF|ATTACK|72248/72553|99.579618|96.696822|--|
|UNSW_DEV|post_window_primary|GUARD_OFF|NORMAL|182/74444|0.244479|0.178755|--|
|UNSW_DEV|post_window_primary|GUARD_OFF|ATTACK|72248/72553|99.579618|96.696822|--|
|EDGE|full|BASE|NORMAL|24/20000|0.120000|1.220180|0.017457|
|EDGE|full|BASE|ATTACK|39690/40000|99.225000|99.205582|--|
|EDGE|full|BASE|HTTP|19958/20000|99.790000|99.751165|99.795250|
|EDGE|full|BASE|UDP|19732/20000|98.660000|98.660000|98.660000|
|EDGE|full|GUARD_OFF|NORMAL|24/20000|0.120000|1.220180|0.017457|
|EDGE|full|GUARD_OFF|ATTACK|39685/40000|99.212500|99.195475|--|
|EDGE|full|GUARD_OFF|HTTP|19953/20000|99.765000|99.730950|99.770251|
|EDGE|full|GUARD_OFF|UDP|19732/20000|98.660000|98.660000|98.660000|

## 配对变化（集成，各头完整结果见JSON）
n10为左配置告警、右配置不告警；n01相反。各头不能相加作为独立查询。

|池|视图|左→右|组|n10|n01|
|---|---|---|---|---|---|
|CIC_DEV|full|BASE→GUARD_OFF|NORMAL|0|0|
|CIC_DEV|full|BASE→GUARD_OFF|ATTACK|0|0|
|CIC_DEV|post_window_primary|BASE→GUARD_OFF|NORMAL|0|0|
|CIC_DEV|post_window_primary|BASE→GUARD_OFF|ATTACK|0|0|
|UNSW_DEV|full|BASE→GUARD_OFF|NORMAL|28|0|
|UNSW_DEV|full|BASE→GUARD_OFF|ATTACK|295|0|
|UNSW_DEV|post_window_primary|BASE→GUARD_OFF|NORMAL|28|0|
|UNSW_DEV|post_window_primary|BASE→GUARD_OFF|ATTACK|295|0|
|EDGE|full|BASE→GUARD_OFF|NORMAL|0|0|
|EDGE|full|BASE→GUARD_OFF|ATTACK|5|0|
|EDGE|full|BASE→GUARD_OFF|HTTP|5|0|
|EDGE|full|BASE→GUARD_OFF|UDP|0|0|

保护命中/未命中、设备和活动/攻击类别分解及加权交叉计数见配对文件。无总体人口分母的Edge子组仅报告HT总量贡献，不生成虚构的子组人口率。
大规模改变UID明细留超算，SHA见CHANGED_UID_MANIFEST。此为缓存后处理计算耗时，不是端到端吞吐。
