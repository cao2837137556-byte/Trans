# 双组件均值与较弱匹配对照

在 v12 表 9 的开发对照库和三种子 MLP 集成上，要求两个不同通信组件均已匹配后，用两者的平均支持度替代较弱匹配，合计额外撤回 25 条正常误报，同时额外撤回 4 条原本正确的攻击告警。CIC 建档后分别撤回 0 和 3 条，UNSW 建档后分别撤回 25 和 0 条。Edge 选中查询中，正常、HTTP、UDP 分别撤回 0、1、0 条。三个种子及集成逐查询均无新增告警，所有撤回均发生在协议旁路之外。

预检作业 184891，正式作业 184893。下表以同一查询上的撤回数计数。

|测试床|视图|种子或集成|组|查询数|较弱匹配告警|均值告警|额外撤回|新增|
|---|---|---|---|---:|---:|---:|---:|---:|
|CIC_DEV|post_window_primary|27|NORMAL|96041|15|15|0|0|
|CIC_DEV|post_window_primary|27|ATTACK|79056|79043|79041|2|0|
|CIC_DEV|post_window_primary|127|NORMAL|96041|12|12|0|0|
|CIC_DEV|post_window_primary|127|ATTACK|79056|79053|79050|3|0|
|CIC_DEV|post_window_primary|227|NORMAL|96041|39|39|0|0|
|CIC_DEV|post_window_primary|227|ATTACK|79056|79050|79046|4|0|
|CIC_DEV|post_window_primary|ensemble|NORMAL|96041|18|18|0|0|
|CIC_DEV|post_window_primary|ensemble|ATTACK|79056|79050|79047|3|0|
|CIC_DEV|full|27|NORMAL|100830|400|400|0|0|
|CIC_DEV|full|27|ATTACK|79056|79043|79041|2|0|
|CIC_DEV|full|127|NORMAL|100830|482|482|0|0|
|CIC_DEV|full|127|ATTACK|79056|79053|79050|3|0|
|CIC_DEV|full|227|NORMAL|100830|453|453|0|0|
|CIC_DEV|full|227|ATTACK|79056|79050|79046|4|0|
|CIC_DEV|full|ensemble|NORMAL|100830|464|464|0|0|
|CIC_DEV|full|ensemble|ATTACK|79056|79050|79047|3|0|
|UNSW_DEV|post_window_primary|27|NORMAL|74444|133|109|24|0|
|UNSW_DEV|post_window_primary|27|ATTACK|72553|72538|72538|0|0|
|UNSW_DEV|post_window_primary|127|NORMAL|74444|114|90|24|0|
|UNSW_DEV|post_window_primary|127|ATTACK|72553|72543|72543|0|0|
|UNSW_DEV|post_window_primary|227|NORMAL|74444|171|139|32|0|
|UNSW_DEV|post_window_primary|227|ATTACK|72553|72533|72533|0|0|
|UNSW_DEV|post_window_primary|ensemble|NORMAL|74444|130|105|25|0|
|UNSW_DEV|post_window_primary|ensemble|ATTACK|72553|72543|72543|0|0|
|UNSW_DEV|full|27|NORMAL|75763|737|713|24|0|
|UNSW_DEV|full|27|ATTACK|72553|72538|72538|0|0|
|UNSW_DEV|full|127|NORMAL|75763|769|745|24|0|
|UNSW_DEV|full|127|ATTACK|72553|72543|72543|0|0|
|UNSW_DEV|full|227|NORMAL|75763|812|780|32|0|
|UNSW_DEV|full|227|ATTACK|72553|72533|72533|0|0|
|UNSW_DEV|full|ensemble|NORMAL|75763|753|728|25|0|
|UNSW_DEV|full|ensemble|ATTACK|72553|72543|72543|0|0|
|EDGE|full|27|NORMAL|20000|1|1|0|0|
|EDGE|full|27|HTTP|20000|19964|19963|1|0|
|EDGE|full|27|UDP|20000|19529|19529|0|0|
|EDGE|full|127|NORMAL|20000|28|28|0|0|
|EDGE|full|127|HTTP|20000|19518|19518|0|0|
|EDGE|full|127|UDP|20000|19876|19876|0|0|
|EDGE|full|227|NORMAL|20000|0|0|0|0|
|EDGE|full|227|HTTP|20000|19958|19955|3|0|
|EDGE|full|227|UDP|20000|19670|19670|0|0|
|EDGE|full|ensemble|NORMAL|20000|0|0|0|0|
|EDGE|full|ensemble|HTTP|20000|19958|19957|1|0|
|EDGE|full|ensemble|UDP|20000|19732|19732|0|0|

## 发生撤回的设备和协议

|测试床|设备、协议与标签|非旁路撤回数|
|---|---|---:|
|CIC_DEV|device:HeimVision Camera / protocol:6 / ATTACK|3|
|UNSW_DEV|device:unsw-attack-traces-2018:00:16:6c:ab:6b:88 / protocol:6 / NORMAL|9|
|UNSW_DEV|device:unsw-attack-traces-2018:70:ee:50:18:34:43 / protocol:6 / NORMAL|1|
|UNSW_DEV|device:unsw-attack-traces-2018:ec:1a:59:83:28:11 / protocol:6 / NORMAL|3|
|UNSW_DEV|device:unsw-attack-traces-2018:ec:1a:59:79:f4:89 / protocol:6 / NORMAL|9|
|UNSW_DEV|device:unsw-attack-traces-2018:70:ee:50:18:34:43 / protocol:17 / NORMAL|3|
|EDGE|device:Edge-IIoTset Raspberry Pi edge server / protocol:6 / ATTACK|1|

[样本级、分层加权与 Edge HT](METRICS.csv) · [分组配对](PAIRED.csv) · [变化查询的超算位置与 SHA](ARTIFACTS.json) · [正式验收](ACCEPTANCE.json)
