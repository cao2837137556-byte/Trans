# 同服务登录正常留出扩充

四个独立服务实例与原有 194 条留出共 1,107 条正常连接。三组使用此前冻结的本地阈值。

| 普通留出 | 三种子集成 | 误报连接 / 总连接 | 误报率 | 1% 预算 |
|---|---|---:|---:|---|
| prior_holdout | RAW | 2 / 194 | 1.03% | 超出 |
| prior_holdout | v12_CCNR | 2 / 194 | 1.03% | 超出 |
| prior_holdout | relative_handshake | 2 / 194 | 1.03% | 超出 |
| batch_01 | RAW | 3 / 226 | 1.33% | 超出 |
| batch_01 | v12_CCNR | 3 / 226 | 1.33% | 超出 |
| batch_01 | relative_handshake | 3 / 226 | 1.33% | 超出 |
| batch_02 | RAW | 9 / 221 | 4.07% | 超出 |
| batch_02 | v12_CCNR | 9 / 221 | 4.07% | 超出 |
| batch_02 | relative_handshake | 9 / 221 | 4.07% | 超出 |
| batch_03 | RAW | 4 / 236 | 1.69% | 超出 |
| batch_03 | v12_CCNR | 4 / 236 | 1.69% | 超出 |
| batch_03 | relative_handshake | 4 / 236 | 1.69% | 超出 |
| batch_04 | RAW | 4 / 230 | 1.74% | 超出 |
| batch_04 | v12_CCNR | 4 / 230 | 1.74% | 超出 |
| batch_04 | relative_handshake | 4 / 230 | 1.74% | 超出 |
| new_holdout | RAW | 20 / 913 | 2.19% | 超出 |
| new_holdout | v12_CCNR | 20 / 913 | 2.19% | 超出 |
| new_holdout | relative_handshake | 20 / 913 | 2.19% | 超出 |
| all_holdout | RAW | 22 / 1107 | 1.99% | 超出 |
| all_holdout | v12_CCNR | 22 / 1107 | 1.99% | 超出 |
| all_holdout | relative_handshake | 22 / 1107 | 1.99% | 超出 |

合法重连压力测试仍按原 51 条连接单列。攻击侧同端点独立标签记录待补。
