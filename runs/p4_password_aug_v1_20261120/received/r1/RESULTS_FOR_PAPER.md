# 密码增强头与冻结 v12 的配对结果

Edge 密码场景在模型冻结后评分。全抓包确认 23,650 条连接，实际有合格评分帧的连接为 23,608 条。其中 42 条缺合格入站查询。ToN Windows 10 属同采集跨主机诊断，CCNR 按逻辑主机配对。Edge 正常侧为同设备已有业务，合法网页登录的正常分母缺失。下表为三种子集成，单种子附在各配对表。

RAW，Edge 的 23,608 条可评价密码关联连接中，增强头多检出 0 条，丢失原检出 0 条。同设备已有正常业务的 19,543 条被抽样查询覆盖的连接中，新增误报 1,395 条，消除原误报 3,026 条。Windows 10 的 18,194 条带数据攻击关联连接中，多检出 3,878 条，丢失 1 条。
CCNR，Edge 的 23,608 条可评价密码关联连接中，增强头多检出 484 条，丢失原检出 0 条。同设备已有正常业务的 19,543 条被抽样查询覆盖的连接中，新增误报 214 条，消除原误报 0 条。Windows 10 的 18,194 条带数据攻击关联连接中，多检出 1,987 条，丢失 0 条。

| 来源 | 阶段 | 类别 | 范围 | 单位 | 分母 | 原告警 | 新告警 | 新增 | 丢失 |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| Edge Password | RAW | attack | any_eligible_inbound | connection | 23608 | 23608 | 23608 | 0 | 0 |
| Edge Password | RAW | attack | confirmed_login_POST | connection | 23608 | 23606 | 23608 | 2 | 0 |
| Edge Password | CCNR | attack | any_eligible_inbound | connection | 23608 | 23122 | 23606 | 484 | 0 |
| Edge Password | CCNR | attack | confirmed_login_POST | connection | 23608 | 19200 | 23547 | 4374 | 27 |
| ToN Windows 10 | RAW | attack | data_connections_any_packet | connection | 18194 | 14308 | 18185 | 3878 | 1 |
| ToN Windows 10 | RAW | normal | data_connections_any_packet | connection | 49 | 10 | 7 | 1 | 4 |
| ToN Windows 10 | CCNR | attack | data_connections_any_packet | connection | 18194 | 349 | 2336 | 1987 | 0 |
| ToN Windows 10 | CCNR | normal | data_connections_any_packet | connection | 49 | 0 | 0 | 0 | 0 |
| CIC_DEV | RAW | normal | post_all | query | 96041 | 99 | 176 | 110 | 33 |
| CIC_DEV | RAW | attack | post_all | query | 79056 | 79056 | 79046 | 0 | 10 |
| CIC_DEV | CCNR | normal | post_all | query | 96041 | 0 | 4 | 4 | 0 |
| CIC_DEV | CCNR | attack | post_all | query | 79056 | 79050 | 79028 | 0 | 22 |
| UNSW_DEV | RAW | normal | post_all | query | 74444 | 40121 | 28023 | 2112 | 14210 |
| UNSW_DEV | RAW | attack | post_all | query | 72553 | 72543 | 72532 | 9 | 20 |
| UNSW_DEV | CCNR | normal | post_all | query | 74444 | 136 | 1419 | 1336 | 53 |
| UNSW_DEV | CCNR | attack | post_all | query | 72553 | 72543 | 72532 | 9 | 20 |
| EDGE | RAW | normal | post_sampled_normal | represented_connection | 19543 | 16371 | 14740 | 1395 | 3026 |
| EDGE | RAW | normal | post_all | query | 20000 | 16699 | 14990 | 1440 | 3149 |
| EDGE | RAW | attack | post_all | query | 40000 | 39698 | 39943 | 280 | 35 |
| EDGE | CCNR | normal | post_sampled_normal | represented_connection | 19543 | 0 | 214 | 214 | 0 |
| EDGE | CCNR | normal | post_all | query | 20000 | 0 | 214 | 214 | 0 |
| EDGE | CCNR | attack | post_all | query | 40000 | 39690 | 39929 | 279 | 40 |
