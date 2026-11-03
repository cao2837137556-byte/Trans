# Qref 预留设备确认：授权与真实输入交付

2026-09-23。用户在完整链路范围说明后回复“可以，动手。”，本次真实执行授权已落盘。
范围为输入身份/分母校验与打包、目标运行时预检、真实E3特征、冻结评分和报告。
用户上传/提交/拉回；0训练、0新CAL、0重试，不启动旧本地作业、不下载新数据。

封存记录：runs/legacy_qref_device_confirmation_authorization_v1_20260923/authorization_record.json。
封存输入验收：同目录input_identity_verification.json；查询文件SHA和UID集合、原始分母、
标签/角色/时间/权重，以及固定LEARN参考对照元数据均PASS。
341222条查询=205345正常+135877攻击；48条自身参考；原始规则不变。
真实查询元数据已经打开以核对身份；结果尚未评分，PCAP尚未解码，0真实forward/更新。
此处“元数据已核验”和“评分尚未发生”分开记录，不继续含糊标注全部HOLDOUT未读。

交付：runs/legacy_qref_device_confirmation_delivery_v1_20260923/OPERATE_CONFIRMATION.md / SHA。
代码包和66成员真实输入包均逐字节/SHA校验。真实输入含1个冻结查询manifest和65个新增PCAP。
7个共享PCAP和旧REFERENCE缓存仍复用超算原位置，远端存在性在授权作业内预检。
输入包144992901 bytes / SHA c301c8ab5c7bfcd756700519046149a761ad7ffd7ba082d0bdeb5949744ae5c6。代码包SHA 05138b3240004543f6c0abbc78353561d94f70579be7ee483ffec3db7eafdf29。
工作树原有无关修改经起止SHA比对保持不变；原有协议、模型、代码包和旧失败结果未改写。

当前READY_FOR_USER_UPLOAD；未上传、未提交、未启动真实特征或评分。
下一步用户按操作文档上传、校验安装并一次提交；该固定链内无需重复逐阶段授权。
本次检验“新设备正常参考能否降低误报而不新增攻击漏检”，不是重训或改阈值。
仍是同采集集的三台预留设备；只有Borun及Netatmo UDP可能自适应，Ring全量Q回退。
独立ID及历史未见攻击/OOD不在本次评分范围内。新科学结论等待真实结果。
